import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
    Monitor,
    FolderPlus,
    Upload,
    Search,
    Grid,
    List as ListIcon,
    Folder,
    FileText,
    Image as ImageIcon,
    FileJson,
    FileSpreadsheet,
    Presentation,
    ChevronRight,
    Check,
    Trash2,
    Download,
    Pencil,
    FolderInput,
    X,
    ArrowLeft,
} from 'lucide-react';
import { driveService, UserFile } from '../lib/driveService';
import { useToast } from '../components/Toast';
import { formatDistanceToNow } from 'date-fns';
import { ptBR } from 'date-fns/locale';

interface ArccoComputerPageProps {
    userId?: string;
}

export const ArccoComputerPage: React.FC<ArccoComputerPageProps> = ({ userId: propUserId }) => {
    const [files, setFiles] = useState<UserFile[]>([]);
    const [folders, setFolders] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const [currentPath, setCurrentPath] = useState('/');
    const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [dragging, setDragging] = useState(false);
    const [uploading, setUploading] = useState(false);

    const userId = propUserId || localStorage.getItem('arcco_user_id') || '';

    // Modals
    const [showNewFolderModal, setShowNewFolderModal] = useState(false);
    const [newFolderName, setNewFolderName] = useState('');
    const [showMoveModal, setShowMoveModal] = useState(false);
    const [moveTarget, setMoveTarget] = useState('/');
    const [allFolders, setAllFolders] = useState<string[]>([]);
    const [renamingId, setRenamingId] = useState<string | null>(null);
    const [renameValue, setRenameValue] = useState('');

    const fileInputRef = useRef<HTMLInputElement>(null);
    const { showToast } = useToast();

    useEffect(() => {
        if (userId) loadContent();
    }, [userId, currentPath]);

    const loadContent = async () => {
        setLoading(true);
        try {
            const [fileList, folderList] = await Promise.all([
                driveService.listByFolder(userId, currentPath),
                driveService.listFolders(userId, currentPath),
            ]);
            setFiles(fileList.filter(f => f.file_type !== 'folder'));
            setFolders(folderList);
        } catch (error) {
            console.error('Error loading files:', error);
            showToast('Erro ao carregar arquivos', 'error');
        } finally {
            setLoading(false);
        }
    };

    const breadcrumbs = currentPath === '/'
        ? [{ label: 'Meus Arquivos', path: '/' }]
        : [
            { label: 'Meus Arquivos', path: '/' },
            ...currentPath.slice(1).split('/').reduce<{ label: string; path: string }[]>((acc, part) => {
                const prevPath = acc.length > 0 ? acc[acc.length - 1].path : '';
                acc.push({ label: part, path: `${prevPath}/${part}` });
                return acc;
            }, []),
        ];

    const navigateToFolder = (folderName: string) => {
        setSelectedIds(new Set());
        setSearchQuery('');
        setCurrentPath(currentPath === '/' ? `/${folderName}` : `${currentPath}/${folderName}`);
    };

    const navigateToPath = (path: string) => {
        setSelectedIds(new Set());
        setSearchQuery('');
        setCurrentPath(path);
    };

    const toggleSelect = (id: string) => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    const selectAll = () => {
        if (selectedIds.size === filteredFiles.length) {
            setSelectedIds(new Set());
        } else {
            setSelectedIds(new Set(filteredFiles.map(f => f.id)));
        }
    };

    const filteredFiles = files.filter(f =>
        f.file_name.toLowerCase().includes(searchQuery.toLowerCase())
    );

    // Upload
    const handleUploadFiles = async (fileList: FileList | File[]) => {
        if (!userId) return;
        setUploading(true);
        try {
            const arr = Array.from(fileList);
            await driveService.uploadMultiple(arr, userId, currentPath);
            showToast(`${arr.length} arquivo(s) enviado(s)`, 'success');
            await loadContent();
        } catch (error) {
            showToast('Erro ao fazer upload', 'error');
        } finally {
            setUploading(false);
        }
    };

    // Drag & drop
    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragging(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragging(false);
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragging(false);
        if (e.dataTransfer.files.length > 0) {
            handleUploadFiles(e.dataTransfer.files);
        }
    }, [userId, currentPath]);

    // Create folder
    const handleCreateFolder = async () => {
        if (!newFolderName.trim() || !userId) return;
        const fullPath = currentPath === '/' ? `/${newFolderName.trim()}` : `${currentPath}/${newFolderName.trim()}`;
        try {
            await driveService.createFolder(userId, fullPath);
            showToast(`Pasta "${newFolderName.trim()}" criada`, 'success');
            setShowNewFolderModal(false);
            setNewFolderName('');
            await loadContent();
        } catch (error) {
            showToast('Erro ao criar pasta', 'error');
        }
    };

    // Delete
    const handleDelete = async () => {
        if (selectedIds.size === 0) return;
        if (!confirm(`Excluir ${selectedIds.size} arquivo(s)?`)) return;
        try {
            for (const id of selectedIds) {
                await driveService.deleteFile(id);
            }
            showToast(`${selectedIds.size} arquivo(s) excluido(s)`, 'success');
            setSelectedIds(new Set());
            await loadContent();
        } catch (error) {
            showToast('Erro ao excluir', 'error');
        }
    };

    // Rename
    const handleRenameSubmit = async () => {
        if (!renamingId || !renameValue.trim()) return;
        try {
            await driveService.renameFile(renamingId, renameValue.trim());
            showToast('Arquivo renomeado', 'success');
            setRenamingId(null);
            setRenameValue('');
            await loadContent();
        } catch (error) {
            showToast('Erro ao renomear', 'error');
        }
    };

    // Move
    const openMoveModal = async () => {
        if (!userId) return;
        // Collect all unique folder paths
        const { data } = await (await import('../lib/supabase')).supabase
            .from('user_files')
            .select('folder_path')
            .eq('user_id', userId);

        const paths = new Set<string>(['/']);
        if (data) {
            for (const row of data) {
                if (row.folder_path) paths.add(row.folder_path);
            }
        }
        setAllFolders(Array.from(paths).sort());
        setMoveTarget('/');
        setShowMoveModal(true);
    };

    const handleMoveSubmit = async () => {
        try {
            for (const id of selectedIds) {
                await driveService.moveFile(id, moveTarget);
            }
            showToast(`${selectedIds.size} arquivo(s) movido(s)`, 'success');
            setShowMoveModal(false);
            setSelectedIds(new Set());
            await loadContent();
        } catch (error) {
            showToast('Erro ao mover', 'error');
        }
    };

    // Download
    const handleDownload = (url: string, name: string, e: React.MouseEvent) => {
        e.stopPropagation();
        const a = document.createElement('a');
        a.href = url;
        a.download = name;
        a.target = '_blank';
        a.click();
    };

    const getFileIcon = (type: string, size: number = 20) => {
        if (type.includes('image')) return <ImageIcon size={size} className="text-purple-400" />;
        if (type.includes('json')) return <FileJson size={size} className="text-yellow-400" />;
        if (type.includes('spreadsheet') || type.includes('excel') || type.includes('csv')) return <FileSpreadsheet size={size} className="text-green-400" />;
        if (type.includes('presentation') || type.includes('pptx')) return <Presentation size={size} className="text-orange-400" />;
        return <FileText size={size} className="text-indigo-400" />;
    };

    const formatSize = (bytes?: number) => {
        if (!bytes) return '';
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    };

    return (
        <div
            className="h-full flex flex-col text-white"
            style={{ backgroundColor: 'var(--bg-base)' }}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
        >
            {/* Drag overlay */}
            {dragging && (
                <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center pointer-events-none">
                    <div className="text-center">
                        <Upload size={32} className="text-neutral-400 mx-auto mb-3" />
                        <p className="text-base font-medium text-white">Solte os arquivos aqui</p>
                        <p className="text-sm text-neutral-500 mt-1">Serão enviados para {currentPath === '/' ? 'raiz' : currentPath}</p>
                    </div>
                </div>
            )}

            {/* Header */}
            <div className="shrink-0 px-8 pt-8 pb-4">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                        <h1 className="text-xl font-semibold">
                            Arcco Computer
                        </h1>
                        <p className="text-neutral-500 text-sm mt-1">Gerencie e organize seus arquivos</p>
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => fileInputRef.current?.click()}
                            disabled={uploading}
                            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-md transition-colors disabled:opacity-50"
                        >
                            <Upload size={16} />
                            {uploading ? 'Enviando...' : 'Upload'}
                        </button>
                        <button
                            onClick={() => { setNewFolderName(''); setShowNewFolderModal(true); }}
                            className="flex items-center gap-2 px-4 py-2 border border-neutral-700 hover:border-neutral-600 hover:text-white text-neutral-300 text-sm rounded-md transition-colors"
                        >
                            <FolderPlus size={16} />
                            Nova Pasta
                        </button>
                        <input
                            ref={fileInputRef}
                            type="file"
                            multiple
                            className="hidden"
                            onChange={(e) => {
                                if (e.target.files && e.target.files.length > 0) {
                                    handleUploadFiles(e.target.files);
                                    e.target.value = '';
                                }
                            }}
                        />
                    </div>
                </div>

                {/* Breadcrumb + Search + View Toggle */}
                <div className="flex items-center justify-between mt-4 gap-4">
                    <div className="flex items-center gap-1 text-sm min-w-0">
                        {currentPath !== '/' && (
                            <button
                                onClick={() => {
                                    const parent = currentPath.substring(0, currentPath.lastIndexOf('/')) || '/';
                                    navigateToPath(parent);
                                }}
                                className="p-1 text-neutral-500 hover:text-white rounded transition-colors mr-1"
                            >
                                <ArrowLeft size={16} />
                            </button>
                        )}
                        {breadcrumbs.map((bc, i) => (
                            <React.Fragment key={bc.path}>
                                {i > 0 && <ChevronRight size={14} className="text-neutral-600 shrink-0" />}
                                <button
                                    onClick={() => navigateToPath(bc.path)}
                                    className={`truncate px-1.5 py-0.5 rounded transition-colors ${
                                        i === breadcrumbs.length - 1
                                            ? 'text-white font-medium'
                                            : 'text-neutral-500 hover:text-white'
                                    }`}
                                >
                                    {bc.label}
                                </button>
                            </React.Fragment>
                        ))}
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-500" size={14} />
                            <input
                                type="text"
                                placeholder="Buscar..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="bg-[#1a1a1a] border border-[#262626] rounded-lg pl-8 pr-4 py-1.5 text-sm text-white focus:outline-none focus:border-indigo-500/50 w-48"
                            />
                        </div>
                        <div className="flex items-center bg-[#1a1a1a] rounded-lg border border-[#262626] p-0.5">
                            <button
                                onClick={() => setViewMode('grid')}
                                className={`p-1.5 rounded ${viewMode === 'grid' ? 'bg-[#262626] text-white' : 'text-neutral-500 hover:text-white'}`}
                            >
                                <Grid size={16} />
                            </button>
                            <button
                                onClick={() => setViewMode('list')}
                                className={`p-1.5 rounded ${viewMode === 'list' ? 'bg-[#262626] text-white' : 'text-neutral-500 hover:text-white'}`}
                            >
                                <ListIcon size={16} />
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto px-8 pb-4 min-h-0">
                {loading ? (
                    <div className="flex-1 flex items-center justify-center text-neutral-500 py-20">
                        <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-neutral-500 mr-3"></div>
                        Carregando...
                    </div>
                ) : folders.length === 0 && filteredFiles.length === 0 ? (
                    <div className="flex-1 flex flex-col items-center justify-center text-neutral-600 py-20">
                        <Monitor size={48} className="mb-4 opacity-20" />
                        <p>Nenhum arquivo nesta pasta.</p>
                        <p className="text-sm mt-1">Arraste arquivos ou clique em Upload.</p>
                    </div>
                ) : (
                    <>
                        {/* Folders */}
                        {folders.length > 0 && (
                            <div className="mb-4">
                                {searchQuery === '' && (
                                    <div className={viewMode === 'grid' ? 'grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3' : 'flex flex-col gap-1'}>
                                        {folders.map(folder => (
                                            <button
                                                key={folder}
                                                onClick={() => navigateToFolder(folder)}
                                                className={`group text-left transition-all rounded-xl border border-[#262626] hover:border-neutral-700 bg-[#0f0f0f] hover:bg-[#141414] ${
                                                    viewMode === 'grid'
                                                        ? 'p-4 flex flex-col items-center gap-2'
                                                        : 'flex items-center gap-3 px-4 py-3'
                                                }`}
                                            >
                                                <Folder size={viewMode === 'grid' ? 32 : 20} className="text-indigo-400/70 group-hover:text-indigo-400 transition-colors" />
                                                <span className="text-sm text-neutral-300 group-hover:text-white truncate">{folder}</span>
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Select all */}
                        {filteredFiles.length > 0 && (
                            <div className="flex items-center gap-3 mb-3">
                                <button
                                    onClick={selectAll}
                                    className="flex items-center gap-2 text-xs text-neutral-500 hover:text-white transition-colors"
                                >
                                    <div className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                                        selectedIds.size === filteredFiles.length && filteredFiles.length > 0
                                            ? 'bg-indigo-600 border-indigo-600'
                                            : 'border-neutral-600'
                                    }`}>
                                        {selectedIds.size === filteredFiles.length && filteredFiles.length > 0 && <Check size={10} className="text-white" />}
                                    </div>
                                    {selectedIds.size === filteredFiles.length && filteredFiles.length > 0 ? 'Desmarcar tudo' : 'Selecionar tudo'}
                                </button>
                                <span className="text-xs text-neutral-600">{filteredFiles.length} arquivo(s)</span>
                            </div>
                        )}

                        {/* Files */}
                        <div className={viewMode === 'grid' ? 'grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3' : 'flex flex-col gap-1'}>
                            {filteredFiles.map(file => {
                                const isSelected = selectedIds.has(file.id);
                                const isRenaming = renamingId === file.id;

                                return viewMode === 'grid' ? (
                                    <div
                                        key={file.id}
                                        onClick={() => toggleSelect(file.id)}
                                        className={`group relative bg-[#0f0f0f] border rounded-xl overflow-hidden cursor-pointer transition-all ${
                                            isSelected
                                                ? 'border-indigo-500'
                                                : 'border-[#262626] hover:border-neutral-600'
                                        }`}
                                    >
                                        {/* Checkbox */}
                                        <div className={`absolute top-2 left-2 z-10 w-5 h-5 rounded border-2 flex items-center justify-center transition-all ${
                                            isSelected
                                                ? 'bg-indigo-600 border-indigo-600'
                                                : 'border-neutral-600 bg-black/40 opacity-0 group-hover:opacity-100'
                                        }`}>
                                            {isSelected && <Check size={12} className="text-white" />}
                                        </div>

                                        {/* Thumbnail */}
                                        <div className="aspect-square w-full flex items-center justify-center bg-[#141414] border-b border-[#262626] relative">
                                            {file.file_type.includes('image') ? (
                                                <img src={file.file_url} alt={file.file_name} className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" />
                                            ) : (
                                                getFileIcon(file.file_type, 28)
                                            )}

                                            {/* Hover actions */}
                                            <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                                                <button
                                                    onClick={(e) => handleDownload(file.file_url, file.file_name, e)}
                                                    className="p-1.5 bg-black/70 hover:bg-black/90 rounded-lg text-white"
                                                >
                                                    <Download size={14} />
                                                </button>
                                            </div>
                                        </div>

                                        {/* Info */}
                                        <div className="p-3">
                                            {isRenaming ? (
                                                <input
                                                    autoFocus
                                                    value={renameValue}
                                                    onChange={e => setRenameValue(e.target.value)}
                                                    onKeyDown={e => {
                                                        if (e.key === 'Enter') handleRenameSubmit();
                                                        if (e.key === 'Escape') setRenamingId(null);
                                                    }}
                                                    onBlur={handleRenameSubmit}
                                                    onClick={e => e.stopPropagation()}
                                                    className="w-full bg-transparent border border-indigo-500/50 rounded px-1.5 py-0.5 text-xs text-white focus:outline-none"
                                                />
                                            ) : (
                                                <h3 className="text-xs font-medium text-neutral-200 truncate" title={file.file_name}>
                                                    {file.file_name}
                                                </h3>
                                            )}
                                            <p className="text-[10px] text-neutral-600 mt-1">
                                                {formatSize(file.size_bytes)}
                                                {file.size_bytes ? ' · ' : ''}
                                                {formatDistanceToNow(new Date(file.created_at), { addSuffix: true, locale: ptBR })}
                                            </p>
                                        </div>
                                    </div>
                                ) : (
                                    <div
                                        key={file.id}
                                        onClick={() => toggleSelect(file.id)}
                                        className={`group flex items-center gap-4 px-4 py-3 rounded-xl cursor-pointer transition-all border ${
                                            isSelected
                                                ? 'border-indigo-500/60 bg-indigo-500/5'
                                                : 'border-transparent hover:bg-[#141414]'
                                        }`}
                                    >
                                        <div className={`w-5 h-5 rounded border-2 flex items-center justify-center shrink-0 transition-all ${
                                            isSelected
                                                ? 'bg-indigo-600 border-indigo-600'
                                                : 'border-neutral-600'
                                        }`}>
                                            {isSelected && <Check size={12} className="text-white" />}
                                        </div>

                                        <div className="w-10 h-10 rounded-lg bg-[#141414] flex items-center justify-center shrink-0">
                                            {file.file_type.includes('image') ? (
                                                <img src={file.file_url} alt="" className="w-full h-full object-cover rounded-lg" />
                                            ) : (
                                                getFileIcon(file.file_type, 18)
                                            )}
                                        </div>

                                        <div className="flex-1 min-w-0">
                                            {isRenaming ? (
                                                <input
                                                    autoFocus
                                                    value={renameValue}
                                                    onChange={e => setRenameValue(e.target.value)}
                                                    onKeyDown={e => {
                                                        if (e.key === 'Enter') handleRenameSubmit();
                                                        if (e.key === 'Escape') setRenamingId(null);
                                                    }}
                                                    onBlur={handleRenameSubmit}
                                                    onClick={e => e.stopPropagation()}
                                                    className="bg-transparent border border-indigo-500/50 rounded px-2 py-0.5 text-sm text-white focus:outline-none w-full"
                                                />
                                            ) : (
                                                <p className="text-sm text-neutral-200 truncate">{file.file_name}</p>
                                            )}
                                            <p className="text-xs text-neutral-600 mt-0.5">
                                                {formatSize(file.size_bytes)}
                                                {file.size_bytes ? ' · ' : ''}
                                                {formatDistanceToNow(new Date(file.created_at), { addSuffix: true, locale: ptBR })}
                                            </p>
                                        </div>

                                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                            <button onClick={(e) => handleDownload(file.file_url, file.file_name, e)} className="p-1.5 text-neutral-500 hover:text-white rounded transition-colors">
                                                <Download size={16} />
                                            </button>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </>
                )}
            </div>

            {/* Action Bar (quando tem selecao) */}
            {selectedIds.size > 0 && (
                <div className="shrink-0 border-t border-[#262626] bg-[#0a0a0a] px-8 py-3">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-neutral-400">
                                {selectedIds.size} arquivo(s) selecionado(s)
                            </span>
                            <button onClick={() => setSelectedIds(new Set())} className="text-neutral-600 hover:text-white p-1">
                                <X size={14} />
                            </button>
                        </div>

                        <div className="flex items-center gap-2">
                            <button
                                onClick={openMoveModal}
                                className="flex items-center gap-2 px-3 py-2 border border-neutral-700 hover:border-neutral-600 hover:text-white text-neutral-300 text-sm rounded-md transition-colors"
                            >
                                <FolderInput size={14} />
                                Mover
                            </button>
                            {selectedIds.size === 1 && (
                                <button
                                    onClick={() => {
                                        const file = files.find(f => f.id === Array.from(selectedIds)[0]);
                                        if (file) {
                                            setRenamingId(file.id);
                                            setRenameValue(file.file_name);
                                        }
                                    }}
                                    className="flex items-center gap-2 px-3 py-2 border border-neutral-700 hover:border-neutral-600 hover:text-white text-neutral-300 text-sm rounded-md transition-colors"
                                >
                                    <Pencil size={14} />
                                    Renomear
                                </button>
                            )}
                            <button
                                onClick={handleDelete}
                                className="flex items-center gap-2 px-3 py-2 border border-neutral-700 hover:border-red-500/30 text-red-400 text-sm rounded-md transition-colors"
                            >
                                <Trash2 size={14} />
                                Excluir
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Modal: Nova Pasta */}
            {showNewFolderModal && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center">
                    <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowNewFolderModal(false)} />
                    <div className="relative bg-[#111113] border border-[#262629] rounded-xl shadow-2xl w-full max-w-sm p-6 m-4">
                        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <FolderPlus size={18} className="text-indigo-400" />
                            Nova Pasta
                        </h3>
                        <input
                            autoFocus
                            value={newFolderName}
                            onChange={e => setNewFolderName(e.target.value)}
                            onKeyDown={e => { if (e.key === 'Enter') handleCreateFolder(); }}
                            placeholder="Nome da pasta"
                            className="w-full bg-[#1a1a1d] border border-[#313134] text-neutral-200 text-sm rounded-lg px-3 py-2.5 outline-none focus:border-indigo-500/50"
                        />
                        <p className="text-xs text-neutral-600 mt-2">
                            Sera criada em: {currentPath === '/' ? '/' : currentPath + '/'}
                        </p>
                        <div className="flex justify-end gap-3 mt-5">
                            <button onClick={() => setShowNewFolderModal(false)} className="px-4 py-2 text-sm text-neutral-400 hover:text-white transition-colors">
                                Cancelar
                            </button>
                            <button
                                onClick={handleCreateFolder}
                                disabled={!newFolderName.trim()}
                                className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium rounded-md transition-colors"
                            >
                                Criar
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Modal: Mover */}
            {showMoveModal && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center">
                    <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowMoveModal(false)} />
                    <div className="relative bg-[#111113] border border-[#262629] rounded-xl shadow-2xl w-full max-w-sm p-6 m-4">
                        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <FolderInput size={18} className="text-indigo-400" />
                            Mover para
                        </h3>
                        <div className="space-y-1 max-h-60 overflow-y-auto">
                            {allFolders.map(fp => (
                                <button
                                    key={fp}
                                    onClick={() => setMoveTarget(fp)}
                                    className={`w-full text-left flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                                        moveTarget === fp
                                            ? 'bg-white/[0.07] text-white border border-transparent'
                                            : 'bg-[#1a1a1a] border border-transparent text-neutral-400 hover:bg-[#222] hover:text-white'
                                    }`}
                                >
                                    <Folder size={14} />
                                    {fp === '/' ? 'Raiz (/)' : fp}
                                </button>
                            ))}
                        </div>
                        <div className="flex justify-end gap-3 mt-5">
                            <button onClick={() => setShowMoveModal(false)} className="px-4 py-2 text-sm text-neutral-400 hover:text-white transition-colors">
                                Cancelar
                            </button>
                            <button
                                onClick={handleMoveSubmit}
                                className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-md transition-colors"
                            >
                                Mover
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
