import { AGENT_API_BASE } from './backendUrl';

const API_BASE = AGENT_API_BASE;

export type ChatStreamEventType =
    | 'conversation_id'
    | 'chunk'
    | 'error'
    | 'steps'
    | 'thought'
    | 'browser_action'
    | 'text_doc'
    | 'design_artifact'
    | 'file_artifact'
    | 'clarification'
    | 'spy_pages_result'
    | 'pre_action'
    | 'thinking_upgrade'
    | 'needs_clarification';

export interface ChatStreamEvent {
    type: ChatStreamEventType;
    content: string;
}

export type SessionFileStatus = 'uploaded' | 'processing' | 'ready' | 'failed';

export interface SessionFileItem {
    file_id: string;
    original_name: string;
    stored_path: string;
    extracted_text_path?: string | null;
    workspace_manifest_path?: string | null;
    mime_type: string;
    size_bytes: number;
    status: SessionFileStatus;
    workspace_status?: 'pending' | 'processing' | 'ready' | 'failed' | null;
    text_char_count?: number | null;
    image_count?: number | null;
    chunk_count?: number | null;
    created_at: string;
    processed_at?: string | null;
    error?: string | null;
}

export interface SessionFileUploadResponse {
    session_id: string;
    file_id: string;
    original_name: string;
    size_bytes: number;
    status: SessionFileStatus;
    message: string;
}

export interface SessionFileUploadOptions {
    onProgress?: (progressPercent: number, loadedBytes: number, totalBytes: number) => void;
}

export interface AgentActionResponse {
    type: 'action' | 'reasoning' | 'error';
    intent?: string;
    confidence?: number;
    payload?: any;
    error?: string;
}

export const agentApi = {
    /**
     * Route the user message to the appropriate intent/action
     */
    async route(message: string, userId: string, conversationId: string): Promise<AgentActionResponse> {
        try {
            const res = await fetch(`${API_BASE}/route`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, user_id: userId, conversation_id: conversationId })
            });
            if (!res.ok) throw new Error(await res.text());
            return await res.json();
        } catch (e: any) {
            console.error('Route API Error:', e);
            return { type: 'error', error: e.message };
        }
    },

    /**
     * Execute Web Search
     */
    async search(query: string, options?: { search_depth?: string, max_results?: number }) {
        const res = await fetch(`${API_BASE}/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, ...options })
        });
        return res.json();
    },

    /**
     * Generate File (PDF, PPTX, DOCX)
     */
    async generateFile(type: 'pdf' | 'pptx' | 'docx' | 'excel', title: string, content: string) {
        const res = await fetch(`${API_BASE}/files`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type, title, content }) // 'excel' might map to a different handler later or same if unified
        });
        return res.json();
    },

    /**
     * OCR Scan
     */
    async ocr(imageUrl: string) {
        const res = await fetch(`${API_BASE}/ocr`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image_url: imageUrl })
        });
        return res.json();
    },

    /**
     * General Chat (Reasoning) — consumes SSE stream from backend
     * Returns the full assembled response text from 'chunk' events.
     */
    async chat(
        messages: any[],
        systemPrompt: string,
        onEvent?: (type: ChatStreamEventType, content: string) => void,
        signal?: AbortSignal,
        model?: string,
        mode: 'agent' | 'normal' = 'agent',
        sessionId?: string,
        userId?: string,
        projectId?: string | null,
        conversationId?: string | null,
        webSearch?: boolean,
        spyPagesEnabled?: boolean,
        fastModel?: string,
        fastSystemPrompt?: string,
        browserResumeToken?: string,
    ): Promise<string> {
        const res = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                messages,
                mode,
                ...(sessionId ? { session_id: sessionId } : {}),
                ...(model ? { model } : {}),
                ...(systemPrompt ? { system_prompt: systemPrompt } : {}),
                ...(userId ? { user_id: userId } : {}),
                ...(projectId ? { project_id: projectId } : {}),
                ...(conversationId ? { conversation_id: conversationId } : {}),
                ...(webSearch ? { web_search: true } : {}),
                ...(spyPagesEnabled ? { spy_pages_enabled: true } : {}),
                ...(fastModel ? { fast_model: fastModel } : {}),
                ...(fastSystemPrompt ? { fast_system_prompt: fastSystemPrompt } : {}),
                ...(browserResumeToken ? { browser_resume_token: browserResumeToken } : {}),
            }),
            signal,
        });

        if (!res.ok) {
            const errorText = await res.text();
            throw new Error(`Chat API error (${res.status}): ${errorText}`);
        }

        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let fullContent = '';
        let buffer = '';

        const processSseLine = (line: string) => {
            if (!line.startsWith('data: ')) return;

            let raw: any;
            try {
                raw = JSON.parse(line.slice(6));
            } catch (e: any) {
                if (e.name === 'AbortError') throw e;
                console.error('ERRO DE PARSE SSE. Linha que causou erro:', line, e);
                return;
            }

            const eventType = raw.type as ChatStreamEventType;

            // spy_pages_result usa campo "data" em vez de "content"
            if (eventType === 'spy_pages_result') {
                if (onEvent) {
                    const payload = typeof raw.data === 'string' ? raw.data : JSON.stringify(raw.data ?? []);
                    onEvent('spy_pages_result', payload);
                }
                return;
            }

            const event = raw as ChatStreamEvent;
            const content = event.content ?? '';

            if (onEvent) onEvent(event.type, content);

            if (event.type === 'chunk') {
                fullContent += content;
                return;
            }

            if (event.type === 'error') {
                throw new Error(content || 'Erro desconhecido no stream do chat.');
            }
        };

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    processSseLine(line);
                }
            }

            if (buffer.trim()) {
                processSseLine(buffer.trim());
            }
        } catch (e: any) {
            if (e.name === 'AbortError') {
                await reader.cancel();
                return fullContent;
            }
            throw e;
        }
        return fullContent;
    },

    /**
     * Uploads a file (PDF, DOCX, XLSX, etc.) to extract raw text
     * endpoint: /api/agent/extract-text
     */
    async extractText(file: File): Promise<string> {
        const formData = new FormData();
        formData.append('file', file);

        const res = await fetch(`${API_BASE}/extract-text`, {
            method: 'POST',
            body: formData,
        });

        if (!res.ok) {
            const errorText = await res.text();
            throw new Error(`Extraction failed: ${errorText}`);
        }

        const data = await res.json();
        return data.text || '';
    },

    async uploadSessionFile(
        sessionId: string,
        file: File,
        options?: SessionFileUploadOptions,
    ): Promise<SessionFileUploadResponse> {
        const formData = new FormData();
        formData.append('file', file);

        return await new Promise<SessionFileUploadResponse>((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', `${API_BASE}/session-files?session_id=${encodeURIComponent(sessionId)}`);

            xhr.upload.onprogress = (event) => {
                if (!event.lengthComputable) return;
                const progressPercent = Math.max(1, Math.min(100, Math.round((event.loaded / event.total) * 100)));
                options?.onProgress?.(progressPercent, event.loaded, event.total);
            };

            xhr.onerror = () => {
                reject(new Error('Upload failed: network error'));
            };

            xhr.onload = () => {
                if (xhr.status < 200 || xhr.status >= 300) {
                    if (xhr.status === 413) {
                        reject(new Error('Arquivo excede o limite de upload de 100MB.'));
                        return;
                    }
                    reject(new Error(`Upload failed (${xhr.status}): ${xhr.responseText}`));
                    return;
                }

                try {
                    const payload = JSON.parse(xhr.responseText) as SessionFileUploadResponse;
                    options?.onProgress?.(100, file.size, file.size);
                    resolve(payload);
                } catch (error: any) {
                    reject(new Error(`Upload failed: invalid server response (${error?.message || 'unknown error'})`));
                }
            };

            xhr.send(formData);
        });
    },

    async listSessionFiles(sessionId: string): Promise<SessionFileItem[]> {
        const res = await fetch(`${API_BASE}/session-files/${encodeURIComponent(sessionId)}`);

        if (res.status === 404) {
            return [];
        }

        if (!res.ok) {
            const errorText = await res.text();
            throw new Error(`List session files failed (${res.status}): ${errorText}`);
        }

        const data = await res.json();
        return data.files || [];
    },

    async prefetchSpyPages(urls: string[]): Promise<any[]> {
        const res = await fetch(`${API_BASE}/spy-pages-prefetch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ urls }),
        });
        if (!res.ok) throw new Error(`Spy Pages prefetch falhou (${res.status})`);
        const data = await res.json();
        return data.results || [];
    },

    async deleteSessionFiles(sessionId: string): Promise<void> {
        const res = await fetch(`${API_BASE}/session-files/${encodeURIComponent(sessionId)}`, {
            method: 'DELETE',
        });

        if (res.status === 404) {
            return;
        }

        if (!res.ok) {
            const errorText = await res.text();
            throw new Error(`Delete session files failed (${res.status}): ${errorText}`);
        }
    },

    async deleteSessionFile(sessionId: string, fileId: string): Promise<void> {
        const res = await fetch(`${API_BASE}/session-files/${encodeURIComponent(sessionId)}/${encodeURIComponent(fileId)}`, {
            method: 'DELETE',
        });

        if (res.status === 404) {
            return;
        }

        if (!res.ok) {
            const errorText = await res.text();
            throw new Error(`Delete session file failed (${res.status}): ${errorText}`);
        }
    }
};
