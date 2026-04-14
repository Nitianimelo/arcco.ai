import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Copy, Download, Eye, Layers, Loader2, Monitor } from 'lucide-react';
import { useToast } from '../Toast';

/* ── helpers ── */

function extractTitle(html: string, fallback: string): string {
  return html.match(/<title[^>]*>([^<]+)<\/title>/i)?.[1]?.trim() || fallback;
}

function normalizeHtmlDocument(src: string): string {
  if (/<!doctype html>/i.test(src) || /<html[\s>]/i.test(src)) return src;
  return `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Design</title></head><body>${src}</body></html>`;
}

function isMultiSlide(html: string): boolean {
  const matches = html.match(/<(?:section|div)[^>]*class="[^"]*\bslide\b(?!-)[^"]*"/gi);
  return !!matches && matches.length > 1;
}

function countSlides(html: string): number {
  return (html.match(/<(?:section|div)[^>]*class="[^"]*\bslide\b(?!-)[^"]*"/gi) || []).length;
}

/** Detect the intended design viewport from CSS hints in the HTML. */
function detectViewport(html: string): { width: number; height: number } {
  const wMatch = html.match(/max-width:\s*(\d+)px/);
  const hMatch = html.match(/max-height:\s*(\d+)px/) || html.match(/min-height:\s*(\d+)px/);
  if (wMatch && hMatch) return { width: parseInt(wMatch[1]), height: parseInt(hMatch[1]) };
  // Slide-wrapper heuristic: detect explicit width/height on .slide-wrapper
  const swW = html.match(/\.slide-wrapper\s*\{[^}]*width:\s*(\d+)px/);
  const swH = html.match(/\.slide-wrapper\s*\{[^}]*height:\s*(\d+)px/);
  if (swW && swH) return { width: parseInt(swW[1]), height: parseInt(swH[1]) };
  if (isMultiSlide(html)) return { width: 1920, height: 1080 };
  return { width: 960, height: 960 };
}

/** For multi-slide thumbnails, hide all slides except the first. */
function thumbnailHtml(html: string, multiSlide: boolean): string {
  const doc = normalizeHtmlDocument(html);
  if (!multiSlide) return doc;
  return doc.replace('</head>', '<style>.slide~.slide,.slide-wrapper~.slide-wrapper,div[style*="text-align:center"]~div[style*="text-align:center"]{display:none!important}</style></head>');
}

/* ── LazyIframe: only mounts iframe when visible ── */

const LazyIframe: React.FC<{
  srcDoc: string;
  viewport: { width: number; height: number };
}> = ({ srcDoc, viewport }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const [containerWidth, setContainerWidth] = useState(0);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setVisible(true); io.disconnect(); } },
      { rootMargin: '200px' },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(entries => {
      const w = entries[0]?.contentRect.width;
      if (w) setContainerWidth(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const scale = containerWidth ? containerWidth / viewport.width : 0.35;
  const scaledHeight = viewport.height * scale;

  return (
    <div ref={containerRef} className="w-full overflow-hidden rounded-xl bg-white" style={{ height: scaledHeight || 280 }}>
      {visible ? (
        <iframe
          srcDoc={srcDoc}
          width={viewport.width}
          height={viewport.height}
          style={{
            width: `${viewport.width}px`,
            height: `${viewport.height}px`,
            transform: `scale(${scale})`,
            transformOrigin: 'top left',
            border: 0,
            pointerEvents: 'none',
            display: 'block',
          }}
          sandbox="allow-scripts"
          title="Preview"
          tabIndex={-1}
          loading="lazy"
        />
      ) : (
        <div className="flex items-center justify-center h-full bg-[#0d0d12]">
          <Loader2 size={18} className="animate-spin text-orange-400/40" />
        </div>
      )}
    </div>
  );
};

/* ── Main component ── */

interface DesignGalleryProps {
  designs: string[];
  isStreaming?: boolean;
  onOpenPreview?: (index: number) => void;
}

const PAGE_SIZE = 24;

const DesignGallery: React.FC<DesignGalleryProps> = ({ designs, isStreaming = false, onOpenPreview }) => {
  const { showToast } = useToast();
  const [page, setPage] = useState(0);

  useEffect(() => { setPage(0); }, [designs.length]);

  const totalPages = Math.max(1, Math.ceil(designs.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages - 1);
  const pageStart = currentPage * PAGE_SIZE;
  const pageEnd = Math.min(designs.length, pageStart + PAGE_SIZE);
  const visibleDesigns = useMemo(() => designs.slice(pageStart, pageEnd), [designs, pageStart, pageEnd]);

  const handleCopy = useCallback(async (html: string) => {
    try {
      await navigator.clipboard.writeText(normalizeHtmlDocument(html));
      showToast('HTML copiado para a área de transferência.', 'success');
    } catch {
      showToast('Falha ao copiar o HTML do design.', 'error');
    }
  }, [showToast]);

  const handleDownload = useCallback((html: string, filename: string) => {
    const blob = new Blob([normalizeHtmlDocument(html)], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${filename}.html`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }, []);

  if (isStreaming) {
    return (
      <div className="my-4 rounded-2xl border border-orange-500/20 bg-[#0d0d0f] overflow-hidden shadow-lg w-full animate-pulse">
        <div className="flex items-center gap-3 px-4 py-3 bg-orange-500/8 border-b border-orange-500/20">
          <Monitor size={15} className="text-orange-300" />
          <span className="text-xs font-semibold text-orange-100">Construindo artes visuais...</span>
        </div>
        <div className="flex items-center justify-center h-48 text-orange-300/50 text-xs">
          <Loader2 size={18} className="animate-spin mr-2" />
          O agente está desenhando as composições visuais...
        </div>
      </div>
    );
  }

  return (
    <div className="my-4 rounded-2xl border border-[#d97706]/20 bg-[#0a0a0d] overflow-hidden shadow-xl shadow-orange-500/10 w-full">
      {/* Header */}
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

      {/* Cards */}
      <div className="grid grid-cols-1 gap-4 p-4 xl:grid-cols-2">
        {visibleDesigns.map((design, index) => {
          const absoluteIndex = pageStart + index;
          const designTitle = extractTitle(design, `Design ${absoluteIndex + 1}`);
          const safeFilename = designTitle.replace(/[^a-zA-Z0-9._\- ]/g, '_').trim() || `design_${absoluteIndex + 1}`;
          const multiSlide = isMultiSlide(design);
          const slideNum = multiSlide ? countSlides(design) : 0;
          const viewport = detectViewport(design);
          const thumbSrc = thumbnailHtml(design, multiSlide);

          return (
            <div key={absoluteIndex} className="rounded-2xl border border-[#1d1d24] bg-[#0d0d12] p-3 group/card">
              {/* Title bar */}
              <div className="mb-2 flex items-center gap-2">
                <div className="rounded-md border border-[#2a2a33] bg-[#13131a] px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-neutral-500">
                  #{absoluteIndex + 1}
                </div>
                <div className="min-w-0 flex-1 text-[10px] uppercase tracking-[0.18em] text-neutral-500 truncate">
                  {designTitle}
                </div>
                {multiSlide && (
                  <div className="flex items-center gap-1 shrink-0 rounded-lg bg-[#1a1d24] px-2 py-1">
                    <Layers size={10} className="text-neutral-500" />
                    <span className="text-[10px] font-medium text-neutral-400">{slideNum} slides</span>
                  </div>
                )}
              </div>

              {/* Iframe preview thumbnail */}
              <div
                className="relative cursor-pointer rounded-xl overflow-hidden border border-[#20202a]"
                onClick={() => onOpenPreview?.(absoluteIndex)}
              >
                <LazyIframe srcDoc={thumbSrc} viewport={viewport} />
                {/* Hover overlay */}
                <div className="absolute inset-0 bg-black/0 group-hover/card:bg-black/30 transition-all duration-200 flex items-center justify-center">
                  <div className="opacity-0 group-hover/card:opacity-100 transition-opacity duration-200 flex items-center gap-1.5 px-4 py-2 rounded-lg bg-orange-500/90 text-white text-xs font-medium shadow-lg">
                    <Eye size={14} />
                    Visualizar
                  </div>
                </div>
              </div>

              {/* Action buttons */}
              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => { void handleCopy(design); }}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-[#2a2a33] px-3 py-1.5 text-[11px] text-neutral-400 hover:bg-white/[0.04] hover:text-neutral-200 transition-colors"
                >
                  <Copy size={12} />
                  Copiar
                </button>
                <button
                  type="button"
                  onClick={() => handleDownload(design, safeFilename)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-[#2a2a33] px-3 py-1.5 text-[11px] text-neutral-400 hover:bg-white/[0.04] hover:text-neutral-200 transition-colors"
                >
                  <Download size={12} />
                  Baixar
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Pagination */}
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
