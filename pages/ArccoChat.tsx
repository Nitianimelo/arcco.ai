import React, { useState, useEffect, useRef } from 'react';
import { Send, Loader2, Sparkles, Save, FileText, Download, ChevronDown, Paperclip, HardDrive, FileSpreadsheet, Eye, Square, Plus, Link, Folder, Pencil, Trash2, Upload, X, Check, AlertTriangle, Wrench, Globe } from 'lucide-react';
import { projectApi, Project, ProjectFile } from '../lib/projectApi';
import { openRouterService } from '../lib/openrouter';
import { agentApi, SessionFileItem, SessionFileStatus } from '../lib/api-client';
import { supabase } from '../lib/supabase';
import { driveService } from '../lib/driveService';
import { ArtifactCard } from '../components/chat/ArtifactCard';
import { ThoughtStep } from '../components/chat/AgentThoughtPanel';
import { BrowserAgentCard } from '../components/chat/BrowserAgentCard';
import TextDocCard from '../components/chat/TextDocCard';
import ClarificationCard from '../components/chat/ClarificationCard';
import PresentationCard from '../components/chat/PresentationCard';
import DesignGallery from '../components/chat/DesignGallery';
import DocumentPreviewModal from '../components/chat/DocumentPreviewModal';
import DesignPreviewModal from '../components/chat/DesignPreviewModal';
import { ProjectEditModal } from '../components/chat/ProjectEditModal';
import DotGridBackground from '../components/ui/DotGridBackground';
import { useToast } from '../components/Toast';
// AgentTerminal removido — steps agora são inline
import { Message } from '../lib/chatStorage';
import { conversationApi } from '../lib/conversationApi';

interface FilePreviewCardProps {
  url: string;
  filename: string;
  type: 'pdf' | 'excel' | 'other';
  onOpenPreview?: () => void;
}

const FilePreviewCard: React.FC<FilePreviewCardProps> = ({ url, filename, type, onOpenPreview }) => {
  const { showToast } = useToast();
  const [isSaving, setIsSaving] = useState(false);

  const handleDownload = async () => {
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`falha ao baixar arquivo (${response.status})`);
      }

      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = filename || `arquivo_${Date.now()}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (err: any) {
      console.error('Erro ao baixar arquivo:', err);
      showToast(`Erro ao baixar arquivo: ${err.message}`, 'error');
    }
  };

  const handleSaveToVault = async () => {
    try {
      setIsSaving(true);
      const fileType = type === 'pdf' ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
      await driveService.saveArtifactReference(filename || `arquivo_${Date.now()}`, fileType, url);
      showToast('Arquivo salvo no Arcco Drive com sucesso!', 'success');
    } catch (err: any) {
      console.error('Erro ao salvar no cofre:', err);
      showToast(`Erro ao salvar no Cofre: ${err.message}`, 'error');
    } finally {
      setIsSaving(false);
    }
  };

  const iconBg = type === 'pdf' ? 'bg-red-500/10' : type === 'excel' ? 'bg-emerald-500/10' : 'bg-indigo-500/10';

  return (
    <div className="my-3 rounded-xl border border-[#2a2a2a] bg-[#111113] overflow-hidden shadow-lg w-full max-w-md group hover:border-indigo-500/30 transition-all duration-200">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-[#1e1e1e]">
        <div className={`p-2 ${iconBg} rounded-lg`}>
          {type === 'pdf' ? (
            <FileText size={16} className="text-red-400" />
          ) : type === 'excel' ? (
            <FileSpreadsheet size={16} className="text-emerald-400" />
          ) : (
            <HardDrive size={16} className="text-indigo-400" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-medium text-neutral-100 truncate" title={filename}>{filename}</h4>
          <span className="text-[10px] text-neutral-500 uppercase">{type === 'pdf' ? 'PDF' : type === 'excel' ? 'Planilha' : 'Arquivo'}</span>
        </div>
      </div>
      <div className="flex items-center gap-2 px-4 py-3">
        {onOpenPreview && (
          <button
            onClick={onOpenPreview}
            className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition-colors"
          >
            <Eye size={13} /> Preview
          </button>
        )}
        <button
          onClick={handleDownload}
          className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-[#1a1a1a] hover:bg-[#222] border border-[#2a2a2a] text-neutral-400 hover:text-neutral-200 text-xs font-medium transition-all"
        >
          <Download size={13} /> Baixar
        </button>
        <button
          onClick={handleSaveToVault}
          disabled={isSaving}
          className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-[#1a1a1a] hover:bg-[#222] border border-[#2a2a2a] text-neutral-400 hover:text-neutral-200 text-xs font-medium transition-all disabled:opacity-50"
        >
          {isSaving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
          Salvar
        </button>
      </div>
    </div>
  );
};

interface ArccoChatPageProps {
  userName: string;
  chatSessionId?: string | null;
  userId?: string;
  projectId?: string | null;
  project?: Project | null;
  onProjectUpdated?: (project: Project) => void;
  onProjectDeleted?: () => void;
  onSessionUpdate?: (session: ChatSession) => void;
  initialMessage?: string | null;
  onClearInitialMessage?: () => void;
}

interface ChatModeConfig {
  id?: number;
  slot_number: number;
  model_name: string;
  openrouter_model_id: string;
  system_prompt?: string;
  is_active: boolean;
}

interface SessionAttachment {
  fileId: string;
  name: string;
  sizeBytes: number;
  status: SessionFileStatus;
  error?: string | null;
}

const allSuggestions = [
  'Criar um post para Instagram',
  'Resumir este documento',
  'Planejar campanha de vendas',
  'Redigir um email profissional',
  'Criar uma planilha de controle',
  'Elaborar uma proposta comercial',
  'Analisar dados e gerar insights',
  'Criar um roteiro de reunião',
  'Escrever uma descrição de produto',
  'Montar um plano de ação',
];

const generateThinkingMessage = (text: string): string => {
  const t = text.toLowerCase();
  if (t.includes('email') || t.includes('e-mail') || t.includes('carta') || t.includes('comunicado'))
    return 'Redigindo a mensagem para você...';
  if (t.includes('planilha') || t.includes('excel') || t.includes('tabela') || (t.includes('dados') && t.includes('organiz')))
    return 'Organizando os dados...';
  if (t.includes('resumo') || t.includes('resumir') || t.includes('síntese') || t.includes('sintetizar'))
    return 'Lendo e analisando o conteúdo...';
  if (t.includes('código') || t.includes('programar') || t.includes('script') || t.includes('bug') || t.includes('função') || t.includes('react') || t.includes('python') || t.includes('javascript'))
    return 'Analisando o código...';
  if (t.includes('post') || t.includes('instagram') || t.includes('twitter') || t.includes('linkedin') || t.includes('marketing') || t.includes('campanha') || t.includes('conteúdo'))
    return 'Criando o conteúdo para você...';
  if (t.includes('apresentação') || t.includes('slides') || t.includes('pitch') || t.includes('deck') || t.includes('powerpoint'))
    return 'Preparando a apresentação...';
  if (t.includes('traduz') || t.includes('inglês') || t.includes('espanhol') || t.includes('francês') || t.includes('idioma'))
    return 'Traduzindo o conteúdo...';
  if (t.includes('proposta') || t.includes('orçamento') || t.includes('cotação') || t.includes('contrato') || t.includes('oferta'))
    return 'Montando a proposta para você...';
  if (t.includes('plano') || t.includes('estratégia') || t.includes('planejamento') || t.includes('roteiro') || t.includes('cronograma'))
    return 'Elaborando o plano para você...';
  if (t.includes('analis') || t.includes('pesquisa') || t.includes('compara') || t.includes('mercado') || t.includes('relatório'))
    return 'Analisando as informações...';
  if (t.includes('como ') || t.includes('por que') || t.includes('porque') || t.includes('explica') || t.includes('o que é') || t.includes('diferença') || t.includes('quando') || t.includes('onde'))
    return 'Buscando a melhor explicação...';
  if (t.includes('cria') || t.includes('gera') || t.includes('escreve') || t.includes('faz') || t.includes('monta') || t.includes('produz'))
    return 'Criando o que você pediu...';
  return 'Trabalhando na melhor resposta para você...';
};

// ── Persistência de modo por conversa ──────────────────────────────────────
const CONV_MODE_KEY = 'arcco_conv_mode';
const saveConvMode = (convId: string, agentMode: boolean) => {
  try {
    const existing = JSON.parse(localStorage.getItem(CONV_MODE_KEY) || '{}');
    existing[convId] = agentMode;
    localStorage.setItem(CONV_MODE_KEY, JSON.stringify(existing));
  } catch { /* ignore */ }
};
const getConvMode = (convId: string): boolean | null => {
  try {
    const existing = JSON.parse(localStorage.getItem(CONV_MODE_KEY) || '{}');
    return convId in existing ? existing[convId] : null;
  } catch { return null; }
};

const ArccoChatPage: React.FC<ArccoChatPageProps> = ({
  userName,
  chatSessionId,
  userId,
  projectId,
  project,
  onProjectUpdated,
  onProjectDeleted,
  onSessionUpdate,
  initialMessage,
  onClearInitialMessage,
}) => {
  const { showToast } = useToast();
  const [localSessionId] = useState(() => Date.now().toString());
  const effectiveSessionId = chatSessionId || localSessionId;
  const [conversationId, setConversationId] = useState<string | null>(null);

  const [isApiKeyReady, setIsApiKeyReady] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [attachments, setAttachments] = useState<SessionAttachment[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [isFileLoading, setIsFileLoading] = useState(false);
  const [isTerminalOpen, setIsTerminalOpen] = useState(false);
  const [terminalContent, setTerminalContent] = useState('');
  const [isAgentMode, setIsAgentMode] = useState(true);

  const [agentThoughts, setAgentThoughts] = useState<ThoughtStep[]>([]);
  const [isThoughtsExpanded, setIsThoughtsExpanded] = useState(true);
  const [browserAction, setBrowserAction] = useState<{ status: string; url: string; title: string } | null>(null);
  const [showModelDropdown, setShowModelDropdown] = useState(false);
  const [showChatModelDropdown, setShowChatModelDropdown] = useState(false);
  const [chatModeConfigs, setChatModeConfigs] = useState<ChatModeConfig[]>([]);
  const [selectedChatSlot, setSelectedChatSlot] = useState<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const thoughtsStartTimeRef = useRef<number>(0);
  const [generatedFiles, setGeneratedFiles] = useState<Array<{ filename: string; url: string; type: 'pdf' | 'excel' | 'other' }>>([]);
  const [textDocArtifact, setTextDocArtifact] = useState<{ title: string; content: string } | null>(null);
  const [clarificationQuestions, setClarificationQuestions] = useState<Array<{ type: 'choice' | 'open'; text: string; options: string[] }> | null>(null);
  const [chatThinkingMessage, setChatThinkingMessage] = useState('');
  const [chatThinkingVisible, setChatThinkingVisible] = useState(false);
  const chatThinkingStartRef = useRef<number>(0);
  const chatThinkingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [modalPreview, setModalPreview] = useState<{ type: 'text_doc' | 'pdf' | 'excel' | 'other'; title: string; content?: string; url?: string } | null>(null);
  const [designPreview, setDesignPreview] = useState<{ designs: string[]; initialIndex: number } | null>(null);
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [isSearchEnabled, setIsSearchEnabled] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const notifiedFailedFilesRef = useRef<Set<string>>(new Set());

  const arccoEmblemUrl = "https://qscezcbpwvnkqoevulbw.supabase.co/storage/v1/object/public/Chipro%20calculadora/8.png";

  // ── Modal de edição do projeto ───────────────────────────────────────────
  const [showEditModal, setShowEditModal] = useState(false);
  const [editName, setEditName] = useState('');
  const [editInstructions, setEditInstructions] = useState('');
  const [editFiles, setEditFiles] = useState<ProjectFile[]>([]);
  const [isLoadingFiles, setIsLoadingFiles] = useState(false);
  const [isUpdatingProject, setIsUpdatingProject] = useState(false);
  const [isDeletingProject, setIsDeletingProject] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [isUploadingFile, setIsUploadingFile] = useState(false);
  const editFileInputRef = useRef<HTMLInputElement>(null);

  const openEditModal = () => {
    if (!project) return;
    setEditName(project.name);
    setEditInstructions(project.instructions || '');
    setDeleteConfirm(false);
    setShowEditModal(true);
    setIsLoadingFiles(true);
    projectApi.listFiles(project.id).then(files => {
      setEditFiles(files);
      setIsLoadingFiles(false);
    }).catch(() => setIsLoadingFiles(false));
  };

  const handleSaveProject = async () => {
    if (!project || !editName.trim()) return;
    setIsUpdatingProject(true);
    const updated = await projectApi.update(project.id, {
      name: editName.trim(),
      instructions: editInstructions,
    });
    setIsUpdatingProject(false);
    if (updated) {
      onProjectUpdated?.(updated);
      setShowEditModal(false);
      showToast('Projeto atualizado com sucesso', 'success');
    } else {
      showToast('Erro ao atualizar projeto', 'error');
    }
  };

  const handleDeleteProjectFile = async (fileId: string) => {
    if (!project) return;
    await projectApi.deleteFile(project.id, fileId);
    setEditFiles(prev => prev.filter(f => f.id !== fileId));
  };

  const handleUploadProjectFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !project) return;
    setIsUploadingFile(true);
    const result = await projectApi.uploadFile(project.id, file);
    if (result) {
      setEditFiles(prev => [...prev, result as ProjectFile]);
      showToast('Arquivo enviado. Processamento em andamento.', 'success');
    } else {
      showToast('Erro ao enviar arquivo', 'error');
    }
    setIsUploadingFile(false);
    if (editFileInputRef.current) editFileInputRef.current.value = '';
  };

  const handleDeleteProject = async () => {
    if (!project) return;
    if (!deleteConfirm) { setDeleteConfirm(true); return; }
    setIsDeletingProject(true);
    await projectApi.delete(project.id);
    setIsDeletingProject(false);
    setShowEditModal(false);
    onProjectDeleted?.();
    showToast('Projeto excluído', 'success');
  };

  // Location + Weather (IP-based, no permission needed)
  const [userLocation, setUserLocation] = useState<{ city: string; temp?: number; weatherCode?: number } | null>(null);

  useEffect(() => {
    const CACHE_KEY = 'arcco_location_v2';
    const CACHE_TTL = 30 * 60 * 1000; // 30 min

    // Check valid cache
    try {
      const cached = localStorage.getItem(CACHE_KEY);
      if (cached) {
        const { data, timestamp } = JSON.parse(cached);
        if (data?.city && Date.now() - timestamp < CACHE_TTL) {
          setUserLocation(data);
          return;
        }
      }
    } catch { /* ignore bad cache */ }

    const fetchLocation = async () => {
      try {
        // Proxied via backend — evita bloqueio Safari ITP / ad-blockers
        const res = await fetch('/api/agent/location');
        const data = await res.json();
        if (!data.city) return;

        const location: { city: string; temp?: number; weatherCode?: number } = { city: data.city };
        if (data.temp !== undefined) location.temp = data.temp;
        if (data.weather_code !== undefined) location.weatherCode = data.weather_code;

        setUserLocation(location);
        localStorage.setItem(CACHE_KEY, JSON.stringify({ data: location, timestamp: Date.now() }));
      } catch (e) {
        console.warn('[Arcco] Location fetch failed:', e);
      }
    };

    fetchLocation();
  }, []);

  const getWeatherEmoji = (code: number) => {
    if (code === 0) return '☀️';
    if (code <= 3) return '⛅';
    if (code <= 48) return '🌫️';
    if (code <= 67) return '🌧️';
    if (code <= 77) return '❄️';
    if (code <= 82) return '🌦️';
    return '⛈️';
  };

  // Dynamic Greeting Logic
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour >= 5 && hour < 12) return "Bom dia";
    if (hour >= 12 && hour < 18) return "Boa tarde";
    return "Boa noite";
  };

  const getSubtitle = () => {
    const now = new Date();
    const hour = now.getHours();
    const day = now.getDay(); // 0=Dom, 1=Seg, ..., 6=Sáb
    const isWeekend = day === 0 || day === 6;

    if (hour >= 5 && hour < 12) {
      if (day === 1) return "Segunda-feira com energia! Como posso te ajudar hoje?";
      if (day === 5) return "Sexta chegou! Vamos fechar a semana com tudo. O que fazemos?";
      if (isWeekend) return "Fim de semana produtivo! O que vamos criar juntos?";
      return "Mais um dia para criar algo incrível. Por onde começamos?";
    }
    if (hour >= 12 && hour < 18) {
      if (day === 5) return "Tarde de sexta! Últimos sprints do dia. No que posso ajudar?";
      if (isWeekend) return "Tarde de fim de semana! Em que posso ser útil?";
      return "A tarde é boa para grandes ideias. O que resolvemos hoje?";
    }
    if (hour >= 18 && hour < 23) {
      if (isWeekend) return "Boa noite! Ótima hora para criar algo memorável. Por onde vamos?";
      return "Encerrando o dia ou só aquecendo? Pode contar comigo.";
    }
    return "Madrugada produtiva! O que faremos juntos?";
  };

  const displayName = userName.trim() || 'Usuário';
  const [greetingTime] = useState(getGreeting());
  const [greetingSubtitle] = useState(getSubtitle());
  const [suggestionHints] = useState(() => {
    const hour = new Date().getHours();
    const seed = Math.floor(hour / 3);
    return Array.from({ length: 3 }, (_, i) => allSuggestions[(seed * 3 + i) % allSuggestions.length]);
  });

  const mapSessionFile = (file: SessionFileItem): SessionAttachment => ({
    fileId: file.file_id,
    name: file.original_name,
    sizeBytes: file.size_bytes,
    status: file.status,
    error: file.error,
  });

  const attachmentStatusLabel = (status: SessionFileStatus) => {
    switch (status) {
      case 'ready':
        return 'pronto';
      case 'failed':
        return 'falhou';
      case 'processing':
      case 'uploaded':
      default:
        return 'processando';
    }
  };

  const attachmentStatusClass = (status: SessionFileStatus) => {
    switch (status) {
      case 'ready':
        return 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300';
      case 'failed':
        return 'bg-red-500/10 border-red-500/30 text-red-300';
      case 'processing':
      case 'uploaded':
      default:
        return 'bg-amber-500/10 border-amber-500/30 text-amber-300';
    }
  };

  // Single Source of Truth: busca a chave do Supabase (tabela ApiKeys) a cada mount.
  // Se a chave já estiver injetada (ex: via App.tsx), apenas confirma o estado.
  useEffect(() => {
    const loadApiKey = async () => {
      if (openRouterService.hasApiKey()) {
        setIsApiKeyReady(true);
        return;
      }
      const { data: apiKeyData } = await supabase
        .from('ApiKeys')
        .select('api_key')
        .eq('provider', 'openrouter')
        .eq('is_active', true)
        .single();
      if (apiKeyData?.api_key) {
        openRouterService.setApiKey(apiKeyData.api_key);
        setIsApiKeyReady(true);
      }
    };
    loadApiKey();
  }, []);

  useEffect(() => {
    const loadChatModeConfigs = async () => {
      try {
        const res = await fetch('/api/agent/chat-models');
        if (!res.ok) return;
        const data = await res.json();
        const configs = ((data.models || []) as ChatModeConfig[]).map(config => ({
          ...config,
          slot_number: Number(config.slot_number),
        }));
        setChatModeConfigs(configs);
        if (configs.length > 0) {
          setSelectedChatSlot(prev => prev ?? configs[0].slot_number);
        }
      } catch {
        // chat normal fica indisponível se o backend não responder
      }
    };

    loadChatModeConfigs();
  }, []);

  // Carrega mensagens do Supabase quando chatSessionId for um UUID
  useEffect(() => {
    const isUUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(chatSessionId || '');
    setGeneratedFiles([]);
    setConversationId(null);
    setMessages([]);

    if (!chatSessionId || !isUUID) return;

    setConversationId(chatSessionId);
    const savedMode = getConvMode(chatSessionId);
    if (savedMode !== null) setIsAgentMode(savedMode);
    conversationApi.getMessages(chatSessionId).then(msgs => {
      setMessages(msgs.map(m => ({
        id: m.id,
        role: m.role as 'user' | 'assistant',
        content: m.content,
        timestamp: m.created_at,
      })));
    }).catch(() => setMessages([]));
  }, [chatSessionId]);

  useEffect(() => {
    let cancelled = false;

    const loadSessionFiles = async () => {
      try {
        const files = await agentApi.listSessionFiles(effectiveSessionId);
        if (!cancelled) {
          setAttachments(files.map(mapSessionFile));
        }
      } catch (error) {
        if (!cancelled) {
          console.warn('Falha ao carregar anexos da sessão:', error);
          setAttachments([]);
        }
      }
    };

    loadSessionFiles();

    return () => {
      cancelled = true;
    };
  }, [effectiveSessionId]);

  useEffect(() => {
    if (!attachments.some(att => att.status === 'processing' || att.status === 'uploaded')) {
      return;
    }

    let cancelled = false;
    const interval = setInterval(async () => {
      try {
        const files = await agentApi.listSessionFiles(effectiveSessionId);
        if (!cancelled) {
          setAttachments(files.map(mapSessionFile));
        }
      } catch (error) {
        if (!cancelled) {
          console.warn('Falha ao atualizar anexos da sessão:', error);
        }
      }
    }, 2500);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [attachments, effectiveSessionId]);

  useEffect(() => {
    attachments.forEach(att => {
      if (att.status !== 'failed') {
        return;
      }
      if (notifiedFailedFilesRef.current.has(att.fileId)) {
        return;
      }
      notifiedFailedFilesRef.current.add(att.fileId);
      showToast(`Falha ao processar ${att.name}: ${att.error || 'erro interno no backend'}`, 'error');
    });
  }, [attachments, showToast]);

  useEffect(() => {
    if (messages.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  // Rola para o final quando o BrowserAgentCard aparecer
  useEffect(() => {
    if (browserAction) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [browserAction]);

  useEffect(() => {
    if (initialMessage) {
      handleSendMessage(initialMessage);
      if (onClearInitialMessage) onClearInitialMessage();
    }
  }, [initialMessage]);

  // Timer para elapsed seconds do painel de pensamentos
  useEffect(() => {
    if (!isLoading || agentThoughts.length === 0) return;
    const interval = setInterval(() => {
      setElapsedSeconds(Math.round((Date.now() - thoughtsStartTimeRef.current) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [isLoading, agentThoughts.length]);


  // Histórico persiste apenas no Supabase via background task no backend
  const saveToSession = (_msgs: Message[]) => { /* no-op */ };

  const selectedChatConfig = chatModeConfigs.find(cfg => cfg.slot_number === selectedChatSlot) || null;

  const handleSendMessage = async (text: string = inputValue) => {
    if (!text.trim() || isLoading || !isApiKeyReady) return;

    const userMsgId = Date.now().toString();
    const newUserMsg: Message = { id: userMsgId, role: 'user', content: text, timestamp: new Date().toISOString() };

    const newMessages = [...messages, newUserMsg];
    setMessages(newMessages);
    saveToSession(newMessages); // Save intermediate state

    setInputValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    setIsLoading(true);
    setAgentThoughts([]);
    setGeneratedFiles([]);
    setBrowserAction(null);
    setTextDocArtifact(null);
    setClarificationQuestions(null);
    if (!isAgentMode) {
      setIsTerminalOpen(false);
      setTerminalContent('');
      setChatThinkingMessage(generateThinkingMessage(text));
      // Garante visibilidade mínima do thinking panel (cancela timer anterior se houver)
      if (chatThinkingTimerRef.current) clearTimeout(chatThinkingTimerRef.current);
      chatThinkingStartRef.current = Date.now();
      setChatThinkingVisible(true);
    }
    setIsThoughtsExpanded(true);
    setElapsedSeconds(0);
    thoughtsStartTimeRef.current = Date.now();

    const assistantMsgId = (Date.now() + 1).toString();
    const placeholderAiMsg: Message = { id: assistantMsgId, role: 'assistant', content: '', timestamp: new Date().toISOString() };

    setMessages(prev => [...prev, placeholderAiMsg]);

    try {

      const formattedMessages = newMessages.map(m => ({ role: m.role, content: m.content }));

      // Typing effect queue
      let displayContent = '';
      let queue: string[] = [];
      let isTyping = false;

      const processQueue = async () => {
        if (isTyping || queue.length === 0) return;
        isTyping = true;

        while (queue.length > 0) {
          const chunk = queue.shift();
          if (chunk) {
            displayContent += chunk;
            setMessages(prev => prev.map(msg =>
              msg.id === assistantMsgId ? { ...msg, content: displayContent } : msg
            ));
            await new Promise(r => setTimeout(r, 15 + Math.random() * 20));
          }
        }
        isTyping = false;

        // Save to storage after typing batch is done
        setMessages(currentMessages => {
          saveToSession(currentMessages);
          return currentMessages;
        });
      };

      let hasStartedTalking = false;

      const controller = new AbortController();
      abortControllerRef.current = controller;

      await agentApi.chat(
        formattedMessages,
        !isAgentMode ? (selectedChatConfig?.system_prompt || '') : '',
        (type: string, content: string) => {

          // Agent Thought Panel — captura os steps do orquestrador/especialistas
          if (type === 'steps') {
            const label = content.replace(/<\/?step>/g, '').trim();
            if (label) {
              setAgentThoughts(prev => {
                const updated = prev.map(s =>
                  s.status === 'running' ? { ...s, status: 'done' as const } : s
                );
                return [...updated, { label, status: 'running' }];
              });
            }
            return;
          }

          // Documento de texto — mostra card com botões DOCX / PDF
          if (type === 'text_doc') {
            try {
              const doc = JSON.parse(content);
              if (doc.title && doc.content) {
                setTextDocArtifact({ title: doc.title, content: doc.content });
              }
            } catch { /* ignore parse errors */ }
            return;
          }

          if (type === 'clarification') {
            try {
              const questions = JSON.parse(content);
              if (Array.isArray(questions) && questions.length > 0) {
                setClarificationQuestions(questions);
              }
            } catch { /* ignore parse errors */ }
            return;
          }

          // Pre-action acknowledgement — mostra no bubble do chat (fora do terminal)
          if (type === 'pre_action') {
            const text = content.trim();
            if (text) {
              setChatThinkingMessage(text);
              chatThinkingStartRef.current = Date.now();
              if (chatThinkingTimerRef.current) clearTimeout(chatThinkingTimerRef.current);
              setChatThinkingVisible(true);
            }
            return;
          }

          // Raciocínio do LLM em texto livre (estilo ChatGPT Thinking)
          if (type === 'thought') {
            const thought = content.trim();
            if (thought) {
              setAgentThoughts(prev => {
                const updated = prev.map(s =>
                  s.status === 'running' ? { ...s, status: 'done' as const } : s
                );
                return [...updated, { label: thought, status: 'running', isThought: true }];
              });
            }
            return;
          }

          // Browser Agent Card — mostra card estilo Manus
          if (type === 'browser_action') {
            try {
              const data = JSON.parse(content);
              setBrowserAction(data);
            } catch { /* ignore parse errors */ }
            return;
          }

          if (type === 'file_artifact') {
            try {
              const data = JSON.parse(content);
              const cleanUrl = String(data.url || '').replace(/[.,;:!)\]"']+$/, '');
              const lowerUrl = cleanUrl.split('?')[0].toLowerCase();

              let fileType: 'pdf' | 'excel' | 'other' = 'other';
              if (lowerUrl.endsWith('.pdf')) fileType = 'pdf';
              else if (/\.(xlsx|xls|csv)$/.test(lowerUrl)) fileType = 'excel';
              else if (/\.(docx|doc|pptx)$/.test(lowerUrl)) fileType = 'other';

              if (!cleanUrl) return;

              setGeneratedFiles(prev => {
                if (prev.some(file => file.url === cleanUrl)) {
                  return prev;
                }
                return [...prev, {
                  filename: String(data.filename || 'Arquivo'),
                  url: cleanUrl,
                  type: fileType,
                }];
              });
            } catch { /* ignore parse errors */ }
            return;
          }

          // ID da conversa emitido pelo backend antes do primeiro chunk
          if (type === 'conversation_id') {
            setConversationId(content);
            saveConvMode(content, isAgentMode);
            return;
          }

          if (type === 'chunk') {
            if (!hasStartedTalking) {
              hasStartedTalking = true;
              // Marca o último step como concluído e recolhe o painel com micro-delay
              setAgentThoughts(prev =>
                prev.map(s => s.status === 'running' ? { ...s, status: 'done' as const } : s)
              );
              // Esconde thinking panel com tempo mínimo garantido de 800ms (ambos os modos)
              if (chatThinkingStartRef.current > 0) {
                const elapsed = Date.now() - chatThinkingStartRef.current;
                const delay = Math.max(0, 800 - elapsed);
                chatThinkingTimerRef.current = setTimeout(() => {
                  setChatThinkingVisible(false);
                  chatThinkingStartRef.current = 0;
                }, delay);
              }
              // Colapsa steps inline após breve delay
              setTimeout(() => setIsThoughtsExpanded(false), 600);
            }

            const cleanChunk = content.replace(/<step>[\s\S]*?(<\/step>|$)/g, '');
            if (cleanChunk) {
              queue.push(cleanChunk);
              processQueue();
            }
          }
        },
        controller.signal,
        !isAgentMode ? selectedChatConfig?.openrouter_model_id : undefined,
        isAgentMode ? 'agent' : 'normal',
        effectiveSessionId,
        userId,
        projectId,
        conversationId,
        !isAgentMode && isSearchEnabled,
      );

      // Wait for queue to finish draining typing effect
      while (isTyping || queue.length > 0) {
        await new Promise(r => setTimeout(r, 50));
      }

      // Final save to guarantee persistence
      setMessages(currentMessages => {
        saveToSession(currentMessages);
        return currentMessages;
      });

    } catch (error: any) {
      console.error('Chat error:', error);

      setMessages(prev => {
        const errMsgs = prev.map(msg => {
          if (msg.id === assistantMsgId) {
            return { ...msg, content: `Desculpe, ocorreu um erro na comunicação (${error.message}).`, isError: true };
          }
          return msg;
        });
        saveToSession(errMsgs);
        return errMsgs;
      });
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
      // Garante limpeza do thinking panel em qualquer caso (erro, abort, fim normal)
      if (chatThinkingTimerRef.current) clearTimeout(chatThinkingTimerRef.current);
      setChatThinkingVisible(false);
    }
  };


  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setIsFileLoading(true);
      const uploaded = await agentApi.uploadSessionFile(effectiveSessionId, file);
      setAttachments(prev => {
        const withoutSameId = prev.filter(att => att.fileId !== uploaded.file_id);
        return [...withoutSameId, {
          fileId: uploaded.file_id,
          name: uploaded.original_name,
          sizeBytes: uploaded.size_bytes,
          status: uploaded.status,
          error: null,
        }];
      });
      showToast('Arquivo anexado. Processamento iniciado em background.', 'success');
    } catch (err: any) {
      console.error('Erro no upload da sessão:', err);
      showToast(`Erro ao processar arquivo: ${err.message} `, 'error');
    } finally {
      setIsFileLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage(inputValue);
    }
  };

  const renderContent = (content: string) => {
    // Detecta resposta que é uma apresentação HTML completa (terminal tool generate_web_page)
    const trimmedContent = content.trim();
    if (trimmedContent.startsWith('<!DOCTYPE') || trimmedContent.toLowerCase().startsWith('<html')) {
      const DESIGN_SEPARATOR = '<!-- ARCCO_DESIGN_SEPARATOR -->';
      const designs = trimmedContent.split(DESIGN_SEPARATOR).map(d => d.trim()).filter(Boolean);
      const openSingleDesign = () => setDesignPreview({ designs, initialIndex: 0 });
      const openDesignByIndex = (index: number) => setDesignPreview({ designs, initialIndex: index });
      if (designs.length > 1) {
        return <DesignGallery designs={designs} isStreaming={isLoading} onOpenPreview={openDesignByIndex} />;
      }
      return <PresentationCard html={designs[0] || trimmedContent} isStreaming={isLoading} onOpenPreview={openSingleDesign} />;
    }

    // Matches closed OR unclosed code blocks (until end of string) for streaming safety
    const parts = content.split(/(```[\s\S]*? (?: ```|$))/g);
    return parts.map((part, index) => {
      if (part.startsWith('```')) {
        const match = part.match(/```(\w*)\n?([\s\S]*?)(?:```|$)/);
        if (!match) return <pre key={index} className="bg-[#111] p-3 rounded-lg overflow-x-auto text-sm">{part}</pre>;
        const language = match[1] || 'text';
        const code = match[2];

        // Fallback for non-design JSONs or invalid JSONs during stream
        return <ArtifactCard key={index} title="Snippet" language={language} content={code} type={language === 'json' ? 'json' : 'code'} />;
      } else {
        // Parse markdown links outside of code blocks: [text](https://url) or bare https://url
        const linkRegex = /\[([^\]]+)\]\((https?:\/\/[^)]+)\)|(https?:\/\/[^\s)]+)/g;
        if (!linkRegex.test(part)) {
          return <div key={index} className="whitespace-pre-wrap leading-relaxed">{part}</div>;
        }

        // Split by regex, yielding array of strings and matches
        const tokens: React.ReactNode[] = [];
        let lastIndex = 0;
        let match;

        // Reset regex state since we tested it
        linkRegex.lastIndex = 0;
        let matchIdx = 0;

        while ((match = linkRegex.exec(part)) !== null) {
          // Add text before match
          if (match.index > lastIndex) {
            tokens.push(<span key={`text-${index}-${lastIndex}`}>{part.substring(lastIndex, match.index)}</span>);
          }

          let title = '';
          let url = '';

          if (match[2]) {
            // Markdown format [title](url)
            title = match[1];
            url = match[2];
          } else if (match[3]) {
            // Bare url format
            url = match[3];
            // Get the last part of the URL, split by ? to remove query params
            const pathPart = url.split('?')[0];
            title = pathPart.split('/').pop() || url;

            // Clean up common URL trailing punctuations like '.' or ','
            if (title.endsWith('.') || title.endsWith(',')) {
              title = title.slice(0, -1);
              url = url.slice(0, -1);
            }
          }

          tokens.push(
            <a key={`link-${index}-${matchIdx}`} href={url} target="_blank" rel="noopener noreferrer" className="text-indigo-400 hover:text-indigo-300 underline underline-offset-2">
              {title}
            </a>
          );

          lastIndex = linkRegex.lastIndex;
          matchIdx++;
        }

        // Add remaining text
        if (lastIndex < part.length) {
          tokens.push(<span key={`text-${index}-${lastIndex}`}>{part.substring(lastIndex)}</span>);
        }

        return <div key={index} className="whitespace-pre-wrap leading-relaxed flex flex-col items-start gap-1">{tokens}</div>;
      }
    });
  };

  const renderInputArea = (variant: 'centered' | 'bottom') => (
    <div className={`relative group w-full ${variant === 'centered' ? 'max-w-2xl' : 'max-w-4xl mx-auto'}`}>
      <div className="absolute -inset-0.5 bg-gradient-to-r from-neutral-700/20 to-neutral-500/20 rounded-[24px] blur opacity-0 group-hover:opacity-100 transition duration-500"></div>
      <div className={`relative bg-[#121212]/95 border border-[#333] rounded-[24px] px-4 py-3 shadow-2xl ${variant === 'centered' ? 'min-h-[56px]' : ''}`}>
        <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          rows={1}
          value={inputValue}
          onChange={(e) => {
            setInputValue(e.target.value);
            if (textareaRef.current) {
              textareaRef.current.style.height = 'auto';
              textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
            }
          }}
          onKeyDown={handleKeyDown}
          placeholder={isFileLoading ? "Enviando arquivo..." : "Digite sua mensagem... (Shift+Enter para nova linha)"}
          className="flex-1 bg-transparent border-none outline-none text-white placeholder-neutral-500 focus:ring-0 resize-none overflow-hidden leading-relaxed py-0"
          autoFocus={variant === 'centered'}
        />

        <div className="relative group/send flex-shrink-0">
          <button
            onClick={() => handleSendMessage(inputValue)}
            disabled={isLoading || !isApiKeyReady || (!isAgentMode && !selectedChatConfig) || !inputValue.trim()}
            className="p-2 rounded-lg text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors bg-neutral-800 hover:bg-neutral-700"
          >
            <Send size={18} />
          </button>
          <div className="absolute bottom-full right-0 mb-2 px-2 py-1 bg-[#1a1a1d] border border-[#2a2a2a] rounded-lg text-[11px] text-neutral-400 whitespace-nowrap opacity-0 invisible group-hover/send:opacity-100 group-hover/send:visible transition-all duration-150 pointer-events-none z-50 flex items-center gap-1.5">
            {!isApiKeyReady ? 'Carregando API...' : (!isAgentMode && !selectedChatConfig) ? 'Configure um modelo no admin' : <><span>Enviar</span><kbd className="px-1 py-0.5 bg-[#252525] rounded text-[10px] text-neutral-500">↵</kbd></>}
          </div>
        </div>
        </div>

        <div className="mt-2 flex items-center gap-1.5">
          <div className="relative flex items-center gap-1">
            <input type="file" hidden ref={fileInputRef} onChange={handleFileUpload} />
            <div className="relative group/add">
            <button
              onClick={() => setShowAddMenu(!showAddMenu)}
              disabled={isFileLoading}
              className="inline-flex h-7 w-7 items-center justify-center rounded-full text-neutral-500 hover:text-neutral-300 hover:bg-white/[0.03] transition-colors disabled:cursor-not-allowed"
            >
              {isFileLoading
                ? <Loader2 size={13} className="animate-spin text-indigo-400" />
                : <Plus size={14} />
              }
            </button>
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-[#1a1a1d] border border-[#2a2a2a] rounded-lg text-[11px] text-neutral-400 whitespace-nowrap opacity-0 invisible group-hover/add:opacity-100 group-hover/add:visible transition-all duration-150 pointer-events-none z-50">
              {isFileLoading ? 'Enviando...' : 'Anexar arquivo ou link'}
            </div>
            </div>

            {showAddMenu && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowAddMenu(false)} />
                <div className="absolute bottom-[calc(100%+12px)] left-0 w-64 bg-[#1a1a1d] border border-[#333] rounded-xl shadow-2xl overflow-hidden z-50 animate-in fade-in slide-in-from-bottom-2">
                  <button
                    onClick={() => { setShowAddMenu(false); !isFileLoading && fileInputRef.current?.click(); }}
                    className="w-full flex items-center gap-3 px-4 py-3 text-sm text-neutral-300 hover:text-white hover:bg-white/[0.05] transition-colors text-left"
                  >
                    <Paperclip size={16} className="text-neutral-500" />
                    Upload de arquivos ou fotos
                  </button>
                  <button
                    onClick={() => {
                      setShowAddMenu(false);
                      const url = window.prompt("URL do site ou arquivo:");
                      if (url && url.trim()) {
                        setInputValue(prev => prev + (prev.endsWith(' ') || prev === '' ? '' : ' ') + url);
                      }
                    }}
                    className="w-full flex items-center gap-3 px-4 py-3 text-sm text-neutral-300 hover:text-white hover:bg-white/[0.05] transition-colors text-left"
                  >
                    <Link size={16} className="text-neutral-500" />
                    Url
                  </button>
                </div>
              </>
            )}
          </div>

          <div className="relative group/tools">
            <button
              onClick={() => showToast('Seletor de tools ainda não está conectado.', 'success')}
              className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] text-neutral-500 hover:text-neutral-300 hover:bg-white/[0.03] transition-colors"
            >
              <Wrench size={12} />
              <span>Tools</span>
            </button>
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-[#1a1a1d] border border-[#2a2a2a] rounded-lg text-[11px] text-neutral-400 whitespace-nowrap opacity-0 invisible group-hover/tools:opacity-100 group-hover/tools:visible transition-all duration-150 pointer-events-none z-50">
              Ferramentas disponíveis para o agente
            </div>
          </div>

          {!isAgentMode && (
            <div className="relative group/search">
              <button
                onClick={() => setIsSearchEnabled(p => !p)}
                className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] transition-all duration-200 ${
                  isSearchEnabled
                    ? 'text-indigo-400 bg-indigo-500/10 hover:bg-indigo-500/15'
                    : 'text-neutral-500 hover:text-neutral-300 hover:bg-white/[0.03]'
                }`}
              >
                <Globe size={12} />
                <span>Pesquisa</span>
              </button>
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-[#1a1a1d] border border-[#2a2a2a] rounded-lg text-[11px] text-neutral-400 whitespace-nowrap opacity-0 invisible group-hover/search:opacity-100 group-hover/search:visible transition-all duration-150 pointer-events-none z-50">
                {isSearchEnabled ? 'Ativo · o modelo pesquisará em tempo real na internet' : 'O modelo pesquisará em tempo real na internet'}
              </div>
            </div>
          )}
        </div>
      </div>

      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-2 px-1">
          {attachments.map((att, i) => (
            <div
              key={att.fileId || i}
              className={`flex items-center gap-2 border text-xs px-2.5 py-1 rounded-full ${attachmentStatusClass(att.status)}`}
              title={att.error || `${att.name} • ${attachmentStatusLabel(att.status)}`}
            >
              {att.status === 'processing' || att.status === 'uploaded' ? (
                <Loader2 size={12} className="animate-spin" />
              ) : null}
              <span className="truncate max-w-[150px]">{att.name}</span>
              <span className="uppercase text-[10px] opacity-80">{attachmentStatusLabel(att.status)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div className="flex flex-row h-full w-full overflow-hidden" style={{ backgroundColor: 'var(--bg-base)' }}>
      <div className="flex flex-col h-full bg-transparent text-white relative w-full">
        <DotGridBackground />

        {/* Header */}
        <div className="h-16 border-b border-[#222] flex items-center px-6 bg-[#0a0a0a]/80 backdrop-blur-md relative z-20 transition-opacity duration-500">

          {/* Projeto ativo — badge + botões de edição */}
          {project && (
            <div className="flex items-center gap-2 mr-4">
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-sm font-medium max-w-[180px]">
                <Folder size={13} className="text-indigo-400 flex-shrink-0" />
                <span className="truncate">{project.name}</span>
              </div>
              <button
                onClick={openEditModal}
                className="p-1.5 text-neutral-500 hover:text-indigo-400 hover:bg-indigo-500/10 rounded-lg transition-colors"
                title="Editar projeto"
              >
                <Pencil size={14} />
              </button>
            </div>
          )}

          {/* Model Selector */}
          <div className="relative">
            <div className="flex flex-col items-start">
              {isAgentMode ? (
                <div className="relative group/model-agent">
                  <button
                    onClick={() => setShowModelDropdown(p => !p)}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-all duration-200 border ${showModelDropdown ? 'text-white bg-white/[0.05] border-[#333]' : 'text-neutral-400 hover:text-white border-transparent hover:bg-white/[0.04] hover:border-[#2a2a2a]'}`}
                  >
                    <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 flex-shrink-0" />
                    <span className="font-medium">Arcco Pro V1</span>
                    <ChevronDown size={13} className={`text-neutral-500 transition-transform duration-200 ${showModelDropdown ? 'rotate-180' : ''}`} />
                  </button>
                  <div className="absolute top-full left-0 mt-2 px-2 py-1 bg-[#1a1a1d] border border-[#2a2a2a] rounded-lg text-[11px] text-neutral-400 whitespace-nowrap opacity-0 invisible group-hover/model-agent:opacity-100 group-hover/model-agent:visible transition-all duration-150 pointer-events-none z-50">
                    Modelo de IA ativo
                  </div>
                </div>
              ) : (
                <div className="relative group/model-chat">
                  <button
                    onClick={() => setShowChatModelDropdown(p => !p)}
                    disabled={chatModeConfigs.length === 0}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-all duration-200 border disabled:opacity-40 disabled:cursor-not-allowed ${showChatModelDropdown ? 'text-white bg-white/[0.05] border-[#333]' : 'text-neutral-400 hover:text-white border-transparent hover:bg-white/[0.04] hover:border-[#2a2a2a]'}`}
                  >
                    <span className="font-medium">{selectedChatConfig?.model_name || 'Nenhum modelo'}</span>
                    <ChevronDown size={13} className={`text-neutral-500 transition-transform duration-200 ${showChatModelDropdown ? 'rotate-180' : ''}`} />
                  </button>
                  <div className="absolute top-full left-0 mt-2 px-2 py-1 bg-[#1a1a1d] border border-[#2a2a2a] rounded-lg text-[11px] text-neutral-400 whitespace-nowrap opacity-0 invisible group-hover/model-chat:opacity-100 group-hover/model-chat:visible transition-all duration-150 pointer-events-none z-50">
                    Selecionar modelo de resposta
                  </div>
                </div>
              )}
              <span className="text-[10px] text-neutral-700 px-3 tracking-wide">
                {isAgentMode ? 'Agent' : 'Chat'}
              </span>
            </div>

            {/* Agent mode dropdown */}
            {isAgentMode && showModelDropdown && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowModelDropdown(false)} />
                <div className="absolute top-full left-0 mt-1.5 w-60 bg-[#111] border border-[#252525] rounded-xl shadow-2xl z-50 overflow-hidden">
                  <div className="p-1.5">
                    <button
                      onClick={() => setShowModelDropdown(false)}
                      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left bg-indigo-500/10 hover:bg-indigo-500/15 transition-colors"
                    >
                      <div className="flex-shrink-0 w-7 h-7 rounded-lg bg-indigo-500/20 flex items-center justify-center">
                        <Sparkles size={12} className="text-indigo-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-white">Arcco Pro V1</p>
                        <p className="text-[11px] text-neutral-500 mt-0.5">Modelo principal</p>
                      </div>
                      <Check size={13} className="text-indigo-400 flex-shrink-0" />
                    </button>
                    <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg opacity-35 cursor-not-allowed mt-0.5">
                      <div className="flex-shrink-0 w-7 h-7 rounded-lg bg-neutral-800 flex items-center justify-center">
                        <Sparkles size={12} className="text-neutral-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-neutral-400">Arcco Symphony</p>
                        <p className="text-[11px] text-neutral-600 mt-0.5">Em breve</p>
                      </div>
                    </div>
                  </div>
                </div>
              </>
            )}

            {/* Chat mode dropdown */}
            {!isAgentMode && showChatModelDropdown && chatModeConfigs.length > 0 && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowChatModelDropdown(false)} />
                <div className="absolute top-full left-0 mt-1.5 w-64 bg-[#111] border border-[#252525] rounded-xl shadow-2xl z-50 overflow-hidden">
                  <div className="p-1.5">
                    {chatModeConfigs.map(config => (
                      <button
                        key={config.slot_number}
                        onClick={() => { setSelectedChatSlot(config.slot_number); setShowChatModelDropdown(false); }}
                        className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors ${config.slot_number === selectedChatSlot
                          ? 'bg-indigo-500/10 hover:bg-indigo-500/15'
                          : 'hover:bg-white/[0.04]'
                        }`}
                      >
                        <div className="flex-1 min-w-0">
                          <p className={`text-sm font-medium ${config.slot_number === selectedChatSlot ? 'text-white' : 'text-neutral-300'}`}>
                            {config.model_name}
                          </p>
                        </div>
                        {config.slot_number === selectedChatSlot && (
                          <Check size={13} className="text-indigo-400 flex-shrink-0" />
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Mode Toggle — header */}
          <div className="ml-auto relative group">
            <button
              onClick={() => {
                if (messages.length > 0) return;
                setIsAgentMode(prev => {
                  const next = !prev;
                  if (!next) {
                    setIsTerminalOpen(false);
                    setTerminalContent('');
                  }
                  if (!next && !selectedChatSlot && chatModeConfigs.length > 0) {
                    setSelectedChatSlot(chatModeConfigs[0].slot_number);
                  }
                  return next;
                });
                setShowModelDropdown(false);
              }}
              disabled={messages.length > 0}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-300 border ${
                messages.length > 0
                  ? 'text-neutral-700 border-[#252525] cursor-not-allowed opacity-50'
                  : 'text-neutral-500 border-[#333] hover:text-neutral-300 hover:border-neutral-600'
              }`}
            >
              <Sparkles size={13} className="opacity-50" />
              {isAgentMode ? 'Modo Chat' : 'Modo Agent'}
            </button>

            {/* Tooltip personalizado on hover */}
            <div className="absolute right-0 top-full mt-2 w-64 p-3 bg-[#1a1a1d] border border-[#333] rounded-xl shadow-2xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50 pointer-events-none">
              <p className="text-xs text-neutral-300 leading-relaxed text-left">
                {messages.length > 0
                  ? 'O modo não pode ser alterado durante uma conversa.'
                  : isAgentMode
                    ? 'Modo chat, é para conversas e dúvidas simples que exigem pouca capacidade computacional e também é para tarefas mais rápidas.'
                    : 'Modo agente, é utilizado para tarefas complexas, pesquisa de mercados, processamento massivo de dados.'}
              </p>
            </div>
          </div>

        </div>

        <div className="flex-1 overflow-y-auto z-10 relative scrollbar-hide">

          {messages.length === 0 ? (
            // GREETING STATE
            <div className="h-full flex flex-col items-center justify-center p-4 -mt-16">

              <div className="flex flex-col items-center text-center mb-10">

                {/* Weather badge — aparece apenas quando location carregou */}
                <div className={`flex items-center gap-2 mb-6 px-3.5 py-1.5 rounded-full bg-[#111] border border-[#222] text-[12px] text-neutral-400 transition-all duration-500 ${userLocation ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
                  {userLocation && (
                    <>
                      <span>{getWeatherEmoji(userLocation.weatherCode ?? 0)}</span>
                      <span className="text-neutral-300">{userLocation.city}</span>
                      {userLocation.temp !== undefined && (
                        <>
                          <span className="text-neutral-700">·</span>
                          <span>{userLocation.temp}°C</span>
                        </>
                      )}
                    </>
                  )}
                </div>

                {/* Greeting */}
                {project ? (
                  <>
                    <div className="flex items-center gap-1.5 mb-2">
                      <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                        <Folder size={22} className="text-indigo-400" />
                      </div>
                      <h1 className="text-2xl md:text-3xl font-normal text-white tracking-tight leading-snug">
                        {project.name}
                      </h1>
                    </div>
                    <p className="text-lg md:text-xl font-normal text-neutral-500 tracking-tight leading-snug mt-1">
                      {project.instructions
                        ? project.instructions.slice(0, 80) + (project.instructions.length > 80 ? '...' : '')
                        : 'Como posso ajudar neste projeto hoje?'
                      }
                    </p>
                  </>
                ) : (
                  <>
                    <div className="flex items-center gap-3 mb-2">
                      <div className="animate-pulse duration-[3000ms]">
                        <img
                          src={arccoEmblemUrl}
                          alt="Arcco Emblem"
                          className="w-[72px] h-[72px] object-contain opacity-90"
                        />
                      </div>
                      <h1 className="text-2xl md:text-3xl font-normal text-white tracking-tight leading-snug">
                        {greetingTime}, {displayName}
                      </h1>
                    </div>
                    <p className="text-lg md:text-xl font-normal text-neutral-500 tracking-tight leading-snug mt-1">
                      {userLocation
                        ? `Como está aí em ${userLocation.city}? ${greetingSubtitle}`
                        : greetingSubtitle
                      }
                    </p>
                  </>
                )}
              </div>

              {renderInputArea('centered')}

              <div className="flex flex-wrap gap-2 justify-center max-w-2xl mt-8 opacity-60 hover:opacity-100 transition-opacity">
                {suggestionHints.map(hint => (
                  <button
                    key={hint}
                    onClick={() => handleSendMessage(hint)}
                    className="px-4 py-2 bg-[#1a1a1a] hover:bg-[#222] border border-[#262626] rounded-full text-xs text-neutral-300 transition-colors"
                  >
                    {hint}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            // ACTIVE CHAT STATE - NO AVATARS
            <div className="flex flex-col min-h-full">
              <div className="flex-1 p-4 md:p-6 space-y-6 max-w-4xl mx-auto w-full">
                {messages.map((msg, msgIndex) => {
                  const isLastAssistant = msg.role === 'assistant' && msgIndex === messages.length - 1;
                  const isStreaming = isLastAssistant && isLoading && msg.content.length > 0;

                  return (
                    <div
                      key={msg.id}
                      className={`flex items-start gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
                    >
                      {msg.role === 'assistant' && (
                        <div className="flex-shrink-0 pt-0.5">
                          <img
                            src={arccoEmblemUrl}
                            alt="Arcco"
                            className={`w-[50px] h-[50px] object-contain opacity-75 ${isStreaming ? 'animate-pulse' : ''}`}
                          />
                        </div>
                      )}
                      <div className={`max-w-[85%] md:max-w-[80%] rounded-2xl px-5 py-4 relative group
                                  ${msg.role === 'user'
                          ? 'bg-[#222] text-white rounded-tr-sm shadow-md'
                          : 'bg-transparent text-neutral-200'
                        } ${msg.isError ? 'border border-red-500/30 bg-red-500/10' : ''} ${isStreaming ? 'animate-typing-border' : ''
                        }`}
                      >
                        {isLastAssistant && chatThinkingVisible ? (
                          <div className="flex flex-col gap-2.5 animate-in fade-in duration-300">
                            <div className="flex items-center gap-2">
                              <div className="w-3.5 h-3.5 rounded-full border-[1.5px] border-indigo-400/80 border-t-transparent animate-spin flex-shrink-0" />
                              <span className="text-sm text-neutral-400 font-medium">Trabalhando</span>
                            </div>
                            <div className="pl-5 border-l border-[#2a2a2a] ml-[3px] animate-in fade-in slide-in-from-left-1 duration-500">
                              <p className="text-xs text-neutral-600 leading-relaxed">
                                {chatThinkingMessage}
                              </p>
                            </div>
                          </div>
                        ) : renderContent(msg.content)}
                      </div>
                    </div>
                  );
                })}

                {/* Inline Steps — mostra steps do orquestrador inline no chat (apenas agent mode) */}
                {isAgentMode && agentThoughts.length > 0 && (() => {
                  const allDone = agentThoughts.every(s => s.status === 'done');
                  const actionSteps = agentThoughts.filter(s => !s.isThought);
                  const collapsed = allDone && !isThoughtsExpanded;

                  return (
                    <div className="w-full max-w-[85%] md:max-w-[80%] pl-[62px]">
                      {collapsed ? (
                        <button
                          onClick={() => setIsThoughtsExpanded(true)}
                          className="flex items-center gap-1.5 text-sm text-neutral-600 hover:text-neutral-400 transition-colors py-1"
                        >
                          <span className="text-neutral-700">&#9662;</span>
                          <span>{actionSteps.length} etapa{actionSteps.length !== 1 ? 's' : ''} · {elapsedSeconds}s</span>
                        </button>
                      ) : (
                        <div className="space-y-3 py-1">
                          {agentThoughts.map((step, i) => {
                            const isRunning = step.status === 'running';
                            const label = step.label.replace(/[\p{Emoji_Presentation}\p{Extended_Pictographic}\u200d\ufe0f]/gu, '').trim();

                            if (step.isThought) {
                              return (
                                <div key={i} className="flex items-start gap-2.5 animate-step-enter" style={{ animationDelay: `${i * 40}ms` }}>
                                  <img
                                    src={arccoEmblemUrl}
                                    alt=""
                                    className={`w-4 h-4 object-contain mt-0.5 flex-shrink-0 ${isRunning ? 'animate-pulse-soft' : 'opacity-30'}`}
                                  />
                                  <span className={`text-sm italic ${isRunning ? 'text-neutral-500 animate-pulse-soft' : 'text-neutral-700'}`}>
                                    {label}
                                  </span>
                                </div>
                              );
                            }

                            return (
                              <div key={i} className="flex items-start gap-2.5 animate-step-enter" style={{ animationDelay: `${i * 40}ms` }}>
                                <img
                                  src={arccoEmblemUrl}
                                  alt=""
                                  className={`w-4 h-4 object-contain mt-0.5 flex-shrink-0 ${isRunning ? 'animate-pulse-soft' : 'opacity-30'}`}
                                />
                                <span className={`text-sm ${isRunning ? 'text-neutral-400 animate-pulse-soft' : 'text-neutral-600'}`}>
                                  {label}
                                </span>
                              </div>
                            );
                          })}
                          {allDone && (
                            <button
                              onClick={() => setIsThoughtsExpanded(false)}
                              className="flex items-center gap-1.5 text-sm text-neutral-600 hover:text-neutral-400 transition-colors pt-1"
                            >
                              <span className="text-neutral-700">&#9652;</span>
                              <span>{actionSteps.length} etapa{actionSteps.length !== 1 ? 's' : ''} · {elapsedSeconds}s</span>
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })()}

                {/* Browser Agent Card — mostra card estilo Manus quando o agente navega */}
                {browserAction && (
                  <div className="w-full max-w-[85%] md:max-w-[80%]">
                    <BrowserAgentCard action={browserAction as any} />
                  </div>
                )}

                {generatedFiles.length > 0 && (
                  <div className="w-full max-w-[85%] md:max-w-[80%] flex flex-col gap-3">
                    {generatedFiles.map(file => (
                      <FilePreviewCard
                        key={file.url}
                        url={file.url}
                        filename={file.filename}
                        type={file.type}
                        onOpenPreview={() => setModalPreview({ type: file.type, title: file.filename, url: file.url })}
                      />
                    ))}
                  </div>
                )}

                {/* Clarification Card — perguntas antes de executar o pipeline */}
                {clarificationQuestions && !isLoading && (
                  <div className="w-full max-w-[85%] md:max-w-[80%]">
                    <ClarificationCard
                      questions={clarificationQuestions}
                      onSubmit={(answers) => {
                        const responseText = clarificationQuestions.map((q, i) =>
                          `${q.text} ${answers[i]}`
                        ).join('\n');
                        setClarificationQuestions(null);
                        handleSendMessage(responseText);
                      }}
                    />
                  </div>
                )}

                {/* Text Document Artifact — botões DOCX / PDF para documentos escritos */}
                {textDocArtifact && !isLoading && (
                  <div className="w-full max-w-[85%] md:max-w-[80%]">
                    <TextDocCard
                      title={textDocArtifact.title}
                      content={textDocArtifact.content}
                      onOpenPreview={(title, content) => setModalPreview({ type: 'text_doc', title, content })}
                    />
                  </div>
                )}

                {/* Loading — Agent mode: aguardando primeiro step inline */}
                {isLoading && isAgentMode && agentThoughts.length === 0 && (
                  <div className="w-full max-w-[85%] md:max-w-[80%] pl-[62px] py-1">
                    <div className="flex items-center gap-2 animate-step-enter">
                      <img
                        src={arccoEmblemUrl}
                        alt=""
                        className="w-4 h-4 object-contain animate-pulse-soft flex-shrink-0"
                      />
                      <span className="text-sm text-neutral-500 animate-pulse-soft">Analisando...</span>
                    </div>
                  </div>
                )}


                {/* Botão Parar — aparece durante execução do agente */}
                {isLoading && (
                  <div className="flex justify-center my-3">
                    <button
                      onClick={() => {
                        abortControllerRef.current?.abort();
                        setIsLoading(false);
                        setAgentThoughts(prev =>
                          prev.map(s => s.status === 'running' ? { ...s, status: 'done' as const, label: s.label + ' (parado)' } : s)
                        );
                        setIsThoughtsExpanded(false);
                      }}
                      className="flex items-center gap-2 px-5 py-2 bg-[#141414] hover:bg-[#1e1e1e] border border-[#2a2a2a] hover:border-neutral-600 rounded-full text-[11px] text-neutral-500 hover:text-neutral-300 transition-all duration-200 backdrop-blur-sm"
                      title="Cancelar a geração da resposta"
                    >
                      <Square size={10} fill="currentColor" />
                      Parar geração
                    </button>
                  </div>
                )}
              </div>
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {messages.length > 0 && (
          <div className="p-4 bg-transparent border-t border-[#222] z-10 relative backdrop-blur-sm flex flex-col gap-4">
            {renderInputArea('bottom')}
          </div>
        )}
      </div>

      {project && (
        <ProjectEditModal
          project={project}
          open={showEditModal}
          editName={editName}
          editInstructions={editInstructions}
          editFiles={editFiles}
          isLoadingFiles={isLoadingFiles}
          isUpdatingProject={isUpdatingProject}
          isDeletingProject={isDeletingProject}
          deleteConfirm={deleteConfirm}
          isUploadingFile={isUploadingFile}
          editFileInputRef={editFileInputRef}
          onClose={() => { setShowEditModal(false); setDeleteConfirm(false); }}
          onEditNameChange={setEditName}
          onEditInstructionsChange={setEditInstructions}
          onUploadClick={() => editFileInputRef.current?.click()}
          onUploadFile={handleUploadProjectFile}
          onDeleteProjectFile={handleDeleteProjectFile}
          onDeleteProject={handleDeleteProject}
          onSaveProject={handleSaveProject}
        />
      )}

      {/* Document Preview Modal */}
      {modalPreview && (
        <DocumentPreviewModal
          isOpen={!!modalPreview}
          onClose={() => setModalPreview(null)}
          data={modalPreview}
        />
      )}

      {/* Design Preview Modal */}
      {designPreview && (
        <DesignPreviewModal
          isOpen={!!designPreview}
          onClose={() => setDesignPreview(null)}
          designs={designPreview.designs}
          initialIndex={designPreview.initialIndex}
        />
      )}
    </div >
  );
};

export default ArccoChatPage;
