/**
 * Client-side wrapper para a API de Conversações.
 * Backend: /api/agent/conversations
 */

import { AGENT_API_BASE } from './backendUrl';

const API_BASE = AGENT_API_BASE;

export interface ConversationRecord {
  id: string;
  user_id: string;
  project_id?: string | null;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface MessageRecord {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

export const conversationApi = {
  async create(
    userId: string,
    title: string,
    projectId?: string | null
  ): Promise<ConversationRecord | null> {
    try {
      const res = await fetch(`${API_BASE}/conversations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, title, project_id: projectId || null }),
      });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    } catch (e) {
      console.error('[conversationApi] Erro ao criar conversa:', e);
      return null;
    }
  },

  async list(userId: string, projectId?: string | null): Promise<ConversationRecord[]> {
    try {
      let url = `${API_BASE}/conversations?user_id=${encodeURIComponent(userId)}`;
      if (projectId) url += `&project_id=${encodeURIComponent(projectId)}`;
      const res = await fetch(url);
      if (!res.ok) return [];
      const data = await res.json();
      return data.conversations || [];
    } catch {
      return [];
    }
  },

  async findByProject(userId: string, projectId: string): Promise<ConversationRecord | null> {
    const convs = await conversationApi.list(userId, projectId);
    return convs.length > 0 ? convs[0] : null;
  },

  async getMessages(conversationId: string, userId: string): Promise<MessageRecord[]> {
    try {
      const res = await fetch(
        `${API_BASE}/conversations/${conversationId}/messages?user_id=${encodeURIComponent(userId)}`
      );
      if (!res.ok) return [];
      const data = await res.json();
      return data.messages || [];
    } catch {
      return [];
    }
  },

  async saveMessages(
    conversationId: string,
    userId: string,
    messages: Array<{ role: string; content: string }>
  ): Promise<void> {
    try {
      await fetch(`${API_BASE}/conversations/${conversationId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, messages }),
      });
    } catch (e) {
      console.error('[conversationApi] Erro ao salvar mensagens:', e);
    }
  },

  async delete(conversationId: string, userId: string): Promise<void> {
    try {
      await fetch(`${API_BASE}/conversations/${conversationId}?user_id=${encodeURIComponent(userId)}`, {
        method: 'DELETE',
      });
    } catch (e) {
      console.error('[conversationApi] Erro ao deletar conversa:', e);
    }
  },

  async updateTitle(conversationId: string, userId: string, title: string): Promise<void> {
    try {
      await fetch(`${API_BASE}/conversations/${conversationId}/title?user_id=${encodeURIComponent(userId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title }),
      });
    } catch (e) {
      console.error('[conversationApi] Erro ao atualizar título:', e);
    }
  },
};
