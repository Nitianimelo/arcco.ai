import React from 'react';
import { AlertTriangle, Check, FileText, Folder, Loader2, Trash2, Upload, X } from 'lucide-react';
import { Project, ProjectFile } from '../../lib/projectApi';

interface ProjectEditModalProps {
  project: Project;
  open: boolean;
  editName: string;
  editInstructions: string;
  editFiles: ProjectFile[];
  isLoadingFiles: boolean;
  isUpdatingProject: boolean;
  isDeletingProject: boolean;
  deleteConfirm: boolean;
  isUploadingFile: boolean;
  editFileInputRef: React.RefObject<HTMLInputElement | null>;
  onClose: () => void;
  onEditNameChange: (value: string) => void;
  onEditInstructionsChange: (value: string) => void;
  onUploadClick: () => void;
  onUploadFile: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onDeleteProjectFile: (fileId: string) => void;
  onDeleteProject: () => void;
  onSaveProject: () => void;
}

export const ProjectEditModal: React.FC<ProjectEditModalProps> = ({
  project,
  open,
  editName,
  editInstructions,
  editFiles,
  isLoadingFiles,
  isUpdatingProject,
  isDeletingProject,
  deleteConfirm,
  isUploadingFile,
  editFileInputRef,
  onClose,
  onEditNameChange,
  onEditInstructionsChange,
  onUploadClick,
  onUploadFile,
  onDeleteProjectFile,
  onDeleteProject,
  onSaveProject,
}) => {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-[#111113] border border-[#262629] rounded-2xl shadow-2xl w-full max-w-[520px] max-h-[90vh] overflow-y-auto m-4 scrollbar-hide">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#222]">
          <div className="flex items-center gap-2">
            <Folder size={16} className="text-indigo-400" />
            <h3 className="text-base font-semibold text-white">Configurações do Projeto</h3>
          </div>
          <button onClick={onClose} className="text-neutral-500 hover:text-white transition-colors">
            <X size={18} />
          </button>
        </div>

        <div className="p-6 space-y-5">
          <div>
            <label className="block text-xs text-neutral-500 mb-1.5 font-medium uppercase tracking-wider">Nome</label>
            <input
              type="text"
              value={editName}
              onChange={(e) => onEditNameChange(e.target.value)}
              className="w-full bg-[#1a1a1d] border border-[#313134] text-neutral-200 text-sm rounded-xl px-3 py-2.5 outline-none focus:border-indigo-500/50"
            />
          </div>

          <div>
            <label className="block text-xs text-neutral-500 mb-1.5 font-medium uppercase tracking-wider">Instruções</label>
            <textarea
              value={editInstructions}
              onChange={(e) => onEditInstructionsChange(e.target.value)}
              rows={4}
              placeholder="Regras de negócio, tom de voz, restrições..."
              className="w-full bg-[#1a1a1d] border border-[#313134] text-neutral-200 text-sm rounded-xl px-3 py-2.5 outline-none focus:border-indigo-500/50 resize-none"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs text-neutral-500 font-medium uppercase tracking-wider">Base de Conhecimento</label>
              <button
                onClick={onUploadClick}
                disabled={isUploadingFile}
                className="flex items-center gap-1.5 px-2.5 py-1 text-xs text-indigo-400 hover:text-indigo-300 bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/20 rounded-lg transition-colors disabled:opacity-40"
              >
                {isUploadingFile ? <Loader2 size={11} className="animate-spin" /> : <Upload size={11} />}
                Adicionar arquivo
              </button>
              <input ref={editFileInputRef} type="file" hidden onChange={onUploadFile} />
            </div>

            {isLoadingFiles ? (
              <div className="flex items-center gap-2 py-3 text-xs text-neutral-600">
                <Loader2 size={12} className="animate-spin" /> Carregando arquivos...
              </div>
            ) : editFiles.length === 0 ? (
              <p className="text-xs text-neutral-600 py-2">Nenhum arquivo adicionado ainda.</p>
            ) : (
              <div className="space-y-1.5">
                {editFiles.map((file) => (
                  <div key={file.id} className="flex items-center gap-3 px-3 py-2 bg-[#1a1a1d] border border-[#2a2a2d] rounded-lg">
                    <FileText size={13} className="text-neutral-500 flex-shrink-0" />
                    <span className="flex-1 text-xs text-neutral-300 truncate">{file.file_name}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                      file.status === 'ready' ? 'bg-emerald-500/10 text-emerald-400' :
                      file.status === 'failed' ? 'bg-red-500/10 text-red-400' :
                      'bg-amber-500/10 text-amber-400'
                    }`}>
                      {file.status === 'ready' ? 'pronto' : file.status === 'failed' ? 'falhou' : 'processando'}
                    </span>
                    <button
                      onClick={() => onDeleteProjectFile(file.id)}
                      className="text-neutral-600 hover:text-red-400 transition-colors"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex justify-between items-center pt-2 border-t border-[#222]">
            <button
              onClick={onDeleteProject}
              disabled={isDeletingProject}
              className={`flex items-center gap-1.5 px-3 py-2 text-xs rounded-lg transition-colors disabled:opacity-40 ${
                deleteConfirm
                  ? 'bg-red-500/20 border border-red-500/40 text-red-400 hover:bg-red-500/30'
                  : 'text-neutral-500 hover:text-red-400 hover:bg-red-500/10 border border-transparent'
              }`}
            >
              {isDeletingProject ? <Loader2 size={12} className="animate-spin" /> : deleteConfirm ? <AlertTriangle size={12} /> : <Trash2 size={12} />}
              {deleteConfirm ? 'Confirmar exclusão' : 'Excluir projeto'}
            </button>

            <div className="flex gap-2">
              <button onClick={onClose} className="px-4 py-2 text-sm text-neutral-400 hover:text-white transition-colors">
                Cancelar
              </button>
              <button
                onClick={onSaveProject}
                disabled={isUpdatingProject || !editName.trim() || !project.id}
                className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-sm font-medium rounded-xl transition-colors"
              >
                {isUpdatingProject ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                Salvar
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
