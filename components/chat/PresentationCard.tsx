import React, { useRef } from 'react';
import { Eye, Loader2, Monitor, Layers } from 'lucide-react';

interface PresentationCardProps {
  html: string;
  isStreaming?: boolean;
  onOpenPreview?: () => void;
}

function extractTitle(html: string) {
  return html.match(/<title[^>]*>([^<]+)<\/title>/i)?.[1] ?? 'Design gerado';
}

/** Detect if the HTML contains multiple slides (presentation vs single design) */
function isMultiSlidePresentation(html: string): boolean {
  // Match elements with class containing "slide" as a standalone word
  // Covers: class="slide", class="slide active", class="slide-container"
  const slideElements = html.match(/<(?:section|div)[^>]*class="[^"]*\bslide\b[^"]*"/gi);
  return !!slideElements && slideElements.length > 1;
}

function countSlides(html: string): number {
  const slideElements = html.match(/<(?:section|div)[^>]*class="[^"]*\bslide\b[^"]*"/gi);
  return slideElements ? slideElements.length : 0;
}

/** For single designs: force 1:1 square thumbnail */
function normalizeSquareThumbnail(src: string) {
  const html = /<!doctype html>/i.test(src) || /<html[\s>]/i.test(src)
    ? src
    : `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Design</title></head><body>${src}</body></html>`;

  const parser = new DOMParser();
  const doc = parser.parseFromString(html, 'text/html');

  if (!doc.head.querySelector('meta[charset]')) {
    const meta = doc.createElement('meta');
    meta.setAttribute('charset', 'UTF-8');
    doc.head.prepend(meta);
  }

  let style = doc.getElementById('arcco-design-thumb-style');
  if (!style) {
    style = doc.createElement('style');
    style.id = 'arcco-design-thumb-style';
    doc.head.appendChild(style);
  }

  style.textContent = `
    html, body { margin: 0; padding: 0; min-height: 100%; background: transparent; }
    body {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0;
      box-sizing: border-box;
    }
    body > * { box-sizing: border-box; }
    #arcco-design-stage {
      width: min(100%, 1080px);
      height: 1080px;
      overflow: hidden;
      background: transparent;
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    #arcco-design-content {
      width: 100%;
      height: 100%;
      padding: 0;
      box-sizing: border-box;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }
    #arcco-design-content > * { max-width: 100%; max-height: 100%; box-sizing: border-box; margin: 0 auto; }
  `;

  let stage = doc.getElementById('arcco-design-stage');
  if (!stage) {
    stage = doc.createElement('div');
    stage.id = 'arcco-design-stage';
    while (doc.body.firstChild) stage.appendChild(doc.body.firstChild);
    doc.body.appendChild(stage);
  }

  let content = doc.getElementById('arcco-design-content');
  if (!content) {
    content = doc.createElement('div');
    content.id = 'arcco-design-content';
    while (stage.firstChild) content.appendChild(stage.firstChild);
    stage.appendChild(content);
  }

  Array.from(content.children).forEach((child) => {
    if (child instanceof HTMLElement) {
      child.style.maxWidth = '100%';
      child.style.maxHeight = '100%';
    }
  });

  return '<!DOCTYPE html>\n' + doc.documentElement.outerHTML;
}

/** For presentations: show only the first slide at 16:9, hide nav controls */
function normalizePresentationThumbnail(html: string): string {
  const overrideCSS = `<style id="arcco-pres-thumb">
    /* Hide all slides, then show only the first */
    .slide, .slide-container { display: none !important; }
    .slide:first-of-type, .slide-container:first-of-type {
      display: flex !important;
      opacity: 1 !important;
      min-height: 100vh !important;
    }
    /* Hide navigation controls */
    .nav-btn, .slide-nav, .slide-counter, .slide-navigation,
    [class*="nav-btn"], [class*="slide-nav"], [class*="slide-counter"],
    button[onclick*="slide"], .navigation { display: none !important; }
    /* Clean body */
    body { margin: 0; overflow: hidden; }
  </style>`;

  // Remove any JS that could interfere with slide visibility
  const noJS = html.replace(/<script(?!.*src=["']https?:\/\/cdn)[\s\S]*?<\/script>/gi, '');

  if (noJS.includes('</head>')) {
    return noJS.replace('</head>', overrideCSS + '</head>');
  }
  return overrideCSS + noJS;
}

const PresentationCard: React.FC<PresentationCardProps> = ({ html, isStreaming = false, onOpenPreview }) => {
  const thumbRef = useRef<HTMLIFrameElement>(null);
  const title = extractTitle(html);
  const isPresentation = isMultiSlidePresentation(html);
  const slideCount = isPresentation ? countSlides(html) : 0;
  const thumbnailHtml = isPresentation
    ? normalizePresentationThumbnail(html)
    : normalizeSquareThumbnail(html);

  if (isStreaming) {
    return (
      <div className="my-3 rounded-xl border border-orange-500/20 bg-[#111113] overflow-hidden shadow-lg w-full max-w-sm animate-pulse">
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

  // Presentation: 16:9 card. Single design: square card.
  const aspectClass = isPresentation ? 'aspect-video' : 'aspect-square';

  return (
    <div className="my-3 w-full max-w-sm group">
      <div
        className={`relative ${aspectClass} overflow-hidden cursor-pointer rounded-xl border border-[#222]`}
        onClick={() => onOpenPreview?.()}
      >
        <iframe
          ref={thumbRef}
          srcDoc={thumbnailHtml}
          className="w-full h-full border-0 pointer-events-none bg-transparent"
          sandbox="allow-scripts allow-same-origin"
          title="Miniatura"
          tabIndex={-1}
        />
        {/* Slide count badge */}
        {isPresentation && slideCount > 0 && (
          <div className="absolute top-2 right-2 flex items-center gap-1 px-2 py-1 rounded-md bg-black/60 backdrop-blur-sm text-white text-[10px] font-medium">
            <Layers size={10} />
            {slideCount} slides
          </div>
        )}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-all duration-200 flex items-center justify-center">
          <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center gap-1.5 px-4 py-2 rounded-lg bg-orange-500/90 text-white text-xs font-medium shadow-lg">
            <Eye size={14} />
            Visualizar
          </div>
        </div>
      </div>
      <div className="mt-2 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs text-neutral-200 truncate">{title}</p>
          <p className="text-[10px] text-neutral-500">
            {isPresentation ? `Apresentacao com ${slideCount} slides` : 'Clique para abrir e editar'}
          </p>
        </div>
        <button
          onClick={() => onOpenPreview?.()}
          className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-orange-600 hover:bg-orange-500 text-white text-xs font-medium transition-colors"
        >
          <Eye size={14} />
          Abrir
        </button>
      </div>
    </div>
  );
};

export default PresentationCard;
