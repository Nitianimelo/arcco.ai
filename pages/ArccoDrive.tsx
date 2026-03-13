
import React, { useState, useEffect } from 'react';
import {
    FileText,
    Image as ImageIcon,
    FileJson,
    Grid,
    List as ListIcon,
    Download,
    Trash2,
    Search,
    HardDrive
} from 'lucide-react';
import { driveService, UserFile } from '../lib/driveService';
import { useToast } from '../components/Toast';
import { formatDistanceToNow } from 'date-fns';
import { ptBR } from 'date-fns/locale';

export const ArccoDrivePage: React.FC = () => {
    const [files, setFiles] = useState<UserFile[]>([]);
    const [loading, setLoading] = useState(true);
    const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
    const [searchQuery, setSearchQuery] = useState('');
    const { showToast } = useToast();

    useEffect(() => {
        loadFiles();
    }, []);

    const loadFiles = async () => {
        setLoading(true);
        try {
            const { data: { user } } = await driveService.getUser();
            if (!user) {
                setFiles([]);
                setLoading(false);
                return;
            }
            const data = await driveService.listFiles(user.id);
            setFiles(data);
        } catch (error) {
            console.error('Error loading files:', error);
            showToast('Erro ao carregar arquivos do cofre', 'error');
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!confirm('Tem certeza que deseja excluir este arquivo?')) return;

        try {
            await driveService.deleteFile(id);
            setFiles(files.filter(f => f.id !== id));
            showToast('Arquivo excluído', 'success');
        } catch (error) {
            showToast('Erro ao excluir arquivo', 'error');
        }
    };

    const handleDownload = (url: string, name: string, e: React.MouseEvent) => {
        e.stopPropagation();
        const a = document.createElement('a');
        a.href = url;
        a.download = name;
        a.target = '_blank';
        a.click();
    };

    const filteredFiles = files.filter(f =>
        f.file_name.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const getFileIcon = (type: string) => {
        if (type.includes('image')) return <ImageIcon size={24} className="text-purple-400" />;
        if (type.includes('json') || type.includes('ast')) return <FileJson size={24} className="text-yellow-400" />;
        return <FileText size={24} className="text-indigo-400" />;
    };

    return (
        <div className="h-full flex flex-col text-white p-8" style={{ backgroundColor: 'var(--bg-base)' }}>

            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        <HardDrive className="text-indigo-500" />
                        Cofre de Arquivos
                    </h1>
                    <p className="text-neutral-500 text-sm">Seus artefatos e uploads seguros</p>
                </div>

                <div className="flex items-center gap-3">
                    {/* Search */}
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-500" size={16} />
                        <input
                            type="text"
                            placeholder="Buscar arquivos..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="bg-[#1a1a1a] border border-[#262626] rounded-lg pl-9 pr-4 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 w-64"
                        />
                    </div>

                    {/* View Toggle */}
                    <div className="flex items-center bg-[#1a1a1a] rounded-lg border border-[#262626] p-1">
                        <button
                            onClick={() => setViewMode('grid')}
                            className={`p-1.5 rounded ${viewMode === 'grid' ? 'bg-[#262626] text-white' : 'text-neutral-500 hover:text-white'}`}
                        >
                            <Grid size={18} />
                        </button>
                        <button
                            onClick={() => setViewMode('list')}
                            className={`p-1.5 rounded ${viewMode === 'list' ? 'bg-[#262626] text-white' : 'text-neutral-500 hover:text-white'}`}
                        >
                            <ListIcon size={18} />
                        </button>
                    </div>
                </div>
            </div>

            {/* Content */}
            {loading ? (
                <div className="flex-1 flex items-center justify-center text-neutral-500">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500 mr-3"></div>
                    Carregando cofre...
                </div>
            ) : filteredFiles.length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center text-neutral-600 border-2 border-dashed border-[#262626] rounded-2xl m-4">
                    <HardDrive size={48} className="mb-4 opacity-20" />
                    <p>Nenhum arquivo encontrado.</p>
                    <p className="text-sm">Gere designs ou faça uploads no chat para vê-los aqui.</p>
                </div>
            ) : (
                <div className={viewMode === 'grid' ? 'grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4' : 'flex flex-col gap-2'}>
                    {filteredFiles.map(file => (
                        <div
                            key={file.id}
                            className={`
                        group bg-[#0F0F0F] border border-[#262626] hover:border-indigo-500/50 rounded-xl overflow-hidden transition-all
                        ${viewMode === 'list' ? 'flex items-center p-3 gap-4' : 'flex flex-col'}
                    `}
                        >
                            {/* Thumbnail / Icon Area */}
                            <div className={`
                        relative flex items-center justify-center bg-[#141414]
                        ${viewMode === 'grid' ? 'aspect-square w-full border-b border-[#262626]' : 'w-12 h-12 rounded-lg'}
                    `}>
                                {file.file_type.includes('image') ? (
                                    <img src={file.file_url} alt={file.file_name} className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" />
                                ) : (
                                    getFileIcon(file.file_type)
                                )}

                                {/* Overlay Actions (Grid) */}
                                {viewMode === 'grid' && (
                                    <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                                        <button onClick={(e) => handleDownload(file.file_url, file.file_name, e)} className="p-2 bg-white/10 hover:bg-white/20 rounded-full text-white backdrop-blur-sm">
                                            <Download size={18} />
                                        </button>
                                        <button onClick={(e) => handleDelete(file.id, e)} className="p-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 rounded-full backdrop-blur-sm">
                                            <Trash2 size={18} />
                                        </button>
                                    </div>
                                )}
                            </div>

                            {/* Info Area */}
                            <div className={`${viewMode === 'grid' ? 'p-3' : 'flex-1 flex items-center justify-between'}`}>
                                <div className="min-w-0">
                                    <h3 className="text-sm font-medium text-neutral-200 truncate" title={file.file_name}>
                                        {file.file_name}
                                    </h3>
                                    <p className="text-xs text-neutral-500 mt-1">
                                        {formatDistanceToNow(new Date(file.created_at), { addSuffix: true, locale: ptBR })}
                                    </p>
                                </div>

                                {/* Actions (List) */}
                                {viewMode === 'list' && (
                                    <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <button onClick={(e) => handleDownload(file.file_url, file.file_name, e)} className="p-2 text-neutral-400 hover:text-white">
                                            <Download size={18} />
                                        </button>
                                        <button onClick={(e) => handleDelete(file.id, e)} className="p-2 text-neutral-400 hover:text-red-400">
                                            <Trash2 size={18} />
                                        </button>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};
