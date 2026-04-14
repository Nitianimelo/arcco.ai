import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, Copy, Download, X } from 'lucide-react';
import { createPortal } from 'react-dom';
import { useToast } from '../Toast';

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

/**
 * Inject JS that hides all slides except the one at `index` (0-based).
 * Uses a generic approach: finds all slide-like elements and toggles display.
 */
function slideHtml(html: string, index: number): string {
  const doc = normalizeHtmlDocument(html);
  const script = `
<script>
(function(){
  var selectors = [
    'div[style*="text-align:center"]',
    '.slide-wrapper',
    'section.slide',
    'div.slide'
  ];
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
  return doc.replace('</body>', script + '</body>');
}

/* ── Component ── */

interface DesignPreviewModalProps {
  designs: string[];
  initialIndex: number;
  onClose: () => void;
}

const DesignPreviewModal: React.FC<DesignPreviewModalProps> = ({ designs, initialIndex, onClose }) => {
  const { showToast } = useToast();
  const [currentIndex, setCurrentIndex] = useState(initialIndex);
  const [slideIndex, setSlideIndex] = useState(0);

  const design = designs[currentIndex] || '';
  const title = extractTitle(design, `Design ${currentIndex + 1}`);
  const multiSlide = isMultiSlide(design);
  const slideNum = multiSlide ? countSlides(design) : 0;

  const iframeSrc = useMemo(() => {
    if (!multiSlide) return normalizeHtmlDocument(design);
    return slideHtml(design, slideIndex);
  }, [design, multiSlide, slideIndex]);

  // Reset slide index when switching designs
  useEffect(() => { setSlideIndex(0); }, [currentIndex]);

  const hasPrevDesign = currentIndex > 0;
  const hasNextDesign = currentIndex < designs.length - 1;
  const hasPrevSlide = slideIndex > 0;
  const hasNextSlide = slideIndex < slideNum - 1;

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape') { onClose(); return; }
    if (multiSlide) {
      if (e.key === 'ArrowLeft') { if (hasPrevSlide) setSlideIndex(s => s - 1); return; }
      if (e.key === 'ArrowRight') { if (hasNextSlide) setSlideIndex(s => s + 1); return; }
    }
    if (e.key === 'ArrowLeft' && hasPrevDesign) setCurrentIndex(i => i - 1);
    if (e.key === 'ArrowRight' && hasNextDesign) setCurrentIndex(i => i + 1);
  }, [onClose, multiSlide, hasPrevSlide, hasNextSlide, hasPrevDesign, hasNextDesign]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(normalizeHtmlDocument(design));
      showToast('HTML copiado.', 'success');
    } catch {
      showToast('Falha ao copiar.', 'error');
    }
  };

  const handleDownload = () => {
    const safeName = title.replace(/[^a-zA-Z0-9._\- ]/g, '_').trim() || `design_${currentIndex + 1}`;
    const blob = new Blob([normalizeHtmlDocument(design)], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${safeName}.html`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex flex-col bg-black/80 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-3 bg-[#111118]/90 border-b border-[#1d1d24] shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-sm font-medium text-neutral-100 truncate">{title}</span>
          {multiSlide && (
            <span className="rounded-full bg-orange-500/15 px-2.5 py-0.5 text-[10px] font-semibold text-orange-200">
              Slide {slideIndex + 1} de {slideNum}
            </span>
          )}
          {designs.length > 1 && (
            <span className="text-[10px] text-neutral-500">
              Design {currentIndex + 1} de {designs.length}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => { void handleCopy(); }}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[#2a2a33] px-3 py-1.5 text-[11px] text-neutral-300 hover:bg-white/[0.06] hover:text-white transition-colors"
          >
            <Copy size={12} />
            Copiar
          </button>
          <button
            type="button"
            onClick={handleDownload}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[#2a2a33] px-3 py-1.5 text-[11px] text-neutral-300 hover:bg-white/[0.06] hover:text-white transition-colors"
          >
            <Download size={12} />
            Baixar
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-neutral-400 hover:bg-white/[0.06] hover:text-white transition-colors"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Main iframe area */}
      <div className="flex-1 flex items-center justify-center p-4 md:p-8 overflow-hidden relative">
        {/* Prev design nav */}
        {!multiSlide && hasPrevDesign && (
          <button
            type="button"
            onClick={() => setCurrentIndex(i => i - 1)}
            className="absolute left-3 top-1/2 -translate-y-1/2 rounded-full bg-[#111118]/80 border border-[#2a2a33] p-2 text-neutral-300 hover:bg-white/10 hover:text-white transition-colors z-10"
          >
            <ChevronLeft size={20} />
          </button>
        )}
        {/* Prev slide nav */}
        {multiSlide && hasPrevSlide && (
          <button
            type="button"
            onClick={() => setSlideIndex(s => s - 1)}
            className="absolute left-3 top-1/2 -translate-y-1/2 rounded-full bg-[#111118]/80 border border-[#2a2a33] p-2 text-neutral-300 hover:bg-white/10 hover:text-white transition-colors z-10"
          >
            <ChevronLeft size={20} />
          </button>
        )}

        <iframe
          srcDoc={iframeSrc}
          className="w-full h-full rounded-xl border border-[#1d1d24] bg-white"
          sandbox="allow-scripts allow-same-origin"
          title={title}
          style={{ maxWidth: 1200, maxHeight: '85vh' }}
        />

        {/* Next design nav */}
        {!multiSlide && hasNextDesign && (
          <button
            type="button"
            onClick={() => setCurrentIndex(i => i + 1)}
            className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full bg-[#111118]/80 border border-[#2a2a33] p-2 text-neutral-300 hover:bg-white/10 hover:text-white transition-colors z-10"
          >
            <ChevronRight size={20} />
          </button>
        )}
        {/* Next slide nav */}
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

      {/* Slide dots */}
      {multiSlide && slideNum > 1 && (
        <div className="flex items-center justify-center gap-2 pb-4 shrink-0">
          {Array.from({ length: slideNum }, (_, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setSlideIndex(i)}
              className={`w-2 h-2 rounded-full transition-colors ${
                i === slideIndex ? 'bg-orange-400' : 'bg-neutral-600 hover:bg-neutral-400'
              }`}
            />
          ))}
        </div>
      )}
    </div>,
    document.body,
  );
};

export default DesignPreviewModal;
