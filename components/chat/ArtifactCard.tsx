
import React, { useState } from 'react';
import { FileText, ChevronDown, ChevronUp, Copy, Check, Code, Box, Eye } from 'lucide-react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface ArtifactCardProps {
    title: string;
    content: string;
    language: string;
    type?: 'code' | 'json' | 'text';
    onOpenPreview?: () => void;
}

export const ArtifactCard: React.FC<ArtifactCardProps> = ({ title, content, language, type = 'code', onOpenPreview }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [isCopied, setIsCopied] = useState(false);

    const handleCopy = () => {
        navigator.clipboard.writeText(content);
        setIsCopied(true);
        setTimeout(() => setIsCopied(false), 2000);
    };

    const getIcon = () => {
        if (type === 'json') return <Box size={16} className="text-amber-400" />;
        if (language === 'python' || language === 'py') return <code className="text-blue-400 font-bold text-xs">PY</code>;
        if (language === 'typescript' || language === 'ts' || language === 'tsx') return <code className="text-blue-400 font-bold text-xs">TS</code>;
        return <Code size={16} className="text-indigo-400" />;
    };

    return (
        <div className="my-4 rounded-lg border border-[#333] bg-[#0f0f0f] overflow-hidden transition-all duration-200 hover:border-[#444]">
            {/* Header */}
            <div
                className="flex items-center justify-between px-4 py-3 bg-[#1a1a1a] cursor-pointer select-none hover:bg-[#202020]"
                onClick={() => setIsExpanded(!isExpanded)}
            >
                <div className="flex items-center gap-3">
                    <div className="p-1.5 bg-[#252525] rounded-md">
                        {getIcon()}
                    </div>
                    <div>
                        <h4 className="text-sm font-medium text-neutral-200">{title}</h4>
                        <p className="text-[10px] text-neutral-500 font-mono">
                            {language.toUpperCase()} • {content.length} chars
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {onOpenPreview && (
                        <button
                            onClick={(e) => { e.stopPropagation(); onOpenPreview(); }}
                            className="p-1.5 hover:bg-[#333] rounded text-indigo-400 hover:text-indigo-300 transition-colors flex items-center gap-1"
                            title="Visualizar lado a lado"
                        >
                            <Eye size={14} />
                        </button>
                    )}
                    <button
                        onClick={(e) => { e.stopPropagation(); handleCopy(); }}
                        className="p-1.5 hover:bg-[#333] rounded text-neutral-400 hover:text-white transition-colors"
                        title="Copy content"
                    >
                        {isCopied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
                    </button>
                    <div className={`transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}>
                        <ChevronDown size={16} className="text-neutral-500" />
                    </div>
                </div>
            </div>

            {/* Content Body */}
            {isExpanded && (
                <div className="border-t border-[#333] bg-[#0d0d0d]">
                    <SyntaxHighlighter
                        language={language}
                        style={vscDarkPlus}
                        customStyle={{
                            margin: 0,
                            padding: '1rem',
                            fontSize: '0.8rem',
                            lineHeight: '1.5',
                            background: 'transparent'
                        }}
                        wrapLines={true}
                        showLineNumbers={true}
                    >
                        {content}
                    </SyntaxHighlighter>
                </div>
            )}
        </div>
    );
};
