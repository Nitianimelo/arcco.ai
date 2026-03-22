import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Canvas as FabricCanvas, Textbox, FabricImage, FabricObject } from 'fabric';
import html2canvas from 'html2canvas';
import {
  AlignCenter,
  AlignLeft,
  AlignRight,
  ChevronDown,
  Download,
  FileImage,
  FileText,
  Image,
  Loader2,
  Maximize2,
  Minimize2,
  Monitor,
  Presentation,
  Type,
  X,
} from 'lucide-react';

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

interface TextInfo {
  text: string;
  left: number;
  top: number;
  width: number;
  fontSize: number;
  fontFamily: string;
  color: string;
  fontWeight: string;
  textAlign: string;
}

interface SelectedState {
  text: string;
  fontSize: number;
  textAlign: string;
  color: string;
}

// ────────────────────────────────────────────────────────────────
// Constants
// ────────────────────────────────────────────────────────────────

const CANVAS_SIZE = 1080;

const EXPORT_BUTTONS: { fmt: ExportFormat; label: string; icon: React.ReactNode }[] = [
  { fmt: 'png', label: 'PNG', icon: <Image size={14} /> },
  { fmt: 'jpeg', label: 'JPEG', icon: <FileImage size={14} /> },
  { fmt: 'pdf', label: 'PDF', icon: <FileText size={14} /> },
  { fmt: 'pptx', label: 'PPTX', icon: <Presentation size={14} /> },
];

const FONT_OPTIONS = [
  'Georgia',
  'Helvetica Neue',
  'Arial',
  'Trebuchet MS',
  'Gill Sans',
  'Verdana',
  'Times New Roman',
];

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

function rgbToHex(rgb: string): string {
  const m = rgb.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
  if (!m) return rgb.startsWith('#') ? rgb : '#000000';
  const hex = (n: number) => n.toString(16).padStart(2, '0');
  return `#${hex(+m[1])}${hex(+m[2])}${hex(+m[3])}`;
}

/** Check if an element has meaningful text content */
function hasVisibleText(node: HTMLElement): boolean {
  const text = (node.innerText || node.textContent || '').replace(/\s+/g, ' ').trim();
  return text.length > 0 && text.length <= 500;
}

/** Collect innermost text-bearing elements (avoids duplicates from wrappers) */
function collectLeafTextElements(root: HTMLElement, iframeWindow: Window): HTMLElement[] {
  const all = Array.from(root.querySelectorAll<HTMLElement>('*')).filter((el) => {
    if (el.closest('script, style, svg, canvas, noscript')) return false;
    const cs = iframeWindow.getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    const rect = el.getBoundingClientRect();
    if (rect.width < 5 || rect.height < 5) return false;
    return hasVisibleText(el);
  });

  // Keep only leaf elements: remove any element that contains another candidate
  // This prevents wrapper divs from duplicating their children's text
  return all.filter((el) => !all.some((other) => other !== el && el.contains(other)));
}

/** Extract text info + capture background from HTML */
async function htmlToFabricData(html: string): Promise<{ bgDataUrl: string; texts: TextInfo[] }> {
  const normalized = ensureHtmlDocument(html);

  return new Promise((resolve, reject) => {
    const iframe = document.createElement('iframe');
    iframe.style.cssText = 'position:fixed;left:-9999px;top:0;width:1080px;height:1080px;border:none;opacity:0;pointer-events:none;';
    document.body.appendChild(iframe);

    iframe.addEventListener('load', async () => {
      try {
        const doc = iframe.contentDocument;
        if (!doc) throw new Error('Cannot access iframe document');

        // Wait a bit for external resources (Tailwind CDN, fonts, images)
        await new Promise((r) => setTimeout(r, 800));

        // Find the root container
        const root = doc.body;
        const rootRect = root.getBoundingClientRect();
        const iframeWin = iframe.contentWindow!;

        // Collect innermost text elements (smart leaf detection, no tag filter)
        const textElements = collectLeafTextElements(root, iframeWin);
        const texts: TextInfo[] = [];

        for (const el of textElements) {
          const rect = el.getBoundingClientRect();
          const cs = iframeWin.getComputedStyle(el);

          texts.push({
            text: el.innerText.trim(),
            left: rect.left - rootRect.left,
            top: rect.top - rootRect.top,
            width: Math.max(rect.width, 50),
            fontSize: parseFloat(cs.fontSize) || 16,
            fontFamily: cs.fontFamily.split(',')[0].replace(/['"]/g, '').trim(),
            color: rgbToHex(cs.color),
            fontWeight: cs.fontWeight,
            textAlign: cs.textAlign || 'left',
          });
        }

        // Hide text elements for background capture
        const savedVisibility: string[] = [];
        textElements.forEach((el, i) => {
          savedVisibility[i] = el.style.visibility;
          el.style.visibility = 'hidden';
        });

        // Capture background without text
        const captureCanvas = await html2canvas(root, {
          width: CANVAS_SIZE,
          height: CANVAS_SIZE,
          scale: 1,
          useCORS: true,
          allowTaint: true,
          backgroundColor: null,
          logging: false,
        });
        const bgDataUrl = captureCanvas.toDataURL('image/png');

        // Restore visibility
        textElements.forEach((el, i) => {
          el.style.visibility = savedVisibility[i];
        });

        // Cleanup
        document.body.removeChild(iframe);

        resolve({ bgDataUrl, texts });
      } catch (err) {
        document.body.removeChild(iframe);
        reject(err);
      }
    });

    iframe.addEventListener('error', () => {
      document.body.removeChild(iframe);
      reject(new Error('Failed to load design in iframe'));
    });

    iframe.srcdoc = normalized;
  });
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

async function downloadHtmlExport(html: string, title: string, format: ExportFormat) {
  const res = await fetch('/api/agent/export-html', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ html, title, format }),
  });
  if (!res.ok) throw new Error(await res.text());
  const blob = await res.blob();
  await downloadBlob(blob, `design.${format}`);
}

// ────────────────────────────────────────────────────────────────
// ColorSwatch
// ────────────────────────────────────────────────────────────────

function ColorSwatch({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const hexVal = value.startsWith('#') ? value : rgbToHex(value);
  return (
    <div className="relative">
      <div className="w-7 h-7 rounded-lg border border-[#333] shadow-sm cursor-pointer" style={{ backgroundColor: hexVal }} />
      <input
        type="color"
        value={hexVal}
        onChange={(e) => onChange(e.target.value)}
        className="absolute inset-0 opacity-0 cursor-pointer"
        style={{ minWidth: 44, minHeight: 44, margin: '-9px' }}
      />
    </div>
  );
}

// ────────────────────────────────────────────────────────────────
// Main Component
// ────────────────────────────────────────────────────────────────

const DesignPreviewModal: React.FC<DesignPreviewModalProps> = ({ isOpen, onClose, designs, initialIndex = 0 }) => {
  const [activeIndex, setActiveIndex] = useState(initialIndex);
  const [isLoading, setIsLoading] = useState(true);
  const [loadingFmt, setLoadingFmt] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [selectedState, setSelectedState] = useState<SelectedState | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const canvasElRef = useRef<HTMLCanvasElement>(null);
  const fabricRef = useRef<FabricCanvas | null>(null);
  const exportMenuRef = useRef<HTMLDivElement>(null);

  const currentHtml = designs[activeIndex] || '';
  const title = extractTitle(currentHtml);

  // ── Build Fabric canvas from HTML ──
  const buildCanvas = useCallback(async (html: string) => {
    // Dispose previous canvas
    if (fabricRef.current) {
      fabricRef.current.dispose();
      fabricRef.current = null;
    }

    if (!canvasElRef.current || !containerRef.current) return;

    setIsLoading(true);
    setSelectedState(null);
    setError(null);

    try {
      const { bgDataUrl, texts } = await htmlToFabricData(html);

      if (!canvasElRef.current || !containerRef.current) return;

      // Create Fabric canvas at native resolution
      const fc = new FabricCanvas(canvasElRef.current, {
        width: CANVAS_SIZE,
        height: CANVAS_SIZE,
        backgroundColor: 'transparent',
        selection: true,
        preserveObjectStacking: true,
      });

      // Set background image
      const bgImg = await FabricImage.fromURL(bgDataUrl);
      bgImg.set({
        scaleX: CANVAS_SIZE / (bgImg.width || CANVAS_SIZE),
        scaleY: CANVAS_SIZE / (bgImg.height || CANVAS_SIZE),
        originX: 'left',
        originY: 'top',
        selectable: false,
        evented: false,
      });
      fc.backgroundImage = bgImg;

      // Add text objects
      for (const t of texts) {
        const tb = new Textbox(t.text, {
          left: t.left,
          top: t.top,
          width: t.width,
          fontSize: t.fontSize,
          fontFamily: t.fontFamily,
          fill: t.color,
          textAlign: t.textAlign as any,
          fontWeight: t.fontWeight === 'bold' || parseInt(t.fontWeight) >= 700 ? 'bold' : 'normal',
          editable: true,
          selectable: true,
          borderColor: '#ea580c',
          cornerColor: '#ea580c',
          cornerStyle: 'circle',
          cornerSize: 8,
          transparentCorners: false,
          padding: 4,
        });
        fc.add(tb);
      }

      // Selection events → update sidebar
      const updateSidebar = (obj: FabricObject | undefined) => {
        if (!obj || !(obj instanceof Textbox)) {
          setSelectedState(null);
          return;
        }
        setSelectedState({
          text: obj.text || '',
          fontSize: obj.fontSize || 16,
          textAlign: (obj.textAlign as string) || 'left',
          color: typeof obj.fill === 'string' ? obj.fill : '#000000',
        });
      };

      fc.on('selection:created', (e) => updateSidebar(e.selected?.[0]));
      fc.on('selection:updated', (e) => updateSidebar(e.selected?.[0]));
      fc.on('selection:cleared', () => setSelectedState(null));
      fc.on('object:modified', (e) => updateSidebar(e.target));
      fc.on('text:changed', (e) => updateSidebar(e.target));

      fabricRef.current = fc;
      fitToContainer();
      fc.requestRenderAll();
    } catch (err: any) {
      setError(`Erro ao processar design: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // ── Fit canvas to container ──
  const fitToContainer = useCallback(() => {
    const fc = fabricRef.current;
    const container = containerRef.current;
    if (!fc || !container) return;

    const cw = container.clientWidth;
    const ch = container.clientHeight;
    if (cw === 0 || ch === 0) return;

    const zoom = Math.min(cw / CANVAS_SIZE, ch / CANVAS_SIZE) * 0.88;
    fc.setZoom(zoom);
    fc.setDimensions({ width: CANVAS_SIZE * zoom, height: CANVAS_SIZE * zoom });
    fc.requestRenderAll();
  }, []);

  // ── Init on open / design change ──
  useEffect(() => {
    if (!isOpen || !currentHtml) return;
    // Small delay to ensure container is rendered
    const t = setTimeout(() => buildCanvas(currentHtml), 50);
    return () => clearTimeout(t);
  }, [isOpen, activeIndex, buildCanvas, currentHtml]);

  // ── Resize handler ──
  useEffect(() => {
    if (!isOpen) return;
    const handler = () => fitToContainer();
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, [isOpen, fitToContainer]);

  // Re-fit on fullscreen toggle
  useEffect(() => {
    if (!isOpen) return;
    const t = setTimeout(fitToContainer, 100);
    return () => clearTimeout(t);
  }, [isFullscreen, isOpen, fitToContainer]);

  // ── Escape to close ──
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handler);
    document.body.style.overflow = 'hidden';
    return () => { document.removeEventListener('keydown', handler); document.body.style.overflow = ''; };
  }, [isOpen, onClose]);

  // ── Close export menu on outside click ──
  useEffect(() => {
    if (!showExportMenu) return;
    const handler = (e: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target as Node)) setShowExportMenu(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showExportMenu]);

  // ── Cleanup on unmount ──
  useEffect(() => {
    return () => {
      if (fabricRef.current) {
        fabricRef.current.dispose();
        fabricRef.current = null;
      }
    };
  }, []);

  // ── Sidebar handlers ──
  const getActiveTextbox = (): Textbox | null => {
    const fc = fabricRef.current;
    if (!fc) return null;
    const obj = fc.getActiveObject();
    return obj instanceof Textbox ? obj : null;
  };

  const handleTextChange = (value: string) => {
    const tb = getActiveTextbox();
    if (!tb) return;
    tb.set({ text: value });
    fabricRef.current?.requestRenderAll();
    setSelectedState((s) => s ? { ...s, text: value } : s);
  };

  const handleFontSizeChange = (size: number) => {
    const tb = getActiveTextbox();
    if (!tb) return;
    tb.set({ fontSize: size });
    fabricRef.current?.requestRenderAll();
    setSelectedState((s) => s ? { ...s, fontSize: size } : s);
  };

  const handleAlignChange = (align: string) => {
    const tb = getActiveTextbox();
    if (!tb) return;
    tb.set({ textAlign: align });
    fabricRef.current?.requestRenderAll();
    setSelectedState((s) => s ? { ...s, textAlign: align } : s);
  };

  const handleColorChange = (color: string) => {
    const tb = getActiveTextbox();
    if (!tb) return;
    tb.set({ fill: color });
    fabricRef.current?.requestRenderAll();
    setSelectedState((s) => s ? { ...s, color } : s);
  };

  const handleFontFamilyChange = (fontFamily: string) => {
    const tb = getActiveTextbox();
    if (!tb) return;
    tb.set({ fontFamily });
    fabricRef.current?.requestRenderAll();
  };

  // ── Export helpers ──
  const exportFullResDataUrl = (format: 'png' | 'jpeg' = 'png'): string => {
    const fc = fabricRef.current;
    if (!fc) return '';
    fc.discardActiveObject();
    const currentZoom = fc.getZoom();
    const currentW = fc.getWidth();
    const currentH = fc.getHeight();
    fc.setZoom(1);
    fc.setDimensions({ width: CANVAS_SIZE, height: CANVAS_SIZE });
    fc.requestRenderAll();
    const dataUrl = fc.toDataURL({ format, quality: 1, multiplier: 1 });
    fc.setZoom(currentZoom);
    fc.setDimensions({ width: currentW, height: currentH });
    fc.requestRenderAll();
    return dataUrl;
  };

  const handleExport = async (fmt: ExportFormat) => {
    setLoadingFmt(fmt);
    setError(null);
    setShowExportMenu(false);
    try {
      if (fmt === 'png' || fmt === 'jpeg') {
        // Client-side export — no backend needed
        const dataUrl = exportFullResDataUrl(fmt);
        const res = await fetch(dataUrl);
        const blob = await res.blob();
        await downloadBlob(blob, `design.${fmt}`);
      } else {
        // PDF/PPTX — wrap PNG in HTML, send to backend
        const pngDataUrl = exportFullResDataUrl('png');
        const wrapperHtml = `<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body style="margin:0;padding:0;width:${CANVAS_SIZE}px;height:${CANVAS_SIZE}px"><img src="${pngDataUrl}" style="width:${CANVAS_SIZE}px;height:${CANVAS_SIZE}px;display:block"></body></html>`;
        await downloadHtmlExport(wrapperHtml, title, fmt);
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
              <Monitor size={15} className="text-neutral-400" />
            </div>
            <div className="min-w-0">
              <h3 className="text-sm font-medium text-neutral-100 truncate">{title}</h3>
              {designs.length > 1 && (
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
                <div className="absolute right-0 top-full mt-1.5 w-52 bg-[#151519] border border-[#2a2a2e] rounded-xl shadow-2xl overflow-hidden z-50">
                  <div className="px-3.5 py-2 border-b border-[#1e1e22]">
                    <p className="text-[10px] text-neutral-500 uppercase tracking-wide">Baixa exatamente o que voce ve</p>
                  </div>
                  {EXPORT_BUTTONS.map(({ fmt, label, icon }) => (
                    <button
                      key={fmt}
                      onClick={() => handleExport(fmt)}
                      disabled={!!loadingFmt}
                      className="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-xs text-neutral-300 hover:text-white hover:bg-white/[0.05] transition-colors text-left disabled:opacity-40"
                    >
                      {loadingFmt === fmt ? <Loader2 size={14} className="animate-spin" /> : icon}
                      Baixar como {label}
                    </button>
                  ))}
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

        {/* ── Design Tabs ────────────────────────────────────── */}
        {designs.length > 1 && (
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

        {/* ── Body: Canvas + Sidebar ─────────────────────────── */}
        <div className="flex flex-1 min-h-0 overflow-hidden">

          {/* Canvas Area */}
          <div ref={containerRef} className="flex-1 min-w-0 checkerboard-bg overflow-hidden relative flex items-center justify-center">
            {isLoading && (
              <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-[#0c0c0f]/80 backdrop-blur-sm">
                <Loader2 size={28} className="animate-spin text-orange-400 mb-3" />
                <p className="text-xs text-neutral-400">Processando design...</p>
              </div>
            )}
            <canvas ref={canvasElRef} className="shadow-2xl shadow-black/60 rounded" />
          </div>

          {/* ── Sidebar ────────────────────────────────────────── */}
          <div className="w-[280px] shrink-0 border-l border-[#1e1e22] bg-[#0e0e12] flex flex-col overflow-y-auto">

            {selectedState ? (
              <div className="p-4 space-y-4 border-b border-[#1a1a1e]">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Type size={13} className="text-orange-400" />
                    <span className="text-xs font-medium text-neutral-300">Texto selecionado</span>
                  </div>
                  <button
                    onClick={() => { fabricRef.current?.discardActiveObject(); fabricRef.current?.requestRenderAll(); setSelectedState(null); }}
                    className="p-1 rounded hover:bg-white/5 transition-colors"
                  >
                    <X size={12} className="text-neutral-500" />
                  </button>
                </div>

                {/* Texto */}
                <div className="space-y-1.5">
                  <label className="text-[11px] text-neutral-500 font-medium">Conteudo</label>
                  <textarea
                    value={selectedState.text}
                    onChange={(e) => handleTextChange(e.target.value)}
                    className="w-full h-20 rounded-lg bg-[#0a0a0e] border border-[#2a2a34] px-3 py-2 text-[13px] text-neutral-200 outline-none resize-none focus:border-orange-500/40 transition-colors leading-relaxed"
                    placeholder="Texto..."
                  />
                </div>

                {/* Tamanho */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] text-neutral-500 font-medium">Tamanho</label>
                    <div className="flex items-center gap-1">
                      <input
                        type="number"
                        min={8}
                        max={200}
                        value={selectedState.fontSize}
                        onChange={(e) => handleFontSizeChange(Number(e.target.value) || 16)}
                        className="w-14 bg-[#0a0a0e] border border-[#2a2a34] rounded px-1.5 py-0.5 text-[11px] text-neutral-300 text-center outline-none"
                      />
                      <span className="text-[10px] text-neutral-600">px</span>
                    </div>
                  </div>
                  <input
                    type="range" min="8" max="200"
                    value={selectedState.fontSize}
                    onChange={(e) => handleFontSizeChange(Number(e.target.value))}
                    className="w-full accent-orange-500"
                  />
                </div>

                {/* Alinhamento */}
                <div className="space-y-1.5">
                  <label className="text-[11px] text-neutral-500 font-medium">Alinhamento</label>
                  <div className="flex gap-1">
                    {([
                      { value: 'left', icon: <AlignLeft size={14} />, tip: 'Esquerda' },
                      { value: 'center', icon: <AlignCenter size={14} />, tip: 'Centro' },
                      { value: 'right', icon: <AlignRight size={14} />, tip: 'Direita' },
                    ] as const).map(({ value, icon, tip }) => (
                      <button
                        key={value}
                        onClick={() => handleAlignChange(value)}
                        title={tip}
                        className={`flex-1 flex items-center justify-center py-2 rounded-lg transition-all ${
                          selectedState.textAlign === value || (value === 'left' && selectedState.textAlign === 'start')
                            ? 'bg-orange-500/15 text-orange-300 border border-orange-500/30'
                            : 'text-neutral-500 hover:text-neutral-300 hover:bg-white/[0.04] border border-transparent'
                        }`}
                      >
                        {icon}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Cor */}
                <div className="flex items-center justify-between">
                  <label className="text-[11px] text-neutral-500 font-medium">Cor do texto</label>
                  <ColorSwatch value={selectedState.color} onChange={handleColorChange} />
                </div>

                {/* Fonte */}
                <div className="space-y-1.5">
                  <label className="text-[11px] text-neutral-500 font-medium">Fonte</label>
                  <select
                    value={getActiveTextbox()?.fontFamily || ''}
                    onChange={(e) => handleFontFamilyChange(e.target.value)}
                    className="w-full rounded-lg bg-[#0a0a0e] border border-[#2a2a34] px-3 py-2 text-xs text-neutral-300 outline-none"
                  >
                    {FONT_OPTIONS.map((f) => <option key={f} value={f}>{f}</option>)}
                  </select>
                </div>
              </div>
            ) : (
              <div className="p-4 border-b border-[#1a1a1e]">
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <div className="w-10 h-10 rounded-xl bg-orange-500/10 flex items-center justify-center mb-3">
                    <Type size={18} className="text-orange-400/60" />
                  </div>
                  <p className="text-xs text-neutral-400 font-medium">Clique em qualquer texto</p>
                  <p className="text-[11px] text-neutral-600 mt-1 leading-relaxed">
                    para editar, arrastar, redimensionar<br />ou alterar estilo
                  </p>
                </div>
              </div>
            )}

            {/* Dicas */}
            <div className="p-4 space-y-2.5">
              <span className="text-[10px] text-neutral-600 uppercase tracking-wide font-semibold">Como usar</span>
              <div className="space-y-1.5 text-[11px] text-neutral-600 leading-relaxed">
                <p>Clique num texto para selecionar</p>
                <p>Duplo clique para editar inline</p>
                <p>Arraste para mover</p>
                <p>Puxe os cantos para redimensionar</p>
              </div>
            </div>
          </div>
        </div>

        {/* ── Footer ─────────────────────────────────────────── */}
        <div className="flex items-center justify-between px-5 py-2.5 border-t border-[#1e1e22] bg-[#0d0d11] shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-[11px] text-neutral-500">{CANVAS_SIZE} x {CANVAS_SIZE}px</span>
            <span className="text-[11px] text-neutral-700">|</span>
            <span className="text-[11px] text-neutral-600">O que voce ve e exatamente o que sera baixado</span>
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
