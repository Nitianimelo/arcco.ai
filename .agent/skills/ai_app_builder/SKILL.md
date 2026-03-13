---
name: ai-app-builder
description: >
  Architecture and implementation guide for AI-powered app builders that generate multi-file projects
  (like Lovable, Bolt, CapCut's new flow, v0). Covers agent orchestration, virtual filesystem persistence
  in Supabase, preview/deploy strategies, context management, and the full prompt-to-app pipeline.
  Use this skill when building platforms where an AI agent generates, edits, and manages complete
  application codebases with multiple files, components, and assets.
---

# AI App Builder — Multi-File Generation & Persistence

This skill covers the complete architecture for building AI-powered app generation platforms where
an LLM agent creates and manages multi-file projects. Think Lovable, Bolt.new, v0, CapCut's new
builder flow — any system where a user describes what they want and an AI generates a working app.

## Core Problem

A real app is NOT a single file. It's a tree of interdependent files. The agent must:
1. **Know what to generate** (orchestration & context management)
2. **Know how to persist** (virtual filesystem in database)
3. **Know how to reconstruct** (preview & deploy)

---

## 1. Data Model — Virtual Filesystem in Supabase

Store projects as a flat virtual filesystem. Do NOT model directories as entities — reconstruct
the tree in the frontend from file paths.

### Schema

```sql
-- ============================================
-- PROJECTS
-- ============================================
CREATE TABLE projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  slug TEXT UNIQUE,
  framework TEXT NOT NULL DEFAULT 'react',  -- 'react' | 'vue' | 'html' | 'nextjs'
  template_id TEXT,                          -- base template used for scaffolding
  current_version INT NOT NULL DEFAULT 0,
  settings JSONB DEFAULT '{}',              -- tailwind config, theme, etc.
  is_public BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- RLS: users can only access their own projects
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users manage own projects"
  ON projects FOR ALL
  USING (auth.uid() = user_id);

-- ============================================
-- PROJECT FILES (Virtual Filesystem)
-- ============================================
CREATE TABLE project_files (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  file_path TEXT NOT NULL,          -- e.g. 'src/components/Header.jsx'
  content TEXT NOT NULL DEFAULT '',
  file_type TEXT NOT NULL,          -- 'jsx' | 'tsx' | 'css' | 'json' | 'html' | 'svg' | 'md'
  version INT NOT NULL DEFAULT 0,
  is_entry_point BOOLEAN DEFAULT false,  -- marks main files like App.jsx
  is_deleted BOOLEAN DEFAULT false,
  metadata JSONB DEFAULT '{}',      -- size, hash, etc.
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(project_id, file_path, version)
);

-- Index for fast lookups
CREATE INDEX idx_files_project_version ON project_files(project_id, version);
CREATE INDEX idx_files_path ON project_files(project_id, file_path);

ALTER TABLE project_files ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users manage own project files"
  ON project_files FOR ALL
  USING (
    project_id IN (SELECT id FROM projects WHERE user_id = auth.uid())
  );

-- ============================================
-- CONVERSATION TURNS (prompt history)
-- ============================================
CREATE TABLE project_turns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  turn_number INT NOT NULL,
  user_prompt TEXT NOT NULL,
  ai_response JSONB,                -- reasoning, explanation, metadata
  files_changed TEXT[] DEFAULT '{}', -- ['src/App.jsx', 'src/index.css']
  actions JSONB DEFAULT '[]',       -- full action list from agent
  version_snapshot INT NOT NULL,    -- links to file versions at this point
  tokens_used INT,
  model_used TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_turns_project ON project_turns(project_id, turn_number);

-- ============================================
-- TEMPLATES (starter scaffolds)
-- ============================================
CREATE TABLE templates (
  id TEXT PRIMARY KEY,               -- 'react-vite-tailwind', 'html-vanilla', etc.
  name TEXT NOT NULL,
  framework TEXT NOT NULL,
  files JSONB NOT NULL,              -- { "file_path": "content", ... }
  description TEXT,
  preview_url TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================
-- HELPER: Batch upsert files in a single transaction
-- ============================================
CREATE OR REPLACE FUNCTION save_project_files(
  p_project_id UUID,
  p_version INT,
  p_files JSONB  -- array of { file_path, content, file_type, is_deleted? }
)
RETURNS VOID AS $$
DECLARE
  f JSONB;
BEGIN
  FOR f IN SELECT * FROM jsonb_array_elements(p_files)
  LOOP
    INSERT INTO project_files (project_id, file_path, content, file_type, version, is_deleted)
    VALUES (
      p_project_id,
      f->>'file_path',
      f->>'content',
      f->>'file_type',
      p_version,
      COALESCE((f->>'is_deleted')::boolean, false)
    );
  END LOOP;

  -- Update project version
  UPDATE projects SET current_version = p_version, updated_at = now()
  WHERE id = p_project_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- HELPER: Get all files at a specific version (snapshot)
-- ============================================
CREATE OR REPLACE FUNCTION get_project_snapshot(
  p_project_id UUID,
  p_version INT DEFAULT NULL
)
RETURNS TABLE(file_path TEXT, content TEXT, file_type TEXT, version INT) AS $$
BEGIN
  RETURN QUERY
  SELECT DISTINCT ON (pf.file_path)
    pf.file_path, pf.content, pf.file_type, pf.version
  FROM project_files pf
  WHERE pf.project_id = p_project_id
    AND pf.version <= COALESCE(p_version, (
      SELECT current_version FROM projects WHERE id = p_project_id
    ))
    AND pf.is_deleted = false
  ORDER BY pf.file_path, pf.version DESC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

### Key Design Decisions

- **`file_path` as flat string**: Directories are implicit. Reconstruct tree in frontend with simple string splitting. No need for a `directories` table.
- **Version per turn, not per file**: Every turn increments the project version. Only changed files get new rows. `get_project_snapshot()` resolves the latest version of each file at any point in time.
- **Batch writes via RPC**: `save_project_files()` ensures atomicity. Never do N separate inserts from the client.
- **`is_deleted` soft delete**: The agent can "delete" files without losing history. Critical for undo.

---

## 2. Agent Orchestration

### System Prompt Structure

The agent needs a structured system prompt that defines its role and output format:

```
You are a frontend engineer AI. You build and modify web applications.

## Rules
- Return COMPLETE file contents, never diffs or patches
- Only modify files that need changes
- Preserve existing code you don't need to change
- Follow the project's established patterns (framework, styling, naming)
- Always return valid, working code

## Output Format
Return a JSON object with this exact structure:
{
  "actions": [
    {
      "type": "create" | "update" | "delete" | "rename",
      "file_path": "src/components/Header.jsx",
      "content": "... full file content ...",
      "rename_to": "new/path.jsx"  // only for rename
    }
  ],
  "explanation": "Brief description of changes made"
}

## Project Context
Framework: {{framework}}
File tree: {{file_tree}}

## Current Files
{{selected_file_contents}}
```

### Why Complete Files, Not Diffs

LLMs are unreliable with diffs. They miscalculate line numbers, lose context, break indentation.
Sending and receiving complete files costs more tokens but is dramatically more reliable.
The tradeoff is worth it — a broken diff wastes the entire turn.

**Exception**: For very large files (>500 lines), consider a hybrid approach where the agent
returns the complete modified function/section with clear markers for where it fits.

### Context Management — What the Agent Sees

This is where most implementations fail. Sending ALL files to the agent is wasteful and
degrades output quality. Use selective context:

```
ALWAYS send:
├── file_tree (list of all paths — small, cheap)
├── package.json (dependencies matter)
├── main entry point (App.jsx / index.html)
├── any file the user explicitly mentions
└── tailwind.config / theme config

CONDITIONALLY send (based on user prompt analysis):
├── files imported by the target file
├── files that import the target file
├── shared types/interfaces
└── related components (same directory)

NEVER send:
├── node_modules anything
├── lock files
├── build output
├── unchanged config files the agent doesn't need
└── assets/images (just reference paths)
```

**Implementation pattern**: Before calling the LLM, run a lightweight "context resolver" that:
1. Parses the user prompt for file references and component names
2. Checks the import graph of referenced files
3. Assembles only the relevant files
4. Stays within token budget (reserve ~60% of context for output)

### Request/Response Flow

```
User prompt arrives
    │
    ▼
Backend: Load project metadata + file tree from Supabase
    │
    ▼
Context Resolver: Select relevant files based on prompt + import graph
    │
    ▼
Assemble LLM request (system prompt + context + user prompt)
    │
    ▼
Call LLM API (streaming preferred for UX)
    │
    ▼
Parse response: Extract actions[] from JSON
    │
    ▼
Validate:
  - Valid file paths (no traversal attacks like ../)
  - Valid file types
  - Syntax check (optional but recommended — quick AST parse)
  - No duplicate paths in same action set
    │
    ▼
Persist:
  - Increment project version
  - Call save_project_files() RPC with all changed files
  - Save turn in project_turns
    │
    ▼
Return to frontend:
  - Updated file tree
  - Changed file contents
  - Agent explanation
  - New version number
```

---

## 3. Templates & Scaffolding

Never make the agent generate boilerplate from scratch. Use pre-built templates:

```json
{
  "react-vite-tailwind": {
    "framework": "react",
    "files": {
      "package.json": "{ \"name\": \"app\", \"dependencies\": { \"react\": \"^18\"... } }",
      "vite.config.js": "import { defineConfig } from 'vite'...",
      "tailwind.config.js": "/** @type {import('tailwindcss').Config} */...",
      "postcss.config.js": "...",
      "index.html": "<!DOCTYPE html>...",
      "src/main.jsx": "import React from 'react'...",
      "src/App.jsx": "// Main app component - AI modifies this\nexport default function App() { return <div>Hello</div> }",
      "src/index.css": "@tailwind base; @tailwind components; @tailwind utilities;"
    }
  }
}
```

When creating a new project:
1. Copy template files into `project_files` at version 0
2. Agent only modifies/adds what's needed
3. Saves massive tokens and avoids config mistakes

---

## 4. Preview & Deploy

### Option A: WebContainer (Browser-based — Best UX)

Use [WebContainer API](https://webcontainers.io/) to run Node.js in the browser:

```javascript
import { WebContainer } from '@webcontainer/api';

async function previewProject(files) {
  const wc = await WebContainer.boot();

  // Mount files as a virtual filesystem
  const mountStructure = {};
  for (const [path, content] of Object.entries(files)) {
    const parts = path.split('/');
    let current = mountStructure;
    for (let i = 0; i < parts.length - 1; i++) {
      current[parts[i]] = current[parts[i]] || { directory: {} };
      current = current[parts[i]].directory;
    }
    current[parts[parts.length - 1]] = { file: { contents: content } };
  }
  await wc.mount(mountStructure);

  // Install & run
  const install = await wc.spawn('npm', ['install']);
  await install.exit;
  const dev = await wc.spawn('npm', ['run', 'dev']);

  // Get preview URL
  wc.on('server-ready', (port, url) => {
    document.getElementById('preview-iframe').src = url;
  });
}
```

**Pros**: Full Node.js, hot reload, npm packages work, closest to real dev experience.
**Cons**: Complex setup, memory intensive, WebContainer API licensing.

### Option B: Sandboxed iframe (Simple apps)

For HTML/CSS/JS projects without build steps:

```javascript
function previewSimple(files) {
  const html = files['index.html'] || '';
  const css = files['style.css'] || '';
  const js = files['script.js'] || '';

  const combined = html
    .replace('</head>', `<style>${css}</style></head>`)
    .replace('</body>', `<script>${js}</script></body>`);

  const blob = new Blob([combined], { type: 'text/html' });
  const url = URL.createObjectURL(blob);

  const iframe = document.getElementById('preview');
  iframe.sandbox = 'allow-scripts allow-same-origin';
  iframe.src = url;
}
```

**Pros**: Trivial to implement, fast, no dependencies.
**Cons**: No npm, no build step, limited to vanilla JS/HTML/CSS.

### Option C: Server-side build + deploy

For production deploys, package files and push via API:

```javascript
// Vercel deploy via API
async function deployToVercel(files, projectName) {
  const vercelFiles = Object.entries(files).map(([path, content]) => ({
    file: path,
    data: Buffer.from(content).toString('base64'),
    encoding: 'base64'
  }));

  const res = await fetch('https://api.vercel.com/v13/deployments', {
    method: 'POST',
    headers: { Authorization: `Bearer ${VERCEL_TOKEN}` },
    body: JSON.stringify({
      name: projectName,
      files: vercelFiles,
      projectSettings: { framework: 'vite' }
    })
  });

  return (await res.json()).url;
}
```

---

## 5. Undo / Version History

Since every turn creates a version snapshot, undo is straightforward:

```javascript
// Get all files at version N
const { data: snapshot } = await supabase
  .rpc('get_project_snapshot', {
    p_project_id: projectId,
    p_version: targetVersion
  });

// Set project back to that version
await supabase
  .from('projects')
  .update({ current_version: targetVersion })
  .eq('id', projectId);
```

For the UI, show a timeline of turns with their prompts. User clicks any turn to restore.

---

## 6. Streaming UX

Don't wait for the full LLM response. Stream changes as they're generated:

```
User sends prompt
    │
    ▼
Show "thinking" state with user prompt echo
    │
    ▼
Stream LLM response tokens
    │
    ├── As each file action completes in stream:
    │   ├── Update file tree sidebar (add/rename indicators)
    │   ├── Show code diff in editor panel
    │   └── Partial preview update (if possible)
    │
    ▼
Full response received → final preview refresh
```

**Parsing streamed JSON**: Use a streaming JSON parser or wait for complete action objects.
A practical approach is to look for complete `{ "type": ..., "content": ... }` objects
in the stream buffer and process them as they complete.

---

## 7. Error Handling & Recovery

```
Agent generates broken code
    │
    ▼
Syntax validation catches error
    │
    ├── Option A: Auto-retry with error context
    │   "The code you generated has a syntax error on line 42:
    │    [error message]. Fix it and return the corrected file."
    │
    ├── Option B: Save anyway, show error in preview
    │   Let the user see the error and describe the fix
    │
    └── Option C: Rollback to previous version
        Show user the error and offer to undo
```

**Best practice**: Try Option A (auto-fix) once. If it fails again, fall back to Option B.
Never silently swallow errors.

---

## 8. Multi-Agent Architecture (Advanced)

For complex apps, split responsibilities:

```
Orchestrator Agent (router)
    │
    ├── UI Agent: Components, layouts, styling
    ├── Logic Agent: State management, API calls, data flow
    ├── Data Agent: Database schema, Supabase queries, RLS
    └── Review Agent: Code review, consistency check, testing
```

Each agent gets only the context it needs. The orchestrator merges their outputs
and resolves conflicts. This is more complex but produces better results for
larger applications.

---

## Summary Checklist

When implementing an AI app builder:

- [ ] Virtual filesystem with flat `file_path` strings in DB
- [ ] Version snapshots per turn (not per file)
- [ ] Batch file writes via RPC function
- [ ] Selective context — don't send everything to the LLM
- [ ] Complete files in/out — no diffs
- [ ] Pre-built templates for scaffolding
- [ ] Streaming response with progressive UI updates
- [ ] Auto-retry on syntax errors (1 attempt)
- [ ] Undo via version snapshots
- [ ] Preview via WebContainer (React/Vue) or iframe (vanilla)
