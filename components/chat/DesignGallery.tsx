import React, { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, Copy, Download, FileCode2, Monitor } from 'lucide-react';
import { useToast } from '../Toast';

function extractTitle(html: string, fallback: string): string {
  return html.match(/<title[^>]*>([^<]+)<\/title>/i)?.[1]?.trim() || fallback;
}

function normalizeHtmlDocument(src: string): string {
  if (/<!doctype html>/i.test(src) || /<html[\s>]/i.test(src)) return src;
  return `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Design</title></head><body>${src}</body></html>`;
}

interface DesignGalleryProps {
  designs: string[];
  isStreaming?: boolean;
}

const PAGE_SIZE = 24;

const DesignGallery: React.FC<DesignGalleryProps> = ({ designs, isStreaming = false }) => {
  const { showToast } = useToast();
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

  const handleCopy = async (html: string) => {
    try {
      await navigator.clipboard.writeText(normalizeHtmlDocument(html));
      showToast('HTML copiado para a área de transferência.', 'success');
    } catch (error) {
      console.error('Falha ao copiar HTML do design:', error);
      showToast('Falha ao copiar o HTML do design.', 'error');
    }
  };

  const handleDownload = (html: string, filename: string) => {
    const blob = new Blob([normalizeHtmlDocument(html)], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${filename}.html`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  if (isStreaming) {
    return (
      <div className="my-4 rounded-2xl border border-orange-500/20 bg-[#0d0d0f] overflow-hidden shadow-lg w-full animate-pulse">
        <div className="flex items-center gap-3 px-4 py-3 bg-orange-500/8 border-b border-orange-500/20">
          <Monitor size={15} className="text-orange-300" />
          <span className="text-xs font-semibold text-orange-100">Gerando artefatos HTML...</span>
        </div>
        <div className="flex items-center justify-center h-48 text-orange-300/50 text-xs">
          O agente está produzindo os arquivos visuais, sem preview embutido.
        </div>
      </div>
    );
  }

  return (
    <div className="my-4 rounded-2xl border border-[#d97706]/20 bg-[#0a0a0d] overflow-hidden shadow-xl shadow-orange-500/10 w-full">
      <div className="flex items-center gap-2 px-4 py-2.5 bg-[#111118] border-b border-orange-500/20">
        <Monitor size={14} className="text-orange-300" />
        <span className="text-xs font-semibold text-orange-100">Artefatos de Design</span>
        <span className="rounded-full border border-orange-500/20 bg-orange-500/8 px-2 py-0.5 text-[10px] text-orange-100">
          {designs.length === 1 ? 'Arquivo único' : 'Múltiplos arquivos'}
        </span>
        <span className="ml-auto text-[10px] text-neutral-500 whitespace-nowrap">
          {designs.length} {designs.length === 1 ? 'artefato' : 'artefatos'}
        </span>
      </div>
      <div className="border-b border-[#1d1d24] px-4 py-3 text-xs text-neutral-400">
        {designs.length > PAGE_SIZE
          ? `Mostrando ${pageStart + 1}-${pageEnd} de ${designs.length} arquivos HTML desta execução.`
          : 'O renderer de preview foi removido. Os HTMLs gerados estão listados abaixo para cópia e download.'}
      </div>
      <div className="grid grid-cols-1 gap-4 p-4 xl:grid-cols-2">
        {visibleDesigns.map((design, index) => {
          const absoluteIndex = pageStart + index;
          const designTitle = extractTitle(design, `Design ${absoluteIndex + 1}`);
          const safeFilename = designTitle.replace(/[^a-zA-Z0-9._\- ]/g, '_').trim() || `design_${absoluteIndex + 1}`;
          return (
            <div key={absoluteIndex} className="rounded-2xl border border-[#1d1d24] bg-[#0d0d12] p-3">
              <div className="mb-3 flex items-center gap-2">
                <div className="rounded-md border border-[#2a2a33] bg-[#13131a] px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-neutral-500">
                  #{absoluteIndex + 1}
                </div>
                <div className="min-w-0 text-[10px] uppercase tracking-[0.18em] text-neutral-500 truncate">
                  {designTitle}
                </div>
              </div>
              <div className="rounded-xl border border-[#20202a] bg-[#101017] p-4">
                <div className="flex items-start gap-3">
                  <div className="rounded-lg bg-orange-500/10 p-2 text-orange-300">
                    <FileCode2 size={16} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-neutral-100 truncate">{designTitle}</p>
                    <p className="mt-1 text-xs text-neutral-500">
                      HTML bruto preservado para a próxima refatoração do renderer.
                    </p>
                    <p className="mt-2 text-[11px] text-neutral-600">
                      {normalizeHtmlDocument(design).length.toLocaleString('pt-BR')} caracteres
                    </p>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => { void handleCopy(design); }}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-[#2a2a33] px-3 py-2 text-xs text-neutral-300 hover:bg-white/[0.04] hover:text-white"
                  >
                    <Copy size={13} />
                    Copiar HTML
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDownload(design, safeFilename)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-[#2a2a33] px-3 py-2 text-xs text-neutral-300 hover:bg-white/[0.04] hover:text-white"
                  >
                    <Download size={13} />
                    Baixar HTML
                  </button>
                </div>
              </div>
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
