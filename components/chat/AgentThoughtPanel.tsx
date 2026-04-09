import React, { useEffect, useState, useRef } from 'react';

export interface ThoughtStep {
  label: string;
  status: 'done' | 'running' | 'pending';
  /** true = raciocínio do LLM em texto livre (não um step de ação) */
  isThought?: boolean;
  kind?: 'step' | 'thought' | 'policy' | 'replan' | 'workflow';
  meta?: any;
}

interface AgentThoughtPanelProps {
  steps: ThoughtStep[];
  isExpanded: boolean;
  onToggle: () => void;
  elapsedSeconds: number;
}

// Remove emojis e caracteres Unicode desnecessários
const stripEmoji = (text: string) =>
  text.replace(/[\p{Emoji_Presentation}\p{Extended_Pictographic}\u200d\ufe0f]/gu, '').trim();

// ────────────────────────────────────────────────────────────
// Step Row — linha individual do log
// ────────────────────────────────────────────────────────────

const StepRow: React.FC<{ step: ThoughtStep; isNew: boolean; delay: number }> = ({
  step,
  isNew,
  delay,
}) => {
  const label = stripEmoji(step.label);

  // Bloco de raciocínio (thought) — indentado, sem indicador
  if (step.isThought) {
    return (
      <div
        className={`pl-5 border-l border-[#242424] ${isNew ? 'animate-step-enter' : ''}`}
        style={isNew ? { animationDelay: `${delay}ms` } : undefined}
      >
        <p className="text-[11px] leading-relaxed text-neutral-700 italic font-mono tracking-wide">
          {label}
          {step.status === 'running' && (
            <span className="animate-cursor-blink ml-0.5 not-italic text-neutral-500">▌</span>
          )}
        </p>
      </div>
    );
  }

  // Step de ação
  const borderClass =
    step.status === 'running'
      ? 'border-l-2 border-neutral-300'
      : step.status === 'done'
      ? 'border-l border-[#333338]'
      : 'border-l border-[#222226]';

  const textClass =
    step.status === 'running'
      ? 'text-neutral-100'
      : step.status === 'done'
      ? 'text-neutral-500'
      : 'text-neutral-700';

  return (
    <div
      className={`pl-4 ${borderClass} ${isNew ? 'animate-step-enter' : ''}`}
      style={isNew ? { animationDelay: `${delay}ms` } : undefined}
    >
      <span className={`text-xs font-mono tracking-wide ${textClass}`}>
        {step.status === 'done' && (
          <span className="mr-2 text-neutral-600">✓</span>
        )}
        {step.status === 'pending' && (
          <span className="mr-2 text-neutral-700">·</span>
        )}
        {label}
        {step.status === 'running' && (
          <span className="animate-cursor-blink ml-0.5 text-neutral-400">▌</span>
        )}
      </span>
    </div>
  );
};

// ────────────────────────────────────────────────────────────
// Componente principal
// ────────────────────────────────────────────────────────────

const AgentThoughtPanel: React.FC<AgentThoughtPanelProps> = ({
  steps,
  isExpanded,
  onToggle,
  elapsedSeconds,
}) => {
  const isRunning = steps.some(s => s.status === 'running');
  const allDone = steps.length > 0 && steps.every(s => s.status === 'done');
  const doneCount = steps.filter(s => s.status === 'done').length;
  const actionSteps = steps.filter(s => !s.isThought);

  const [showList, setShowList] = useState(true);

  // Expande automaticamente quando inicia
  useEffect(() => {
    if (isRunning) setShowList(true);
  }, [isRunning]);

  // Controla animação dos novos steps
  const prevCountRef = useRef(0);
  useEffect(() => {
    prevCountRef.current = steps.length;
  }, [steps.length]);

  const handleHeaderClick = () => {
    if (allDone) setShowList(p => !p);
    else onToggle();
  };

  return (
    <div className={`my-2 w-full rounded-lg border overflow-hidden transition-colors duration-500 ${
      isRunning ? 'bg-[#111114] border-[#2e2e34]' : allDone ? 'bg-[#0f0f12] border-[#252528]' : 'bg-[#0f0f12] border-[#252528]'
    }`}>

      {/* ── Header ───────────────────────────────────────────── */}
      <button
        onClick={handleHeaderClick}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/[0.02] transition-colors"
      >
        <span className="font-mono text-xs text-neutral-500 tracking-wide">
          agente
          <span className="mx-2 text-neutral-800">·</span>
          {isRunning ? (
            <span className="text-neutral-300">
              pensando
              <span className="animate-cursor-blink ml-0.5 text-neutral-400">▌</span>
            </span>
          ) : allDone ? (
            <span className="text-neutral-500">
              concluído em {elapsedSeconds}s
            </span>
          ) : (
            <span className="text-neutral-600">iniciando</span>
          )}
        </span>

        <span className="font-mono text-[10px] text-neutral-600 tabular-nums">
          {isRunning && steps.length > 0
            ? `${doneCount} / ${actionSteps.length}`
            : allDone
            ? `${actionSteps.length} etapas`
            : null
          }
        </span>
      </button>

      {/* ── Linha divisória ──────────────────────────────────── */}
      {showList && steps.length > 0 && (
        <div className="h-px bg-[#1e1e22]" />
      )}

      {/* ── Lista de steps ───────────────────────────────────── */}
      {showList && steps.length > 0 && (
        <div className="px-5 py-3 space-y-2.5">
          {steps.map((step, i) => {
            const isNew = i >= prevCountRef.current;
            const delay = isNew ? (i - prevCountRef.current) * 60 : 0;
            return <StepRow key={i} step={step} isNew={isNew} delay={delay} />;
          })}
        </div>
      )}
    </div>
  );
};

export default AgentThoughtPanel;
