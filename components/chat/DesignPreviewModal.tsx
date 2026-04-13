import React, { useEffect, useMemo, useRef, useState } from 'react';
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

interface DesignPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  designs: string[];
  initialIndex?: number;
}

type ExportFormat = 'pdf' | 'pptx' | 'png' | 'jpeg';
type ResolutionOption = 'hd-720' | 'hd-1080';

type ViewerItem = {
  id: string;
  label: string;
};

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
  if (format !== 'png' && format !== 'jpeg') return 'Documento';
  return resolution === 'hd-1080' ? '1920 x 1080' : '1280 x 720';
}

function extractTitle(html: string) {
  return html.match(/<title[^>]*>([^<]+)<\/title>/i)?.[1]?.trim() || 'Design';
}

function ensureHtmlDocument(src: string): string {
  if (/<!doctype html>/i.test(src) || /<html[\s>]/i.test(src)) return src;
  return `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Design</title></head><body>${src}</body></html>`;
}

function detectSlidesFromHtml(html: string): boolean {
  const matches = html.match(/<(?:section|div)[^>]*class="[^"]*\bslide\b(?!-)[^"]*"/gi);
  return Boolean(matches && matches.length > 1);
}

function detectViewerItems(doc: Document, isSlideDeck: boolean): ViewerItem[] {
  if (isSlideDeck) {
    const candidates = Array.from(doc.querySelectorAll('.slide, .slide-container'));
    const slideNodes = candidates.filter(el => el.querySelector('.slide') === null);
    return slideNodes.map((node, index) => {
      const heading = node.querySelector('h1, h2, h3, [data-role="headline"]')?.textContent?.trim();
      const element = node as HTMLElement;
      if (!element.id) element.id = `arcco-slide-${index + 1}`;
      return {
        id: element.id,
        label: heading ? `Slide ${index + 1} · ${heading.slice(0, 48)}` : `Slide ${index + 1}`,
      };
    });
  }

  const pageNodes = Array.from(
    doc.querySelectorAll('.page, .sheet, [data-page], [data-arcco-page], [data-page-number]')
  );
  if (pageNodes.length === 0) {
    return [{ id: 'document-root', label: 'Documento completo' }];
  }

  return pageNodes.map((node, index) => {
    const element = node as HTMLElement;
    const pageNumber =
      element.getAttribute('data-page-number')?.trim() ||
      element.getAttribute('data-page')?.trim();
    const heading = element.querySelector('h1, h2, h3')?.textContent?.trim();
    if (!element.id) element.id = `arcco-page-${index + 1}`;
    return {
      id: element.id,
      label: pageNumber
        ? `Página ${pageNumber}`
        : heading
          ? `Página ${index + 1} · ${heading.slice(0, 48)}`
          : `Página ${index + 1}`,
    };
  });
}

function getSlideDisplayMode(el: Element): string {
  if (el.classList.contains('slide')) return 'flex';
  return 'block';
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

async function downloadHtmlExport(
  html: string,
  title: string,
  format: ExportFormat,
  resolution: ResolutionOption,
) {
  const res = await fetch('/api/agent/export-html', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ html, title, format, resolution }),
  });
  if (!res.ok) throw new Error(await res.text());
  const contentType = res.headers.get('content-type') || '';
  const blob = await res.blob();
  const ext = contentType.includes('application/zip') ? 'zip' : format;
  const safeName = title.replace(/[^a-zA-Z0-9._\- ]/g, '_').slice(0, 50);
  await downloadBlob(blob, `${safeName}.${ext}`);
}

const DesignPreviewModal: React.FC<DesignPreviewModalProps> = ({ isOpen, onClose, designs, initialIndex = 0 }) => {
  const [activeIndex, setActiveIndex] = useState(initialIndex);
  const [items, setItems] = useState<ViewerItem[]>([]);
  const [activeItem, setActiveItem] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [selectedFmt, setSelectedFmt] = useState<ExportFormat>('png');
  const [resolution, setResolution] = useState<ResolutionOption>('hd-720');
  const [loadingFmt, setLoadingFmt] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);

  const iframeRef = useRef<HTMLIFrameElement>(null);
  const exportMenuRef = useRef<HTMLDivElement>(null);
  const iframeContainerRef = useRef<HTMLDivElement>(null);
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });

  const currentHtml = designs[activeIndex] || '';
  const previewHtml = ensureHtmlDocument(currentHtml);
  const title = extractTitle(previewHtml);
  const isSlideDeck = detectSlidesFromHtml(previewHtml);

  const designDimensions = useMemo(() => {
    const maxWMatch = currentHtml.match(/max-width:\s*(\d+)px\s*;/);
    const maxHMatch = currentHtml.match(/max-height:\s*(\d+)px\s*;/);
    if (maxWMatch && maxHMatch) {
      return { width: parseInt(maxWMatch[1]), height: parseInt(maxHMatch[1]) };
    }
    return { width: 1920, height: 1080 };
  }, [currentHtml]);

  const iframeScale = useMemo(() => {
    if (!containerSize.width || !containerSize.height) return 1;
    const scaleX = containerSize.width / designDimensions.width;
    const scaleY = containerSize.height / designDimensions.height;
    return Math.min(scaleX, scaleY, 1);
  }, [containerSize, designDimensions]);

  const syncSlideState = (index: number) => {
    const doc = iframeRef.current?.contentDocument;
    if (!doc || !isSlideDeck) return;
    const candidates = Array.from(doc.querySelectorAll('.slide, .slide-container'));
    const slides = candidates.filter(el => el.querySelector('.slide') === null);
    slides.forEach((slide, slideIndex) => {
      const element = slide as HTMLElement;
      if (slideIndex === index) {
        element.style.display = getSlideDisplayMode(slide);
        element.classList.add('active');
        element.classList.remove('hidden');
      } else {
        element.style.display = 'none';
        element.classList.remove('active');
        element.classList.add('hidden');
      }
    });
  };

  const goToItem = (index: number) => {
    const bounded = Math.max(0, Math.min(index, items.length - 1));
    const doc = iframeRef.current?.contentDocument;
    if (!doc) return;

    if (isSlideDeck) {
      syncSlideState(bounded);
      setActiveItem(bounded);
      return;
    }

    const item = items[bounded];
    if (!item) return;
    if (item.id === 'document-root') {
      doc.documentElement.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
      doc.getElementById(item.id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    setActiveItem(bounded);
  };

  useEffect(() => {
    if (!isOpen) return;
    setActiveIndex(initialIndex);
  }, [isOpen, initialIndex]);

  useEffect(() => {
    if (!isOpen) return;
    setIsLoading(true);
    setItems([]);
    setActiveItem(0);
    setError(null);
  }, [isOpen, activeIndex, currentHtml]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
      if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
        if (items.length > 1) goToItem(activeItem + 1);
      }
      if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
        if (items.length > 1) goToItem(activeItem - 1);
      }
    };
    document.addEventListener('keydown', handleKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', handleKey);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose, activeItem, items.length]);

  useEffect(() => {
    const el = iframeContainerRef.current;
    if (!el) return;
    const observer = new ResizeObserver(entries => {
      const entry = entries[0];
      if (entry) {
        setContainerSize({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!showExportMenu) return;
    const handler = (event: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(event.target as Node)) {
        setShowExportMenu(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showExportMenu]);

  useEffect(() => {
    if (!isOpen || !iframeRef.current) return;

    const handleLoad = () => {
      const doc = iframeRef.current?.contentDocument;
      if (!doc) {
        setIsLoading(false);
        return;
      }

      const nextItems = detectViewerItems(doc, isSlideDeck);
      setItems(nextItems);
      setActiveItem(0);

      if (isSlideDeck) {
        syncSlideState(0);
      } else {
        const scrollRoot = doc.scrollingElement || doc.documentElement;
        const pageNodes = nextItems
          .map(item => item.id === 'document-root' ? null : doc.getElementById(item.id))
          .filter(Boolean) as HTMLElement[];
        const onScroll = () => {
          if (pageNodes.length === 0 || !scrollRoot) return;
          const offset = scrollRoot.scrollTop + 48;
          let current = 0;
          for (let i = 0; i < pageNodes.length; i += 1) {
            if (pageNodes[i].offsetTop <= offset) current = i;
          }
          setActiveItem(current);
        };
        doc.addEventListener('scroll', onScroll, { passive: true });
      }

      setIsLoading(false);
    };

    const iframe = iframeRef.current;
    iframe.addEventListener('load', handleLoad);
    if (iframe.contentDocument?.readyState === 'complete') handleLoad();
    return () => iframe.removeEventListener('load', handleLoad);
  }, [isOpen, currentHtml, isSlideDeck]);

  const handleExport = async (fmt: ExportFormat) => {
    setLoadingFmt(fmt);
    setError(null);
    setShowExportMenu(false);
    try {
      await downloadHtmlExport(previewHtml, title, fmt, resolution);
    } catch (err: any) {
      setError(`Erro ao exportar: ${err.message}`);
    } finally {
      setLoadingFmt(null);
    }
  };

  if (!isOpen) return null;

  const panelWidth = isFullscreen ? 'w-screen rounded-none' : 'w-[min(96vw,1480px)]';

  return (
    <div className="fixed inset-0 z-[100] flex items-stretch justify-end">
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={onClose} />

      <div className={`relative h-full ${panelWidth} bg-[#0a0b0f] border-l border-[#20232a] flex overflow-hidden shadow-2xl`}>
        <aside className="hidden lg:flex w-[300px] shrink-0 flex-col border-r border-[#181b21] bg-[#0d1016]">
          <div className="px-5 py-4 border-b border-[#181b21]">
            <div className="text-[10px] uppercase tracking-[0.2em] text-neutral-500">Renderer HTML</div>
            <h3 className="mt-2 text-sm font-medium text-neutral-100 truncate">{title}</h3>
            <p className="mt-1 text-xs text-neutral-500">
              {isSlideDeck ? `${items.length || 1} slides` : `${items.length || 1} páginas`}
            </p>
          </div>

          {designs.length > 1 && (
            <div className="px-3 py-3 border-b border-[#181b21]">
              <div className="mb-2 px-2 text-[10px] uppercase tracking-[0.18em] text-neutral-500">Artes</div>
              <div className="space-y-1.5 max-h-52 overflow-y-auto pr-1">
                {designs.map((design, index) => (
                  <button
                    key={index}
                    onClick={() => setActiveIndex(index)}
                    className={`w-full rounded-xl border px-3 py-2.5 text-left transition-colors ${
                      index === activeIndex
                        ? 'border-[#3b4453] bg-[#141823] text-neutral-100'
                        : 'border-[#20232c] bg-[#0f1117] text-neutral-400 hover:bg-[#151923] hover:text-neutral-200'
                    }`}
                  >
                    <div className="text-[10px] uppercase tracking-[0.18em] text-neutral-500">Arte {index + 1}</div>
                    <div className="mt-1 truncate text-xs">{extractTitle(design)}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="flex-1 px-3 py-3 min-h-0">
            <div className="mb-2 flex items-center gap-2 px-2 text-[10px] uppercase tracking-[0.18em] text-neutral-500">
              {isSlideDeck ? <Layers size={12} /> : <Monitor size={12} />}
              {isSlideDeck ? 'Slides' : 'Páginas'}
            </div>
            <div className="space-y-1.5 overflow-y-auto pr-1 max-h-full">
              {(items.length > 0 ? items : [{ id: 'loading', label: isSlideDeck ? 'Slide 1' : 'Documento completo' }]).map((item, index) => (
                <button
                  key={item.id}
                  onClick={() => goToItem(index)}
                  className={`w-full rounded-xl border px-3 py-2.5 text-left transition-colors ${
                    index === activeItem
                      ? 'border-[#3b4453] bg-[#141823] text-neutral-100'
                      : 'border-[#20232c] bg-[#0f1117] text-neutral-400 hover:bg-[#151923] hover:text-neutral-200'
                  }`}
                >
                  <div className="text-[10px] uppercase tracking-[0.18em] text-neutral-500">
                    {isSlideDeck ? `Slide ${index + 1}` : `Página ${index + 1}`}
                  </div>
                  <div className="mt-1 text-xs line-clamp-2">{item.label}</div>
                </button>
              ))}
            </div>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b border-[#181b21] bg-[#0e1117] shrink-0">
            <div className="flex items-center gap-3 min-w-0">
              <div className="p-1.5 bg-[#151923] rounded-lg">
                {isSlideDeck ? <Layers size={15} className="text-orange-400" /> : <Monitor size={15} className="text-neutral-300" />}
              </div>
              <div className="min-w-0">
                <h3 className="text-sm font-medium text-neutral-100 truncate">{title}</h3>
                <p className="text-[10px] text-neutral-500">
                  Renderização bruta do HTML gerado pelo agente
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <div className="relative" ref={exportMenuRef}>
                <button
                  onClick={() => setShowExportMenu(prev => !prev)}
                  disabled={!!loadingFmt || isLoading}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-white/[0.06] hover:bg-white/[0.1] text-neutral-200 text-xs font-medium transition-all disabled:opacity-50 border border-[#2a2e35]"
                >
                  {loadingFmt ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
                  Baixar
                  <ChevronDown size={11} className={`text-neutral-500 transition-transform ${showExportMenu ? 'rotate-180' : ''}`} />
                </button>

                {showExportMenu && (
                  <div className="absolute right-0 top-full mt-1.5 w-68 bg-[#151519] border border-[#2a2a2e] rounded-xl shadow-2xl z-50">
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
                            onChange={(event) => setResolution(event.target.value as ResolutionOption)}
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
                  </div>
                )}
              </div>

              <button
                onClick={() => setIsFullscreen(prev => !prev)}
                className="p-2 rounded-lg text-neutral-500 hover:text-neutral-300 hover:bg-white/[0.04] transition-colors"
                title={isFullscreen ? 'Sair de tela cheia' : 'Tela cheia'}
              >
                {isFullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
              </button>
              <button onClick={onClose} className="p-2 rounded-lg text-neutral-500 hover:text-neutral-300 hover:bg-white/[0.04] transition-colors">
                <X size={16} />
              </button>
            </div>
          </div>

          <div className="flex items-center justify-between gap-3 border-b border-[#181b21] bg-[#0c0f15] px-4 py-3 shrink-0">
            <div className="min-w-0">
              <div className="text-[10px] uppercase tracking-[0.18em] text-neutral-500">Viewport</div>
              <div className="truncate text-xs text-neutral-300">
                {isSlideDeck ? 'Deck com paginação por slide' : 'Documento com scroll e navegação por página'}
              </div>
            </div>
            {items.length > 1 && (
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => goToItem(activeItem - 1)}
                  disabled={activeItem === 0}
                  className="rounded-lg border border-[#2a2f39] p-2 text-neutral-400 transition-colors hover:bg-white/[0.05] hover:text-neutral-200 disabled:opacity-35"
                >
                  <ChevronLeft size={15} />
                </button>
                <div className="rounded-lg border border-[#232833] bg-[#11151d] px-3 py-2 text-[11px] text-neutral-300">
                  {isSlideDeck ? 'Slide' : 'Página'} {activeItem + 1} / {items.length}
                </div>
                <button
                  onClick={() => goToItem(activeItem + 1)}
                  disabled={activeItem >= items.length - 1}
                  className="rounded-lg border border-[#2a2f39] p-2 text-neutral-400 transition-colors hover:bg-white/[0.05] hover:text-neutral-200 disabled:opacity-35"
                >
                  <ChevronRight size={15} />
                </button>
              </div>
            )}
          </div>

          <div ref={iframeContainerRef} className="relative flex-1 min-h-0 bg-[#090b10] overflow-hidden">
            {isLoading && (
              <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-[#0c0c0f]/80 backdrop-blur-sm">
                <Loader2 size={28} className="animate-spin text-orange-400 mb-3" />
                <p className="text-xs text-neutral-400">Renderizando HTML bruto...</p>
              </div>
            )}
            <div
              style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                width: `${designDimensions.width}px`,
                height: `${designDimensions.height}px`,
                transform: `translate(-50%, -50%) scale(${iframeScale})`,
              }}
            >
              <iframe
                ref={iframeRef}
                srcDoc={previewHtml}
                className="border-0 bg-white"
                style={{ width: '100%', height: '100%' }}
                sandbox="allow-scripts allow-same-origin"
                title={title}
              />
            </div>
          </div>

          <div className="flex items-center justify-between px-5 py-2.5 border-t border-[#1e1e22] bg-[#0d0d11] shrink-0">
            <div className="flex items-center gap-3 text-[11px] text-neutral-500">
              <span>{isSlideDeck ? `${items.length || 1} slides` : `${items.length || 1} páginas`}</span>
              <span className="text-neutral-700">|</span>
              <span>{selectedFmt.toUpperCase()} · {describeResolution(selectedFmt, resolution)}</span>
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
    </div>
  );
};

export default DesignPreviewModal;
