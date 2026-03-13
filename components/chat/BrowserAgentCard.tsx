import React, { useEffect, useState, useRef } from 'react';
import { Globe, Loader2, Lock, ArrowLeft, ArrowRight, RotateCw } from 'lucide-react';

interface BrowserAction {
    status: 'navigating' | 'reading' | 'done' | 'error';
    url: string;
    title: string;
}

interface BrowserAgentCardProps {
    action: BrowserAction;
}

/* Simula conteúdo de uma página sendo carregada progressivamente */
const FAKE_LINES = [
    { w: '72%', delay: 0.3 },
    { w: '90%', delay: 0.5 },
    { w: '55%', delay: 0.7 },
    { w: '80%', delay: 0.9 },
    { w: '65%', delay: 1.1 },
    { w: '95%', delay: 1.3 },
    { w: '40%', delay: 1.5 },
    { w: '85%', delay: 1.7 },
    { w: '60%', delay: 1.9 },
    { w: '75%', delay: 2.1 },
];

export const BrowserAgentCard: React.FC<BrowserAgentCardProps> = ({ action }) => {
    const [cursorPos, setCursorPos] = useState({ x: 50, y: 30 });
    const [visibleLines, setVisibleLines] = useState(0);
    const [scrollY, setScrollY] = useState(0);
    const animRef = useRef<number>(0);

    const isLoading = action.status === 'navigating' || action.status === 'reading';
    const isDone = action.status === 'done';
    const isError = action.status === 'error';

    // Extrai domínio
    let domain = '';
    try { domain = new URL(action.url).hostname; } catch { domain = action.url.slice(0, 40); }

    // ── Animação do cursor (movimento suave tipo mouse real) ──
    useEffect(() => {
        if (!isLoading) return;
        let frame = 0;
        const move = () => {
            frame++;
            // Movimento orgânico tipo Lissajous
            const x = 50 + Math.sin(frame * 0.025) * 35 + Math.cos(frame * 0.041) * 15;
            const y = 40 + Math.cos(frame * 0.031) * 25 + Math.sin(frame * 0.019) * 10;
            setCursorPos({ x: Math.max(5, Math.min(95, x)), y: Math.max(10, Math.min(85, y)) });
            animRef.current = requestAnimationFrame(move);
        };
        animRef.current = requestAnimationFrame(move);
        return () => cancelAnimationFrame(animRef.current);
    }, [isLoading]);

    // ── Linhas de conteúdo aparecendo progressivamente ──
    useEffect(() => {
        if (!isLoading && !isDone) return;
        const timers: NodeJS.Timeout[] = [];
        FAKE_LINES.forEach((_, i) => {
            timers.push(setTimeout(() => setVisibleLines(i + 1), (i + 1) * 250));
        });
        return () => timers.forEach(clearTimeout);
    }, [isLoading, isDone]);

    // ── Scroll automático da "página" ──
    useEffect(() => {
        if (!isLoading) return;
        const interval = setInterval(() => {
            setScrollY(prev => (prev + 0.4) % 100);
        }, 50);
        return () => clearInterval(interval);
    }, [isLoading]);

    return (
        <div className="my-3 w-full max-w-xl">
            <div className={`
        rounded-xl border overflow-hidden transition-all duration-500
        ${isLoading ? 'border-indigo-500/30 shadow-xl shadow-indigo-500/8' : ''}
        ${isDone ? 'border-green-500/25 shadow-lg shadow-green-500/5' : ''}
        ${isError ? 'border-red-500/25' : ''}
        bg-[#0a0a0a]
      `}>

                {/* ── Tab bar (Chrome-like) ── */}
                <div className="flex items-center bg-[#1a1a1a] border-b border-neutral-800/50 px-2 pt-2 pb-0">
                    {/* Tab ativa */}
                    <div className="flex items-center gap-1.5 bg-[#0a0a0a] rounded-t-lg px-3 py-1.5 max-w-[200px] border border-neutral-800 border-b-0 relative -mb-px">
                        {isLoading ? (
                            <Loader2 size={11} className="text-indigo-400 animate-spin shrink-0" />
                        ) : (
                            <Globe size={11} className={isDone ? 'text-green-400' : 'text-red-400'} />
                        )}
                        <span className="text-[11px] text-neutral-400 truncate">{domain || 'Nova aba'}</span>
                    </div>
                    {/* Semáforo (macOS) */}
                    <div className="flex items-center gap-1.5 ml-auto pr-2 pb-1.5">
                        <div className={`w-2.5 h-2.5 rounded-full transition-colors ${isError ? 'bg-neutral-700' : 'bg-[#ff5f57]'}`} />
                        <div className={`w-2.5 h-2.5 rounded-full transition-colors ${isError ? 'bg-neutral-700' : isLoading ? 'bg-[#ffbd2e] animate-pulse' : 'bg-[#ffbd2e]'}`} />
                        <div className={`w-2.5 h-2.5 rounded-full transition-colors ${isError ? 'bg-neutral-700' : 'bg-[#28c840]'}`} />
                    </div>
                </div>

                {/* ── URL bar ── */}
                <div className="flex items-center gap-2 px-3 py-1.5 bg-[#111] border-b border-neutral-800/40">
                    <div className="flex items-center gap-1 text-neutral-700">
                        <ArrowLeft size={12} />
                        <ArrowRight size={12} />
                        <RotateCw size={12} className={isLoading ? 'animate-spin text-neutral-500' : ''} />
                    </div>
                    <div className="flex-1 flex items-center gap-1.5 bg-[#0a0a0a] rounded-md px-2.5 py-1 border border-neutral-800/50">
                        <Lock size={10} className={isDone ? 'text-green-500' : 'text-neutral-600'} />
                        <span className="text-[11px] text-neutral-500 truncate font-mono select-all">
                            {action.url}
                        </span>
                    </div>
                </div>

                {/* ── Viewport (conteúdo da "página") ── */}
                <div className="relative h-60 overflow-hidden bg-[#0d0d0d]">

                    {/* Linhas de conteúdo simulado */}
                    <div
                        className="absolute inset-x-0 px-5 pt-4 space-y-2.5 transition-transform duration-100"
                        style={{ transform: `translateY(-${scrollY * 0.6}px)` }}
                    >
                        {/* "Header" da página */}
                        <div className="h-5 rounded bg-neutral-800/50 w-[40%] mb-4" style={{
                            opacity: visibleLines >= 1 ? 1 : 0,
                            transition: 'opacity 0.3s ease'
                        }} />

                        {/* Linhas de texto */}
                        {FAKE_LINES.map((line, i) => (
                            <div
                                key={i}
                                className="h-2 rounded-full"
                                style={{
                                    width: line.w,
                                    opacity: visibleLines > i ? 1 : 0,
                                    transition: 'opacity 0.4s ease',
                                    background: visibleLines > i
                                        ? 'linear-gradient(90deg, rgba(99,102,241,0.12) 0%, rgba(99,102,241,0.06) 100%)'
                                        : 'transparent',
                                }}
                            />
                        ))}

                        {/* Bloco "imagem" placeholder */}
                        <div className="h-16 rounded-lg bg-neutral-800/30 w-[70%] mt-3" style={{
                            opacity: visibleLines >= 6 ? 1 : 0,
                            transition: 'opacity 0.5s ease'
                        }} />

                        {/* Mais linhas */}
                        {FAKE_LINES.slice(0, 5).map((line, i) => (
                            <div
                                key={`b-${i}`}
                                className="h-2 rounded-full"
                                style={{
                                    width: `${parseInt(line.w) - 10}%`,
                                    opacity: visibleLines >= 8 ? 1 : 0,
                                    transition: 'opacity 0.4s ease',
                                    background: visibleLines >= 8
                                        ? 'linear-gradient(90deg, rgba(99,102,241,0.08) 0%, rgba(99,102,241,0.03) 100%)'
                                        : 'transparent',
                                }}
                            />
                        ))}
                    </div>

                    {/* ── Cursor animado ── */}
                    {isLoading && (
                        <div
                            className="absolute z-20 pointer-events-none transition-all duration-[180ms]"
                            style={{
                                left: `${cursorPos.x}%`,
                                top: `${cursorPos.y}%`,
                            }}
                        >
                            {/* SVG cursor (seta) */}
                            <svg width="16" height="20" viewBox="0 0 16 20" fill="none" className="drop-shadow-lg">
                                <path
                                    d="M1 1L1 15L5.5 11L9.5 18L12 17L8 10L13.5 9.5L1 1Z"
                                    fill="white"
                                    stroke="#111"
                                    strokeWidth="1.2"
                                />
                            </svg>
                            {/* Ripple ao "clicar" */}
                            <div className="absolute -top-1 -left-1 w-5 h-5 rounded-full bg-indigo-400/20 animate-ping" />
                        </div>
                    )}

                    {/* Overlay gradiente no fundo */}
                    <div className="absolute bottom-0 inset-x-0 h-16 bg-gradient-to-t from-[#0d0d0d] to-transparent pointer-events-none" />

                    {/* Status badge */}
                    <div className="absolute bottom-3 left-4 z-10">
                        <div className={`
              flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-medium backdrop-blur-sm
              ${isLoading ? 'bg-indigo-500/15 text-indigo-300 border border-indigo-500/20' : ''}
              ${isDone ? 'bg-green-500/15 text-green-300 border border-green-500/20' : ''}
              ${isError ? 'bg-red-500/15 text-red-300 border border-red-500/20' : ''}
            `}>
                            {isLoading && <Loader2 size={10} className="animate-spin" />}
                            {isLoading ? 'Lendo página...' : isDone ? '✓ Página lida' : '✕ Erro'}
                        </div>
                    </div>
                </div>

                {/* ── Barra de progresso no rodapé ── */}
                {isLoading && (
                    <div className="h-0.5 bg-neutral-900">
                        <div className="h-full bg-gradient-to-r from-indigo-600 via-purple-500 to-indigo-600 rounded-full animate-browser-progress" />
                    </div>
                )}
            </div>
        </div>
    );
};
