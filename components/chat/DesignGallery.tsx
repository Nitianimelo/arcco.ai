import React, { useState } from 'react';
import { ChevronLeft, ChevronRight, Monitor } from 'lucide-react';
import PresentationCard from './PresentationCard';

interface DesignGalleryProps {
  designs: string[];
  isStreaming?: boolean;
  onOpenPreview?: (html: string) => void;
}

const DesignGallery: React.FC<DesignGalleryProps> = ({ designs, isStreaming = false, onOpenPreview }) => {
  const [activeIndex, setActiveIndex] = useState(0);
  const total = designs.length;

  const goPrev = () => setActiveIndex((i) => (i > 0 ? i - 1 : total - 1));
  const goNext = () => setActiveIndex((i) => (i < total - 1 ? i + 1 : 0));

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

      {/* ── Thumbnail strip + navigation ── */}
      <div className="flex items-center gap-2 px-4 py-2.5 bg-[#111118] border-b border-orange-500/20">
        <Monitor size={14} className="text-orange-300" />
        <span className="text-xs font-semibold text-orange-100">Galeria de Artes</span>

        <div className="flex items-center gap-1.5 ml-auto">
          <button
            onClick={goPrev}
            className="p-1 rounded-lg bg-[#1a1a2a] border border-[#333] text-neutral-500 hover:text-white transition-colors"
          >
            <ChevronLeft size={14} />
          </button>

          {/* Thumbnails */}
          <div className="flex items-center gap-1 overflow-x-auto max-w-[280px] sm:max-w-none">
            {designs.map((_, i) => (
              <button
                key={i}
                onClick={() => setActiveIndex(i)}
                className={`flex-shrink-0 w-8 h-8 rounded-lg border-2 text-[11px] font-semibold transition-all animate-gallery-thumb ${
                  i === activeIndex
                    ? 'border-orange-500 bg-orange-500/15 text-orange-200'
                    : 'border-[#2a2a34] bg-[#111] text-neutral-600 hover:border-orange-500/30 hover:text-neutral-400'
                }`}
                style={{ animationDelay: `${i * 50}ms` }}
              >
                {i + 1}
              </button>
            ))}
          </div>

          <button
            onClick={goNext}
            className="p-1 rounded-lg bg-[#1a1a2a] border border-[#333] text-neutral-500 hover:text-white transition-colors"
          >
            <ChevronRight size={14} />
          </button>

          <span className="text-[10px] text-neutral-500 ml-1 whitespace-nowrap">
            {activeIndex + 1} de {total}
          </span>
        </div>
      </div>

      {/* ── Active design ── */}
      <PresentationCard
        key={activeIndex}
        html={designs[activeIndex]}
        isStreaming={false}
        onOpenPreview={onOpenPreview}
      />
    </div>
  );
};

export default DesignGallery;
