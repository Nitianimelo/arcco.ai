/**
 * Client-side wrapper para a API de Projetos.
 * Backend: /api/agent/projects
 */

import { AGENT_API_BASE } from './backendUrl';

const API_BASE = AGENT_API_BASE;

export interface Project {
  id: string;
  user_id: string;
  name: string;
  instructions: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectFile {
  id: string;
  project_id: string;
  user_id: string;
  file_name: string;
  mime_type: string;
  size_bytes: number;
  status: 'processing' | 'ready' | 'failed';
  error_message?: string | null;
  created_at: string;
}

export const projectApi = {
  async get(projectId: string, userId: string): Promise<Project | null> {
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}?user_id=${encodeURIComponent(userId)}`);
      if (!res.ok) return null;
      return res.json();
    } catch {
      return null;
    }
  },

  async list(userId: string): Promise<Project[]> {
    try {
      const res = await fetch(`${API_BASE}/projects?user_id=${encodeURIComponent(userId)}`);
      if (!res.ok) return [];
      const data = await res.json();
      return data.projects || [];
    } catch {
      return [];
    }
  },

  async create(userId: string, name: string, instructions: string): Promise<Project | null> {
    try {
      const res = await fetch(`${API_BASE}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, name, instructions }),
      });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    } catch (e) {
      console.error('[projectApi] Erro ao criar projeto:', e);
      return null;
    }
  },

  async update(
    userId: string,
    projectId: string,
    data: { name?: string; instructions?: string }
  ): Promise<Project | null> {
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}?user_id=${encodeURIComponent(userId)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    } catch (e) {
      console.error('[projectApi] Erro ao atualizar projeto:', e);
      return null;
    }
  },

  async delete(projectId: string, userId: string): Promise<void> {
    try {
      await fetch(`${API_BASE}/projects/${projectId}?user_id=${encodeURIComponent(userId)}`, { method: 'DELETE' });
    } catch (e) {
      console.error('[projectApi] Erro ao deletar projeto:', e);
    }
  },

  async uploadFile(projectId: string, userId: string, file: File): Promise<ProjectFile | null> {
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch(`${API_BASE}/projects/${projectId}/files?user_id=${encodeURIComponent(userId)}`, {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    } catch (e) {
      console.error('[projectApi] Erro ao fazer upload:', e);
      return null;
    }
  },

  async listFiles(projectId: string, userId: string): Promise<ProjectFile[]> {
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}/files?user_id=${encodeURIComponent(userId)}`);
      if (!res.ok) return [];
      const data = await res.json();
      return data.files || [];
    } catch {
      return [];
    }
  },

  async deleteFile(projectId: string, fileId: string, userId: string): Promise<void> {
    try {
      await fetch(`${API_BASE}/projects/${projectId}/files/${fileId}?user_id=${encodeURIComponent(userId)}`, {
        method: 'DELETE',
      });
    } catch (e) {
      console.error('[projectApi] Erro ao deletar arquivo:', e);
    }
  },
};
