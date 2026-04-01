import React from 'react';
import { Check, CheckCircle, Database, Eye, EyeOff, Loader2, Pencil, Power, Trash2, XCircle } from 'lucide-react';

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
  editingKeyId: number | null;
  editingProvider: string;
  editingValue: string;
  editingActive: boolean;
  editingError: string;
  savingEdit: boolean;
  actionKeyId: number | null;
  providerIcons: Record<string, string>;
  maskKey: (key: string) => string;
  formatDate: (dateStr?: string) => string;
  onToggleShowAddKey: () => void;
  onNewKeyProviderChange: (value: string) => void;
  onNewKeyValueChange: (value: string) => void;
  onSaveKey: () => void;
  onStartEditKey: (row: ApiKeyRow) => void;
  onCancelEditKey: () => void;
  onEditingProviderChange: (value: string) => void;
  onEditingValueChange: (value: string) => void;
  onEditingActiveChange: (value: boolean) => void;
  onSaveEditKey: () => void;
  onToggleKeyActive: (row: ApiKeyRow) => void;
  onDeleteKey: (row: ApiKeyRow) => void;
  onToggleKeyVisibility: (id: number) => void;
}

const SUGGESTED_PROVIDERS = [
  'browserbase',
  'browserbase_project_id',
  'openrouter',
  'anthropic',
  'openai',
  'tavily',
  'firecrawl',
  'e2b',
  'e2b_api_key',
];

export const AdminApiKeysTab: React.FC<AdminApiKeysTabProps> = ({
  apiKeys,
  visibleKeys,
  showAddKey,
  newKeyProvider,
  newKeyValue,
  addingKey,
  addKeyError,
  editingKeyId,
  editingProvider,
  editingValue,
  editingActive,
  editingError,
  savingEdit,
  actionKeyId,
  providerIcons,
  maskKey,
  formatDate,
  onToggleShowAddKey,
  onNewKeyProviderChange,
  onNewKeyValueChange,
  onSaveKey,
  onStartEditKey,
  onCancelEditKey,
  onEditingProviderChange,
  onEditingValueChange,
  onEditingActiveChange,
  onSaveEditKey,
  onToggleKeyActive,
  onDeleteKey,
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
              <input
                list="apikey-provider-suggestions"
                value={newKeyProvider}
                onChange={(e) => onNewKeyProviderChange(e.target.value)}
                placeholder="ex: e2b"
                className="bg-[#1a1a1a] border border-neutral-800 text-white text-sm rounded-lg px-3 py-2 outline-none focus:border-indigo-500/50"
              />
              <datalist id="apikey-provider-suggestions">
                {SUGGESTED_PROVIDERS.map((provider) => (
                  <option key={provider} value={provider} />
                ))}
              </datalist>
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
              {editingKeyId === key.id ? (
                <div className="flex-1 min-w-0">
                  <div className="grid grid-cols-[minmax(140px,220px)_1fr_auto] gap-3 items-end">
                    <div>
                      <label className="block text-[10px] font-medium text-neutral-500 uppercase tracking-wider mb-1.5">Provider</label>
                      <input
                        list="apikey-provider-suggestions"
                        value={editingProvider}
                        onChange={(e) => onEditingProviderChange(e.target.value)}
                        className="w-full bg-[#1a1a1a] border border-neutral-800 text-white text-sm rounded-lg px-3 py-2 outline-none focus:border-indigo-500/50"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-medium text-neutral-500 uppercase tracking-wider mb-1.5">API Key</label>
                      <input
                        value={editingValue}
                        onChange={(e) => onEditingValueChange(e.target.value)}
                        className="w-full bg-[#1a1a1a] border border-neutral-800 text-white text-sm font-mono rounded-lg px-3 py-2 outline-none focus:border-indigo-500/50"
                      />
                    </div>
                    <label className="flex items-center gap-2 text-xs text-neutral-400 mb-2">
                      <input
                        type="checkbox"
                        checked={editingActive}
                        onChange={(e) => onEditingActiveChange(e.target.checked)}
                      />
                      Ativa
                    </label>
                  </div>
                  {editingError && <p className="text-xs text-red-400 mt-2">{editingError}</p>}
                </div>
              ) : (
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
              )}
              <div className="flex items-center gap-2">
                {editingKeyId === key.id ? (
                  <>
                    <button
                      onClick={onSaveEditKey}
                      disabled={savingEdit}
                      className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs transition-colors disabled:opacity-50"
                    >
                      {savingEdit ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
                      Salvar
                    </button>
                    <button
                      onClick={onCancelEditKey}
                      disabled={savingEdit}
                      className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-neutral-900 hover:bg-neutral-800 text-neutral-400 text-xs transition-colors border border-neutral-800 disabled:opacity-50"
                    >
                      <XCircle size={13} />
                      Cancelar
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={() => onStartEditKey(key)}
                      className="text-neutral-500 hover:text-white transition-colors"
                      title="Editar chave"
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      onClick={() => onToggleKeyActive(key)}
                      disabled={actionKeyId === key.id}
                      className="text-neutral-500 hover:text-white transition-colors disabled:opacity-50"
                      title={key.is_active ? 'Desativar chave' : 'Ativar chave'}
                    >
                      {actionKeyId === key.id ? <Loader2 size={14} className="animate-spin" /> : <Power size={14} />}
                    </button>
                    <button
                      onClick={() => onDeleteKey(key)}
                      disabled={actionKeyId === key.id}
                      className="text-neutral-500 hover:text-red-400 transition-colors disabled:opacity-50"
                      title="Excluir chave"
                    >
                      <Trash2 size={14} />
                    </button>
                  </>
                )}
              </div>
              <div className="text-xs text-neutral-600 text-right min-w-[110px]">
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
