import React, { useState, useEffect, useRef } from 'react';
import { X, Loader2, FileText, FileSpreadsheet, Maximize2, Minimize2 } from 'lucide-react';

interface DocumentPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  data: {
    type: 'text_doc' | 'pdf' | 'excel' | 'other';
    title: string;
    content?: string;
    url?: string;
  };
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

const DocumentPreviewModal: React.FC<DocumentPreviewModalProps> = ({ isOpen, onClose, data }) => {
  const [editedContent, setEditedContent] = useState(data.content || '');
  const [loading, setLoading] = useState<'docx' | 'pdf' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setEditedContent(data.content || '');
    setError(null);
  }, [data.content]);

  useEffect(() => {
    if (isOpen && data.type === 'text_doc' && textareaRef.current) {
      setTimeout(() => textareaRef.current?.focus(), 200);
    }
  }, [isOpen, data.type]);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) {
      document.addEventListener('keydown', handleEsc);
      document.body.style.overflow = 'hidden';
    }
    return () => {
      document.removeEventListener('keydown', handleEsc);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleDownload = async (fmt: 'docx' | 'pdf') => {
    setLoading(fmt);
    setError(null);
    try {
      await downloadExport(editedContent, data.title, fmt);
    } catch (e: any) {
      setError(`Erro ao gerar ${fmt.toUpperCase()}: ${e.message}`);
    } finally {
      setLoading(null);
    }
  };

  const wordCount = editedContent.trim() ? editedContent.trim().split(/\s+/).length : 0;
  const charCount = editedContent.length;

  const modalSize = isFullscreen ? 'inset-0' : 'inset-4 md:inset-8 lg:inset-12';

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200"
        onClick={onClose}
      />

      {/* Modal */}
      <div className={`absolute ${modalSize} bg-[#0e0e10] border border-[#2a2a2a] rounded-2xl flex flex-col overflow-hidden shadow-2xl animate-in zoom-in-95 fade-in duration-200`}>

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-[#1e1e1e] bg-[#111113] shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-1.5 bg-indigo-500/10 rounded-lg">
              {data.type === 'text_doc' && <FileText size={16} className="text-indigo-400" />}
              {data.type === 'pdf' && <FileText size={16} className="text-red-400" />}
              {data.type === 'excel' && <FileSpreadsheet size={16} className="text-emerald-400" />}
              {data.type === 'other' && <FileText size={16} className="text-neutral-400" />}
            </div>
            <div>
              <h3 className="text-sm font-medium text-neutral-100">{data.title}</h3>
              <p className="text-[10px] text-neutral-500">
                {data.type === 'text_doc' ? 'Clique no texto para editar' : 'Visualização do arquivo'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={() => setIsFullscreen(f => !f)}
              className="p-2 hover:bg-white/5 rounded-lg text-neutral-500 hover:text-neutral-300 transition-colors"
              title={isFullscreen ? 'Sair de tela cheia' : 'Tela cheia'}
            >
              {isFullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
            </button>
            <button
              onClick={onClose}
              className="p-2 hover:bg-white/5 rounded-lg text-neutral-500 hover:text-neutral-300 transition-colors"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden">
          {data.type === 'text_doc' && (
            <div className="h-full overflow-auto bg-[#141416]">
              <div className="min-h-full px-6 py-8 md:px-12 md:py-10 flex justify-center">
                <div className="w-full max-w-2xl bg-[#0e0e11] rounded-xl border border-[#1e1e22] shadow-xl">
                  <textarea
                    ref={textareaRef}
                    value={editedContent}
                    onChange={(e) => setEditedContent(e.target.value)}
                    className="w-full min-h-[480px] h-full bg-transparent text-neutral-200 text-sm leading-loose p-8 md:p-10 outline-none resize-none selection:bg-indigo-500/30"
                    style={{ fontFamily: 'Georgia, "Times New Roman", serif' }}
                    spellCheck={false}
                    placeholder="Conteúdo do documento..."
                  />
                </div>
              </div>
            </div>
          )}

          {data.type === 'pdf' && data.url && (
            <iframe
              src={data.url}
              className="w-full h-full border-none bg-white"
              title="PDF Preview"
            />
          )}

          {data.type === 'excel' && data.url && (
            <iframe
              src={`https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(data.url)}`}
              className="w-full h-full border-none bg-white"
              title="Excel Preview"
            />
          )}

          {data.type === 'other' && (
            <div className="flex flex-col items-center justify-center h-full text-neutral-500 p-8 text-center">
              <p className="text-sm">Formato não suportado para preview.</p>
              {data.url && (
                <a
                  href={data.url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-4 px-4 py-2 bg-[#1a1a1a] hover:bg-[#222] border border-[#2a2a2a] rounded-lg text-indigo-400 transition-colors text-sm font-medium"
                >
                  Download Direto
                </a>
              )}
            </div>
          )}
        </div>

        {/* Footer — word count + download buttons (text_doc only) */}
        {data.type === 'text_doc' && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-[#1e1e1e] bg-[#111113] shrink-0">
            <span className="text-[11px] text-neutral-600 font-mono tabular-nums">
              {wordCount} {wordCount === 1 ? 'palavra' : 'palavras'} · {charCount} caracteres
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleDownload('docx')}
                disabled={!!loading}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[#1a1a1d] hover:bg-[#222] border border-[#2a2a2d] text-neutral-300 hover:text-white text-xs font-medium transition-all disabled:opacity-50"
              >
                {loading === 'docx'
                  ? <Loader2 size={13} className="animate-spin" />
                  : <FileText size={13} className="text-blue-400" />
                }
                Word
              </button>
              <button
                onClick={() => handleDownload('pdf')}
                disabled={!!loading}
                className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[#1a1a1d] hover:bg-[#222] border border-[#2a2a2d] text-neutral-300 hover:text-white text-xs font-medium transition-all disabled:opacity-50"
              >
                {loading === 'pdf'
                  ? <Loader2 size={13} className="animate-spin" />
                  : <FileText size={13} className="text-red-400" />
                }
                PDF
              </button>
            </div>
          </div>
        )}

        {/* Error bar */}
        {error && (
          <div className="px-5 py-2 border-t border-red-500/20 bg-red-500/5 shrink-0">
            <p className="text-xs text-red-400">{error}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default DocumentPreviewModal;
