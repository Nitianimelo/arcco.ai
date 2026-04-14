import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Eye, Layers, Loader2, Monitor } from 'lucide-react';

interface PresentationCardProps {
  html: string;
  isStreaming?: boolean;
  onOpenPreview?: () => void;
}

function extractTitle(html: string) {
  return html.match(/<title[^>]*>([^<]+)<\/title>/i)?.[1]?.trim() ?? 'Design gerado';
}

function ensureHtmlDocument(src: string): string {
  if (/<!doctype html>/i.test(src) || /<html[\s>]/i.test(src)) return src;
  return `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Design</title></head><body>${src}</body></html>`;
}

function isMultiSlidePresentation(html: string): boolean {
  const slideElements = html.match(/<(?:section|div)[^>]*class="[^"]*\bslide\b(?!-)[^"]*"/gi);
  return !!slideElements && slideElements.length > 1;
}

function countSlides(html: string): number {
  const slideElements = html.match(/<(?:section|div)[^>]*class="[^"]*\bslide\b(?!-)[^"]*"/gi);
  return slideElements ? slideElements.length : 0;
}

/** Detect the intended render dimensions from the design CSS. */
function detectDesignDims(html: string): { width: number; height: number } {
  const maxWMatch = html.match(/max-width:\s*(\d+)px\s*;/);
  const maxHMatch = html.match(/max-height:\s*(\d+)px\s*;/);
  if (maxWMatch && maxHMatch) {
    return { width: parseInt(maxWMatch[1]), height: parseInt(maxHMatch[1]) };
  }
  // Scrollable designs: try max-width + min-height (px only, not vh)
  const minHMatch = html.match(/min-height:\s*(\d+)px\s*;/);
  if (maxWMatch && minHMatch) {
    return { width: parseInt(maxWMatch[1]), height: parseInt(minHMatch[1]) };
  }
  return { width: 1200, height: 900 };
}

const PresentationCard: React.FC<PresentationCardProps> = ({ html, isStreaming = false, onOpenPreview }) => {
  const title = extractTitle(html);
  const isPresentation = isMultiSlidePresentation(html);
  const slideCount = isPresentation ? countSlides(html) : 0;

  const previewHtml = useMemo(() => {
    const doc = ensureHtmlDocument(html);
    if (!isPresentation) return doc;
    // Inject CSS to show only the first slide in the thumbnail
    return doc.replace('</head>', '<style>.slide~.slide{display:none!important}</style></head>');
  }, [html, isPresentation]);

  const thumbRef = useRef<HTMLDivElement>(null);
  const [thumbSize, setThumbSize] = useState({ width: 0, height: 0 });

  const designDims = useMemo(() => detectDesignDims(html), [html]);

  useEffect(() => {
    const el = thumbRef.current;
    if (!el) return;
    const observer = new ResizeObserver(entries => {
      const entry = entries[0];
      if (entry) {
        setThumbSize({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const thumbScale = useMemo(() => {
    if (!thumbSize.width) return 0.3;
    return Math.min(thumbSize.width / designDims.width, 1);
  }, [thumbSize, designDims]);

  if (isStreaming) {
    return (
      <div className="my-3 rounded-xl border border-orange-500/20 bg-[#111113] overflow-hidden shadow-lg w-full animate-pulse">
        <div className="flex items-center gap-3 px-4 py-3 border-b border-[#1e1e1e]">
          <div className="p-2 bg-orange-500/10 rounded-lg">
            <Monitor size={16} className="text-orange-400" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-neutral-100">Criando design...</p>
            <p className="text-[10px] text-neutral-500 mt-0.5">O agente esta desenhando a composicao visual</p>
          </div>
        </div>
        <div className="flex items-center justify-center h-32 bg-[#0b0b0d]">
          <Loader2 size={20} className="animate-spin text-orange-400/50" />
        </div>
      </div>
    );
  }

  // Unified thumbnail for both presentations and single-page designs
  return (
    <div className="my-3 w-full group">
      <div
        ref={thumbRef}
        className="relative h-72 overflow-hidden cursor-pointer rounded-xl border border-[#222] bg-white"
        onClick={() => onOpenPreview?.()}
      >
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: `${designDims.width}px`,
            height: `${designDims.height}px`,
            transform: `scale(${thumbScale})`,
            transformOrigin: 'top left',
          }}
        >
          <iframe
            srcDoc={previewHtml}
            style={{ width: '100%', height: '100%', border: 0 }}
            className="pointer-events-none bg-white"
            sandbox="allow-scripts allow-same-origin"
            title="Miniatura"
            tabIndex={-1}
          />
        </div>
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-all duration-200 flex items-center justify-center">
          <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center gap-1.5 px-4 py-2 rounded-lg bg-orange-500/90 text-white text-xs font-medium shadow-lg">
            <Eye size={14} />
            Visualizar
          </div>
        </div>
      </div>
      <div className="mt-2 flex items-center justify-between min-w-0">
        <div className="min-w-0">
          <p className="text-xs text-neutral-200 truncate">{title}</p>
          <p className="text-[10px] text-neutral-500">{isPresentation ? 'Deck HTML' : 'HTML bruto do agente'}</p>
        </div>
        {isPresentation && (
          <div className="flex items-center gap-1.5 shrink-0 rounded-lg bg-[#1a1d24] px-2.5 py-1.5">
            <Layers size={10} className="text-neutral-500" />
            <span className="text-[10px] font-medium text-neutral-400">{slideCount} slides</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default PresentationCard;
