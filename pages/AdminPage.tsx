/**
 * Painel Administrativo â€” /admin
 *
 * ACESSO: URL direta /admin (bypass do auth normal, ver App.tsx â†’ isAdminRoute)
 *
 * ABAS:
 *   UsuÃ¡rios      â†’ tabela "User" do Supabase, ediÃ§Ã£o de plano inline
 *   API Keys      â†’ tabela "ApiKeys" com toggle show/hide da chave
 *   OrquestraÃ§Ã£o  â†’ painel de controle dos agentes Python do backend
 *
 * ORQUESTRAÃ‡ÃƒO:
 *   Conecta ao backend FastAPI em localhost:8001 via Vite proxy (/api/admin/*)
 *   Permite editar model, system_prompt e tools de cada agente.
 *   Ao salvar, o backend reescreve diretamente os arquivos prompts.py / tools.py.
 *   Uvicorn detecta a mudanÃ§a e reinicia automaticamente (--reload).
 *
 * backendUrl = '' â†’ usa Vite proxy (nÃ£o aponta direto para localhost:8001)
 *   â†’ vite.config.ts mapeia /api/admin/* para http://localhost:8001
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  Users,
  Key,
  RefreshCw,
  Shield,
  Mail,
  Calendar,
  Eye,
  EyeOff,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Database,
  Check,
  Loader2,
  GitBranch,
  ChevronDown,
  ChevronUp,
  RotateCcw,
  Save,
  Terminal,
  Cpu,
  Wrench,
  Brain,
  Code2,
  Monitor,
  FileText
} from 'lucide-react';
import { supabase } from '../lib/supabase';

// â”€â”€ Tipos de dados â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

interface UserRow {
  id: string;
  nome: string;
  email: string;
  plano: string;
  cpf?: string;
  content?: { telefone?: string; ocupacao?: string };
  created_at?: string;
}

interface ApiKeyRow {
  id: number;
  provider: string;
  api_key: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

type Tab = 'usuarios' | 'apikeys' | 'orquestracao' | 'chat_normal';

// ConfiguraÃ§Ã£o de um agente Python (retornada pelo backend)
interface AgentConfig {
  id: string;
  name: string;
  module: string;       // Produto ao qual pertence: "Arcco Chat", "Sistema", etc.
  description: string;
  system_prompt: string;
  model: string;        // ID do modelo OpenRouter (ex: "openai/gpt-4o")
  tools: any[];         // Ferramentas no formato OpenAI/OpenRouter
}

// Modelo retornado por GET /api/admin/models
interface ORModel {
  id: string;
  name: string;
  context_length: number;
  pricing: { prompt_1m: number; completion_1m: number };
}

interface ChatConfigRow {
  id?: string;
  slot_number: number;
  model_name: string;
  openrouter_model_id: string;
  system_prompt?: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

// Cores de badge por mÃ³dulo/produto
const MODULE_COLORS: Record<string, string> = {
  'Sistema': 'bg-orange-900/40 text-orange-300 border-orange-500/20',
  'Arcco Chat': 'bg-indigo-900/40 text-indigo-300 border-indigo-500/20',
};

// Ãcone de cada agente no header do card
const AGENT_ICONS: Record<string, React.ReactNode> = {
  chat: <Brain size={15} />,
  orchestrator: <GitBranch size={15} />,
  web_search: <Terminal size={15} />,
  text_generator: <FileText size={15} />,
  design_generator: <Monitor size={15} />,
  file_modifier: <Wrench size={15} />,
  design: <Cpu size={15} />,
  dev: <Code2 size={15} />,
  qa: <CheckCircle size={15} />,
};

/** Formata preÃ§o por 1M tokens: 0 â†’ "GrÃ¡tis", outros â†’ "$0.0050" */
function fmtPrice(v: number) {
  if (v === 0) return 'GrÃ¡tis';
  return `$${v.toFixed(4)}`;
}


// â”€â”€ Componente: Dropdown de modelo pesquisÃ¡vel â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
/**
 * Combobox que lista todos os modelos do OpenRouter com preÃ§o.
 * Filtra por nome ou ID em tempo real conforme o usuÃ¡rio digita.
 * Fecha ao clicar fora (listener no document).
 */

interface ModelDropdownProps {
  value: string;
  models: ORModel[];
  loadingModels: boolean;
  onChange: (id: string) => void;
}

const ModelDropdown: React.FC<ModelDropdownProps> = ({ value, models, loadingModels, onChange }) => {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  const selected = models.find(m => m.id === value);
  const filtered = models.filter(m =>
    m.name.toLowerCase().includes(search.toLowerCase()) ||
    m.id.toLowerCase().includes(search.toLowerCase())
  );

  // Fecha o dropdown ao clicar fora do componente
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={ref} className="relative">
      {/* BotÃ£o trigger */}
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between gap-2 bg-[#1a1a1a] border border-neutral-800 hover:border-neutral-700 text-white text-sm rounded-lg px-3 py-2.5 outline-none transition-colors text-left"
      >
        <div className="flex-1 min-w-0">
          {loadingModels ? (
            <span className="text-neutral-500">Carregando modelos...</span>
          ) : selected ? (
            <span className="truncate">{selected.name} <span className="text-neutral-500 text-xs">â€” {selected.id}</span></span>
          ) : (
            <span className="text-neutral-400 truncate">{value || 'Selecionar modelo'}</span>
          )}
        </div>
        <ChevronDown size={14} className={`text-neutral-500 transition-transform shrink-0 ${open ? 'rotate-180' : ''}`} />
      </button>

      {/* Lista de modelos */}
      {open && (
        <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-[#141414] border border-neutral-800 rounded-xl shadow-2xl overflow-hidden">
          {/* Campo de busca */}
          <div className="p-2 border-b border-neutral-800">
            <input
              autoFocus
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Buscar por nome ou ID..."
              className="w-full bg-[#1a1a1a] border border-neutral-800 rounded-lg px-3 py-1.5 text-xs text-white outline-none placeholder-neutral-600"
            />
          </div>
          {/* Itens */}
          <div className="max-h-72 overflow-y-auto">
            {filtered.length === 0 ? (
              <div className="px-4 py-3 text-xs text-neutral-600">Nenhum modelo encontrado</div>
            ) : filtered.map(m => (
              <button
                key={m.id}
                onClick={() => { onChange(m.id); setOpen(false); setSearch(''); }}
                className={`w-full flex items-start justify-between gap-3 px-4 py-2.5 hover:bg-white/[0.04] transition-colors text-left ${value === m.id ? 'bg-indigo-500/10' : ''}`}
              >
                <div className="flex-1 min-w-0">
                  <p className={`text-xs font-medium truncate ${value === m.id ? 'text-indigo-300' : 'text-white'}`}>{m.name}</p>
                  <p className="text-[10px] text-neutral-600 truncate">{m.id}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-[10px] text-green-400">In: {fmtPrice(m.pricing.prompt_1m)}/1M</p>
                  <p className="text-[10px] text-blue-400">Out: {fmtPrice(m.pricing.completion_1m)}/1M</p>
                </div>
              </button>
            ))}
          </div>
          <div className="px-4 py-2 border-t border-neutral-800 text-[10px] text-neutral-700">
            {filtered.length} de {models.length} modelos
          </div>
        </div>
      )}
    </div>
  );
};


// â”€â”€ Componente: Card de Agente â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
/**
 * Card expansÃ­vel para cada agente do backend.
 *
 * Estado local: mantÃ©m cÃ³pias editÃ¡veis dos campos do agente.
 * isDirty: detecta se algo foi modificado em relaÃ§Ã£o ao estado original
 *          (usado para habilitar o botÃ£o Salvar e mostrar badge "nÃ£o salvo").
 *
 * Ao salvar: chama onSave() que faz PUT /api/admin/agents/{id}
 * Ao resetar: chama onReset() que faz POST /api/admin/agents/reset/{id}
 */

interface AgentCardProps {
  agent: AgentConfig;
  models: ORModel[];
  loadingModels: boolean;
  onSave: (id: string, data: Partial<AgentConfig & { name: string; description: string }>) => Promise<void>;
  onReset: (id: string) => Promise<void>;
}

const AgentCard: React.FC<AgentCardProps> = ({ agent, models, loadingModels, onSave, onReset }) => {
  // Estado local de ediÃ§Ã£o â€” espelha os campos do agente
  const [expanded, setExpanded] = useState(false);
  const [name, setName] = useState(agent.name);
  const [description, setDesc] = useState(agent.description);
  const [prompt, setPrompt] = useState(agent.system_prompt);
  const [model, setModel] = useState(agent.model);
  const [toolsJson, setToolsJson] = useState(JSON.stringify(agent.tools, null, 2));
  const [toolsError, setToolsError] = useState('');
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState('');

  const selectedModel = models.find(m => m.id === model);

  // Detecta se o usuÃ¡rio modificou algo em relaÃ§Ã£o ao estado original do agente
  const isDirty =
    name !== agent.name ||
    description !== agent.description ||
    prompt !== agent.system_prompt ||
    model !== agent.model ||
    toolsJson !== JSON.stringify(agent.tools, null, 2);

  const handleSave = async () => {
    // Valida JSON das tools antes de enviar
    let parsedTools;
    try {
      parsedTools = JSON.parse(toolsJson);
      setToolsError('');
    } catch {
      setToolsError('JSON invÃ¡lido â€” corrija antes de salvar');
      return;
    }
    setSaving(true);
    setSaveError('');
    try {
      await onSave(agent.id, { name, description, system_prompt: prompt, model, tools: parsedTools });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e: any) {
      setSaveError(e.message || 'Erro ao salvar');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!confirm(`Resetar "${agent.name}" para o padrÃ£o original?`)) return;
    setResetting(true);
    try {
      await onReset(agent.id);
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className={`bg-[#0f0f0f] border rounded-xl overflow-hidden transition-all duration-200 ${expanded ? 'border-indigo-500/30' : 'border-neutral-900 hover:border-neutral-800'}`}>
      {/* Header clicÃ¡vel â€” expande/recolhe o card */}
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center gap-4 px-5 py-4 hover:bg-white/[0.02] transition-colors text-left"
      >
        <div className="w-8 h-8 rounded-lg bg-neutral-900 border border-neutral-800 flex items-center justify-center text-indigo-400 shrink-0">
          {AGENT_ICONS[agent.id] || <Cpu size={15} />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5 flex-wrap">
            <span className="text-sm font-semibold text-white">{name}</span>
            {/* Badge do mÃ³dulo/produto */}
            <span className={`inline-flex items-center text-[10px] font-medium px-2 py-0.5 rounded-full border ${MODULE_COLORS[agent.module] || 'bg-neutral-800 text-neutral-400 border-neutral-700'}`}>
              {agent.module}
            </span>
            {/* Indicador de mudanÃ§as nÃ£o salvas */}
            {isDirty && (
              <span className="text-[10px] text-yellow-400 bg-yellow-500/10 px-2 py-0.5 rounded-full border border-yellow-500/20">
                nÃ£o salvo
              </span>
            )}
          </div>
          <p className="text-xs text-neutral-500 truncate">{description}</p>
        </div>
        {/* Info resumida visÃ­vel sem expandir */}
        <div className="flex items-center gap-3 shrink-0 text-xs text-neutral-600">
          {selectedModel && (
            <span className="hidden lg:block text-green-500/70">{fmtPrice(selectedModel.pricing.prompt_1m)}/1M</span>
          )}
          <span>{agent.tools.length} tools</span>
          <div className="text-neutral-600">{expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}</div>
        </div>
      </button>

      {/* Corpo expandido â€” campos editÃ¡veis */}
      {expanded && (
        <div className="border-t border-neutral-900 px-5 py-5 space-y-5">

          {/* Nome e DescriÃ§Ã£o */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-neutral-500 uppercase tracking-wider mb-1.5">Nome</label>
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                className="w-full bg-[#1a1a1a] border border-neutral-800 text-white text-sm rounded-lg px-3 py-2 outline-none focus:border-indigo-500/50 transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-neutral-500 uppercase tracking-wider mb-1.5">DescriÃ§Ã£o</label>
              <input
                value={description}
                onChange={e => setDesc(e.target.value)}
                className="w-full bg-[#1a1a1a] border border-neutral-800 text-white text-sm rounded-lg px-3 py-2 outline-none focus:border-indigo-500/50 transition-colors"
              />
            </div>
          </div>

          {/* Seletor de modelo â€” lista todos os modelos do OpenRouter */}
          <div>
            <label className="block text-xs font-medium text-neutral-500 uppercase tracking-wider mb-1.5">
              Modelo OpenRouter
              {selectedModel && (
                <span className="ml-2 font-normal normal-case text-neutral-600">
                  ctx: {(selectedModel.context_length / 1000).toFixed(0)}k tokens â€¢{' '}
                  <span className="text-green-500/80">in: {fmtPrice(selectedModel.pricing.prompt_1m)}/1M</span>{' '}â€¢{' '}
                  <span className="text-blue-500/80">out: {fmtPrice(selectedModel.pricing.completion_1m)}/1M</span>
                </span>
              )}
            </label>
            <ModelDropdown
              value={model}
              models={models}
              loadingModels={loadingModels}
              onChange={setModel}
            />
          </div>

          {/* System Prompt â€” textarea monoespaÃ§ada, redimensionÃ¡vel */}
          <div>
            <label className="block text-xs font-medium text-neutral-500 uppercase tracking-wider mb-1.5">
              System Prompt
              <span className="ml-2 normal-case font-normal text-neutral-700">{prompt.length} chars</span>
            </label>
            <textarea
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              rows={14}
              className="w-full bg-[#1a1a1a] border border-neutral-800 text-neutral-200 text-xs font-mono rounded-lg px-4 py-3 outline-none focus:border-indigo-500/50 transition-colors resize-y leading-relaxed"
              spellCheck={false}
            />
          </div>

          {/* Tools â€” JSON raw editÃ¡vel. Agentes sem tools mostram aviso em vez do editor */}
          <div>
            <label className="block text-xs font-medium text-neutral-500 uppercase tracking-wider mb-1.5">
              Tools (JSON)
              <span className="ml-2 normal-case font-normal text-neutral-700">{agent.tools.length} definidas</span>
            </label>
            {agent.tools.length === 0 && toolsJson === '[]' ? (
              <div className="flex items-center gap-2 px-4 py-3 bg-neutral-900/50 border border-neutral-800 rounded-lg text-xs text-neutral-600">
                <XCircle size={13} /> Este agente nÃ£o usa ferramentas (design/dev/chat/qa)
              </div>
            ) : (
              <>
                <textarea
                  value={toolsJson}
                  onChange={e => { setToolsJson(e.target.value); setToolsError(''); }}
                  rows={12}
                  className={`w-full bg-[#1a1a1a] border text-neutral-200 text-xs font-mono rounded-lg px-4 py-3 outline-none transition-colors resize-y leading-relaxed ${toolsError ? 'border-red-500/50' : 'border-neutral-800 focus:border-indigo-500/50'}`}
                  spellCheck={false}
                />
                {toolsError && <p className="text-xs text-red-400 mt-1">{toolsError}</p>}
              </>
            )}
          </div>

          {/* Feedback de erro ao salvar */}
          {saveError && (
            <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-400">
              <AlertTriangle size={13} /> {saveError}
            </div>
          )}

          {/* ConfirmaÃ§Ã£o de sucesso + aviso de hot-reload */}
          {saved && (
            <div className="flex items-center gap-2 p-3 bg-green-500/10 border border-green-500/20 rounded-lg text-xs text-green-400">
              <Check size={13} />
              Salvo em <code className="mx-1 text-green-300">prompts.py</code> / <code className="mx-1 text-green-300">tools.py</code> â€” uvicorn reiniciando automaticamente...
            </div>
          )}

          {/* AÃ§Ãµes */}
          <div className="flex items-center justify-between pt-1">
            <button
              onClick={handleReset}
              disabled={resetting}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs text-neutral-500 hover:text-red-400 hover:bg-red-500/10 border border-neutral-800 hover:border-red-500/20 transition-all disabled:opacity-50"
            >
              {resetting ? <Loader2 size={13} className="animate-spin" /> : <RotateCcw size={13} />}
              Resetar padrÃ£o
            </button>
            {/* BotÃ£o salvar sÃ³ fica ativo quando hÃ¡ mudanÃ§as (isDirty) */}
            <button
              onClick={handleSave}
              disabled={saving || !isDirty}
              className="flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium bg-indigo-500/20 text-indigo-300 hover:bg-indigo-500/30 border border-indigo-500/30 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {saving ? <Loader2 size={14} className="animate-spin" /> :
                saved ? <Check size={14} className="text-green-400" /> :
                  <Save size={14} />}
              {saved ? 'Salvo no .py!' : 'Salvar no cÃ³digo'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

interface ChatConfigCardProps {
  config: ChatConfigRow;
  models: ORModel[];
  loadingModels: boolean;
  onSave: (config: ChatConfigRow) => Promise<void>;
}

const ChatConfigCard: React.FC<ChatConfigCardProps> = ({ config, models, loadingModels, onSave }) => {
  const [modelName, setModelName] = useState(config.model_name);
  const [modelId, setModelId] = useState(config.openrouter_model_id);
  const [systemPrompt, setSystemPrompt] = useState(config.system_prompt || '');
  const [isActive, setIsActive] = useState(config.is_active);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const selectedModel = models.find(m => m.id === modelId);

  useEffect(() => {
    setModelName(config.model_name);
    setModelId(config.openrouter_model_id);
    setSystemPrompt(config.system_prompt || '');
    setIsActive(config.is_active);
  }, [config]);

  useEffect(() => {
    if (selectedModel && (!modelName || modelName === config.model_name || modelName === config.openrouter_model_id)) {
      setModelName(selectedModel.name);
    }
  }, [selectedModel]);

  const isDirty =
    modelName !== config.model_name ||
    modelId !== config.openrouter_model_id ||
    systemPrompt !== (config.system_prompt || '') ||
    isActive !== config.is_active;

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave({
        ...config,
        model_name: modelName || selectedModel?.name || modelId || `Chat Slot ${config.slot_number}`,
        openrouter_model_id: modelId,
        system_prompt: systemPrompt,
        is_active: isActive,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-[#0f0f0f] border border-neutral-900 rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold text-white">{modelName || `Modelo ${config.slot_number}`}</h3>
          <p className="text-xs text-neutral-500">Slot {config.slot_number} exibido no seletor do modo chat.</p>
        </div>
        <label className="flex items-center gap-2 text-xs text-neutral-400">
          <input
            type="checkbox"
            checked={isActive}
            onChange={e => setIsActive(e.target.checked)}
            className="rounded border-neutral-700 bg-[#1a1a1a]"
          />
          Ativo
        </label>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-medium text-neutral-500 uppercase tracking-wider mb-1.5">Nome exibido</label>
          <input
            value={modelName}
            onChange={e => setModelName(e.target.value)}
            className="w-full bg-[#1a1a1a] border border-neutral-800 text-white text-sm rounded-lg px-3 py-2 outline-none focus:border-indigo-500/50 transition-colors"
            placeholder={`Chat Slot ${config.slot_number}`}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-neutral-500 uppercase tracking-wider mb-1.5">
            Modelo OpenRouter
            {selectedModel && (
              <span className="ml-2 font-normal normal-case text-neutral-600">
                ctx: {(selectedModel.context_length / 1000).toFixed(0)}k tokens
              </span>
            )}
          </label>
          <ModelDropdown
            value={modelId}
            models={models}
            loadingModels={loadingModels}
            onChange={setModelId}
          />
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-neutral-500 uppercase tracking-wider mb-1.5">
          System Prompt
          <span className="ml-2 normal-case font-normal text-neutral-700">{systemPrompt.length} chars</span>
        </label>
        <textarea
          value={systemPrompt}
          onChange={e => setSystemPrompt(e.target.value)}
          rows={10}
          className="w-full bg-[#1a1a1a] border border-neutral-800 text-neutral-200 text-xs font-mono rounded-lg px-4 py-3 outline-none focus:border-indigo-500/50 transition-colors resize-y leading-relaxed"
          spellCheck={false}
        />
      </div>

      {selectedModel && (
        <div className="flex flex-wrap items-center gap-3 text-[11px] text-neutral-500">
          <span className="text-green-400">In: {fmtPrice(selectedModel.pricing.prompt_1m)}/1M</span>
          <span className="text-blue-400">Out: {fmtPrice(selectedModel.pricing.completion_1m)}/1M</span>
          <span>Contexto: {selectedModel.context_length.toLocaleString('pt-BR')} tokens</span>
        </div>
      )}

      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={saving || !isDirty || !modelId}
          className="flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium bg-indigo-500/20 text-indigo-300 hover:bg-indigo-500/30 border border-indigo-500/30 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {saving ? <Loader2 size={14} className="animate-spin" /> : saved ? <Check size={14} className="text-green-400" /> : <Save size={14} />}
          {saved ? 'Salvo' : 'Salvar slot'}
        </button>
      </div>
    </div>
  );
};


// â”€â”€ Constantes do painel â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

const PLANS = ['free', 'starter', 'ultra'] as const;
type Plan = typeof PLANS[number];

const PLAN_COLORS: Record<string, string> = {
  free: 'bg-neutral-700/60 text-neutral-300',
  starter: 'bg-blue-900/50 text-blue-300',
  ultra: 'bg-purple-900/50 text-purple-300',
};

const PROVIDER_ICONS: Record<string, string> = {
  openrouter: 'ðŸ”€',
  anthropic: 'ðŸ¤–',
  browserbase: 'ðŸŒ',
  browserbase_project_id: 'ðŸ—‚ï¸',
};

/** Exibe apenas inÃ­cio e fim da chave: "sk-abâ€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢ef12" */
function maskKey(key: string): string {
  if (!key || key.length < 12) return 'â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢';
  return key.slice(0, 6) + 'â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢â€¢' + key.slice(-4);
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return 'â€”';
  return new Date(dateStr).toLocaleDateString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric'
  });
}


// â”€â”€ Componente principal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export const AdminPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('usuarios');

  // Dados do Supabase
  const [users, setUsers] = useState<UserRow[]>([]);
  const [apiKeys, setApiKeys] = useState<ApiKeyRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [visibleKeys, setVisibleKeys] = useState<Set<number>>(new Set());
  const [savingPlan, setSavingPlan] = useState<string | null>(null);
  const [savedPlan, setSavedPlan] = useState<string | null>(null);

  // Form para adicionar nova API Key
  const [showAddKey, setShowAddKey] = useState(false);
  const [newKeyProvider, setNewKeyProvider] = useState('browserbase');
  const [newKeyValue, setNewKeyValue] = useState('');
  const [addingKey, setAddingKey] = useState(false);
  const [addKeyError, setAddKeyError] = useState('');

  // Dados da aba OrquestraÃ§Ã£o (carregados sÃ³ quando a aba Ã© aberta)
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(false);
  const [agentsError, setAgentsError] = useState<string | null>(null);
  const [orModels, setOrModels] = useState<ORModel[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [chatConfigs, setChatConfigs] = useState<ChatConfigRow[]>([]);
  const [chatConfigsLoading, setChatConfigsLoading] = useState(false);
  const [chatConfigsError, setChatConfigsError] = useState<string | null>(null);

  // '' = usa Vite proxy (/api/admin/* â†’ localhost:8001). NÃ£o hardcodar localhost aqui.
  const backendUrl = '';

  // â”€â”€ Busca de dados Supabase â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [usersRes, keysRes] = await Promise.all([
        supabase.from('User').select('*').order('created_at', { ascending: false }),
        supabase.from('ApiKeys').select('*').order('id'),
      ]);

      if (usersRes.error) throw new Error('UsuÃ¡rios: ' + usersRes.error.message);
      if (keysRes.error) throw new Error('ApiKeys: ' + keysRes.error.message);

      setUsers(usersRes.data || []);
      setApiKeys(keysRes.data || []);
    } catch (err: any) {
      setError(err.message || 'Erro ao carregar dados');
    } finally {
      setLoading(false);
    }
  };

  // â”€â”€ Busca de dados do backend Python â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  const fetchModels = async () => {
    setModelsLoading(true);
    try {
      const res = await fetch(`${backendUrl}/api/admin/models`);
      if (!res.ok) return;
      const data = await res.json();
      setOrModels(data.models || []);
    } catch { /* silencioso â€” dropdown funciona mesmo sem lista de modelos */ }
    finally { setModelsLoading(false); }
  };

  const fetchAgents = async () => {
    setAgentsLoading(true);
    setAgentsError(null);
    try {
      const res = await fetch(`${backendUrl}/api/admin/agents`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      const data = await res.json();
      setAgents(data.agents || []);
    } catch (err: any) {
      setAgentsError(err.message || 'Erro ao conectar com o backend');
    } finally {
      setAgentsLoading(false);
    }
  };

  const fetchChatConfigs = async () => {
    setChatConfigsLoading(true);
    setChatConfigsError(null);
    try {
      const res = await fetch(`${backendUrl}/api/admin/chat-models`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const rows = (data.models || []) as ChatConfigRow[];
      setChatConfigs(rows.sort((a, b) => a.slot_number - b.slot_number));
    } catch (err: any) {
      setChatConfigsError(err.message || 'Erro ao carregar configuracoes do chat');
    } finally {
      setChatConfigsLoading(false);
    }
  };

  /** Envia alteraÃ§Ãµes de um agente para o backend (PUT /api/admin/agents/{id}) */
  const saveAgent = async (id: string, data: Partial<AgentConfig>) => {
    const res = await fetch(`${backendUrl}/api/admin/agents/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`Erro ao salvar: ${await res.text()}`);
    const updated = await res.json();
    // Atualiza sÃ³ o agente modificado na lista local
    setAgents(prev => prev.map(a => a.id === id ? updated.agent : a));
  };

  /** Reseta um agente para os valores padrÃ£o (POST /api/admin/agents/reset/{id}) */
  const resetAgent = async (id: string) => {
    const res = await fetch(`${backendUrl}/api/admin/agents/reset/${id}`, { method: 'POST' });
    if (!res.ok) throw new Error(`Erro ao resetar: ${await res.text()}`);
    const updated = await res.json();
    setAgents(prev => prev.map(a => a.id === id ? updated.agent : a));
  };

  const saveChatConfig = async (config: ChatConfigRow) => {
    const url = config.id
      ? `${backendUrl}/api/admin/chat-models/${config.id}`
      : `${backendUrl}/api/admin/chat-models`;
    const method = config.id ? 'PUT' : 'POST';
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    if (!res.ok) throw new Error(await res.text());
    const result = await res.json();
    const saved = result.model as ChatConfigRow;
    setChatConfigs(prev =>
      [...prev.filter(item => item.slot_number !== config.slot_number), saved]
        .sort((a, b) => a.slot_number - b.slot_number)
    );
  };

  const createChatConfig = () => {
    setChatConfigs(prev => {
      const nextSlot = prev.length > 0 ? Math.max(...prev.map(item => item.slot_number)) + 1 : 1;
      return [
        ...prev,
        {
          slot_number: nextSlot,
          model_name: `Novo modelo ${nextSlot}`,
          openrouter_model_id: '',
          system_prompt: '',
          is_active: true,
        }
      ].sort((a, b) => a.slot_number - b.slot_number);
    });
  };

  // Carrega dados do Supabase ao montar o componente
  useEffect(() => {
    fetchData();
  }, []);

  // Carrega agentes e modelos somente quando a aba OrquestraÃ§Ã£o Ã© aberta
  // (lazy loading â€” evita chamar o backend desnecessariamente)
  useEffect(() => {
    if (activeTab === 'orquestracao') {
      if (agents.length === 0) fetchAgents();
      if (orModels.length === 0) fetchModels();
    }
    if (activeTab === 'chat_normal') {
      if (chatConfigs.length === 0) fetchChatConfigs();
      if (orModels.length === 0) fetchModels();
    }
  }, [activeTab]);

  // â”€â”€ AÃ§Ãµes de usuÃ¡rio â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  /** Atualiza o plano de um usuÃ¡rio no Supabase e reflete localmente */
  const updateUserPlan = async (userId: string, newPlan: Plan) => {
    setSavingPlan(userId);
    setSavedPlan(null);
    const { error } = await supabase
      .from('User')
      .update({ plano: newPlan })
      .eq('id', userId);

    if (!error) {
      setUsers(prev => prev.map(u => u.id === userId ? { ...u, plano: newPlan } : u));
      setSavedPlan(userId);
      setTimeout(() => setSavedPlan(null), 2000);
    }
    setSavingPlan(null);
  };

  const toggleKeyVisibility = (id: number) => {
    setVisibleKeys(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // â”€â”€ ConfiguraÃ§Ã£o das tabs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  const tabs: { id: Tab; label: string; icon: React.ReactNode; count: number }[] = [
    { id: 'usuarios', label: 'UsuÃ¡rios', icon: <Users size={16} />, count: users.length },
    { id: 'apikeys', label: 'API Keys', icon: <Key size={16} />, count: apiKeys.length },
    { id: 'orquestracao', label: 'OrquestraÃ§Ã£o', icon: <GitBranch size={16} />, count: agents.length },
    { id: 'chat_normal', label: 'Chat Normal', icon: <Brain size={16} />, count: chatConfigs.filter(c => c.is_active).length },
  ];

  // â”€â”€ RenderizaÃ§Ã£o â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  return (
    <div className="min-h-screen text-white" style={{ backgroundColor: 'var(--bg-base)' }}>
      {/* Topo */}
      <div className="border-b border-neutral-900 bg-[#0a0a0a]">
        <div className="max-w-7xl mx-auto px-6 py-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-red-500/20 to-orange-500/20 border border-red-500/20 flex items-center justify-center">
              <Shield size={18} className="text-red-400" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-white">Painel Administrativo</h1>
              <p className="text-xs text-neutral-500">Arcco Agents â€” Acesso restrito</p>
            </div>
          </div>
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-neutral-900 hover:bg-neutral-800 text-neutral-300 text-sm transition-colors border border-neutral-800 disabled:opacity-50"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Atualizar
          </button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* Cards de resumo */}
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-[#0f0f0f] border border-neutral-900 rounded-xl p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-indigo-500/10 flex items-center justify-center">
              <Users size={20} className="text-indigo-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{users.length}</p>
              <p className="text-xs text-neutral-500">UsuÃ¡rios cadastrados</p>
            </div>
          </div>
          <div className="bg-[#0f0f0f] border border-neutral-900 rounded-xl p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center">
              <Key size={20} className="text-green-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-white">{apiKeys.filter(k => k.is_active).length}</p>
              <p className="text-xs text-neutral-500">API Keys ativas</p>
            </div>
          </div>
        </div>

        {/* Erro geral do Supabase */}
        {error && (
          <div className="mb-4 flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
            <AlertTriangle size={16} />
            {error}
          </div>
        )}

        {/* NavegaÃ§Ã£o por tabs */}
        <div className="flex gap-1 mb-6 bg-[#0f0f0f] border border-neutral-900 rounded-xl p-1 w-fit">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === tab.id
                ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
                : 'text-neutral-500 hover:text-neutral-300'
                }`}
            >
              {tab.icon}
              {tab.label}
              <span className={`text-xs px-1.5 py-0.5 rounded-full ${activeTab === tab.id ? 'bg-indigo-500/30 text-indigo-300' : 'bg-neutral-800 text-neutral-500'
                }`}>
                {tab.count}
              </span>
            </button>
          ))}
        </div>

        {/* Loading global */}
        {loading && (
          <div className="flex items-center justify-center py-20 text-neutral-500">
            <RefreshCw size={20} className="animate-spin mr-3" />
            Carregando dados...
          </div>
        )}

        {/* â”€â”€ Tab: UsuÃ¡rios â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
        {!loading && activeTab === 'usuarios' && (
          <div className="bg-[#0f0f0f] border border-neutral-900 rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-neutral-900 flex items-center gap-2">
              <Database size={15} className="text-neutral-500" />
              <span className="text-sm font-medium text-neutral-300">Tabela: User</span>
              <span className="ml-auto text-xs text-neutral-600">{users.length} registros</span>
            </div>
            {users.length === 0 ? (
              <div className="py-16 text-center text-neutral-600 text-sm">Nenhum usuÃ¡rio encontrado</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-neutral-900">
                      <th className="text-left px-5 py-3 text-xs font-medium text-neutral-600 uppercase tracking-wider">Nome</th>
                      <th className="text-left px-5 py-3 text-xs font-medium text-neutral-600 uppercase tracking-wider">Email</th>
                      <th className="text-left px-5 py-3 text-xs font-medium text-neutral-600 uppercase tracking-wider">Plano</th>
                      <th className="text-left px-5 py-3 text-xs font-medium text-neutral-600 uppercase tracking-wider">CPF</th>
                      <th className="text-left px-5 py-3 text-xs font-medium text-neutral-600 uppercase tracking-wider">Telefone</th>
                      <th className="text-left px-5 py-3 text-xs font-medium text-neutral-600 uppercase tracking-wider">Cadastro</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((user, idx) => (
                      <tr
                        key={user.id}
                        className={`border-b border-neutral-900/50 hover:bg-white/[0.02] transition-colors ${idx % 2 === 0 ? '' : 'bg-white/[0.01]'}`}
                      >
                        <td className="px-5 py-3">
                          <div className="flex items-center gap-3">
                            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-xs font-bold text-white shrink-0">
                              {user.nome?.charAt(0)?.toUpperCase() || '?'}
                            </div>
                            <span className="text-white font-medium">{user.nome || 'â€”'}</span>
                          </div>
                        </td>
                        <td className="px-5 py-3">
                          <div className="flex items-center gap-1.5 text-neutral-400">
                            <Mail size={12} className="text-neutral-600" />
                            {user.email}
                          </div>
                        </td>
                        <td className="px-5 py-3">
                          {/* Dropdown de plano â€” salva imediatamente no Supabase */}
                          <div className="flex items-center gap-2">
                            <select
                              value={user.plano}
                              disabled={savingPlan === user.id}
                              onChange={e => updateUserPlan(user.id, e.target.value as Plan)}
                              className={`text-xs font-medium rounded-lg px-2.5 py-1.5 border outline-none cursor-pointer transition-all
                                ${PLAN_COLORS[user.plano] || 'bg-neutral-800 text-neutral-400'}
                                border-white/10 hover:border-white/20 disabled:opacity-60 disabled:cursor-not-allowed`}
                            >
                              {PLANS.map(p => (
                                <option key={p} value={p} className="bg-[#1a1a1a] text-white capitalize">{p.charAt(0).toUpperCase() + p.slice(1)}</option>
                              ))}
                            </select>
                            {savingPlan === user.id && <Loader2 size={13} className="animate-spin text-neutral-500" />}
                            {savedPlan === user.id && <Check size={13} className="text-green-400" />}
                          </div>
                        </td>
                        <td className="px-5 py-3 text-neutral-500 font-mono text-xs">{user.cpf || 'â€”'}</td>
                        <td className="px-5 py-3 text-neutral-500 text-xs">{user.content?.telefone || 'â€”'}</td>
                        <td className="px-5 py-3">
                          <div className="flex items-center gap-1.5 text-neutral-600 text-xs">
                            <Calendar size={11} />
                            {formatDate(user.created_at)}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* â”€â”€ Tab: API Keys â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
        {!loading && activeTab === 'apikeys' && (
          <div className="bg-[#0f0f0f] border border-neutral-900 rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-neutral-900 flex items-center gap-2">
              <Database size={15} className="text-neutral-500" />
              <span className="text-sm font-medium text-neutral-300">Tabela: ApiKeys</span>
              <span className="ml-auto text-xs text-neutral-600">{apiKeys.length} registros</span>
              <button
                onClick={() => setShowAddKey(v => !v)}
                className="ml-3 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-300 text-xs font-medium border border-indigo-500/30 transition-all"
              >
                {showAddKey ? 'âœ• Cancelar' : '+ Nova Chave'}
              </button>
            </div>

            {/* FormulÃ¡rio para adicionar nova chave */}
            {showAddKey && (
              <div className="px-5 py-4 border-b border-neutral-900 bg-neutral-900/30">
                <div className="flex items-end gap-3">
                  <div className="flex-shrink-0">
                    <label className="block text-xs font-medium text-neutral-500 uppercase tracking-wider mb-1.5">Provider</label>
                    <select
                      value={newKeyProvider}
                      onChange={e => setNewKeyProvider(e.target.value)}
                      className="bg-[#1a1a1a] border border-neutral-800 text-white text-sm rounded-lg px-3 py-2 outline-none focus:border-indigo-500/50"
                    >
                      <option value="browserbase">ðŸŒ Browserbase (API Key)</option>
                      <option value="browserbase_project_id">ðŸ—‚ï¸ Browserbase (Project ID)</option>
                      <option value="openrouter">ðŸ”€ OpenRouter</option>
                      <option value="anthropic">ðŸ¤– Anthropic</option>
                    </select>
                  </div>
                  <div className="flex-1">
                    <label className="block text-xs font-medium text-neutral-500 uppercase tracking-wider mb-1.5">API Key</label>
                    <input
                      value={newKeyValue}
                      onChange={e => { setNewKeyValue(e.target.value); setAddKeyError(''); }}
                      placeholder={
                        newKeyProvider === 'browserbase' ? 'bb_live_...' :
                        newKeyProvider === 'browserbase_project_id' ? 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx' :
                        'sk-...'
                      }
                      className="w-full bg-[#1a1a1a] border border-neutral-800 text-white text-sm font-mono rounded-lg px-3 py-2 outline-none focus:border-indigo-500/50"
                    />
                  </div>
                  <button
                    onClick={async () => {
                      if (!newKeyValue.trim()) { setAddKeyError('Insira a chave'); return; }
                      setAddingKey(true);
                      setAddKeyError('');
                      try {
                        const { error } = await supabase.from('ApiKeys').insert({
                          provider: newKeyProvider,
                          api_key: newKeyValue.trim(),
                          is_active: true,
                        });
                        if (error) throw error;
                        setNewKeyValue('');
                        setShowAddKey(false);
                        fetchData(); // Recarrega a lista
                      } catch (err: any) {
                        setAddKeyError(err.message || 'Erro ao salvar');
                      } finally {
                        setAddingKey(false);
                      }
                    }}
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
                {apiKeys.map(key => (
                  <div key={key.id} className="px-5 py-4 flex items-center gap-4 hover:bg-white/[0.02] transition-colors">
                    <div className="w-9 h-9 rounded-lg bg-neutral-900 border border-neutral-800 flex items-center justify-center text-lg">
                      {PROVIDER_ICONS[key.provider] || 'ðŸ”‘'}
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
                          onClick={() => toggleKeyVisibility(key.id)}
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
        )}

        {activeTab === 'chat_normal' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between mb-2">
              <div>
                <h2 className="text-sm font-semibold text-white">Slots do Chat Normal</h2>
                <p className="text-xs text-neutral-500 mt-0.5">Crie modelos do chat normal e selecione qualquer modelo do OpenRouter com preco e contexto.</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={createChatConfig}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-300 text-xs transition-colors border border-indigo-500/30"
                >
                  <Check size={12} />
                  Novo modelo
                </button>
                <button
                  onClick={fetchChatConfigs}
                  disabled={chatConfigsLoading}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-neutral-900 hover:bg-neutral-800 text-neutral-400 text-xs transition-colors border border-neutral-800 disabled:opacity-50"
                >
                  <RefreshCw size={12} className={chatConfigsLoading ? 'animate-spin' : ''} />
                  Recarregar
                </button>
              </div>
            </div>

            {chatConfigsError && (
              <div className="flex items-start gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
                <AlertTriangle size={16} className="shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium">Erro ao carregar configuracoes do chat</p>
                  <p className="text-xs text-red-400/70 mt-1">{chatConfigsError}</p>
                </div>
              </div>
            )}

            {chatConfigsLoading && (
              <div className="flex items-center justify-center py-16 text-neutral-500">
                <RefreshCw size={18} className="animate-spin mr-3" />
                Carregando slots do chat...
              </div>
            )}

            {!chatConfigsLoading && !chatConfigsError && chatConfigs.length > 0 && (
              <div className="space-y-4">
                {chatConfigs.map(config => (
                  <ChatConfigCard
                    key={config.slot_number}
                    config={config}
                    models={orModels}
                    loadingModels={modelsLoading}
                    onSave={saveChatConfig}
                  />
                ))}
              </div>
            )}

            {!chatConfigsLoading && !chatConfigsError && chatConfigs.length === 0 && (
              <div className="py-16 text-center text-neutral-600">
                <Brain size={32} className="mx-auto mb-3 opacity-30" />
                <p className="text-sm">Nenhum modelo criado para o chat normal</p>
                <p className="text-xs mt-1">Use "Novo modelo" para cadastrar o primeiro com qualquer ID do OpenRouter.</p>
              </div>
            )}
          </div>
        )}

        {/* â”€â”€ Tab: OrquestraÃ§Ã£o â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */}
        {activeTab === 'orquestracao' && (
          <div className="space-y-4">
            {/* CabeÃ§alho da aba */}
            <div className="flex items-center justify-between mb-2">
              <div>
                <h2 className="text-sm font-semibold text-white">Agentes do Backend Python</h2>
                <p className="text-xs text-neutral-500 mt-0.5">Edite model, system prompt e tools de cada agente. As alteraÃ§Ãµes entram em vigor imediatamente.</p>
              </div>
              <button
                onClick={fetchAgents}
                disabled={agentsLoading}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-neutral-900 hover:bg-neutral-800 text-neutral-400 text-xs transition-colors border border-neutral-800 disabled:opacity-50"
              >
                <RefreshCw size={12} className={agentsLoading ? 'animate-spin' : ''} />
                Recarregar
              </button>
            </div>

            {/* Erro de conexÃ£o com o backend */}
            {agentsError && (
              <div className="flex items-start gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
                <AlertTriangle size={16} className="shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium">Erro ao conectar com o backend</p>
                  <p className="text-xs text-red-400/70 mt-1">{agentsError}</p>
                  <p className="text-xs text-neutral-600 mt-2">Certifique-se que o backend Python estÃ¡ rodando em <code className="text-neutral-500">localhost:8001</code></p>
                </div>
              </div>
            )}

            {/* Loading de agentes */}
            {agentsLoading && (
              <div className="flex items-center justify-center py-16 text-neutral-500">
                <RefreshCw size={18} className="animate-spin mr-3" />
                Conectando ao backend...
              </div>
            )}

            {/* Lista de agentes agrupados por mÃ³dulo/produto */}
            {!agentsLoading && !agentsError && agents.length > 0 && (() => {
              // Agrupa { "Arcco Chat": [...], "Sistema": [...], ... }
              const byModule: Record<string, AgentConfig[]> = {};
              agents.forEach(a => {
                if (!byModule[a.module]) byModule[a.module] = [];
                byModule[a.module].push(a);
              });
              return Object.entries(byModule).map(([mod, modAgents]) => (
                <div key={mod}>
                  <div className="flex items-center gap-2 mb-3">
                    <span className={`inline-flex items-center text-xs font-medium px-2.5 py-1 rounded-full border ${MODULE_COLORS[mod] || 'bg-neutral-800 text-neutral-400 border-neutral-700'}`}>
                      {mod}
                    </span>
                    <span className="text-xs text-neutral-700">{modAgents.length} agente{modAgents.length > 1 ? 's' : ''}</span>
                  </div>
                  <div className="space-y-3 mb-6">
                    {modAgents.map(agent => (
                      <AgentCard
                        key={agent.id}
                        agent={agent}
                        models={orModels}
                        loadingModels={modelsLoading}
                        onSave={saveAgent}
                        onReset={resetAgent}
                      />
                    ))}
                  </div>
                </div>
              ));
            })()}

            {/* Estado vazio â€” backend rodando mas sem agentes */}
            {!agentsLoading && !agentsError && agents.length === 0 && (
              <div className="py-16 text-center text-neutral-600">
                <GitBranch size={32} className="mx-auto mb-3 opacity-30" />
                <p className="text-sm">Nenhum agente encontrado</p>
                <p className="text-xs mt-1">Verifique se o backend estÃ¡ rodando</p>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
};

export default AdminPage;
