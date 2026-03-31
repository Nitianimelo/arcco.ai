import React from 'react';
import { Monitor } from 'lucide-react';
import PresentationCard from './PresentationCard';

function extractTitle(html: string, fallback: string): string {
  return html.match(/<title[^>]*>([^<]+)<\/title>/i)?.[1]?.trim() || fallback;
}

interface DesignGalleryProps {
  designs: string[];
  isStreaming?: boolean;
  onOpenPreview?: (index: number) => void;
}

const DesignGallery: React.FC<DesignGalleryProps> = ({ designs, isStreaming = false, onOpenPreview }) => {
  if (isStreaming) {
    return (
      <div className="my-4 rounded-2xl border border-orange-500/20 bg-[#0d0d0f] overflow-hidden shadow-lg w-full animate-pulse">
        <div className="flex items-center gap-3 px-4 py-3 bg-orange-500/8 border-b border-orange-500/20">
          <Monitor size={15} className="text-orange-300" />
          <span className="text-xs font-semibold text-orange-100">Construindo artes editaveis...</span>
        </div>
        <div className="flex items-center justify-center h-48 text-orange-300/50 text-xs">
          O agente esta desenhando multiplas composicoes visuais...
        </div>
      </div>
    );
  }

  return (
    <div className="my-4 rounded-2xl border border-[#d97706]/20 bg-[#0a0a0d] overflow-hidden shadow-xl shadow-orange-500/10 w-full">
      <div className="flex items-center gap-2 px-4 py-2.5 bg-[#111118] border-b border-orange-500/20">
        <Monitor size={14} className="text-orange-300" />
        <span className="text-xs font-semibold text-orange-100">Galeria de Artes</span>
        <span className="ml-auto text-[10px] text-neutral-500 whitespace-nowrap">
          {designs.length} {designs.length === 1 ? 'arte' : 'artes'}
        </span>
      </div>
      <div className="flex flex-col gap-4 p-4">
        {designs.map((design, index) => {
          const designTitle = extractTitle(design, `Arte ${index + 1}`);
          return (
          <div key={index} className="rounded-2xl border border-[#1d1d24] bg-[#0d0d12] p-3">
            <div className="mb-2 text-[10px] uppercase tracking-[0.18em] text-neutral-500 truncate">
              {designTitle}
            </div>
            <PresentationCard
              html={design}
              isStreaming={false}
              onOpenPreview={() => onOpenPreview?.(index)}
            />
          </div>
          );
        })}
      </div>
    </div>
  );
};

export default DesignGallery;
