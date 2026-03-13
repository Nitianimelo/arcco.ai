import React, { useState } from 'react';
import { FileText, Download, Loader2, Eye } from 'lucide-react';

interface TextDocCardProps {
  title: string;
  content: string;
  onOpenPreview?: (title: string, content: string) => void;
}

async function downloadExport(text: string, title: string, format: 'docx' | 'pdf') {
  const res = await fetch('/api/agent/export-doc', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, title, format }),
  });
  if (!res.ok) throw new Error(await res.text());
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${title.replace(/\s+/g, '_')}.${format}`;
  a.click();
  URL.revokeObjectURL(url);
}

const TextDocCard: React.FC<TextDocCardProps> = ({ title, content, onOpenPreview }) => {
  const [loading, setLoading] = useState<'docx' | 'pdf' | null>(null);
  const [error, setError] = useState<string | null>(null);

  const preview = content.slice(0, 160).trim();

  const handleDownload = async (fmt: 'docx' | 'pdf') => {
    setLoading(fmt);
    setError(null);
    try {
      await downloadExport(content, title, fmt);
    } catch (e: any) {
      setError(`Erro ao gerar ${fmt.toUpperCase()}: ${e.message}`);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="my-3 rounded-xl border border-[#2a2a2a] bg-[#111113] overflow-hidden shadow-lg w-full max-w-md group hover:border-indigo-500/30 transition-all duration-200">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-[#1e1e1e]">
        <div className="p-2 bg-indigo-500/10 rounded-lg">
          <FileText size={16} className="text-indigo-400" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-neutral-100 truncate">{title}</p>
          <p className="text-[10px] text-neutral-500 mt-0.5">Documento gerado</p>
        </div>
      </div>

      {/* Preview snippet */}
      <div className="px-4 py-3">
        <p className="text-xs text-neutral-400 leading-relaxed line-clamp-3">
          {preview}{content.length > 160 ? '...' : ''}
        </p>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 px-4 pb-3">
        {onOpenPreview && (
          <button
            onClick={() => onOpenPreview(title, content)}
            className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition-colors"
          >
            <Eye size={13} />
            Preview
          </button>
        )}
        <button
          onClick={() => handleDownload('docx')}
          disabled={!!loading}
          className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-[#1a1a1a] hover:bg-[#222] border border-[#2a2a2a] text-neutral-400 hover:text-neutral-200 text-xs font-medium transition-all disabled:opacity-50"
        >
          {loading === 'docx' ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
          DOCX
        </button>
        <button
          onClick={() => handleDownload('pdf')}
          disabled={!!loading}
          className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-[#1a1a1a] hover:bg-[#222] border border-[#2a2a2a] text-neutral-400 hover:text-neutral-200 text-xs font-medium transition-all disabled:opacity-50"
        >
          {loading === 'pdf' ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
          PDF
        </button>
      </div>

      {error && (
        <p className="px-4 pb-3 text-[10px] text-red-400">{error}</p>
      )}
    </div>
  );
};

export default TextDocCard;
