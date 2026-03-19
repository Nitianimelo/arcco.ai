const API_BASE = '/api/agent';

export type ChatStreamEventType =
    | 'conversation_id'
    | 'chunk'
    | 'error'
    | 'steps'
    | 'thought'
    | 'browser_action'
    | 'text_doc'
    | 'file_artifact';

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
    mime_type: string;
    size_bytes: number;
    status: SessionFileStatus;
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
        conversationId?: string | null
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

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    try {
                        const event = JSON.parse(line.slice(6)) as ChatStreamEvent;

                        if (onEvent) onEvent(event.type, event.content);

                        if (event.type === 'chunk') {
                            fullContent += event.content;
                        } else if (event.type === 'error') {
                            throw new Error(event.content);
                        }
                    } catch (e: any) {
                        if (e.name === 'AbortError') throw e;
                        console.error('ERRO DE PARSE SSE. Linha que causou erro:', line, e);
                    }
                }
            }
        } catch (e: any) {
            if (e.name === 'AbortError') {
                reader.cancel();
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

    async uploadSessionFile(sessionId: string, file: File): Promise<SessionFileUploadResponse> {
        const formData = new FormData();
        formData.append('file', file);

        const res = await fetch(`${API_BASE}/session-files?session_id=${encodeURIComponent(sessionId)}`, {
            method: 'POST',
            body: formData,
        });

        if (!res.ok) {
            const errorText = await res.text();
            throw new Error(`Upload failed (${res.status}): ${errorText}`);
        }

        return res.json();
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
    }
};
