import React, { useEffect, useRef, useState } from 'react';
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Download,
  FileImage,
  FileText,
  Image,
  Layers,
  Loader2,
  Maximize2,
  Minimize2,
  Monitor,
  Presentation,
  X,
} from 'lucide-react';
import {
  CANVAS_PRESETS,
  type CanvasPreset,
  inferCanvasPreset,
  normalizeDesignHtml,
} from '../../lib/designContract';

// ────────────────────────────────────────────────────────────────
// Types
// ────────────────────────────────────────────────────────────────

interface DesignPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  designs: string[];
  initialIndex?: number;
}

type ExportFormat = 'pdf' | 'pptx' | 'png' | 'jpeg';
type ResolutionOption = 'hd-720' | 'hd-1080';
type SlideSelection = 'all' | 'current';

// ────────────────────────────────────────────────────────────────
// Constants
// ────────────────────────────────────────────────────────────────

const EXPORT_BUTTONS: { fmt: ExportFormat; label: string; icon: React.ReactNode }[] = [
  { fmt: 'png', label: 'PNG', icon: <Image size={14} /> },
  { fmt: 'jpeg', label: 'JPEG', icon: <FileImage size={14} /> },
  { fmt: 'pdf', label: 'PDF', icon: <FileText size={14} /> },
  { fmt: 'pptx', label: 'PPTX', icon: <Presentation size={14} /> },
];

const RESOLUTION_OPTIONS: { value: ResolutionOption; label: string }[] = [
  { value: 'hd-720', label: '1280 x 720 (HD)' },
  { value: 'hd-1080', label: '1920 x 1080 (Full HD)' },
];

function describeResolution(format: ExportFormat, resolution: ResolutionOption) {
  if (format !== 'png' && format !== 'jpeg') return 'Vetorial / documento';
  return resolution === 'hd-1080' ? '1920 x 1080' : '1280 x 720';
}

// ────────────────────────────────────────────────────────────────
// Detection utilities
// ────────────────────────────────────────────────────────────────

function isMultiSlidePresentation(html: string): boolean {
  const slideElements = html.match(/<(?:section|div)[^>]*class="[^"]*\bslide\b[^"]*"/gi);
  return !!slideElements && slideElements.length > 1;
}

function countSlidesFromHtml(html: string): number {
  const slideElements = html.match(/<(?:section|div)[^>]*class="[^"]*\bslide\b[^"]*"/gi);
  return slideElements ? slideElements.length : 0;
}

// ────────────────────────────────────────────────────────────────
// Utility functions
// ────────────────────────────────────────────────────────────────

function extractTitle(html: string) {
  return html.match(/<title[^>]*>([^<]+)<\/title>/i)?.[1] ?? 'Design';
}

function ensureHtmlDocument(src: string): string {
  if (/<!doctype html>/i.test(src) || /<html[\s>]/i.test(src)) return src;
  return `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Design</title></head><body>${src}</body></html>`;
}

async function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

interface ExportOptions {
  slide_index?: number;
  page_size?: string;
  resolution?: string;
  canvas_preset?: CanvasPreset;
}

async function downloadHtmlExport(html: string, title: string, format: ExportFormat, opts?: ExportOptions) {
  const res = await fetch('/api/agent/export-html', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ html, title, format, ...opts }),
  });
  if (!res.ok) throw new Error(await res.text());
  const contentType = res.headers.get('content-type') || '';
  const blob = await res.blob();
  // Se for ZIP (multi-imagem), usar extensão .zip
  const ext = contentType.includes('application/zip') ? 'zip' : format;
  const safeName = title.replace(/[^a-zA-Z0-9._\- ]/g, '_').slice(0, 50);
  await downloadBlob(blob, `${safeName}.${ext}`);
}

// ────────────────────────────────────────────────────────────────
// Presentation iframe utilities
// ────────────────────────────────────────────────────────────────

/** Inject navigation script into presentation HTML for postMessage-based control */
function injectPresentationNav(html: string): string {
  const navScript = `<script>
    (function() {
      var slides = [];
      var currentSlide = 0;

      function findSlides() {
        slides = Array.from(document.querySelectorAll('.slide, .slide-container'));
        if (slides.length === 0) return;
        // Show first slide, hide rest
        goToSlide(0);
      }

      function goToSlide(index) {
        if (index < 0 || index >= slides.length) return;
        currentSlide = index;
        slides.forEach(function(s, i) {
          s.style.display = i === index ? '' : 'none';
          s.style.opacity = i === index ? '1' : '0';
          s.classList.toggle('active', i === index);
        });
        // Report state to parent
        window.parent.postMessage({
          type: 'arcco_slide_state',
          current: currentSlide,
          total: slides.length
        }, '*');
      }

      window.addEventListener('message', function(e) {
        if (!e.data || !e.data.type) return;
        if (e.data.type === 'arcco_go_to_slide') {
          goToSlide(e.data.index);
        }
        if (e.data.type === 'arcco_get_state') {
          window.parent.postMessage({
            type: 'arcco_slide_state',
            current: currentSlide,
            total: slides.length
          }, '*');
        }
      });

      // Init after DOM + resources load
      if (document.readyState === 'complete') {
        setTimeout(findSlides, 200);
      } else {
        window.addEventListener('load', function() { setTimeout(findSlides, 200); });
      }

      // Keyboard navigation inside iframe
      document.addEventListener('keydown', function(e) {
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
          e.preventDefault();
          goToSlide(currentSlide + 1);
        } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
          e.preventDefault();
          goToSlide(currentSlide - 1);
        }
      });
    })();
  </script>`;

  // Remove existing navigation scripts that might conflict
  let cleaned = html.replace(/<script(?!.*src=["']https?:\/\/)[\s\S]*?<\/script>/gi, '');

  // Inject before </body>
  if (cleaned.includes('</body>')) {
    return cleaned.replace('</body>', navScript + '</body>');
  }
  return cleaned + navScript;
}

// ────────────────────────────────────────────────────────────────
// Main Component
// ────────────────────────────────────────────────────────────────

const getPresetAspect = (preset: CanvasPreset): string => {
  const spec = CANVAS_PRESETS[preset];
  return `${spec.width} / ${spec.height}`;
};

type FrameKind = 'mobile' | 'tablet' | 'desktop';

const getFrameKind = (preset: CanvasPreset): FrameKind => {
  if (preset === 'story' || preset === 'instagram-square' || preset === 'instagram-portrait') return 'mobile';
  if (preset === 'a4-portrait' || preset === 'a4-landscape') return 'tablet';
  return 'desktop';
};

const renderFrameShell = (kind: FrameKind, children: React.ReactNode) => {
  if (kind === 'mobile') {
    return (
      <div className="relative rounded-[2.2rem] border border-[#2a2d33] bg-[#050506] p-3 shadow-[0_30px_90px_rgba(0,0,0,0.55)]">
        <div className="pointer-events-none absolute left-1/2 top-2 h-1.5 w-20 -translate-x-1/2 rounded-full bg-[#15171b]" />
        <div className="overflow-hidden rounded-[1.6rem] border border-[#17191d] bg-[#09090c]">
          {children}
        </div>
      </div>
    );
  }

  if (kind === 'tablet') {
    return (
      <div className="relative rounded-[2rem] border border-[#2a2d33] bg-[#050506] p-4 shadow-[0_30px_90px_rgba(0,0,0,0.48)]">
        <div className="overflow-hidden rounded-[1.35rem] border border-[#17191d] bg-[#09090c]">
          {children}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-[1.4rem] border border-[#2a2d33] bg-[#050506] p-3 shadow-[0_30px_90px_rgba(0,0,0,0.42)]">
      <div className="mb-3 flex items-center gap-2 px-2">
        <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
        <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
        <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
      </div>
      <div className="overflow-hidden rounded-[0.9rem] border border-[#17191d] bg-[#09090c]">
        {children}
      </div>
    </div>
  );
};

const DesignPreviewModal: React.FC<DesignPreviewModalProps> = ({ isOpen, onClose, designs, initialIndex = 0 }) => {
  const [activeIndex, setActiveIndex] = useState(initialIndex);
  const [isLoading, setIsLoading] = useState(true);
  const [loadingFmt, setLoadingFmt] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement>(null);

  // Presentation mode state
  const [currentSlide, setCurrentSlide] = useState(0);
  const [totalSlides, setTotalSlides] = useState(0);
  const presIframeRef = useRef<HTMLIFrameElement>(null);
  const singleIframeRef = useRef<HTMLIFrameElement>(null);

  const [selectedFmt, setSelectedFmt] = useState<ExportFormat>('png');
  const [slideSelection, setSlideSelection] = useState<SlideSelection>('all');
  const [resolution, setResolution] = useState<ResolutionOption>('hd-720');
  const [previewPreset, setPreviewPreset] = useState<CanvasPreset>('instagram-square');

  const currentHtml = designs[activeIndex] || '';
  const title = extractTitle(currentHtml);
  const isPresentationMode = isMultiSlidePresentation(currentHtml);
  const normalizedPreviewHtml = normalizeDesignHtml(currentHtml, previewPreset);
  const previewPresetSpec = CANVAS_PRESETS[previewPreset];
  const previewAspect = getPresetAspect(previewPreset);
  const frameKind = getFrameKind(previewPreset);

  // ── Presentation: listen for messages from iframe ──
  useEffect(() => {
    if (!isOpen || !isPresentationMode) return;
    const handler = (e: MessageEvent) => {
      if (e.data?.type === 'arcco_slide_state') {
        setCurrentSlide(e.data.current);
        setTotalSlides(e.data.total);
        setIsLoading(false);
      }
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, [isOpen, isPresentationMode]);

  // ── Presentation: init iframe ──
  useEffect(() => {
    if (!isOpen || !isPresentationMode) return;
    setIsLoading(true);
    setCurrentSlide(0);
    setTotalSlides(countSlidesFromHtml(currentHtml));
    // iframe loads via srcdoc, nav script auto-inits and sends state
    const t = setTimeout(() => {
      presIframeRef.current?.contentWindow?.postMessage({ type: 'arcco_get_state' }, '*');
      // Fallback: if script didn't respond, stop loading after 3s
      setTimeout(() => setIsLoading(false), 3000);
    }, 1000);
    return () => clearTimeout(t);
  }, [isOpen, activeIndex, isPresentationMode, currentHtml]);

  useEffect(() => {
    if (!isOpen) return;
    const inferred = inferCanvasPreset(currentHtml);
    const fallbackPreset =
      isPresentationMode && inferred === 'banner'
        ? 'widescreen'
        : inferred;
    setPreviewPreset(fallbackPreset);
    setIsLoading(true);
  }, [isOpen, isPresentationMode, currentHtml, activeIndex]);

  const goToSlide = (index: number) => {
    presIframeRef.current?.contentWindow?.postMessage({ type: 'arcco_go_to_slide', index }, '*');
  };

  // ── Escape to close ──
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      // Presentation keyboard nav (when focus is on modal, not iframe)
      if (isPresentationMode) {
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') goToSlide(currentSlide + 1);
        if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') goToSlide(currentSlide - 1);
      }
    };
    document.addEventListener('keydown', handler);
    document.body.style.overflow = 'hidden';
    return () => { document.removeEventListener('keydown', handler); document.body.style.overflow = ''; };
  }, [isOpen, onClose, isPresentationMode, currentSlide]);

  // ── Close export menu on outside click ──
  useEffect(() => {
    if (!showExportMenu) return;
    const handler = (e: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target as Node)) {
        setShowExportMenu(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showExportMenu]);

  const handleExport = async (fmt: ExportFormat) => {
    setLoadingFmt(fmt);
    setError(null);
    setShowExportMenu(false);
    try {
      const opts: ExportOptions = { canvas_preset: previewPreset };
      if (isPresentationMode) {
        if (slideSelection === 'current') opts.slide_index = currentSlide;
        if (fmt === 'png' || fmt === 'jpeg') opts.resolution = resolution;
        await downloadHtmlExport(normalizedPreviewHtml, title, fmt, opts);
      } else {
        if (fmt === 'png' || fmt === 'jpeg') opts.resolution = resolution;
        await downloadHtmlExport(normalizedPreviewHtml, title, fmt, opts);
      }
    } catch (e: any) {
      setError(`Erro ao exportar: ${e.message}`);
    } finally {
      setLoadingFmt(null);
    }
  };

  const switchDesign = (index: number) => {
    setActiveIndex(index);
  };

  // ── Render ──
  if (!isOpen) return null;

  const modalSize = isFullscreen ? 'inset-0 rounded-none' : 'inset-3 sm:inset-4 md:inset-6 lg:inset-10';

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={onClose} />

      <div className={`absolute ${modalSize} bg-[#0c0c0f] border border-[#222] rounded-2xl flex flex-col overflow-hidden shadow-2xl`}>

        {/* ── Header ─────────────────────────────────────────── */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-[#1e1e22] bg-[#0f0f13] shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="p-1.5 bg-neutral-800 rounded-lg">
              {isPresentationMode ? <Layers size={15} className="text-orange-400" /> : <Monitor size={15} className="text-neutral-400" />}
            </div>
            <div className="min-w-0">
              <h3 className="text-sm font-medium text-neutral-100 truncate">{title}</h3>
              {isPresentationMode && totalSlides > 0 && (
                <p className="text-[10px] text-neutral-500">Slide {currentSlide + 1} de {totalSlides}</p>
              )}
              {!isPresentationMode && designs.length > 1 && (
                <p className="text-[10px] text-neutral-600">{activeIndex + 1} de {designs.length} artes</p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-1">
            {/* Export dropdown */}
            <div className="relative" ref={exportMenuRef}>
              <button
                onClick={() => setShowExportMenu((p) => !p)}
                disabled={!!loadingFmt || isLoading}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-white/[0.08] hover:bg-white/[0.12] text-neutral-200 text-xs font-medium transition-all disabled:opacity-50 border border-[#2a2a2e]"
              >
                {loadingFmt ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
                Baixar
                <ChevronDown size={11} className={`text-neutral-500 transition-transform ${showExportMenu ? 'rotate-180' : ''}`} />
              </button>
              {showExportMenu && (
                <div className="absolute right-0 top-full mt-1.5 w-68 bg-[#151519] border border-[#2a2a2e] rounded-xl shadow-2xl z-50">
                  {isPresentationMode ? (
                    /* ── Apresentações: painel flat ── */
                    <div className="p-3.5 space-y-3">
                      {/* Slides */}
                      <div className="space-y-1.5">
                        <p className="text-[10px] text-neutral-500 uppercase tracking-wide font-medium">Slides</p>
                        <div className="flex gap-1.5">
                          {([
                            { value: 'all' as SlideSelection, label: 'Todos' },
                            { value: 'current' as SlideSelection, label: `Slide ${currentSlide + 1}` },
                          ]).map(({ value, label }) => (
                            <button
                              key={value}
                              onClick={() => setSlideSelection(value)}
                              className={`flex-1 py-1.5 rounded-lg text-[11px] font-medium transition-all ${
                                slideSelection === value
                                  ? 'bg-white/[0.10] text-neutral-100 border border-[#434750]'
                                  : 'text-neutral-500 hover:text-neutral-300 bg-white/[0.03] border border-[#2a2a2e]'
                              }`}
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Formato */}
                      <div className="space-y-1.5">
                        <p className="text-[10px] text-neutral-500 uppercase tracking-wide font-medium">Formato</p>
                        <div className="grid grid-cols-4 gap-1.5">
                          {EXPORT_BUTTONS.map(({ fmt, label, icon }) => (
                            <button
                              key={fmt}
                              onClick={() => setSelectedFmt(fmt)}
                              className={`flex flex-col items-center gap-1 py-2 rounded-lg text-[10px] font-medium transition-all ${
                                selectedFmt === fmt
                                  ? 'bg-white/[0.10] text-neutral-100 border border-[#434750]'
                                  : 'text-neutral-500 hover:text-neutral-300 bg-white/[0.03] border border-[#2a2a2e]'
                              }`}
                            >
                              {icon}
                              {label}
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Opções contextuais */}
                      {(selectedFmt === 'png' || selectedFmt === 'jpeg') && (
                        <div className="space-y-1.5">
                          <p className="text-[10px] text-neutral-500 uppercase tracking-wide font-medium">Resolução</p>
                          <select
                            value={resolution}
                            onChange={(e) => setResolution(e.target.value as ResolutionOption)}
                            className="w-full rounded-lg bg-[#0a0a0e] border border-[#2a2a34] px-3 py-2 text-[11px] text-neutral-300 outline-none focus:border-neutral-500 transition-colors"
                          >
                            {RESOLUTION_OPTIONS.map(({ value, label }) => (
                              <option key={value} value={value}>{label}</option>
                            ))}
                          </select>
                        </div>
                      )}

                      {/* Botão baixar */}
                      <button
                        onClick={() => handleExport(selectedFmt)}
                        disabled={!!loadingFmt}
                        className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-white/[0.08] hover:bg-white/[0.12] text-neutral-100 text-xs font-medium tracking-[0.01em] transition-colors disabled:opacity-50 border border-[#2a2a2e]"
                      >
                        {loadingFmt ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                        Baixar {selectedFmt.toUpperCase()}
                      </button>
                    </div>
                  ) : (
                    <div className="p-3.5 space-y-3">
                      <div className="space-y-1.5">
                        <p className="text-[10px] text-neutral-500 uppercase tracking-wide font-medium">Exportar como</p>
                        <div className="grid grid-cols-4 gap-1.5">
                          {EXPORT_BUTTONS.map(({ fmt, label, icon }) => (
                            <button
                              key={fmt}
                              onClick={() => setSelectedFmt(fmt)}
                              className={`flex flex-col items-center gap-1 py-2 rounded-lg text-[10px] font-medium transition-all ${
                                selectedFmt === fmt
                                  ? 'bg-white/[0.10] text-neutral-100 border border-[#434750]'
                                  : 'text-neutral-500 hover:text-neutral-300 bg-white/[0.03] border border-[#2a2a2e]'
                              }`}
                            >
                              {icon}
                              {label}
                            </button>
                          ))}
                        </div>
                      </div>

                      {(selectedFmt === 'png' || selectedFmt === 'jpeg') && (
                        <div className="space-y-1.5">
                          <p className="text-[10px] text-neutral-500 uppercase tracking-wide font-medium">Resolução</p>
                          <select
                            value={resolution}
                            onChange={(e) => setResolution(e.target.value as ResolutionOption)}
                            className="w-full rounded-lg bg-[#0a0a0e] border border-[#2a2a34] px-3 py-2 text-[11px] text-neutral-300 outline-none focus:border-neutral-500 transition-colors"
                          >
                            {RESOLUTION_OPTIONS.map(({ value, label }) => (
                              <option key={value} value={value}>{label}</option>
                            ))}
                          </select>
                        </div>
                      )}

                      <button
                        onClick={() => handleExport(selectedFmt)}
                        disabled={!!loadingFmt}
                        className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-white/[0.08] hover:bg-white/[0.12] text-neutral-100 text-xs font-medium tracking-[0.01em] transition-colors disabled:opacity-50 border border-[#2a2a2e]"
                      >
                        {loadingFmt ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                        Baixar {selectedFmt.toUpperCase()}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>

            <button onClick={() => setIsFullscreen((p) => !p)} className="p-2 rounded-lg text-neutral-500 hover:text-neutral-300 hover:bg-white/[0.04] transition-colors" title={isFullscreen ? 'Sair de tela cheia' : 'Tela cheia'}>
              {isFullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
            </button>
            <button onClick={onClose} className="p-2 rounded-lg text-neutral-500 hover:text-neutral-300 hover:bg-white/[0.04] transition-colors">
              <X size={16} />
            </button>
          </div>
        </div>

        {/* ── Design Tabs (multi-design, non-presentation) ──── */}
        {!isPresentationMode && designs.length > 1 && (
          <div className="px-5 py-2 border-b border-[#1a1a1e] bg-[#0d0d11] shrink-0">
            <div className="flex gap-1.5 overflow-x-auto">
              {designs.map((_, i) => (
                <button key={i} onClick={() => switchDesign(i)} className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all ${i === activeIndex ? 'bg-white/[0.08] text-neutral-200 border border-[#333]' : 'text-neutral-500 hover:text-neutral-300 hover:bg-white/[0.03] border border-transparent'}`}>
                  Arte {i + 1}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── Body ────────────────────────────────────────────── */}
        <div className="flex flex-1 min-h-0 overflow-hidden">

          {isPresentationMode ? (
            /* ── PRESENTATION MODE: iframe viewer with slide nav ── */
            <div className="flex-1 min-w-0 relative flex flex-col bg-[#0a0a0e]">
              {isLoading && (
                <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-[#0c0c0f]/80 backdrop-blur-sm">
                  <Loader2 size={28} className="animate-spin text-orange-400 mb-3" />
                  <p className="text-xs text-neutral-400">Carregando...</p>
                </div>
              )}

              {/* Iframe container */}
              <div className="flex-1 min-h-0 relative flex items-center justify-center p-6">
                {renderFrameShell(
                  frameKind,
                  <div
                    className="w-full max-w-[calc(100vw-440px)] max-h-full"
                    style={{ aspectRatio: previewAspect }}
                  >
                    <iframe
                      ref={presIframeRef}
                      srcDoc={injectPresentationNav(normalizedPreviewHtml)}
                      className="w-full h-full border-0"
                      sandbox="allow-scripts allow-same-origin"
                      title="Apresentacao"
                      onLoad={() => setIsLoading(false)}
                    />
                  </div>,
                )}
              </div>

              {/* Slide navigation bar */}
              {totalSlides > 1 && (
                <div className="shrink-0 flex items-center justify-center gap-4 px-5 py-3 border-t border-[#1e1e22] bg-[#0d0d11]">
                  <button
                    onClick={() => goToSlide(currentSlide - 1)}
                    disabled={currentSlide === 0}
                    className="p-2 rounded-lg text-neutral-400 hover:text-white hover:bg-white/[0.06] transition-colors disabled:opacity-30 disabled:hover:bg-transparent"
                  >
                    <ChevronLeft size={18} />
                  </button>

                  {/* Slide dots */}
                  <div className="flex items-center gap-1.5">
                    {Array.from({ length: totalSlides }, (_, i) => (
                      <button
                        key={i}
                        onClick={() => goToSlide(i)}
                        className={`w-2 h-2 rounded-full transition-all ${
                          i === currentSlide
                            ? 'bg-orange-500 w-6'
                            : 'bg-neutral-700 hover:bg-neutral-500'
                        }`}
                        title={`Slide ${i + 1}`}
                      />
                    ))}
                  </div>

                  <button
                    onClick={() => goToSlide(currentSlide + 1)}
                    disabled={currentSlide >= totalSlides - 1}
                    className="p-2 rounded-lg text-neutral-400 hover:text-white hover:bg-white/[0.06] transition-colors disabled:opacity-30 disabled:hover:bg-transparent"
                  >
                    <ChevronRight size={18} />
                  </button>

                  <span className="text-[11px] text-neutral-500 ml-2">
                    {currentSlide + 1} / {totalSlides}
                  </span>
                </div>
              )}
            </div>
          ) : (
            /* ── SINGLE DESIGN MODE: exact HTML preview + export sidebar ── */
            <>
              <div className="flex-1 min-w-0 bg-[#0a0a0e] overflow-hidden relative flex items-center justify-center">
                {isLoading && (
                  <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-[#0c0c0f]/80 backdrop-blur-sm">
                  <Loader2 size={28} className="animate-spin text-orange-400 mb-3" />
                  <p className="text-xs text-neutral-400">Renderizando...</p>
                </div>
              )}
                {renderFrameShell(
                  frameKind,
                  <div
                    className="w-full max-w-[calc(100vw-440px)] max-h-full"
                    style={{ aspectRatio: previewAspect }}
                  >
                    <iframe
                      ref={singleIframeRef}
                      srcDoc={normalizedPreviewHtml}
                      className="w-full h-full border-0"
                      sandbox="allow-scripts allow-same-origin"
                      title="Design"
                      onLoad={() => setIsLoading(false)}
                    />
                  </div>,
                )}
              </div>

            </>
          )}
        </div>

        {/* ── Footer ─────────────────────────────────────────── */}
        <div className="flex items-center justify-between px-5 py-2.5 border-t border-[#1e1e22] bg-[#0d0d11] shrink-0">
          <div className="flex items-center gap-3">
            {isPresentationMode ? (
              <>
                <span className="text-[11px] text-neutral-500">{previewPresetSpec.shortLabel}</span>
              </>
            ) : (
              <>
                <span className="text-[11px] text-neutral-500">{previewPresetSpec.shortLabel}</span>
                <span className="text-[11px] text-neutral-700">|</span>
                <span className="text-[11px] text-neutral-600">{previewPresetSpec.width} x {previewPresetSpec.height}px</span>
              </>
            )}
            <span className="text-[11px] text-neutral-700">|</span>
            <span className="text-[11px] text-neutral-600">{selectedFmt.toUpperCase()} · {describeResolution(selectedFmt, resolution)}</span>
          </div>

          {loadingFmt && (
            <div className="flex items-center gap-2">
              <Loader2 size={12} className="animate-spin text-neutral-500" />
              <span className="text-[11px] text-neutral-500">Exportando {loadingFmt.toUpperCase()}...</span>
            </div>
          )}
          {error && <span className="text-[11px] text-red-400 truncate max-w-xs">{error}</span>}
        </div>
      </div>
    </div>
  );
};

export default DesignPreviewModal;
