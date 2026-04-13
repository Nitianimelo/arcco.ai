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

const PresentationCard: React.FC<PresentationCardProps> = ({ html, isStreaming = false, onOpenPreview }) => {
  const title = extractTitle(html);
  const isPresentation = isMultiSlidePresentation(html);
  const slideCount = isPresentation ? countSlides(html) : 0;
  const previewHtml = ensureHtmlDocument(html);

  const thumbRef = useRef<HTMLDivElement>(null);
  const [thumbSize, setThumbSize] = useState({ width: 0, height: 0 });

  const designDims = useMemo(() => {
    const maxWMatch = html.match(/max-width:\s*(\d+)px\s*;/);
    const maxHMatch = html.match(/max-height:\s*(\d+)px\s*;/);
    if (maxWMatch && maxHMatch) {
      return { width: parseInt(maxWMatch[1]), height: parseInt(maxHMatch[1]) };
    }
    return { width: 1920, height: 1080 };
  }, [html]);

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
    if (!thumbSize.width || !thumbSize.height) return 0.3;
    const scaleX = thumbSize.width / designDims.width;
    const scaleY = thumbSize.height / designDims.height;
    return Math.min(scaleX, scaleY);
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

  if (isPresentation) {
    return (
      <div className="my-3 w-full">
        <button
          type="button"
          onClick={() => onOpenPreview?.()}
          className="group w-full rounded-2xl border border-[#222833] bg-[linear-gradient(180deg,#11151d_0%,#0d1016_100%)] p-5 text-left transition-colors hover:border-[#384152]"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] text-neutral-500">
                <Layers size={12} />
                Deck HTML
              </div>
              <h4 className="mt-3 truncate text-sm font-medium text-neutral-100">{title}</h4>
              <p className="mt-2 max-w-xl text-xs leading-5 text-neutral-400">
                O preview expandido renderiza o HTML bruto do deck e permite paginação por slide.
              </p>
            </div>
            <div className="shrink-0 rounded-xl border border-[#2c3341] bg-[#0a0d14] px-3 py-2 text-right">
              <div className="text-[10px] uppercase tracking-[0.18em] text-neutral-500">Slides</div>
              <div className="mt-1 text-lg font-semibold text-neutral-100">{slideCount}</div>
            </div>
          </div>

          <div className="mt-4 flex items-center justify-between rounded-xl border border-[#1d2230] bg-[#0a0d14] px-4 py-3">
            <div className="text-xs text-neutral-400">Abrir renderer bruto</div>
            <div className="flex items-center gap-1.5 rounded-lg bg-orange-500/90 px-3 py-2 text-xs font-medium text-white shadow-lg transition-opacity group-hover:opacity-100">
              <Eye size={14} />
              Visualizar
            </div>
          </div>
        </button>
      </div>
    );
  }

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
            top: '50%',
            left: '50%',
            width: `${designDims.width}px`,
            height: `${designDims.height}px`,
            transform: `translate(-50%, -50%) scale(${thumbScale})`,
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
      <div className="mt-2 min-w-0">
        <p className="text-xs text-neutral-200 truncate">{title}</p>
        <p className="text-[10px] text-neutral-500">HTML bruto do agente</p>
      </div>
    </div>
  );
};

export default PresentationCard;
