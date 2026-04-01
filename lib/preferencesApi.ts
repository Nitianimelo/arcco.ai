/**
 * Client-side wrapper para a API de Preferências do Usuário.
 * Backend: GET/PUT /api/agent/preferences/{user_id}
 */

import { AGENT_API_BASE } from './backendUrl';

const API_BASE = AGENT_API_BASE;

export interface UserPreferences {
  user_id?: string;
  theme: string;
  display_name: string | null;
  custom_instructions: string | null;
  logo_url: string | null;
  occupation: string | null;
  updated_at?: string;
}

const DEFAULT_PREFS: UserPreferences = {
  theme: 'dark',
  display_name: null,
  custom_instructions: null,
  logo_url: null,
  occupation: null,
};

export const preferencesApi = {
  /**
   * Busca preferências do usuário. Retorna defaults se não existir no Supabase.
   * Também atualiza o cache local.
   */
  async get(userId: string): Promise<UserPreferences> {
    if (!userId) return DEFAULT_PREFS;
    try {
      const res = await fetch(`${API_BASE}/preferences/${userId}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) return DEFAULT_PREFS;
      const data: UserPreferences = await res.json();
      // Cache local para acesso offline rápido
      localStorage.setItem('arcco_prefs', JSON.stringify(data));
      return data;
    } catch {
      // Fallback para cache local se backend indisponível
      const cached = localStorage.getItem('arcco_prefs');
      if (cached) return JSON.parse(cached) as UserPreferences;
      return DEFAULT_PREFS;
    }
  },

  /**
   * Salva (upsert) as preferências. Também atualiza o cache local.
   */
  async save(userId: string, prefs: Partial<UserPreferences>): Promise<void> {
    if (!userId) return;
    // Atualiza cache local imediatamente (otimista)
    const cached = localStorage.getItem('arcco_prefs');
    const current = cached ? JSON.parse(cached) : DEFAULT_PREFS;
    const updated = { ...current, ...prefs };
    localStorage.setItem('arcco_prefs', JSON.stringify(updated));
    if (prefs.theme) {
      localStorage.setItem('arcco_theme', prefs.theme);
    }

    try {
      await fetch(`${API_BASE}/preferences/${userId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(prefs),
      });
    } catch (e) {
      console.warn('[preferencesApi] Erro ao salvar preferências:', e);
    }
  },

  /**
   * Lê do cache local sem fazer request (útil para acesso síncrono).
   */
  getCached(): UserPreferences {
    const cached = localStorage.getItem('arcco_prefs');
    if (cached) return JSON.parse(cached) as UserPreferences;
    return DEFAULT_PREFS;
  },
};
