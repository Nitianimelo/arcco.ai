import React, { useRef } from 'react';
import { Monitor, Eye, Loader2 } from 'lucide-react';

interface PresentationCardProps {
  html: string;
  isStreaming?: boolean;
  onOpenPreview?: (html: string) => void;
}

function extractTitle(html: string) {
  return html.match(/<title[^>]*>([^<]+)<\/title>/i)?.[1] ?? 'Design gerado';
}

const PresentationCard: React.FC<PresentationCardProps> = ({ html, isStreaming = false, onOpenPreview }) => {
  const thumbRef = useRef<HTMLIFrameElement>(null);
  const title = extractTitle(html);

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

  return (
    <div className="my-3 rounded-xl border border-[#2a2a2a] bg-[#111113] overflow-hidden shadow-lg w-full max-w-sm group hover:border-orange-500/30 transition-all duration-200">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-[#1e1e1e]">
        <div className="p-2 bg-orange-500/10 rounded-lg">
          <Monitor size={16} className="text-orange-400" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-neutral-100 truncate">{title}</p>
          <p className="text-[10px] text-neutral-500 mt-0.5">Arte editavel</p>
        </div>
      </div>

      {/* Thumbnail preview */}
      <div
        className="relative h-40 bg-[#0b0b0d] overflow-hidden cursor-pointer"
        onClick={() => onOpenPreview?.(html)}
      >
        <iframe
          ref={thumbRef}
          srcDoc={html}
          className="w-[200%] h-[200%] border-0 origin-top-left pointer-events-none"
          style={{ transform: 'scale(0.5)' }}
          sandbox="allow-scripts allow-same-origin"
          title="Miniatura"
          tabIndex={-1}
        />
        {/* Hover overlay */}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-all duration-200 flex items-center justify-center">
          <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center gap-1.5 px-4 py-2 rounded-lg bg-orange-500/90 text-white text-xs font-medium shadow-lg">
            <Eye size={14} />
            Visualizar
          </div>
        </div>
      </div>

      {/* Action button */}
      <div className="px-4 py-3">
        <button
          onClick={() => onOpenPreview?.(html)}
          className="w-full flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg bg-orange-600 hover:bg-orange-500 text-white text-xs font-medium transition-colors"
        >
          <Eye size={14} />
          Visualizar e editar
        </button>
      </div>
    </div>
  );
};

export default PresentationCard;
