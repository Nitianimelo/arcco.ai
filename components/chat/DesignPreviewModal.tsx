import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Download, X } from 'lucide-react';
import { createPortal } from 'react-dom';
import { useToast } from '../Toast';
import { agentApi } from '../../lib/api-client';
import ExportDialog from './ExportDialog';

/* ── helpers ── */

function normalizeHtmlDocument(src: string): string {
  if (/<!doctype html>/i.test(src) || /<html[\s>]/i.test(src)) return src;
  return `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Design</title></head><body>${src}</body></html>`;
}

function extractTitle(html: string, fallback: string): string {
  return html.match(/<title[^>]*>([^<]+)<\/title>/i)?.[1]?.trim() || fallback;
}

function isMultiSlide(html: string): boolean {
  const matches = html.match(/<(?:section|div)[^>]*class="[^"]*\bslide\b(?!-)[^"]*"/gi);
  return !!matches && matches.length > 1;
}

function countSlides(html: string): number {
  return (html.match(/<(?:section|div)[^>]*class="[^"]*\bslide\b(?!-)[^"]*"/gi) || []).length;
}

/** Detecta as dimensões do viewport a partir de hints no CSS do HTML gerado. */
function detectViewport(html: string): { width: number; height: number } {
  // P1: section.slide / div.slide com width e height fixos (novas skills)
  const slideBlock = html.match(/(?:section|div)\.slide\s*\{([^}]*)\}/s);
  if (slideBlock) {
    const block = slideBlock[1];
    const w = block.match(/\bwidth:\s*(\d+)px/)?.[1];
    const h = block.match(/\bheight:\s*(\d+)px/)?.[1];
    if (w && h) return { width: parseInt(w), height: parseInt(h) };
  }
  // P2: max-width / max-height
  const wMatch = html.match(/max-width:\s*(\d+)px/);
  const hMatch = html.match(/max-height:\s*(\d+)px/) || html.match(/min-height:\s*(\d+)px/);
  if (wMatch && hMatch) return { width: parseInt(wMatch[1]), height: parseInt(hMatch[1]) };
  // P3: .slide-wrapper
  const swW = html.match(/\.slide-wrapper\s*\{[^}]*width:\s*(\d+)px/);
  const swH = html.match(/\.slide-wrapper\s*\{[^}]*height:\s*(\d+)px/);
  if (swW && swH) return { width: parseInt(swW[1]), height: parseInt(swH[1]) };
  // P4: heurística
  if (isMultiSlide(html)) return { width: 1920, height: 1080 };
  return { width: 960, height: 960 };
}

/** Infere page_size ou canvas_preset para o endpoint de export com base nas dimensões. */
function inferExportParams(vp: { width: number; height: number }): { pageSize?: string; canvasPreset?: string } {
  if (vp.width === 1920 && vp.height === 1080) return { pageSize: 'widescreen' };
  if (vp.width === 794  && vp.height === 1123) return { pageSize: 'a4-portrait' };
  if (vp.width === 1080 && vp.height === 1080) return { canvasPreset: 'ig-post-square' };
  if (vp.width === 1080 && vp.height === 1920) return { canvasPreset: 'ig-story' };
  return {};
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/**
 * Injeta reset de margens + JS que oculta todos os slides exceto o de índice `index` (0-based).
 */
function slideHtml(html: string, index: number): string {
  const doc = normalizeHtmlDocument(html);
  const reset = '<style>html,body{margin:0;padding:0;overflow:hidden;}</style>';
  const script = `
<script>
(function(){
  var selectors = ['section.slide', 'div.slide', '.slide-wrapper'];
  var slides = [];
  for (var i = 0; i < selectors.length; i++) {
    var found = document.querySelectorAll(selectors[i]);
    if (found.length > 1) { slides = Array.from(found); break; }
  }
  if (slides.length < 2) return;
  for (var j = 0; j < slides.length; j++) {
    slides[j].style.display = j === ${index} ? '' : 'none';
  }
})();
</script>`;
  const withReset = doc.includes('</head>')
    ? doc.replace('</head>', reset + '</head>')
    : reset + doc;
  return withReset.replace('</body>', script + '</body>');
}

/* ── Component ── */

interface DesignPreviewModalProps {
  designs: string[];
  initialIndex: number;
  onClose: () => void;
}

const EXPORT_FORMATS = [
  { fmt: 'pdf',  label: 'PDF' },
  { fmt: 'pptx', label: 'PPTX' },
  { fmt: 'png',  label: 'PNG' },
  { fmt: 'jpeg', label: 'JPEG' },
] as const;

const DesignPreviewModal: React.FC<DesignPreviewModalProps> = ({ designs, initialIndex, onClose }) => {
  const { showToast } = useToast();

  const [currentIndex, setCurrentIndex] = useState(initialIndex);
  const [slideIndex, setSlideIndex]     = useState(0);
  const [exporting, setExporting]       = useState<string | null>(null);
  /** Abre o ExportDialog para um formato específico */
  const [exportDialog, setExportDialog] = useState<{ format: 'pdf' | 'pptx' | 'png' | 'jpeg' } | null>(null);

  // Medição do container para calcular escala
  const iframeContainerRef                   = useRef<HTMLDivElement>(null);
  const [containerSize, setContainerSize]    = useState({ w: 0, h: 0 });

  const design     = designs[currentIndex] || '';
  const title      = extractTitle(design, `Design ${currentIndex + 1}`);
  const multiSlide = isMultiSlide(design);
  const slideNum   = multiSlide ? countSlides(design) : 0;
  const viewport   = useMemo(() => detectViewport(design), [design]);

  // ResizeObserver no container central
  useEffect(() => {
    const el = iframeContainerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setContainerSize({ w: width, h: height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Escala proporcional (fit inside) com margem de 4%
  const scale    = (containerSize.w && containerSize.h)
    ? Math.min(containerSize.w / viewport.width, containerSize.h / viewport.height) * 0.96
    : 0;
  const scaledW  = Math.round(viewport.width  * scale);
  const scaledH  = Math.round(viewport.height * scale);

  const iframeSrc = useMemo(() => {
    if (!multiSlide) {
      const doc = normalizeHtmlDocument(design);
      const reset = '<style>html,body{margin:0;padding:0;overflow:hidden;}</style>';
      return doc.includes('</head>') ? doc.replace('</head>', reset + '</head>') : reset + doc;
    }
    return slideHtml(design, slideIndex);
  }, [design, multiSlide, slideIndex]);

  // Reset slide ao trocar design
  useEffect(() => { setSlideIndex(0); }, [currentIndex]);

  const hasPrevDesign = currentIndex > 0;
  const hasNextDesign = currentIndex < designs.length - 1;
  const hasPrevSlide  = slideIndex > 0;
  const hasNextSlide  = slideIndex < slideNum - 1;

  // Navegação por teclado
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') { onClose(); return; }
    if (multiSlide) {
      if (e.key === 'ArrowLeft')  { if (hasPrevSlide) setSlideIndex(s => s - 1); return; }
      if (e.key === 'ArrowRight') { if (hasNextSlide) setSlideIndex(s => s + 1); return; }
    }
    if (e.key === 'ArrowLeft'  && hasPrevDesign) setCurrentIndex(i => i - 1);
    if (e.key === 'ArrowRight' && hasNextDesign) setCurrentIndex(i => i + 1);
  }, [onClose, multiSlide, hasPrevSlide, hasNextSlide, hasPrevDesign, hasNextDesign]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Export via backend (PDF / PPTX / PNG / JPEG)
  // selectedIndices: null = todas as páginas, number[] = páginas específicas
  const handleExport = async (
    format: 'pdf' | 'pptx' | 'png' | 'jpeg',
    selectedIndices: number[] | null,
  ) => {
    setExporting(format);
    try {
      const { pageSize, canvasPreset } = inferExportParams(viewport);
      const safeName = title.replace(/[^a-zA-Z0-9._\- ]/g, '_').trim() || `design_${currentIndex + 1}`;
      const blob = await agentApi.exportHtml(
        normalizeHtmlDocument(design),
        title,
        format,
        null,             // slide_index: null (slide_indices tem prioridade)
        pageSize,
        canvasPreset,
        viewport.width,
        viewport.height,
        selectedIndices,  // slide_indices: páginas selecionadas pelo usuário
      );
      const isZip = blob.type === 'application/zip';
      const ext   = isZip ? 'zip' : (format === 'jpeg' ? 'jpg' : format);
      downloadBlob(blob, `${safeName}.${ext}`);
      showToast(`Export ${format.toUpperCase()} concluído.`, 'success');
    } catch (e: any) {
      showToast(`Falha ao exportar: ${String(e?.message || e)}`, 'error');
    } finally {
      setExporting(null);
      setExportDialog(null);
    }
  };

  const modal = createPortal(
    <div
      className="fixed inset-0 z-50 flex flex-col bg-black/85 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {/* ── Top bar ── */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-[#111118]/95 border-b border-[#1d1d24] shrink-0 gap-2 flex-wrap">
        {/* Info */}
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="text-sm font-medium text-neutral-100 truncate">{title}</span>
          {multiSlide && (
            <span className="rounded-full bg-orange-500/15 px-2.5 py-0.5 text-[10px] font-semibold text-orange-200 shrink-0">
              {slideIndex + 1} / {slideNum}
            </span>
          )}
          {designs.length > 1 && (
            <span className="text-[10px] text-neutral-500 shrink-0">
              Design {currentIndex + 1} de {designs.length}
            </span>
          )}
        </div>

        {/* Ações */}
        <div className="flex items-center gap-1.5 shrink-0 flex-wrap justify-end">
          {/* Botões de export — abrem ExportDialog */}
          {EXPORT_FORMATS.map(({ fmt, label }) => (
            <button
              key={fmt}
              type="button"
              disabled={!!exporting}
              onClick={() => setExportDialog({ format: fmt })}
              className="inline-flex items-center gap-1 rounded-lg border border-[#2a2a33] px-2.5 py-1.5 text-[11px] text-neutral-300 hover:bg-white/[0.06] hover:text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Download size={10} />
              {label}
            </button>
          ))}

          {/* Fechar */}
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-neutral-400 hover:bg-white/[0.06] hover:text-white transition-colors"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* ── Área central com iframe escalado ── */}
      <div
        ref={iframeContainerRef}
        className="flex-1 flex items-center justify-center p-6 overflow-hidden relative"
      >
        {/* Seta prev design */}
        {!multiSlide && hasPrevDesign && (
          <button
            type="button"
            onClick={() => setCurrentIndex(i => i - 1)}
            className="absolute left-3 top-1/2 -translate-y-1/2 rounded-full bg-[#111118]/80 border border-[#2a2a33] p-2 text-neutral-300 hover:bg-white/10 hover:text-white transition-colors z-10"
          >
            <ChevronLeft size={20} />
          </button>
        )}
        {/* Seta prev slide */}
        {multiSlide && hasPrevSlide && (
          <button
            type="button"
            onClick={() => setSlideIndex(s => s - 1)}
            className="absolute left-3 top-1/2 -translate-y-1/2 rounded-full bg-[#111118]/80 border border-[#2a2a33] p-2 text-neutral-300 hover:bg-white/10 hover:text-white transition-colors z-10"
          >
            <ChevronLeft size={20} />
          </button>
        )}

        {/* Bezel / frame do slide */}
        {scale > 0 && (
          <div
            style={{
              width:        scaledW,
              height:       scaledH,
              position:     'relative',
              borderRadius: 12,
              overflow:     'hidden',
              boxShadow:    '0 24px 80px rgba(0,0,0,0.75), 0 0 0 1px rgba(255,255,255,0.07)',
              flexShrink:   0,
            }}
          >
            <iframe
              key={`${currentIndex}-${slideIndex}`}
              srcDoc={iframeSrc}
              width={viewport.width}
              height={viewport.height}
              style={{
                width:           `${viewport.width}px`,
                height:          `${viewport.height}px`,
                transform:       `scale(${scale})`,
                transformOrigin: 'top left',
                border:          0,
                display:         'block',
                pointerEvents:   'none',
              }}
              sandbox="allow-scripts allow-same-origin"
              title={title}
            />
          </div>
        )}

        {/* Seta next design */}
        {!multiSlide && hasNextDesign && (
          <button
            type="button"
            onClick={() => setCurrentIndex(i => i + 1)}
            className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full bg-[#111118]/80 border border-[#2a2a33] p-2 text-neutral-300 hover:bg-white/10 hover:text-white transition-colors z-10"
          >
            <ChevronRight size={20} />
          </button>
        )}
        {/* Seta next slide */}
        {multiSlide && hasNextSlide && (
          <button
            type="button"
            onClick={() => setSlideIndex(s => s + 1)}
            className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full bg-[#111118]/80 border border-[#2a2a33] p-2 text-neutral-300 hover:bg-white/10 hover:text-white transition-colors z-10"
          >
            <ChevronRight size={20} />
          </button>
        )}
      </div>

      {/* ── Dots de slide ── */}
      {multiSlide && slideNum > 1 && (
        <div className="flex items-center justify-center gap-2 pb-4 shrink-0">
          {Array.from({ length: slideNum }, (_, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setSlideIndex(i)}
              className={`rounded-full transition-all ${
                i === slideIndex
                  ? 'w-5 h-2 bg-orange-400'
                  : 'w-2 h-2 bg-neutral-600 hover:bg-neutral-400'
              }`}
            />
          ))}
        </div>
      )}
    </div>,
    document.body,
  );

  return (
    <>
      {modal}
      {exportDialog && (
        <ExportDialog
          design={design}
          multiSlide={multiSlide}
          slideNum={slideNum}
          viewport={viewport}
          format={exportDialog.format}
          title={title}
          exporting={!!exporting}
          onClose={() => { if (!exporting) setExportDialog(null); }}
          onConfirm={(selectedIndices) => { void handleExport(exportDialog.format, selectedIndices); }}
        />
      )}
    </>
  );
};



export default DesignPreviewModal;
