import React, { useState, useEffect } from 'react';
import {
  Wrench,
  MessageSquare,
  HardDrive,
  Settings,
  ChevronDown,
  ChevronRight,
  LogOut,
  Lock,
  Clock,
  MessageCircle,
  Trash2,
  FolderOpen,
  Store,
  ChevronsLeft,
  ChevronsRight,
  Users,
  Plus,
  Folder,
  Upload,
  Info,
  Loader2,
} from 'lucide-react';
import { ViewState, NavItem } from '../types';
import { ChatSession } from '../lib/chatStorage';
import { SettingsModal } from './SettingsModal';
import { projectApi, Project } from '../lib/projectApi';
import { conversationApi, ConversationRecord } from '../lib/conversationApi';

interface SidebarProps {
  currentView: ViewState;
  userName: string;
  userPlan: string;
  userId: string;
  selectedProjectId?: string | null;
  onSelectProject?: (projectId: string | null) => void;
  onNavigate: (view: ViewState) => void;
  onNewInteraction?: () => void;
  onLoadSession?: (sessionId: string) => void;
  onLogout?: () => void;
  onTriggerUpsell: (feature: string) => void;
  onCollapsedChange?: (collapsed: boolean) => void;
}

interface NavButtonProps {
  item: NavItem;
  isActive: boolean;
  userPlan: string;
  collapsed: boolean;
  onNavigate: (view: ViewState) => void;
  onClickOverride?: () => void;
  onTriggerUpsell: (feature: string) => void;
}

const NavButton: React.FC<NavButtonProps> = ({ item, isActive, userPlan, collapsed, onNavigate, onClickOverride, onTriggerUpsell }) => {
  const isFreePlan = userPlan === 'free';
  const lockedTools = ['ARC_BUILDER_PREMIUM'];
  const isLocked = isFreePlan && lockedTools.includes(item.id);
  const isDisabled = !!item.disabled;

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (isDisabled) return;

    if (isLocked) {
      onTriggerUpsell(item.label);
    } else if (onClickOverride) {
      onClickOverride();
    } else {
      onNavigate(item.id);
    }
  };

  return (
    <button
      title={collapsed ? item.label : undefined}
      onClick={handleClick}
      disabled={isDisabled}
      className={`group relative w-full flex items-center transition-all duration-200 outline-none rounded-xl
        ${collapsed ? 'justify-center px-0 py-2.5' : 'gap-3 px-3 py-2.5'}
        ${isDisabled
          ? 'opacity-40 cursor-not-allowed text-neutral-500 border-l-2 border-transparent'
          : isActive
            ? 'bg-gradient-to-r from-indigo-500/10 to-transparent border-l-2 border-indigo-500 text-white shadow-[0_0_20px_rgba(99,102,241,0.15)]'
            : 'text-neutral-400 hover:text-white hover:bg-white/[0.03] border-l-2 border-transparent'
        } text-sm font-medium`}
    >
      <div className={`relative flex items-center justify-center transition-transform duration-300 ${isActive && !isDisabled ? 'scale-110' : !isDisabled ? 'group-hover:scale-110' : ''}`}>
        <item.icon
          size={20}
          className={`transition-colors duration-200 ${isDisabled
            ? 'text-neutral-600'
            : isActive
              ? 'text-indigo-400 drop-shadow-[0_0_8px_rgba(129,140,248,0.5)]'
              : isLocked
                ? 'text-neutral-600'
                : 'text-neutral-500 group-hover:text-neutral-200'
            }`}
        />
      </div>

      {!collapsed && (
        <span className="flex-1 text-left truncate relative z-10 flex items-center gap-2">
          {item.label}
        </span>
      )}

      {!collapsed && isDisabled && (
        <span className="text-[10px] bg-neutral-800 text-neutral-600 px-1.5 py-0.5 rounded-full leading-none">
          Em breve
        </span>
      )}

      {!collapsed && !isDisabled && isLocked && (
        <Lock size={14} className="text-neutral-600 group-hover:text-neutral-400" />
      )}
    </button>
  );
};

const SectionHeader: React.FC<{ label: string; icon?: React.ReactNode; collapsed: boolean }> = ({ label, icon, collapsed }) => {
  if (collapsed) return null;
  return (
    <div className="px-4 mt-6 mb-2 flex items-center gap-2">
      {icon}
      <h3 className="text-[10px] uppercase tracking-widest text-neutral-600 font-semibold">{label}</h3>
    </div>
  );
};

export const Sidebar: React.FC<SidebarProps> = ({
  currentView,
  userName,
  userPlan,
  userId,
  selectedProjectId,
  onSelectProject,
  onNavigate,
  onNewInteraction,
  onLoadSession,
  onLogout,
  onTriggerUpsell,
  onCollapsedChange
}) => {
  const [collapsed, setCollapsed] = useState(false);
  const [toolsOpen, setToolsOpen] = useState(false);
  const [projectsOpen, setProjectsOpen] = useState(false);
  const [recentSessions, setRecentSessions] = useState<ChatSession[]>([]);
  const [showSettings, setShowSettings] = useState(false);

  // Projetos State
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(false);
  const [showProjectModal, setShowProjectModal] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectInstructions, setNewProjectInstructions] = useState('');
  const [projectFiles, setProjectFiles] = useState<File[]>([]);
  const [newProjectTools, setNewProjectTools] = useState('');

  // Carrega projetos do backend ao montar (quando userId disponível)
  useEffect(() => {
    if (!userId) return;
    setProjectsLoading(true);
    projectApi.list(userId).then(list => {
      setProjects(list);
      setProjectsLoading(false);
    });
  }, [userId]);

  const [isCreatingProject, setIsCreatingProject] = useState(false);
  const [projectUploadStatus, setProjectUploadStatus] = useState('');

  const handleCreateProject = async () => {
    if (!newProjectName.trim() || !userId) return;
    setIsCreatingProject(true);
    setProjectUploadStatus('');

    // 1. Cria o projeto
    const created = await projectApi.create(userId, newProjectName, newProjectInstructions);
    if (!created) {
      setIsCreatingProject(false);
      return;
    }
    setProjects(prev => [created, ...prev]);

    // 2. Faz upload dos arquivos para o RAG do projeto (se houver)
    if (projectFiles.length > 0) {
      setProjectUploadStatus(`Enviando ${projectFiles.length} arquivo(s)...`);
      for (const file of projectFiles) {
        await projectApi.uploadFile(created.id, file);
      }
      setProjectUploadStatus('');
    }

    setIsCreatingProject(false);
    setShowProjectModal(false);
    setNewProjectName('');
    setNewProjectInstructions('');
    setProjectFiles([]);
    setNewProjectTools('');
  };

  // Carrega histórico apenas do Supabase (sem localStorage)
  const loadSessions = () => {
    if (!userId) {
      setRecentSessions([]);
      return;
    }
    conversationApi.list(userId).then(convs => {
      const mapped: ChatSession[] = convs.map(c => ({
        id: c.id,
        title: c.title,
        updatedAt: new Date(c.updated_at).getTime(),
        messages: [],
      }));
      setRecentSessions(mapped);
    }).catch(() => setRecentSessions([]));
  };

  useEffect(() => {
    loadSessions();
    const interval = setInterval(loadSessions, 15000);
    return () => clearInterval(interval);
  }, [userId]);

  useEffect(() => {
    onCollapsedChange?.(collapsed);
    if (collapsed) {
      setToolsOpen(false);
    }
  }, [collapsed]);

  const appTools: NavItem[] = [
    { id: 'ARCCO_DRIVE', label: 'Arcco Drive', icon: HardDrive },
  ];

  const isToolsActive = currentView === 'TOOLS_MY' || currentView === 'TOOLS_STORE';

  const handleDeleteSession = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    conversationApi.delete(id).catch(() => {});
    setRecentSessions(prev => prev.filter(s => s.id !== id));
  };

  return (
    <aside
      className={`h-screen border-r border-[#262629] flex flex-col fixed left-0 top-0 z-50 shadow-[4px_0_24px_rgba(0,0,0,0.3)] transition-all duration-300 ease-in-out
        ${collapsed ? 'w-16' : 'w-64'}`}
      style={{ backgroundColor: 'var(--bg-sidebar)' }}
    >

      {/* 1. Logo + botão colapsar */}
      <div className={`flex items-center shrink-0 pt-5 pb-6 ${collapsed ? 'justify-center px-0' : 'justify-between px-4'}`}>
        {!collapsed && (
          <div className="flex items-center gap-2 cursor-pointer" onClick={() => onNavigate('ARCCO_CHAT')}>
            <img
              src="https://qscezcbpwvnkqoevulbw.supabase.co/storage/v1/object/public/Chipro%20calculadora/arcco%20(1).png"
              alt="Arcco Logo"
              className="h-10 w-auto object-contain"
            />
          </div>
        )}

        {collapsed && (
          <div className="cursor-pointer" onClick={() => onNavigate('ARCCO_CHAT')}>
            <img
              src="https://qscezcbpwvnkqoevulbw.supabase.co/storage/v1/object/public/Chipro%20calculadora/arcco%20(1).png"
              alt="Arcco Logo"
              className="h-7 w-auto object-contain"
            />
          </div>
        )}

        {!collapsed && (
          <button
            onClick={() => setCollapsed(true)}
            className="p-2 text-neutral-600 hover:text-neutral-300 hover:bg-white/[0.04] rounded-lg transition-colors"
            title="Recolher menu"
          >
            <ChevronsLeft size={18} />
          </button>
        )}
      </div>

      {/* Botão expandir — só aparece quando colapsado */}
      {collapsed && (
        <div className="flex justify-center pb-1 shrink-0">
          <button
            onClick={() => setCollapsed(false)}
            className="p-2 text-neutral-600 hover:text-neutral-300 hover:bg-white/[0.04] rounded-lg transition-colors"
            title="Expandir menu"
          >
            <ChevronsRight size={18} />
          </button>
        </div>
      )}

      {/* 2. Nova Interação + Projetos + Tools */}
      <div className={`pb-2 shrink-0 space-y-0.5 ${collapsed ? 'px-1' : 'px-2'}`}>
        <NavButton
          item={{ id: 'ARCCO_CHAT', label: 'Nova Interação', icon: MessageSquare }}
          isActive={currentView === 'ARCCO_CHAT'}
          userPlan={userPlan}
          collapsed={collapsed}
          onNavigate={onNavigate}
          onClickOverride={onNewInteraction}
          onTriggerUpsell={onTriggerUpsell}
        />
        <NavButton
          item={{ id: 'ESPECIALISTAS', label: 'Especialistas', icon: Users, disabled: true }}
          isActive={false}
          userPlan={userPlan}
          collapsed={collapsed}
          onNavigate={onNavigate}
          onTriggerUpsell={onTriggerUpsell}
        />

        {/* Projetos com sub-menu e Modal */}
        <div>
          <button
            title={collapsed ? 'Projetos' : undefined}
            onClick={() => {
              if (collapsed) return;
              setProjectsOpen(!projectsOpen);
            }}
            className={`group relative w-full flex items-center transition-all duration-200 outline-none rounded-xl text-sm font-medium
              ${collapsed ? 'justify-center px-0 py-2.5' : 'gap-3 px-3 py-2.5'}
              text-neutral-400 hover:text-white hover:bg-white/[0.03] border-l-2 border-transparent`}
          >
            <div className={`relative flex items-center justify-center transition-transform duration-300 group-hover:scale-110`}>
              <FolderOpen
                size={20}
                className="transition-colors duration-200 text-neutral-500 group-hover:text-neutral-200"
              />
            </div>
            {!collapsed && (
              <>
                <span className="flex-1 text-left">Projetos</span>
                <span
                  onClick={(e) => { e.stopPropagation(); setShowProjectModal(true); setProjectsOpen(true); }}
                  className="p-1 hover:bg-white/[0.1] rounded text-neutral-500 hover:text-white transition-colors mr-1"
                  title="Novo Projeto"
                >
                  <Plus size={14} />
                </span>
                {projectsOpen
                  ? <ChevronDown size={14} className="text-neutral-500" />
                  : <ChevronRight size={14} className="text-neutral-500" />
                }
              </>
            )}
          </button>

          {projectsOpen && !collapsed && (
            <div className="mt-0.5 ml-3 border-l border-[#313134] pl-3 space-y-0.5 pb-1">
              {projectsLoading ? (
                <div className="px-2 py-2 text-[11px] text-neutral-600">Carregando...</div>
              ) : projects.length === 0 ? (
                <div className="px-2 py-2 text-[11px] text-neutral-600">Nenhum projeto</div>
              ) : (
                projects.map(proj => (
                  <button
                    key={proj.id}
                    onClick={() => onSelectProject?.(selectedProjectId === proj.id ? null : proj.id)}
                    className={`w-full flex items-center gap-2.5 px-2 py-2 text-sm rounded-lg transition-colors
                      ${selectedProjectId === proj.id
                        ? 'text-white bg-indigo-500/10 border border-indigo-500/30'
                        : 'text-neutral-400 hover:text-white hover:bg-white/[0.03]'
                      }`}
                  >
                    <Folder size={14} className={selectedProjectId === proj.id ? 'text-indigo-400' : 'text-indigo-400/70'} />
                    <span className="truncate">{proj.name}</span>
                  </button>
                ))
              )}
            </div>
          )}
        </div>

        {/* Tools com sub-menu */}
        <div>
          <button
            title={collapsed ? 'Tools' : undefined}
            onClick={() => {
              if (collapsed) return;
              setToolsOpen(!toolsOpen);
            }}
            className={`group relative w-full flex items-center transition-all duration-200 outline-none rounded-xl text-sm font-medium
              ${collapsed ? 'justify-center px-0 py-2.5' : 'gap-3 px-3 py-2.5'}
              ${isToolsActive
                ? 'bg-gradient-to-r from-indigo-500/10 to-transparent border-l-2 border-indigo-500 text-white shadow-[0_0_20px_rgba(99,102,241,0.15)]'
                : 'text-neutral-400 hover:text-white hover:bg-white/[0.03] border-l-2 border-transparent'
              }`}
          >
            <div className={`relative flex items-center justify-center transition-transform duration-300 ${isToolsActive ? 'scale-110' : 'group-hover:scale-110'}`}>
              <Wrench
                size={20}
                className={`transition-colors duration-200 ${isToolsActive
                  ? 'text-indigo-400 drop-shadow-[0_0_8px_rgba(129,140,248,0.5)]'
                  : 'text-neutral-500 group-hover:text-neutral-200'
                  }`}
              />
            </div>
            {!collapsed && (
              <>
                <span className="flex-1 text-left">Tools</span>
                {toolsOpen
                  ? <ChevronDown size={14} className="text-neutral-500" />
                  : <ChevronRight size={14} className="text-neutral-500" />
                }
              </>
            )}
          </button>

          {toolsOpen && !collapsed && (
            <div className="mt-0.5 ml-3 border-l border-[#313134] pl-3 space-y-0.5">
              <button
                onClick={() => onNavigate('TOOLS_MY')}
                className={`w-full flex items-center gap-2.5 px-2 py-2 text-sm rounded-lg transition-colors
                  ${currentView === 'TOOLS_MY'
                    ? 'text-white bg-white/[0.05]'
                    : 'text-neutral-400 hover:text-white hover:bg-white/[0.03]'
                  }`}
              >
                <Wrench size={15} className="text-neutral-500 flex-shrink-0" />
                Minhas Tools
              </button>
              <button
                onClick={() => onNavigate('TOOLS_STORE')}
                className={`w-full flex items-center gap-2.5 px-2 py-2 text-sm rounded-lg transition-colors
                  ${currentView === 'TOOLS_STORE'
                    ? 'text-white bg-white/[0.05]'
                    : 'text-neutral-400 hover:text-white hover:bg-white/[0.03]'
                  }`}
              >
                <Store size={15} className="text-neutral-500 flex-shrink-0" />
                Loja
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 3. Sessões recentes — rolável (só no expandido) */}
      <div className="flex-1 overflow-y-auto scrollbar-hide px-2 min-h-0">
        {!collapsed && recentSessions.length > 0 && (
          <div className="pt-1 border-t border-[#262629]">
            <SectionHeader collapsed={collapsed} label="Recentes" icon={<Clock size={10} className="text-neutral-600" />} />
            <div className="space-y-0.5 px-2">
              {recentSessions.map((session) => (
                <div key={session.id} className="relative group w-full flex items-center">
                  <button
                    onClick={() => { if (onLoadSession) onLoadSession(session.id); }}
                    className="w-full flex items-center gap-3 px-3 py-2 text-sm text-neutral-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
                  >
                    <MessageCircle size={16} className="text-neutral-600 group-hover:text-indigo-400 transition-colors flex-shrink-0" />
                    <span className="truncate pr-6 text-left w-full">{session.title}</span>
                  </button>
                  <button
                    onClick={(e) => handleDeleteSession(e, session.id)}
                    className="absolute right-2 opacity-0 group-hover:opacity-100 p-1 text-neutral-500 hover:text-red-400 transition-all rounded hover:bg-[#3b3b3e]"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 4. Apps */}
      <div className={`pt-2 pb-1 border-t border-[#262629] shrink-0 ${collapsed ? 'px-1' : 'px-2'}`}>
        <SectionHeader collapsed={collapsed} label="APPS" />
        {appTools.map((item) => (
          <NavButton
            key={item.id}
            item={item}
            isActive={currentView === item.id}
            userPlan={userPlan}
            collapsed={collapsed}
            onNavigate={onNavigate}
            onTriggerUpsell={onTriggerUpsell}
          />
        ))}

        <NavButton
          item={{ id: 'SETTINGS', label: 'Configurações', icon: Settings }}
          isActive={false}
          userPlan={userPlan}
          collapsed={collapsed}
          onNavigate={onNavigate}
          onClickOverride={() => setShowSettings(true)}
          onTriggerUpsell={onTriggerUpsell}
        />
      </div>

      {/* 5. Conta */}
      <div className={`border-t border-[#262629] shrink-0 ${collapsed ? 'p-2' : 'p-4'}`}>
        <div className={`flex items-center rounded-xl hover:bg-neutral-900/50 cursor-pointer transition-colors group ${collapsed ? 'justify-center p-1' : 'gap-3 p-2'}`}>
          <div
            title={collapsed ? `${userName} · ${userPlan}` : undefined}
            className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-xs font-bold text-white flex-shrink-0"
          >
            {userName.charAt(0)}
          </div>
          {!collapsed && (
            <>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">{userName}</p>
                <p className="text-xs text-neutral-500 capitalize">{userPlan}</p>
              </div>
              {onLogout && (
                <button onClick={(e) => { e.stopPropagation(); onLogout(); }} className="text-neutral-600 hover:text-red-400 transition-colors">
                  <LogOut size={16} />
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Modal de Configurações */}
      <SettingsModal
        open={showSettings}
        onClose={() => setShowSettings(false)}
        userName={userName}
        userPlan={userPlan}
        userId={userId}
      />

      {/* Modal Criar Projeto (Popup) */}
      {showProjectModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowProjectModal(false)} />
          <div className="relative bg-[#111113] border border-[#262629] rounded-2xl shadow-2xl w-full max-w-[480px] max-h-[90vh] overflow-y-auto p-6 m-4 scrollbar-hide">
            <h3 className="text-lg font-semibold text-white mb-2 flex items-center gap-2">
              <Folder className="text-indigo-400" size={18} />
              Novo Projeto
            </h3>
            <p className="text-sm text-neutral-400 mb-5">Crie um contexto de instruções para a IA focar.</p>

            <div className="space-y-4">
              <div>
                <label className="block text-xs text-neutral-500 mb-1.5 font-medium uppercase tracking-wider">Nome</label>
                <input
                  type="text"
                  value={newProjectName}
                  onChange={e => setNewProjectName(e.target.value)}
                  placeholder="Ex: SaaS Landing Page"
                  className="w-full bg-[#1a1a1d] border border-[#313134] text-neutral-200 text-sm rounded-xl px-3 py-2.5 outline-none focus:border-indigo-500/50"
                  autoFocus
                />
              </div>

              <div>
                <label className="text-xs text-neutral-500 mb-1.5 font-medium uppercase tracking-wider flex items-center gap-1.5 w-max relative group cursor-help">
                  Instruções
                  <Info size={14} className="opacity-70 group-hover:opacity-100 transition-opacity" />
                  <div className="absolute left-0 bottom-full mb-2 w-64 p-2.5 bg-[#1a1a1d] border border-[#333] rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50 pointer-events-none normal-case font-normal text-xs text-neutral-300">
                    Aqui você define como a IA deve se comportar nesse projeto, incluindo tom de voz, regras de negócio e restrições.
                  </div>
                </label>
                <textarea
                  value={newProjectInstructions}
                  onChange={e => setNewProjectInstructions(e.target.value)}
                  placeholder="Informações relevantes, regras de negócios..."
                  className="w-full h-24 bg-[#1a1a1d] border border-[#313134] text-neutral-200 text-sm rounded-xl px-3 py-2.5 outline-none focus:border-indigo-500/50 resize-none"
                />
              </div>

              <div>
                <label className="text-xs text-neutral-500 mb-1.5 font-medium uppercase tracking-wider flex items-center gap-1.5 w-max relative group cursor-help">
                  Base de Conhecimento
                  <Info size={14} className="opacity-70 group-hover:opacity-100 transition-opacity" />
                  <div className="absolute left-0 bottom-full mb-2 w-64 p-2.5 bg-[#1a1a1d] border border-[#333] rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50 pointer-events-none normal-case font-normal text-xs text-neutral-300">
                    Faça upload de documentos (PDF, planilhas) que contêm informações cruciais para a IA consultar durante o projeto.
                  </div>
                </label>
                <button
                  type="button"
                  onClick={() => document.getElementById('project-file-upload')?.click()}
                  className="w-full flex flex-col items-center justify-center border border-dashed border-[#313134] hover:border-indigo-500/50 bg-[#1a1a1d] hover:bg-white/[0.02] transition-colors rounded-xl p-4 text-sm text-neutral-400 gap-2 cursor-pointer"
                >
                  <Upload size={20} className="text-neutral-500" />
                  <span>Upload de arquivos para aprendizado</span>
                  {projectFiles.length > 0 && (
                    <span className="text-xs text-indigo-400 mt-1">{projectFiles.length} arquivo(s) selecionado(s)</span>
                  )}
                </button>
                <input
                  id="project-file-upload"
                  type="file"
                  multiple
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files) {
                      setProjectFiles(Array.from(e.target.files));
                    }
                  }}
                />
              </div>

              <div>
                <label className="text-xs text-neutral-500 mb-1.5 font-medium uppercase tracking-wider flex items-center gap-1.5 w-max relative group cursor-help">
                  Ferramentas (Tools)
                  <Info size={14} className="opacity-70 group-hover:opacity-100 transition-opacity" />
                  <div className="absolute left-0 bottom-full mb-2 w-64 p-2.5 bg-[#1a1a1d] border border-[#333] rounded-lg shadow-xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50 pointer-events-none normal-case font-normal text-xs text-neutral-300">
                    Selecione quais habilidades a IA terá acesso neste projeto.
                  </div>
                </label>
                <input
                  type="text"
                  value={newProjectTools}
                  onChange={e => setNewProjectTools(e.target.value)}
                  placeholder="Ex: Busca Web, Manipulação de Arquivos..."
                  className="w-full bg-[#1a1a1d] border border-[#313134] text-neutral-200 text-sm rounded-xl px-3 py-2.5 outline-none focus:border-indigo-500/50"
                />
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-3">
              {projectUploadStatus && (
                <span className="text-xs text-indigo-400 mr-auto">{projectUploadStatus}</span>
              )}
              <button
                onClick={() => setShowProjectModal(false)}
                disabled={isCreatingProject}
                className="px-4 py-2 text-sm text-neutral-400 hover:text-white transition-colors disabled:opacity-40"
              >
                Cancelar
              </button>
              <button
                onClick={handleCreateProject}
                disabled={!newProjectName.trim() || isCreatingProject}
                className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium rounded-xl transition-colors flex items-center gap-2"
              >
                {isCreatingProject && <Loader2 size={14} className="animate-spin" />}
                {isCreatingProject ? 'Criando...' : 'Criar Projeto'}
              </button>
            </div>
          </div>
        </div>
      )}

    </aside>
  );
};
