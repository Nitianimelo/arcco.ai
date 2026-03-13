import React, { useRef, useEffect, useState } from 'react';
import { BrainCircuit, CheckCircle2, ChevronDown, Loader2, Sparkles } from 'lucide-react';

export interface ThoughtStep {
  label: string;
  status: 'done' | 'running' | 'pending';
  /** true = raciocínio do LLM em texto livre (não um step de ação) */
  isThought?: boolean;
}

interface AgentThoughtPanelProps {
  steps: ThoughtStep[];
  isExpanded: boolean;
  onToggle: () => void;
  elapsedSeconds: number;
}

const stripEmoji = (text: string) =>
  text.replace(/[\p{Emoji_Presentation}\p{Extended_Pictographic}\u200d\ufe0f]/gu, '').trim();

const AgentThoughtPanel: React.FC<AgentThoughtPanelProps> = ({
  steps,
  isExpanded,
  onToggle,
  elapsedSeconds,
}) => {
  const doneCount = steps.filter(s => s.status === 'done').length;
  const isRunning = steps.some(s => s.status === 'running');
  const allDone = doneCount === steps.length && steps.length > 0;

  // Local state: whether to show full list when done (default compact)
  const [showFullWhenDone, setShowFullWhenDone] = useState(false);

  // Reset to compact when a new run starts
  useEffect(() => {
    if (isRunning) setShowFullWhenDone(false);
  }, [isRunning]);

  const prevCountRef = useRef(0);
  useEffect(() => { prevCountRef.current = steps.length; }, [steps.length]);

  const progress = steps.length > 0 ? (doneCount / steps.length) * 100 : 0;
  const actionSteps = steps.filter(s => !s.isThought);

  const headerLabel = isRunning
    ? 'Pensando...'
    : allDone
    ? `Concluído em ${elapsedSeconds}s`
    : 'Processo do Agente';

  const handleHeaderClick = () => {
    if (allDone) {
      setShowFullWhenDone(p => !p);
    } else {
      onToggle();
    }
  };

  const showList = allDone ? showFullWhenDone : isExpanded;

  return (
    <div className={`rounded-xl border bg-[#0F0F0F] overflow-hidden my-2 w-full transition-all duration-500 ${
      isRunning ? 'animate-border-breathe' : allDone ? 'border-emerald-500/15' : 'border-[#262626]'
    }`}>

      {/* Header */}
      <button
        onClick={handleHeaderClick}
        className={`w-full flex items-center justify-between px-4 py-2.5 hover:bg-[#151515] transition-all group relative overflow-hidden ${
          allDone && !isRunning ? 'animate-success-flash' : ''
        }`}
      >
        <div className="flex items-center gap-2.5">
          {isRunning ? (
            <div className="w-2 h-2 rounded-full bg-indigo-400 animate-ring-pulse shrink-0" />
          ) : allDone ? (
            <CheckCircle2 size={13} className="text-emerald-500 animate-check-pop shrink-0" />
          ) : (
            <BrainCircuit size={13} className="text-indigo-400 shrink-0" />
          )}

          <span className={`text-xs font-medium transition-colors ${
            isRunning
              ? 'shimmer-text text-indigo-300'
              : allDone
              ? 'text-emerald-400/80'
              : 'text-neutral-400 group-hover:text-neutral-300'
          }`}>
            {headerLabel}
          </span>

          {/* Progress pill — while running */}
          {!allDone && (
            <span className="text-[10px] text-neutral-600 bg-[#1a1a1a] px-1.5 py-0.5 rounded-full font-mono">
              {doneCount}/{steps.length}
            </span>
          )}

          {/* Step count pill — when done */}
          {allDone && (
            <span className="text-[10px] text-neutral-600 bg-[#1a1a1a] px-1.5 py-0.5 rounded-full font-mono">
              {actionSteps.length} etapas
            </span>
          )}
        </div>

        <ChevronDown
          size={13}
          className={`text-neutral-600 transition-transform duration-300 ${showList ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Micro progress bar — only while running */}
      {isRunning && (
        <div className="h-[1px] bg-[#1a1a1a] relative overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-indigo-500/40 via-violet-500/50 to-indigo-500/40 transition-all duration-700 ease-out"
            style={{ width: `${Math.max(progress, 8)}%` }}
          />
        </div>
      )}

      {/* Compact pills — when done and list collapsed */}
      {allDone && !showList && actionSteps.length > 0 && (
        <div className="px-4 pb-3 pt-2 border-t border-[#1a1a1a] flex flex-wrap gap-1.5">
          {actionSteps.map((step, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-[#161616] border border-[#262626] text-[10px] text-neutral-500 max-w-[190px]"
              title={stripEmoji(step.label)}
            >
              <CheckCircle2 size={9} className="text-emerald-500/60 shrink-0" />
              <span className="truncate">{stripEmoji(step.label)}</span>
            </span>
          ))}
        </div>
      )}

      {/* Full steps list */}
      {showList && steps.length > 0 && (
        <div className="px-4 pb-3 pt-2 space-y-2 border-t border-[#1a1a1a] relative">

          {/* Timeline line */}
          <div className="absolute left-[22px] top-4 bottom-4 w-[1px] bg-gradient-to-b from-[#262626] via-[#262626] to-transparent pointer-events-none" />

          {steps.map((step, i) => {
            const isNew = i >= prevCountRef.current;

            if (step.isThought) {
              return (
                <div
                  key={i}
                  className={`rounded-lg border border-violet-500/20 bg-violet-500/5 px-3 py-2.5 transition-all duration-300 ml-[26px] ${
                    step.status === 'pending' ? 'opacity-25' : 'opacity-100'
                  } ${step.status === 'running' ? 'animate-thought-glow' : ''} ${
                    isNew ? 'animate-step-enter' : ''
                  }`}
                  style={isNew ? { animationDelay: `${(i - prevCountRef.current) * 80}ms` } : undefined}
                >
                  <div className="flex items-center gap-1.5 mb-1.5">
                    {step.status === 'running' ? (
                      <Sparkles size={11} className="text-violet-400 animate-pulse" />
                    ) : (
                      <Sparkles size={11} className="text-violet-600" />
                    )}
                    <span className="text-[9px] font-semibold uppercase tracking-widest text-violet-500">
                      Raciocínio
                    </span>
                  </div>
                  <p className={`text-[11px] leading-relaxed italic whitespace-pre-wrap ${
                    step.status === 'running' ? 'text-violet-200' : 'text-violet-400/70'
                  }`}>
                    {step.label}
                  </p>
                </div>
              );
            }

            return (
              <div
                key={i}
                className={`flex items-start gap-2.5 transition-all duration-300 relative ${
                  step.status === 'pending' ? 'opacity-25' : 'opacity-100'
                } ${isNew ? 'animate-step-enter' : ''}`}
                style={isNew ? { animationDelay: `${(i - prevCountRef.current) * 80}ms` } : undefined}
              >
                <div className="mt-0.5 shrink-0 relative z-10">
                  {step.status === 'done' && (
                    <span className="animate-check-pop inline-flex">
                      <CheckCircle2 size={13} className="text-emerald-500" />
                    </span>
                  )}
                  {step.status === 'running' && (
                    <span className="inline-flex">
                      <Loader2 size={13} className="text-indigo-400 animate-spin" />
                    </span>
                  )}
                  {step.status === 'pending' && (
                    <div className="w-3 h-3 rounded-full border border-[#333]" />
                  )}
                </div>
                <span className={`text-xs leading-relaxed transition-colors duration-300 ${
                  step.status === 'running'
                    ? 'text-neutral-200'
                    : step.status === 'done'
                    ? 'text-neutral-400'
                    : 'text-neutral-700'
                }`}>
                  {stripEmoji(step.label)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default AgentThoughtPanel;
