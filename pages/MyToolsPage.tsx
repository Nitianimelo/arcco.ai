import React, { useState, useEffect } from 'react';
import { Wrench, Store, X, CheckCircle2 } from 'lucide-react';
import { ALL_TOOLS, getSelectedTools } from './ToolsStorePage';

const STORAGE_KEY = 'arcco_selected_tools';

function saveSelectedTools(ids: string[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
}

interface MyToolsPageProps {
  onNavigateToStore?: () => void;
}

const MyToolsPage: React.FC<MyToolsPageProps> = ({ onNavigateToStore }) => {
  const [selectedIds, setSelectedIds] = useState<string[]>(() => getSelectedTools());

  // Sincroniza caso localStorage mude em outra aba
  useEffect(() => {
    const handler = () => setSelectedIds(getSelectedTools());
    window.addEventListener('storage', handler);
    return () => window.removeEventListener('storage', handler);
  }, []);

  const removeTool = (id: string) => {
    const updated = selectedIds.filter(x => x !== id);
    setSelectedIds(updated);
    saveSelectedTools(updated);
  };

  const myTools = ALL_TOOLS.filter(t => selectedIds.includes(t.id));

  return (
    <div className="h-full flex flex-col overflow-hidden" style={{ backgroundColor: 'var(--bg-elevated)' }}>

      {/* Header */}
      <div className="px-8 pt-8 pb-6 border-b border-[#262629] shrink-0">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Minhas Tools</h1>
            <p className="text-sm text-neutral-500 mt-1">
              Tools que você adicionou ao seu agente.
            </p>
          </div>
          <button
            onClick={onNavigateToStore}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-xl transition-colors"
          >
            <Store size={15} />
            Explorar Loja
          </button>
        </div>
      </div>

      {/* Conteúdo */}
      <div className="flex-1 overflow-y-auto px-8 py-6">
        {myTools.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 gap-4">
            <div className="p-5 rounded-2xl bg-[#1a1a1d] border border-[#313134]">
              <Wrench size={32} className="text-neutral-600" />
            </div>
            <div className="text-center">
              <p className="text-neutral-400 font-medium">Nenhuma tool adicionada ainda</p>
              <p className="text-sm text-neutral-600 mt-1">
                Acesse a Loja para adicionar capacidades ao seu agente.
              </p>
            </div>
            <button
              onClick={onNavigateToStore}
              className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold rounded-xl transition-colors"
            >
              <Store size={15} />
              Ir para a Loja
            </button>
          </div>
        ) : (
          <>
            <p className="text-xs text-neutral-600 mb-4 uppercase tracking-wider font-medium">
              {myTools.length} tool{myTools.length !== 1 ? 's' : ''} ativa{myTools.length !== 1 ? 's' : ''}
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {myTools.map(tool => (
                <div
                  key={tool.id}
                  className={`relative flex flex-col rounded-2xl border p-5 bg-gradient-to-br ${tool.color} transition-all duration-200`}
                >
                  {/* Remover */}
                  <button
                    onClick={() => removeTool(tool.id)}
                    title="Remover tool"
                    className="absolute top-3 right-3 p-1 rounded-lg text-neutral-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                  >
                    <X size={14} />
                  </button>

                  {/* Ícone + nome */}
                  <div className="flex items-start gap-3 mb-3 pr-6">
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

                  {/* Status ativa */}
                  <div className="flex items-center gap-1.5 text-xs text-indigo-300">
                    <CheckCircle2 size={13} />
                    <span>Ativa</span>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default MyToolsPage;
