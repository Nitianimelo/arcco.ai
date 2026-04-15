import React, { useCallback, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { CheckSquare, Download, Loader2, Square, X } from 'lucide-react';

// ── helpers ───────────────────────────────────────────────────────────────────

function normalizeHtmlDocument(src: string): string {
  if (/<!doctype html>/i.test(src) || /<html[\s>]/i.test(src)) return src;
  return `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Design</title></head><body>${src}</body></html>`;
}

/** Constrói o srcDoc para mostrar apenas o slide `slideIndex` (0-based). */
function buildSlidePreview(html: string, slideIndex: number, total: number): string {
  const doc = normalizeHtmlDocument(html);
  const reset = '<style>html,body{margin:0;padding:0;overflow:hidden;}</style>';
  const script =
    total > 1
      ? `<script>(function(){var ss=['section.slide','div.slide','.slide-wrapper'];var sl=[];for(var i=0;i<ss.length;i++){var f=document.querySelectorAll(ss[i]);if(f.length>1){sl=Array.from(f);break;}}if(sl.length<2)return;for(var j=0;j<sl.length;j++)sl[j].style.display=j===${slideIndex}?'':'none';})();</script>`
      : '';
  const withReset = doc.includes('</head>') ? doc.replace('</head>', reset + '</head>') : reset + doc;
  return script ? withReset.replace('</body>', script + '</body>') : withReset;
}

// ── Format labels & colors ────────────────────────────────────────────────────

const FORMAT_LABELS: Record<string, string> = {
  pdf: 'PDF', pptx: 'PPTX', png: 'PNG', jpeg: 'JPEG',
};

const FORMAT_BADGE: Record<string, string> = {
  pdf:  'text-red-400   border-red-500/30   bg-red-500/10',
  pptx: 'text-orange-400 border-orange-500/30 bg-orange-500/10',
  png:  'text-blue-400  border-blue-500/30  bg-blue-500/10',
  jpeg: 'text-green-400 border-green-500/30 bg-green-500/10',
};

// ── SlideThumb ─────────────────────────────────────────────────────────────────

const THUMB_W = 160;

const SlideThumb: React.FC<{
  html:       string;
  slideIndex: number;
  total:      number;
  viewport:   { width: number; height: number };
  selected:   boolean;
  onClick:    () => void;
}> = ({ html, slideIndex, total, viewport, selected, onClick }) => {
  const thumbH = Math.round(THUMB_W * viewport.height / viewport.width);
  const scale  = THUMB_W / viewport.width;

  const iframeContent = useMemo(
    () => buildSlidePreview(html, slideIndex, total),
    [html, slideIndex, total],
  );

  return (
    <div
      onClick={onClick}
      className={`relative cursor-pointer select-none rounded-xl overflow-hidden transition-all ${
        selected
          ? 'ring-2 ring-orange-400 ring-offset-2 ring-offset-[#0d0d12]'
          : 'ring-1 ring-[#2a2a33] hover:ring-[#3a3a48]'
      }`}
      style={{ width: THUMB_W, flexShrink: 0 }}
    >
      {/* Iframe preview */}
      <div style={{ width: THUMB_W, height: thumbH, overflow: 'hidden', background: '#08080f' }}>
        <iframe
          srcDoc={iframeContent}
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
          title={`Página ${slideIndex + 1}`}
        />
      </div>

      {/* Label + checkbox */}
      <div className={`flex items-center justify-between px-2 py-1.5 transition-colors ${
        selected ? 'bg-orange-500/12 text-orange-200' : 'bg-[#0f0f16] text-neutral-500'
      }`}>
        <span className="text-[10px] font-medium">Pág {slideIndex + 1}</span>
        {selected
          ? <CheckSquare size={11} className="text-orange-400 shrink-0" />
          : <Square      size={11} className="text-neutral-600 shrink-0" />
        }
      </div>
    </div>
  );
};

// ── ExportDialog ───────────────────────────────────────────────────────────────

export interface ExportDialogProps {
  design:     string;
  multiSlide: boolean;
  slideNum:   number;
  viewport:   { width: number; height: number };
  format:     'pdf' | 'pptx' | 'png' | 'jpeg';
  title:      string;
  exporting:  boolean;
  onClose:    () => void;
  /** null = todas as páginas; number[] = índices selecionados (0-based) */
  onConfirm:  (selectedIndices: number[] | null) => void;
}

const ExportDialog: React.FC<ExportDialogProps> = ({
  design, multiSlide, slideNum, viewport, format, title, exporting, onClose, onConfirm,
}) => {
  const total = multiSlide ? slideNum : 1;

  const [selected, setSelected] = useState<Set<number>>(
    () => new Set(Array.from({ length: total }, (_, i) => i)),
  );

  const togglePage = useCallback((i: number) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(i)) {
        if (next.size > 1) next.delete(i); // mantém ao menos 1
      } else {
        next.add(i);
      }
      return next;
    });
  }, []);

  const selectAll = useCallback(
    () => setSelected(new Set(Array.from({ length: total }, (_, i) => i))),
    [total],
  );
  const clearAll = useCallback(() => setSelected(new Set([0])), []);

  const handleConfirm = () => {
    if (selected.size === total) {
      onConfirm(null);   // todas
    } else {
      onConfirm(Array.from(selected).sort((a, b) => a - b));
    }
  };

  const selectedCount = selected.size;
  const fmtLabel = FORMAT_LABELS[format] ?? format.toUpperCase();
  const fmtBadge = FORMAT_BADGE[format] ?? '';

  // Single-page preview
  const singlePreviewSrc = useMemo(() => buildSlidePreview(design, 0, 1), [design]);
  const PREVIEW_W  = 480;
  const previewH   = Math.round(PREVIEW_W * viewport.height / viewport.width);
  const previewScale = PREVIEW_W / viewport.width;

  return createPortal(
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget && !exporting) onClose(); }}
    >
      <div className="relative flex flex-col rounded-2xl border border-[#2a2a33] bg-[#0d0d12] shadow-2xl shadow-black/70 w-full max-w-3xl mx-4 overflow-hidden max-h-[90vh]">

        {/* ── Header ── */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-[#1d1d24] shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className={`rounded-md border px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider shrink-0 ${fmtBadge}`}>
              {fmtLabel}
            </span>
            <span className="text-sm font-medium text-neutral-200 truncate">{title}</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={exporting}
            className="ml-3 shrink-0 rounded-lg p-1.5 text-neutral-500 hover:bg-white/[0.06] hover:text-white transition-colors disabled:opacity-40"
          >
            <X size={15} />
          </button>
        </div>

        {/* ── Barra de seleção (multi-slide) ── */}
        {multiSlide && total > 1 && (
          <div className="flex items-center gap-3 px-5 py-2 border-b border-[#1d1d24] shrink-0 bg-[#0a0a0d]">
            <p className="text-xs text-neutral-500">
              <span className="text-neutral-200 font-semibold">{selectedCount}</span> de {total} páginas selecionadas
            </p>
            <div className="ml-auto flex items-center gap-2.5">
              <button
                type="button"
                onClick={selectAll}
                className="text-[11px] text-orange-400 hover:text-orange-300 transition-colors"
              >
                Todas
              </button>
              <span className="text-neutral-700 text-[10px]">·</span>
              <button
                type="button"
                onClick={clearAll}
                className="text-[11px] text-neutral-500 hover:text-neutral-300 transition-colors"
              >
                Limpar
              </button>
            </div>
          </div>
        )}

        {/* ── Conteúdo: grid de thumbs ou preview único ── */}
        <div
          className="overflow-auto flex-1 p-5"
          style={{ scrollbarWidth: 'thin', scrollbarColor: '#2a2a33 transparent' }}
        >
          {multiSlide && total > 1 ? (
            <div className="flex flex-wrap gap-3">
              {Array.from({ length: total }, (_, i) => (
                <SlideThumb
                  key={i}
                  html={design}
                  slideIndex={i}
                  total={total}
                  viewport={viewport}
                  selected={selected.has(i)}
                  onClick={() => togglePage(i)}
                />
              ))}
            </div>
          ) : (
            /* Preview de design único */
            <div className="flex justify-center">
              <div
                className="rounded-xl overflow-hidden ring-1 ring-[#2a2a33]"
                style={{ width: PREVIEW_W, height: previewH, background: '#08080f' }}
              >
                <iframe
                  srcDoc={singlePreviewSrc}
                  width={viewport.width}
                  height={viewport.height}
                  style={{
                    width:           `${viewport.width}px`,
                    height:          `${viewport.height}px`,
                    transform:       `scale(${previewScale})`,
                    transformOrigin: 'top left',
                    border:          0,
                    display:         'block',
                    pointerEvents:   'none',
                  }}
                  sandbox="allow-scripts allow-same-origin"
                  title="Preview do design"
                />
              </div>
            </div>
          )}
        </div>

        {/* ── Footer ── */}
        <div className="flex items-center justify-end gap-2.5 px-5 py-3.5 border-t border-[#1d1d24] shrink-0 bg-[#0a0a0d]">
          <button
            type="button"
            onClick={onClose}
            disabled={exporting}
            className="rounded-lg border border-[#2a2a33] px-4 py-2 text-xs text-neutral-400 hover:bg-white/[0.04] hover:text-neutral-200 transition-colors disabled:opacity-40"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={exporting || selectedCount === 0}
            className="inline-flex items-center gap-1.5 rounded-lg bg-orange-500 px-5 py-2 text-xs font-semibold text-white hover:bg-orange-400 active:bg-orange-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {exporting ? (
              <><Loader2 size={12} className="animate-spin" />Exportando...</>
            ) : (
              <>
                <Download size={12} />
                {multiSlide && total > 1
                  ? `Baixar ${selectedCount} página${selectedCount !== 1 ? 's' : ''}`
                  : `Baixar ${fmtLabel}`}
              </>
            )}
          </button>
        </div>

      </div>
    </div>,
    document.body,
  );
};

export default ExportDialog;
