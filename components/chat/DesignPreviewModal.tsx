import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  X, Loader2, Maximize2, Minimize2, Monitor, PencilRuler, Eye,
  FileText, Image, Presentation, FileImage, Palette, Code2
} from 'lucide-react';

/* ═══════════════════════════════════════════════════════════════════════════
   TYPES & CONSTANTS
   ═══════════════════════════════════════════════════════════════════════════ */

interface DesignPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  html: string;
}

type ExportFormat = 'pdf' | 'pptx' | 'png' | 'jpeg';
type CanvasPresetId = 'square' | 'story' | 'slide' | 'banner' | 'a4';

interface CanvasPreset {
  id: CanvasPresetId;
  label: string;
  width: number;
  height: number;
}

interface SelectedNodeState {
  path: number[];
  text: string;
  color: string;
  tagName: string;
}

const EXPORT_BUTTONS: { fmt: ExportFormat; label: string; icon: React.ReactNode; color: string }[] = [
  { fmt: 'pdf', label: 'PDF', icon: <FileText size={13} />, color: 'text-red-400 border-red-500/30 hover:bg-red-500/10' },
  { fmt: 'pptx', label: 'PowerPoint', icon: <Presentation size={13} />, color: 'text-orange-400 border-orange-500/30 hover:bg-orange-500/10' },
  { fmt: 'png', label: 'PNG', icon: <Image size={13} />, color: 'text-blue-400 border-blue-500/30 hover:bg-blue-500/10' },
  { fmt: 'jpeg', label: 'JPEG', icon: <FileImage size={13} />, color: 'text-green-400 border-green-500/30 hover:bg-green-500/10' },
];

const CANVAS_PRESETS: CanvasPreset[] = [
  { id: 'square', label: 'Post 1080x1080', width: 1080, height: 1080 },
  { id: 'story', label: 'Story 1080x1920', width: 1080, height: 1920 },
  { id: 'slide', label: 'Slide 16:9', width: 1280, height: 720 },
  { id: 'banner', label: 'Banner 1920x1080', width: 1920, height: 1080 },
  { id: 'a4', label: 'A4 Vertical', width: 794, height: 1123 },
];

const FONT_OPTIONS = [
  { value: 'Georgia', label: 'Editorial' },
  { value: 'Helvetica Neue', label: 'Sans Premium' },
  { value: 'Trebuchet MS', label: 'Comercial' },
  { value: 'Gill Sans', label: 'Apresentacao' },
];

const EDITABLE_SELECTOR = 'h1, h2, h3, h4, h5, h6, p, span, a, li, button, strong, em, blockquote';
const DESIGN_STYLE_ID = 'arcco-design-editor-style';
const SELECTED_ATTR = 'data-arcco-selected';

/* ═══════════════════════════════════════════════════════════════════════════
   HELPERS
   ═══════════════════════════════════════════════════════════════════════════ */

async function downloadHtmlExport(html: string, title: string, format: ExportFormat) {
  const res = await fetch('/api/agent/export-html', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ html, title, format }),
  });
  if (!res.ok) throw new Error(await res.text());
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `design.${format}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function ensureHtmlDocument(src: string): string {
  if (/<!doctype html>/i.test(src) || /<html[\s>]/i.test(src)) return src;
  return `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Design</title></head><body>${src}</body></html>`;
}

function buildEditorCss(p: CanvasPreset, bg: string, text: string, accent: string, font: string) {
  return `
    :root {
      --arcco-bg: ${bg}; --arcco-text: ${text}; --arcco-accent: ${accent}; --arcco-font: ${font};
      --arcco-canvas-width: ${p.width}px; --arcco-canvas-height: ${p.height}px;
    }
    html, body { margin:0; padding:0; min-height:100%;
      background: radial-gradient(circle at top, color-mix(in srgb, var(--arcco-accent) 16%, transparent), transparent 32%),
                  linear-gradient(180deg, #f8f8f7 0%, #ecebe7 100%);
    }
    body { color: var(--arcco-text); font-family: var(--arcco-font), sans-serif;
      display:flex; align-items:center; justify-content:center; padding:24px; box-sizing:border-box;
    }
    body > * { box-sizing: border-box; }
    #arcco-design-stage {
      width: min(100%, var(--arcco-canvas-width)); min-height: var(--arcco-canvas-height);
      background: var(--arcco-bg); color: var(--arcco-text); overflow:hidden; border-radius:28px;
      box-shadow: 0 24px 80px rgba(15, 23, 42, 0.18); position:relative;
    }
    #arcco-design-stage [${SELECTED_ATTR}="true"] { outline: 2px solid var(--arcco-accent); outline-offset: 4px; }
    #arcco-design-stage a { color: inherit; }
  `;
}

function normalizeForEditor(src: string, p: CanvasPreset, bg: string, text: string, accent: string, font: string) {
  const parser = new DOMParser();
  const doc = parser.parseFromString(ensureHtmlDocument(src), 'text/html');
  if (!doc.head.querySelector('meta[charset]')) {
    const meta = doc.createElement('meta');
    meta.setAttribute('charset', 'UTF-8');
    doc.head.prepend(meta);
  }
  let style = doc.getElementById(DESIGN_STYLE_ID);
  if (!style) { style = doc.createElement('style'); style.id = DESIGN_STYLE_ID; doc.head.appendChild(style); }
  style.textContent = buildEditorCss(p, bg, text, accent, font);
  doc.querySelectorAll(`[${SELECTED_ATTR}]`).forEach((n) => n.removeAttribute(SELECTED_ATTR));
  let stage = doc.getElementById('arcco-design-stage');
  if (!stage) {
    stage = doc.createElement('div'); stage.id = 'arcco-design-stage';
    while (doc.body.firstChild) stage.appendChild(doc.body.firstChild);
    doc.body.appendChild(stage);
  }
  Array.from(stage.children).forEach((ch) => {
    if (ch instanceof HTMLElement && !ch.style.width) ch.style.width = '100%';
  });
  return '<!DOCTYPE html>\n' + doc.documentElement.outerHTML;
}

function extractTitle(h: string) { return h.match(/<title[^>]*>([^<]+)<\/title>/i)?.[1] ?? 'Design'; }

function getNodePath(root: HTMLElement, el: HTMLElement) {
  const path: number[] = [];
  let c: HTMLElement | null = el;
  while (c && c !== root) { const p = c.parentElement; if (!p) break; path.unshift(Array.from(p.children).indexOf(c)); c = p as HTMLElement; }
  return path;
}

function getNodeByPath(root: HTMLElement, path: number[]) {
  let c: Element = root;
  for (const i of path) { const n = c.children.item(i); if (!n) return null; c = n; }
  return c instanceof HTMLElement ? c : null;
}

/* ═══════════════════════════════════════════════════════════════════════════
   COLOR SWATCH
   ═══════════════════════════════════════════════════════════════════════════ */

function ColorSwatch({ value, onChange, label }: { value: string; onChange: (v: string) => void; label: string }) {
  return (
    <label className="flex items-center gap-1.5 cursor-pointer group" title={label}>
      <span className="text-[10px] text-neutral-500 group-hover:text-neutral-300 transition-colors hidden sm:inline">{label}</span>
      <div className="relative">
        <div className="w-6 h-6 rounded-lg border border-[#333] shadow-sm group-hover:border-orange-500/40 transition-colors" style={{ backgroundColor: value }} />
        <input type="color" value={value} onChange={(e) => onChange(e.target.value)}
          className="absolute inset-0 opacity-0 cursor-pointer" style={{ minWidth: 44, minHeight: 44, margin: '-9px' }} />
      </div>
    </label>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   MODAL COMPONENT
   ═══════════════════════════════════════════════════════════════════════════ */

const DesignPreviewModal: React.FC<DesignPreviewModalProps> = ({ isOpen, onClose, html }) => {
  const [editing, setEditing] = useState(false);
  const [workingHtml, setWorkingHtml] = useState(html);
  const [loadingFmt, setLoadingFmt] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [selectedPresetId, setSelectedPresetId] = useState<CanvasPresetId>('slide');
  const [backgroundColor, setBackgroundColor] = useState('#fff7ed');
  const [textColor, setTextColor] = useState('#1f2937');
  const [accentColor, setAccentColor] = useState('#ea580c');
  const [fontFamily, setFontFamily] = useState('Georgia');
  const [selectedNode, setSelectedNode] = useState<SelectedNodeState | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const selectedPreset = useMemo(
    () => CANVAS_PRESETS.find((p) => p.id === selectedPresetId) ?? CANVAS_PRESETS[2],
    [selectedPresetId]
  );

  // Reset state when modal opens with new content
  useEffect(() => {
    if (isOpen) {
      setWorkingHtml(html);
      setEditing(false);
      setSelectedNode(null);
      setError(null);
      setShowAdvanced(false);
    }
  }, [isOpen, html]);

  const activeHtml = useMemo(
    () => normalizeForEditor(workingHtml, selectedPreset, backgroundColor, textColor, accentColor, fontFamily),
    [workingHtml, selectedPreset, backgroundColor, textColor, accentColor, fontFamily]
  );

  const title = extractTitle(activeHtml);

  // ESC to close
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    if (isOpen) {
      document.addEventListener('keydown', handler);
      document.body.style.overflow = 'hidden';
    }
    return () => { document.removeEventListener('keydown', handler); document.body.style.overflow = ''; };
  }, [isOpen, onClose]);

  // ── Iframe click/input handlers for text editing ──
  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe || !isOpen) return;

    const onLoad = () => {
      const doc = iframe.contentDocument;
      if (!doc) return;
      const stage = doc.getElementById('arcco-design-stage');
      if (!(stage instanceof HTMLElement)) return;

      const clickHandler = (event: Event) => {
        if (!editing) return;
        const target = event.target instanceof HTMLElement ? event.target.closest(EDITABLE_SELECTOR) : null;
        if (!(target instanceof HTMLElement) || !stage.contains(target)) return;
        event.preventDefault();
        event.stopPropagation();
        doc.querySelectorAll(`[${SELECTED_ATTR}]`).forEach((n) => n.removeAttribute(SELECTED_ATTR));
        target.setAttribute(SELECTED_ATTR, 'true');
        const computed = doc.defaultView?.getComputedStyle(target);
        setSelectedNode({
          path: getNodePath(stage, target),
          text: target.innerText,
          color: computed?.color || textColor,
          tagName: target.tagName.toLowerCase(),
        });
      };

      const inputHandler = (event: Event) => {
        if (!editing) return;
        const target = event.target instanceof HTMLElement ? event.target.closest(EDITABLE_SELECTOR) : null;
        if (!(target instanceof HTMLElement) || !stage.contains(target)) return;
        const path = getNodePath(stage, target);
        const computed = doc.defaultView?.getComputedStyle(target);
        setSelectedNode({ path, text: target.innerText, color: computed?.color || textColor, tagName: target.tagName.toLowerCase() });
        doc.querySelectorAll(`[${SELECTED_ATTR}]`).forEach((n) => n.removeAttribute(SELECTED_ATTR));
        target.setAttribute(SELECTED_ATTR, 'true');
        setWorkingHtml('<!DOCTYPE html>\n' + doc.documentElement.outerHTML);
      };

      stage.querySelectorAll<HTMLElement>(EDITABLE_SELECTOR).forEach((node) => {
        node.style.cursor = editing ? 'text' : 'default';
        node.contentEditable = editing ? 'true' : 'false';
        if (!editing) node.removeAttribute(SELECTED_ATTR);
      });

      doc.removeEventListener('click', clickHandler, true);
      doc.removeEventListener('input', inputHandler, true);
      doc.addEventListener('click', clickHandler, true);
      doc.addEventListener('input', inputHandler, true);
    };

    iframe.addEventListener('load', onLoad);
    return () => iframe.removeEventListener('load', onLoad);
  }, [editing, activeHtml, textColor, isOpen]);

  // Sync selected node highlight
  useEffect(() => {
    const doc = iframeRef.current?.contentDocument;
    if (!doc || !selectedNode) return;
    const stage = doc.getElementById('arcco-design-stage');
    if (!(stage instanceof HTMLElement)) return;
    const node = getNodeByPath(stage, selectedNode.path);
    if (!node) return;
    doc.querySelectorAll(`[${SELECTED_ATTR}]`).forEach((item) => item.removeAttribute(SELECTED_ATTR));
    node.setAttribute(SELECTED_ATTR, 'true');
  }, [selectedNode, activeHtml]);

  const syncIframeBack = () => {
    const doc = iframeRef.current?.contentDocument;
    if (!doc) return;
    doc.querySelectorAll(`[${SELECTED_ATTR}]`).forEach((n) => n.removeAttribute(SELECTED_ATTR));
    setWorkingHtml('<!DOCTYPE html>\n' + doc.documentElement.outerHTML);
  };

  const clearSelection = () => {
    const doc = iframeRef.current?.contentDocument;
    if (doc) doc.querySelectorAll(`[${SELECTED_ATTR}]`).forEach((n) => n.removeAttribute(SELECTED_ATTR));
    setSelectedNode(null);
  };

  const handleExport = async (fmt: ExportFormat) => {
    setLoadingFmt(fmt);
    setError(null);
    syncIframeBack();
    try {
      await downloadHtmlExport(activeHtml, title, fmt);
    } catch (e: any) {
      setError(`Erro ao exportar: ${e.message}`);
    } finally {
      setLoadingFmt(null);
    }
  };

  const handleSelectedTextChange = (value: string) => {
    setSelectedNode((c) => c ? { ...c, text: value } : c);
    const doc = iframeRef.current?.contentDocument;
    if (!doc || !selectedNode) return;
    const stage = doc.getElementById('arcco-design-stage');
    if (!(stage instanceof HTMLElement)) return;
    const node = getNodeByPath(stage, selectedNode.path);
    if (!node) return;
    node.innerText = value;
    syncIframeBack();
  };

  const handleSelectedColorChange = (value: string) => {
    setSelectedNode((c) => c ? { ...c, color: value } : c);
    const doc = iframeRef.current?.contentDocument;
    if (!doc || !selectedNode) return;
    const stage = doc.getElementById('arcco-design-stage');
    if (!(stage instanceof HTMLElement)) return;
    const node = getNodeByPath(stage, selectedNode.path);
    if (!node) return;
    node.style.color = value;
    syncIframeBack();
  };

  if (!isOpen) return null;

  const modalSize = isFullscreen ? 'inset-0' : 'inset-3 sm:inset-4 md:inset-8 lg:inset-12';

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200" onClick={onClose} />

      {/* Modal */}
      <div className={`absolute ${modalSize} bg-[#0a0a0d] border border-[#2a2a2a] rounded-2xl flex flex-col overflow-hidden shadow-2xl animate-in zoom-in-95 fade-in duration-200`}>

        {/* ── HEADER ── */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#1e1e1e] bg-[#111113] shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-1.5 bg-orange-500/10 rounded-lg">
              <Monitor size={16} className="text-orange-400" />
            </div>
            <div>
              <h3 className="text-sm font-medium text-neutral-100">{title}</h3>
              <p className="text-[10px] text-neutral-500">
                {editing ? 'Clique no texto do design para editar' : 'Visualizacao do design'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            {/* Toggle Visualizar / Editar */}
            <div className="flex rounded-lg overflow-hidden border border-[#333]">
              <button
                onClick={() => { setEditing(false); clearSelection(); }}
                className={`flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-medium transition-all ${
                  !editing ? 'bg-orange-500/20 text-orange-100' : 'bg-[#1a1a2a] text-neutral-500 hover:text-white'
                }`}
              >
                <Eye size={11} /> Visualizar
              </button>
              <button
                onClick={() => setEditing(true)}
                className={`flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-medium transition-all ${
                  editing ? 'bg-orange-500/20 text-orange-100' : 'bg-[#1a1a2a] text-neutral-500 hover:text-white'
                }`}
              >
                <PencilRuler size={11} /> Editar
              </button>
            </div>
            <button onClick={() => setIsFullscreen((f) => !f)}
              className="p-2 hover:bg-white/5 rounded-lg text-neutral-500 hover:text-neutral-300 transition-colors"
              title={isFullscreen ? 'Sair de tela cheia' : 'Tela cheia'}>
              {isFullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
            </button>
            <button onClick={onClose}
              className="p-2 hover:bg-white/5 rounded-lg text-neutral-500 hover:text-neutral-300 transition-colors">
              <X size={16} />
            </button>
          </div>
        </div>

        {/* ── TOOLBAR (editing only) ── */}
        {editing && (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2.5 bg-[#0f1014] border-b border-[#222] shrink-0">
            <select value={selectedPresetId} onChange={(e) => setSelectedPresetId(e.target.value as CanvasPresetId)}
              className="rounded-lg bg-[#17181d] border border-[#2a2a34] px-2.5 py-1.5 text-xs text-neutral-200 outline-none">
              {CANVAS_PRESETS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>

            <div className="w-px h-5 bg-[#2a2a34] hidden sm:block" />

            <div className="flex items-center gap-3">
              <ColorSwatch value={backgroundColor} onChange={setBackgroundColor} label="Fundo" />
              <ColorSwatch value={textColor} onChange={setTextColor} label="Texto" />
              <ColorSwatch value={accentColor} onChange={setAccentColor} label="Destaque" />
            </div>

            <div className="w-px h-5 bg-[#2a2a34] hidden sm:block" />

            <select value={fontFamily} onChange={(e) => setFontFamily(e.target.value)}
              className="rounded-lg bg-[#17181d] border border-[#2a2a34] px-2.5 py-1.5 text-xs text-neutral-200 outline-none">
              {FONT_OPTIONS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
            </select>

            <button onClick={() => setShowAdvanced((p) => !p)}
              className={`ml-auto flex items-center gap-1 px-2 py-1.5 rounded-lg text-[11px] font-medium border transition-all ${
                showAdvanced ? 'bg-green-500/15 border-green-500/30 text-green-300' : 'bg-[#1a1a2a] border-[#333] text-neutral-500 hover:text-white'
              }`}>
              <Code2 size={12} />
              <span className="hidden sm:inline">Codigo</span>
            </button>
          </div>
        )}

        {/* ── ADVANCED CODE PANEL ── */}
        {editing && showAdvanced && (
          <div className="px-4 py-3 bg-[#0b0b0d] border-b border-[#1a1a20] shrink-0 max-h-48 overflow-auto">
            <textarea
              value={workingHtml}
              onChange={(e) => setWorkingHtml(e.target.value)}
              className="w-full h-36 rounded-xl bg-[#080810] border border-[#23232a] px-3 py-2 text-[11px] text-green-400 font-mono outline-none resize-y"
              spellCheck={false}
            />
          </div>
        )}

        {/* ── CANVAS ── */}
        <div className={`relative flex-1 min-h-0 bg-[#0b0b0d] p-3 sm:p-4 overflow-auto ${editing ? 'animate-editor-glow' : ''}`}>
          <div className="mx-auto w-full transition-all" style={{ maxWidth: selectedPreset.width }}>
            <iframe
              ref={iframeRef}
              srcDoc={activeHtml}
              className="w-full border-0 rounded-2xl bg-white"
              style={{ aspectRatio: `${selectedPreset.width} / ${selectedPreset.height}`, minHeight: 280 }}
              sandbox="allow-scripts allow-same-origin"
              title="Preview do design"
            />
          </div>

          {/* Floating text editor */}
          {editing && selectedNode && (
            <div className="absolute top-3 right-3 z-10 w-64 rounded-xl bg-[#111118] border border-orange-500/30 shadow-xl shadow-black/40 p-3 space-y-2.5 animate-float-panel">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Palette size={11} className="text-orange-400" />
                  <span className="text-[10px] text-neutral-400">Editar elemento</span>
                </div>
                <button onClick={clearSelection} className="p-1 rounded hover:bg-white/5 transition-colors">
                  <X size={12} className="text-neutral-500" />
                </button>
              </div>
              <textarea
                value={selectedNode.text}
                onChange={(e) => handleSelectedTextChange(e.target.value)}
                className="w-full h-20 rounded-lg bg-[#0b0b0d] border border-[#2a2a34] px-2.5 py-2 text-xs text-neutral-200 outline-none resize-none"
                placeholder="Texto do elemento..."
              />
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-neutral-500">Cor do texto</span>
                <ColorSwatch value={selectedNode.color} onChange={handleSelectedColorChange} label="" />
              </div>
            </div>
          )}

          {/* Edit mode hint */}
          {editing && !selectedNode && (
            <div className="absolute bottom-3 left-1/2 -translate-x-1/2 px-3 py-1.5 rounded-full bg-[#111118]/90 border border-orange-500/20 text-[10px] text-orange-200/70 pointer-events-none">
              Clique em qualquer texto do design para editar
            </div>
          )}
        </div>

        {/* ── FOOTER — Export ── */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-t border-[#1e1e1e] bg-[#111113] shrink-0">
          <div className="min-w-0">
            <p className="text-[10px] text-neutral-600 uppercase tracking-widest font-semibold">Baixar como</p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {EXPORT_BUTTONS.map(({ fmt, label, icon, color }) => (
              <button key={fmt} onClick={() => handleExport(fmt)} disabled={!!loadingFmt}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-lg bg-transparent border text-xs font-medium transition-all disabled:opacity-40 ${color}`}>
                {loadingFmt === fmt ? <Loader2 size={13} className="animate-spin" /> : icon}
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Export progress */}
        {loadingFmt && (
          <div className="px-4 pb-3 bg-[#111113] shrink-0">
            <p className="text-[10px] text-orange-300/70 mb-1">Exportando {loadingFmt.toUpperCase()}...</p>
            <div className="h-1 rounded-full bg-[#1a1a1d] overflow-hidden">
              <div className="h-full bg-orange-500 rounded-full animate-browser-progress" />
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="px-4 py-2 border-t border-red-500/20 bg-red-500/5 shrink-0">
            <p className="text-xs text-red-400">{error}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default DesignPreviewModal;
