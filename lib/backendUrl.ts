const rawBackendUrl = (import.meta.env.VITE_BACKEND_URL as string | undefined)?.trim() || '';

export const BACKEND_BASE_URL = rawBackendUrl.replace(/\/+$/, '');

export function withBackendUrl(path: string): string {
  if (!path.startsWith('/')) {
    throw new Error(`withBackendUrl expected absolute path, got: ${path}`);
  }
  return BACKEND_BASE_URL ? `${BACKEND_BASE_URL}${path}` : path;
}

export const AGENT_API_BASE = withBackendUrl('/api/agent');
export const ADMIN_API_BASE = withBackendUrl('/api/admin');
