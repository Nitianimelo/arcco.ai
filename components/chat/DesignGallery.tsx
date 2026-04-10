import React, { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, Monitor } from 'lucide-react';
import PresentationCard from './PresentationCard';

function extractTitle(html: string, fallback: string): string {
  return html.match(/<title[^>]*>([^<]+)<\/title>/i)?.[1]?.trim() || fallback;
}

interface DesignGalleryProps {
  designs: string[];
  isStreaming?: boolean;
  onOpenPreview?: (index: number) => void;
}

const PAGE_SIZE = 24;

const DesignGallery: React.FC<DesignGalleryProps> = ({ designs, isStreaming = false, onOpenPreview }) => {
  const [page, setPage] = useState(0);

  useEffect(() => {
    setPage(0);
  }, [designs.length]);

  const totalPages = Math.max(1, Math.ceil(designs.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages - 1);
  const pageStart = currentPage * PAGE_SIZE;
  const pageEnd = Math.min(designs.length, pageStart + PAGE_SIZE);
  const visibleDesigns = useMemo(
    () => designs.slice(pageStart, pageEnd),
    [designs, pageStart, pageEnd],
  );

  if (isStreaming) {
    return (
      <div className="my-4 rounded-2xl border border-orange-500/20 bg-[#0d0d0f] overflow-hidden shadow-lg w-full animate-pulse">
        <div className="flex items-center gap-3 px-4 py-3 bg-orange-500/8 border-b border-orange-500/20">
          <Monitor size={15} className="text-orange-300" />
          <span className="text-xs font-semibold text-orange-100">Construindo artes editaveis...</span>
        </div>
        <div className="flex items-center justify-center h-48 text-orange-300/50 text-xs">
          O agente esta desenhando multiplas composicoes visuais...
        </div>
      </div>
    );
  }

  return (
    <div className="my-4 rounded-2xl border border-[#d97706]/20 bg-[#0a0a0d] overflow-hidden shadow-xl shadow-orange-500/10 w-full">
      <div className="flex items-center gap-2 px-4 py-2.5 bg-[#111118] border-b border-orange-500/20">
        <Monitor size={14} className="text-orange-300" />
        <span className="text-xs font-semibold text-orange-100">Executor Visual</span>
        <span className="rounded-full border border-orange-500/20 bg-orange-500/8 px-2 py-0.5 text-[10px] text-orange-100">
          {designs.length === 1 ? 'Design único' : 'Múltiplos designs'}
        </span>
        <span className="ml-auto text-[10px] text-neutral-500 whitespace-nowrap">
          {designs.length} {designs.length === 1 ? 'design' : 'designs'}
        </span>
      </div>
      <div className="border-b border-[#1d1d24] px-4 py-3 text-xs text-neutral-400">
        {designs.length > PAGE_SIZE
          ? `Mostrando ${pageStart + 1}-${pageEnd} de ${designs.length} resultados desta execução.`
          : 'Todos os resultados visuais desta execução estão disponíveis abaixo.'}
      </div>
      <div className="grid grid-cols-1 gap-4 p-4 xl:grid-cols-2">
        {visibleDesigns.map((design, index) => {
          const absoluteIndex = pageStart + index;
          const designTitle = extractTitle(design, `Design ${absoluteIndex + 1}`);
          return (
            <div key={absoluteIndex} className="rounded-2xl border border-[#1d1d24] bg-[#0d0d12] p-3">
              <div className="mb-2 flex items-center gap-2">
                <div className="rounded-md border border-[#2a2a33] bg-[#13131a] px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-neutral-500">
                  #{absoluteIndex + 1}
                </div>
                <div className="min-w-0 text-[10px] uppercase tracking-[0.18em] text-neutral-500 truncate">
                  {designTitle}
                </div>
              </div>
              <PresentationCard
                html={design}
                isStreaming={false}
                onOpenPreview={() => onOpenPreview?.(absoluteIndex)}
              />
            </div>
          );
        })}
      </div>
      {designs.length > PAGE_SIZE && (
        <div className="flex items-center justify-between border-t border-[#1d1d24] px-4 py-3">
          <button
            type="button"
            onClick={() => setPage(prev => Math.max(0, prev - 1))}
            disabled={currentPage === 0}
            className="inline-flex items-center gap-1 rounded-lg border border-[#2a2a33] px-3 py-2 text-xs text-neutral-300 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <ChevronLeft size={14} />
            Anterior
          </button>
          <div className="text-xs text-neutral-500">
            Página {currentPage + 1} de {totalPages}
          </div>
          <button
            type="button"
            onClick={() => setPage(prev => Math.min(totalPages - 1, prev + 1))}
            disabled={currentPage >= totalPages - 1}
            className="inline-flex items-center gap-1 rounded-lg border border-[#2a2a33] px-3 py-2 text-xs text-neutral-300 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Próxima
            <ChevronRight size={14} />
          </button>
        </div>
      )}
    </div>
  );
};

export default DesignGallery;
