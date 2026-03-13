import React, { useEffect, useState, useRef } from 'react';
import { Terminal, Maximize2, Minimize2, Brain, Zap, Eye, CheckCircle2, AlertTriangle, MonitorPlay } from 'lucide-react';

interface AgentTerminalProps {
    isOpen: boolean;
    content: string;
    onClose: () => void;
    status?: string;
    className?: string;
}

interface StepStyle {
    color: string;
    bg: string;
    icon: React.ReactNode;
    pulse: boolean;
}

const STEP_STYLES: Array<{ match: string[]; style: StepStyle }> = [
    {
        match: ['🤔', 'Thought:', 'Pensando'],
        style: { color: 'text-violet-300', bg: 'bg-violet-500/10 border-violet-500/25', icon: <Brain size={14} className="text-violet-400" />, pulse: true },
    },
    {
        match: ['⚡', 'Action:', 'Executando', 'tool_calls'],
        style: { color: 'text-amber-300', bg: 'bg-amber-500/10 border-amber-500/25', icon: <Zap size={14} className="text-amber-400" />, pulse: false },
    },
    {
        match: ['👀', 'Observation:', 'Resultado'],
        style: { color: 'text-cyan-300', bg: 'bg-cyan-500/10 border-cyan-500/25', icon: <Eye size={14} className="text-cyan-400" />, pulse: false },
    },
    {
        match: ['✅', 'cumprida', 'concluído', 'Finalizado'],
        style: { color: 'text-emerald-300', bg: 'bg-emerald-500/10 border-emerald-500/25', icon: <CheckCircle2 size={14} className="text-emerald-400" />, pulse: false },
    },
    {
        match: ['❌', 'Erro'],
        style: { color: 'text-red-300', bg: 'bg-red-500/10 border-red-500/25', icon: <AlertTriangle size={14} className="text-red-400" />, pulse: false },
    },
    {
        match: ['⏳', 'Processando'],
        style: { color: 'text-neutral-400', bg: 'bg-neutral-500/10 border-neutral-700', icon: <MonitorPlay size={14} className="text-neutral-500" />, pulse: true },
    },
];

const DEFAULT_STYLE: StepStyle = {
    color: 'text-neutral-300',
    bg: 'bg-neutral-500/10 border-neutral-500/25',
    icon: <Terminal size={14} className="text-neutral-400" />,
    pulse: false,
};

const getStepStyle = (text: string): StepStyle => {
    for (const { match, style } of STEP_STYLES) {
        if (match.some(m => text.includes(m))) return style;
    }
    return DEFAULT_STYLE;
};

const formatElapsed = (seconds: number): string => {
    if (seconds < 60) return `${seconds}s`;
    return `${Math.floor(seconds / 60)}m${seconds % 60}s`;
};

const AgentTerminal: React.FC<AgentTerminalProps> = ({
    isOpen,
    content,
    onClose,
    status = 'Processando...',
    className,
}) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [elapsed, setElapsed] = useState(0);
    const scrollRef = useRef<HTMLDivElement>(null);
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

    // Reset and start timer when terminal opens
    useEffect(() => {
        if (isOpen) {
            setElapsed(0);
            const start = Date.now();
            timerRef.current = setInterval(() => {
                setElapsed(Math.floor((Date.now() - start) / 1000));
            }, 1000);
        } else {
            if (timerRef.current) clearInterval(timerRef.current);
        }
        return () => {
            if (timerRef.current) clearInterval(timerRef.current);
        };
    }, [isOpen]);

    // Auto-scroll to bottom on new content
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [content]);

    if (!isOpen) return null;

    const lines = content.split('\n');
    const stepLines = lines.filter(l => l.includes('<step>'));
    const isDone = content.includes('✅ Missão cumprida');
    const isError = content.includes('❌ Erro');

    const statusColor = isDone ? 'text-emerald-400' : isError ? 'text-red-400' : 'text-indigo-400 animate-pulse';

    return (
        <div
            className={
                className ||
                `transition-all duration-300 ease-in-out rounded-2xl overflow-hidden border border-[#2a2a2a] bg-[#0c0c0c]/98 backdrop-blur-xl font-mono
        shadow-[0_0_80px_rgba(99,102,241,0.15),0_25px_60px_rgba(0,0,0,0.6)] w-full
        ${isExpanded
                    ? 'fixed inset-4 z-[200] m-0'
                    : 'relative mt-4 h-auto max-h-[300px]'
                }`
            }
        >
            {/* Header — macOS style */}
            <div className="flex items-center justify-between px-4 py-2.5 bg-[#111111] border-b border-[#1f1f1f] select-none">
                <div className="flex items-center gap-3">
                    {/* Traffic lights */}
                    <div className="flex items-center gap-1.5">
                        <button
                            onClick={onClose}
                            className="w-3 h-3 rounded-full bg-[#FF5F57] hover:brightness-110 transition-all group relative"
                            title="Fechar"
                        >
                            <span className="absolute inset-0 flex items-center justify-center text-[7px] text-black/60 opacity-0 group-hover:opacity-100">✕</span>
                        </button>
                        <div className="w-3 h-3 rounded-full bg-[#FFBD2E]" />
                        <button
                            onClick={() => setIsExpanded(!isExpanded)}
                            className="w-3 h-3 rounded-full bg-[#28CA41] hover:brightness-110 transition-all"
                            title="Expandir"
                        />
                    </div>

                    {/* Title */}
                    <div className="flex items-center gap-2">
                        <Terminal size={12} className="text-indigo-400" />
                        <span className="text-neutral-200 text-xs font-semibold tracking-wide">arcco-agent</span>
                        <span className="text-neutral-700 text-xs">—</span>
                        <span className={`text-xs ${statusColor}`}>{status}</span>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    {/* Stats */}
                    <div className="flex items-center gap-2 text-[10px] text-neutral-600 font-mono tabular-nums">
                        <span className={`px-1.5 py-0.5 rounded ${isDone ? 'bg-emerald-500/10 text-emerald-500' : 'bg-indigo-500/10 text-indigo-400'}`}>
                            {stepLines.length} steps
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-neutral-800 text-neutral-500">
                            {formatElapsed(elapsed)}
                        </span>
                    </div>
                    <button
                        onClick={() => setIsExpanded(!isExpanded)}
                        className="p-1 hover:bg-[#222] rounded text-neutral-600 hover:text-neutral-300 transition-colors"
                    >
                        {isExpanded ? <Minimize2 size={12} /> : <Maximize2 size={12} />}
                    </button>
                </div>
            </div>

            {/* Body */}
            <div
                ref={scrollRef}
                className="p-4 h-[calc(100%-41px)] overflow-y-auto overflow-x-hidden space-y-1.5 scrollbar-thin scrollbar-thumb-[#222] scrollbar-track-transparent"
            >
                {/* Shell prompt line */}
                <div className="flex items-center gap-2 text-[11px] mb-3 pb-2.5 border-b border-[#181818]">
                    <span className="text-emerald-400">❯</span>
                    <span className="text-neutral-500">arcco</span>
                    <span className="text-indigo-400 font-medium">--agent</span>
                    <span className="text-neutral-600">--stream</span>
                    <span className="text-neutral-700">--model</span>
                    <span className="text-neutral-600">openrouter</span>
                </div>

                {/* Steps */}
                {lines.map((line, i) => {
                    if (!line.trim()) return null;

                    if (line.includes('<step>')) {
                        const text = line.replace(/<\/?step>/g, '').trim();
                        const style = getStepStyle(text);
                        const isLastActive = !isDone && i === lines.filter(l => l.trim()).length - 1;

                        return (
                            <div
                                key={i}
                                className={`flex items-start gap-3 px-3 py-2.5 rounded-lg border text-[13px] leading-6 ${style.bg} ${style.color}`}
                                style={{ animation: 'slide-in 0.18s ease-out both' }}
                            >
                                <div className={`mt-0.5 flex-shrink-0 ${(style.pulse && isLastActive) ? 'animate-pulse' : ''}`}>
                                    {style.icon}
                                </div>
                                <span className="flex-1">{text}</span>
                                {isLastActive && (
                                    <span className="text-[10px] text-neutral-600 tabular-nums">{formatElapsed(elapsed)}</span>
                                )}
                            </div>
                        );
                    }

                    // Non-step raw lines
                    return (
                        <div key={i} className="text-[10px] text-neutral-700 pl-4 font-mono leading-4">
                            {line}
                        </div>
                    );
                })}

                {/* Cursor blink — only when running */}
                {!isDone && !isError && (
                    <div className="flex items-center gap-2 pt-0.5 pl-3">
                        <span className="inline-block w-1.5 h-3.5 bg-indigo-500/70 rounded-sm animate-pulse" />
                    </div>
                )}

                {/* Done state */}
                {isDone && (
                    <div className="mt-3 pt-2.5 border-t border-[#181818] flex items-center gap-2 text-[11px] text-emerald-500/70">
                        <span>✓</span>
                        <span>Processo concluído em {formatElapsed(elapsed)}</span>
                    </div>
                )}
            </div>
        </div>
    );
};

export default AgentTerminal;
