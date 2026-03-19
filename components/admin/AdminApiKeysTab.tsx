import React from 'react';
import { Check, CheckCircle, Database, Eye, EyeOff, Loader2, XCircle } from 'lucide-react';

interface ApiKeyRow {
  id: number;
  provider: string;
  api_key: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

interface AdminApiKeysTabProps {
  apiKeys: ApiKeyRow[];
  visibleKeys: Set<number>;
  showAddKey: boolean;
  newKeyProvider: string;
  newKeyValue: string;
  addingKey: boolean;
  addKeyError: string;
  providerIcons: Record<string, string>;
  maskKey: (key: string) => string;
  formatDate: (dateStr?: string) => string;
  onToggleShowAddKey: () => void;
  onNewKeyProviderChange: (value: string) => void;
  onNewKeyValueChange: (value: string) => void;
  onSaveKey: () => void;
  onToggleKeyVisibility: (id: number) => void;
}

export const AdminApiKeysTab: React.FC<AdminApiKeysTabProps> = ({
  apiKeys,
  visibleKeys,
  showAddKey,
  newKeyProvider,
  newKeyValue,
  addingKey,
  addKeyError,
  providerIcons,
  maskKey,
  formatDate,
  onToggleShowAddKey,
  onNewKeyProviderChange,
  onNewKeyValueChange,
  onSaveKey,
  onToggleKeyVisibility,
}) => {
  return (
    <div className="bg-[#0f0f0f] border border-neutral-900 rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-neutral-900 flex items-center gap-2">
        <Database size={15} className="text-neutral-500" />
        <span className="text-sm font-medium text-neutral-300">Tabela: ApiKeys</span>
        <span className="ml-auto text-xs text-neutral-600">{apiKeys.length} registros</span>
        <button
          onClick={onToggleShowAddKey}
          className="ml-3 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-300 text-xs font-medium border border-indigo-500/30 transition-all"
        >
          {showAddKey ? 'âœ• Cancelar' : '+ Nova Chave'}
        </button>
      </div>

      {showAddKey && (
        <div className="px-5 py-4 border-b border-neutral-900 bg-neutral-900/30">
          <div className="flex items-end gap-3">
            <div className="flex-shrink-0">
              <label className="block text-xs font-medium text-neutral-500 uppercase tracking-wider mb-1.5">Provider</label>
              <select
                value={newKeyProvider}
                onChange={(e) => onNewKeyProviderChange(e.target.value)}
                className="bg-[#1a1a1a] border border-neutral-800 text-white text-sm rounded-lg px-3 py-2 outline-none focus:border-indigo-500/50"
              >
                <option value="browserbase">ðŸŒ Browserbase (API Key)</option>
                <option value="browserbase_project_id">ðŸ—‚ï¸ Browserbase (Project ID)</option>
                <option value="openrouter">ðŸ”€ OpenRouter</option>
                <option value="anthropic">ðŸ¤– Anthropic</option>
                <option value="openai">🟢 OpenAI</option>
              </select>
            </div>
            <div className="flex-1">
              <label className="block text-xs font-medium text-neutral-500 uppercase tracking-wider mb-1.5">API Key</label>
              <input
                value={newKeyValue}
                onChange={(e) => onNewKeyValueChange(e.target.value)}
                placeholder={
                  newKeyProvider === 'browserbase' ? 'bb_live_...' :
                  newKeyProvider === 'browserbase_project_id' ? 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx' :
                  'sk-...'
                }
                className="w-full bg-[#1a1a1a] border border-neutral-800 text-white text-sm font-mono rounded-lg px-3 py-2 outline-none focus:border-indigo-500/50"
              />
            </div>
            <button
              onClick={onSaveKey}
              disabled={addingKey || !newKeyValue.trim()}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors disabled:opacity-40"
            >
              {addingKey ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
              Salvar
            </button>
          </div>
          {addKeyError && <p className="text-xs text-red-400 mt-2">{addKeyError}</p>}
        </div>
      )}

      {apiKeys.length === 0 ? (
        <div className="py-16 text-center text-neutral-600 text-sm">Nenhuma API key encontrada</div>
      ) : (
        <div className="divide-y divide-neutral-900">
          {apiKeys.map((key) => (
            <div key={key.id} className="px-5 py-4 flex items-center gap-4 hover:bg-white/[0.02] transition-colors">
              <div className="w-9 h-9 rounded-lg bg-neutral-900 border border-neutral-800 flex items-center justify-center text-lg">
                {providerIcons[key.provider] || 'ðŸ”‘'}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-medium text-white capitalize">{key.provider}</span>
                  {key.is_active ? (
                    <span className="flex items-center gap-1 text-xs text-green-400 bg-green-500/10 border border-green-500/20 px-2 py-0.5 rounded-full">
                      <CheckCircle size={10} /> Ativa
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-xs text-red-400 bg-red-500/10 border border-red-500/20 px-2 py-0.5 rounded-full">
                      <XCircle size={10} /> Inativa
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <code className="text-xs font-mono text-neutral-500 bg-neutral-900 px-2 py-0.5 rounded">
                    {visibleKeys.has(key.id) ? key.api_key : maskKey(key.api_key)}
                  </code>
                  <button
                    onClick={() => onToggleKeyVisibility(key.id)}
                    className="text-neutral-600 hover:text-neutral-400 transition-colors"
                  >
                    {visibleKeys.has(key.id) ? <EyeOff size={13} /> : <Eye size={13} />}
                  </button>
                </div>
              </div>
              <div className="text-xs text-neutral-600 text-right">
                <div>Criada: {formatDate(key.created_at)}</div>
                {key.updated_at && key.updated_at !== key.created_at && (
                  <div>Atualizada: {formatDate(key.updated_at)}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
