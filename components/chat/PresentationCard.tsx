import React, { useState, useRef, useEffect } from 'react';
import {
  Monitor, Download, Edit3, X, Loader2, FileText,
  Image, Presentation, FileImage, Maximize2, Minimize2
} from 'lucide-react';

interface PresentationCardProps {
  html: string;
  isStreaming?: boolean;
}

type ExportFormat = 'pdf' | 'pptx' | 'png' | 'jpeg';

interface ExportBtn {
  fmt: ExportFormat;
  label: string;
  icon: React.ReactNode;
  color: string;
}

const EXPORT_BUTTONS: ExportBtn[] = [
  { fmt: 'pdf',  label: 'PDF',        icon: <FileText size={12} />,       color: 'text-red-400 border-red-500/30 hover:bg-red-500/10' },
  { fmt: 'pptx', label: 'PowerPoint', icon: <Presentation size={12} />,   color: 'text-orange-400 border-orange-500/30 hover:bg-orange-500/10' },
  { fmt: 'png',  label: 'PNG',        icon: <Image size={12} />,          color: 'text-blue-400 border-blue-500/30 hover:bg-blue-500/10' },
  { fmt: 'jpeg', label: 'JPEG',       icon: <FileImage size={12} />,      color: 'text-green-400 border-green-500/30 hover:bg-green-500/10' },
];

async function downloadHtmlExport(html: string, title: string, format: ExportFormat) {
  const res = await fetch('/api/agent/export-html', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ html, title, format }),
  });
  if (!res.ok) {
    const msg = await res.text();
    throw new Error(msg);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `apresentacao.${format}`;
  a.click();
  URL.revokeObjectURL(url);
}

const PresentationCard: React.FC<PresentationCardProps> = ({ html, isStreaming = false }) => {
  const [editing, setEditing] = useState(false);
  const [editedHtml, setEditedHtml] = useState(html);
  const [loadingFmt, setLoadingFmt] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Sync edited HTML when prop changes (during streaming)
  useEffect(() => {
    if (!editing) setEditedHtml(html);
  }, [html, editing]);

  const activeHtml = editing ? editedHtml : html;
  const title = html.match(/<title[^>]*>([^<]+)<\/title>/i)?.[1] ?? 'Apresentação';

  const handleExport = async (fmt: ExportFormat) => {
    setLoadingFmt(fmt);
    setError(null);
    try {
      await downloadHtmlExport(activeHtml, title, fmt);
    } catch (e: any) {
      setError(`Erro ao exportar ${fmt.toUpperCase()}: ${e.message}`);
    } finally {
      setLoadingFmt(null);
    }
  };

  if (isStreaming) {
    return (
      <div className="my-4 rounded-xl border border-indigo-500/30 bg-[#0d0d0f] overflow-hidden shadow-lg w-full animate-pulse">
        <div className="flex items-center gap-3 px-4 py-3 bg-indigo-500/8 border-b border-indigo-500/20">
          <Monitor size={15} className="text-indigo-400" />
          <span className="text-xs font-semibold text-indigo-200">Construindo apresentação...</span>
        </div>
        <div className="flex items-center justify-center h-40 text-indigo-400/50 text-xs">
          O agente está renderizando os slides...
        </div>
      </div>
    );
  }

  return (
    <div className={`my-4 rounded-xl border border-indigo-500/30 bg-[#0a0a0d] overflow-hidden shadow-xl shadow-indigo-500/10 w-full ${fullscreen ? 'fixed inset-4 z-50' : ''}`}>
      {/* Header toolbar */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-[#111118] border-b border-indigo-500/20">
        <div className="flex items-center gap-2">
          <Monitor size={14} className="text-indigo-400" />
          <span className="text-xs font-semibold text-indigo-200">Apresentação Gerada</span>
          <span className="text-[10px] text-indigo-400/50 bg-indigo-500/10 px-1.5 py-0.5 rounded font-mono">HTML</span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setEditing(p => !p)}
            className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] font-medium border transition-all ${editing ? 'bg-amber-500/20 border-amber-500/40 text-amber-300' : 'bg-[#1a1a2a] border-[#333] text-neutral-400 hover:text-white'}`}
          >
            <Edit3 size={11} />
            {editing ? 'Fechar Editor' : 'Editar HTML'}
          </button>
          <button
            onClick={() => setFullscreen(p => !p)}
            className="p-1.5 rounded-lg bg-[#1a1a2a] border border-[#333] text-neutral-500 hover:text-white transition-colors"
          >
            {fullscreen ? <Minimize2 size={11} /> : <Maximize2 size={11} />}
          </button>
        </div>
      </div>

      {/* Editor pane */}
      {editing && (
        <div className="border-b border-[#222]">
          <textarea
            value={editedHtml}
            onChange={e => setEditedHtml(e.target.value)}
            className="w-full h-48 bg-[#0a0a0a] text-[11px] text-green-400 font-mono p-3 resize-none outline-none"
            spellCheck={false}
          />
        </div>
      )}

      {/* Preview iframe */}
      <div className={`w-full bg-white ${fullscreen ? 'h-[calc(100%-120px)]' : 'h-[480px]'}`}>
        <iframe
          ref={iframeRef}
          srcDoc={activeHtml}
          className="w-full h-full border-0"
          sandbox="allow-scripts allow-same-origin"
          title="Prévia da apresentação"
        />
      </div>

      {/* Export toolbar */}
      <div className="px-4 py-3 bg-[#0d0d10] border-t border-[#1a1a1a]">
        <p className="text-[10px] text-neutral-600 mb-2 uppercase tracking-widest font-semibold">Exportar como</p>
        <div className="flex flex-wrap gap-2">
          {EXPORT_BUTTONS.map(({ fmt, label, icon, color }) => (
            <button
              key={fmt}
              onClick={() => handleExport(fmt)}
              disabled={!!loadingFmt}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-transparent border text-[11px] font-medium transition-all disabled:opacity-40 ${color}`}
            >
              {loadingFmt === fmt ? <Loader2 size={11} className="animate-spin" /> : icon}
              {label}
            </button>
          ))}
        </div>
        {error && <p className="mt-2 text-[10px] text-red-400">{error}</p>}
      </div>
    </div>
  );
};

export default PresentationCard;
