import React, { useState, useEffect } from 'react';
import {
  Search,
  Globe,
  Code2,
  Monitor,
  FileText,
  Eye,
  Table2,
  Presentation,
  SearchCode,
  BarChart3,
  Image,
  Mail,
  Database,
  Zap,
  CheckCircle2,
  Plus,
  Clock,
  Bot,
  Webhook,
  Calculator,
  Calendar,
  MessageSquare,
  Loader2,
} from 'lucide-react';
import { withBackendUrl } from '../lib/backendUrl';

// ────────────────────────────────────────────────────────────
// Mapeamento de icon_name (string do backend) → componente Lucide
// Ao adicionar um novo ícone no catálogo backend, registre aqui também.
// ────────────────────────────────────────────────────────────

const ICON_MAP: Record<string, React.ElementType> = {
  Globe,
  Code2,
  Monitor,
  FileText,
  Eye,
  Table2,
  Presentation,
  SearchCode,
  BarChart3,
  Image,
  Mail,
  Database,
  Zap,
  Bot,
  Webhook,
  Calculator,
  Calendar,
  MessageSquare,
  Search,
};

function resolveIcon(icon_name: string): React.ElementType {
  return ICON_MAP[icon_name] ?? Zap;
}

// ────────────────────────────────────────────────────────────
// Tipo que vem da API (espelha catalog.py do backend)
// ────────────────────────────────────────────────────────────

export interface ToolDefinition {
  id: string;
  name: string;
  description: string;
  icon: React.ElementType;  // resolvido localmente a partir de icon_name
  category: string;
  status: 'available' | 'coming_soon';
  color: string;
}

interface ToolFromAPI {
  id: string;
  name: string;
  description: string;
  icon_name: string;
  category: string;
  status: 'available' | 'coming_soon';
  color: string;
}

// Fallback local caso a API esteja fora do ar
const FALLBACK_TOOLS: ToolDefinition[] = [
  {
    id: 'spy_pages',
    name: 'Spy Pages',
    description: 'Analise tráfego, engajamento, países e concorrentes de qualquer site com dados do SimilarWeb.',
    icon: Eye,
    category: 'Análise',
    status: 'available',
    color: 'from-violet-500/20 to-violet-600/10 border-violet-500/30',
  },
];

export let ALL_TOOLS: ToolDefinition[] = FALLBACK_TOOLS;

const STORAGE_KEY = 'arcco_selected_tools';

export function getSelectedTools(): string[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
  } catch {
    return [];
  }
}

function saveSelectedTools(ids: string[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
}

// ────────────────────────────────────────────────────────────
// Componente principal
// ────────────────────────────────────────────────────────────

const CATEGORIES = ['Todas', 'Análise'] as const;
type FilterCategory = typeof CATEGORIES[number];

const ToolsStorePage: React.FC = () => {
  const [selectedIds, setSelectedIds] = useState<string[]>(() => getSelectedTools());
  const [activeCategory, setActiveCategory] = useState<FilterCategory>('Todas');
  const [searchQuery, setSearchQuery] = useState('');
  const [tools, setTools] = useState<ToolDefinition[]>(FALLBACK_TOOLS);
  const [loadingCatalog, setLoadingCatalog] = useState(true);

  // Busca catálogo do backend (fonte da verdade)
  useEffect(() => {
    fetch(withBackendUrl('/api/agent/tools'))
      .then(r => r.json())
      .then((data: ToolFromAPI[]) => {
        const resolved: ToolDefinition[] = data.map(t => ({
          ...t,
          icon: resolveIcon(t.icon_name),
        }));
        setTools(resolved);
        ALL_TOOLS = resolved; // atualiza referência global usada por MyToolsPage
      })
      .catch(() => { /* mantém fallback */ })
      .finally(() => setLoadingCatalog(false));
  }, []);

  useEffect(() => {
    saveSelectedTools(selectedIds);
  }, [selectedIds]);

  const toggleTool = (id: string) => {
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const filtered = tools.filter(tool => {
    const matchCategory = activeCategory === 'Todas' || tool.category === activeCategory;
    const matchSearch =
      searchQuery.trim() === '' ||
      tool.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      tool.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchCategory && matchSearch;
  });

  return (
    <div className="h-full flex flex-col overflow-hidden" style={{ backgroundColor: 'var(--bg-elevated)' }}>

      {/* Header */}
      <div className="px-8 pt-8 pb-6 border-b border-[#262629] shrink-0">
        <div className="flex items-start justify-between mb-5">
          <div>
            <h1 className="text-2xl font-bold text-white">Loja de Tools</h1>
            <p className="text-sm text-neutral-500 mt-1">
              Adicione capacidades especiais ao seu agente de IA.
            </p>
          </div>
          <div className="text-right flex flex-col items-end gap-1">
            <div className="flex items-center gap-2">
              {loadingCatalog && <Loader2 size={14} className="animate-spin text-neutral-500" />}
              <span className="text-2xl font-bold text-indigo-400">{selectedIds.length}</span>
            </div>
            <p className="text-xs text-neutral-500">tools ativas</p>
          </div>
        </div>

        {/* Search */}
        <div className="relative mb-4">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Buscar tools..."
            className="w-full bg-[#1a1a1d] border border-[#313134] text-neutral-200 text-sm rounded-xl pl-9 pr-4 py-2.5 outline-none focus:border-indigo-500/50 transition-colors"
          />
        </div>

        {/* Filtros de categoria */}
        <div className="flex gap-2 flex-wrap">
          {CATEGORIES.map(cat => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`px-3 py-1.5 text-xs rounded-lg font-medium transition-colors ${
                activeCategory === cat
                  ? 'bg-indigo-600 text-white'
                  : 'bg-[#1a1a1d] text-neutral-400 hover:text-white hover:bg-[#222224] border border-[#313134]'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-y-auto px-8 py-6">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-neutral-500">
            <Search size={32} className="mb-3 opacity-30" />
            <p className="text-sm">Nenhuma tool encontrada</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map(tool => {
              const isSelected = selectedIds.includes(tool.id);
              const isAvailable = tool.status === 'available';

              return (
                <div
                  key={tool.id}
                  className={`relative flex flex-col rounded-2xl border p-5 transition-all duration-200 bg-gradient-to-br ${tool.color}
                    ${isAvailable
                      ? isSelected
                        ? 'shadow-[0_0_20px_rgba(99,102,241,0.15)]'
                        : 'hover:shadow-md cursor-pointer'
                      : 'opacity-60 cursor-not-allowed'
                    }`}
                >
                  {/* Badge "Em breve" */}
                  {!isAvailable && (
                    <div className="absolute top-3 right-3 flex items-center gap-1 px-2 py-0.5 bg-neutral-800/80 rounded-full">
                      <Clock size={11} className="text-neutral-400" />
                      <span className="text-[10px] text-neutral-400 font-medium">Em breve</span>
                    </div>
                  )}

                  {/* Ícone + nome */}
                  <div className="flex items-start gap-3 mb-3">
                    <div className="p-2 rounded-xl bg-white/[0.06] border border-white/[0.08]">
                      <tool.icon size={20} className="text-white/80" />
                    </div>
                    <div className="flex-1 min-w-0 pt-0.5">
                      <h3 className="text-sm font-semibold text-white truncate">{tool.name}</h3>
                      <span className="text-[10px] text-neutral-500 font-medium uppercase tracking-wider">
                        {tool.category}
                      </span>
                    </div>
                  </div>

                  {/* Descrição */}
                  <p className="text-xs text-neutral-400 leading-relaxed flex-1 mb-4">
                    {tool.description}
                  </p>

                  {/* Botão */}
                  {isAvailable && (
                    <button
                      onClick={() => toggleTool(tool.id)}
                      className={`w-full flex items-center justify-center gap-2 py-2 rounded-xl text-xs font-semibold transition-all ${
                        isSelected
                          ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/40 hover:bg-red-500/10 hover:text-red-400 hover:border-red-500/40'
                          : 'bg-white/[0.06] text-neutral-300 border border-white/[0.08] hover:bg-indigo-600/20 hover:text-indigo-300 hover:border-indigo-500/40'
                      }`}
                    >
                      {isSelected ? (
                        <>
                          <CheckCircle2 size={14} />
                          Adicionada — clique para remover
                        </>
                      ) : (
                        <>
                          <Plus size={14} />
                          Adicionar
                        </>
                      )}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default ToolsStorePage;
