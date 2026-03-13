export interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: string | Date;
    isError?: boolean;
}

export interface ChatSession {
    id: string;
    title: string;
    updatedAt: number;
    messages: Message[];
}

const STORAGE_KEY = 'arcco_chat_sessions';

export const chatStorage = {
    getSessions(): ChatSession[] {
        try {
            const data = localStorage.getItem(STORAGE_KEY);
            if (!data) return [];
            return JSON.parse(data);
        } catch {
            return [];
        }
    },

    getSession(id: string): ChatSession | undefined {
        return this.getSessions().find(s => s.id === id);
    },

    saveSession(session: ChatSession) {
        const sessions = this.getSessions();
        const existingIndex = sessions.findIndex(s => s.id === session.id);

        if (existingIndex >= 0) {
            sessions[existingIndex] = session;
        } else {
            sessions.unshift(session); // Add to beginning
        }

        // Keep only last 50 sessions to avoid localStorage quota issues
        const trimmedSessions = sessions.slice(0, 50);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmedSessions));
    },

    deleteSession(id: string) {
        const sessions = this.getSessions().filter(s => s.id !== id);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
    },

    generateTitle(messages: Message[]): string {
        const firstUserMsg = messages.find(m => m.role === 'user');
        if (!firstUserMsg) return 'Nova Conversa';

        const title = firstUserMsg.content.slice(0, 30);
        return title.length === 30 ? title + '...' : title;
    }
};
