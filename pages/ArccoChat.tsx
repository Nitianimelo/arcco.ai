import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Send, Loader2, Sparkles, FileText, Download, ChevronDown, Paperclip, HardDrive, FileSpreadsheet, Eye, Square, Plus, Link, Folder, Pencil, Trash2, Upload, X, Check, AlertTriangle, Wrench, Globe } from 'lucide-react';
import SpyPagesInputCard from '../components/chat/SpyPagesInputCard';
import SpyPagesResultCard, { SpyPagesSite } from '../components/chat/SpyPagesResultCard';
import { projectApi, Project, ProjectFile } from '../lib/projectApi';
import { openRouterService } from '../lib/openrouter';
import { agentApi, SessionFileItem, SessionFileStatus } from '../lib/api-client';
import { supabase } from '../lib/supabase';
import { ArtifactCard } from '../components/chat/ArtifactCard';
import { ThoughtStep } from '../components/chat/AgentThoughtPanel';
import { BrowserAgentCard } from '../components/chat/BrowserAgentCard';
import TextDocCard from '../components/chat/TextDocCard';
import ClarificationCard from '../components/chat/ClarificationCard';
import DesignGallery from '../components/chat/DesignGallery';
import DesignPreviewModal from '../components/chat/DesignPreviewModal';
import DocumentPreviewModal from '../components/chat/DocumentPreviewModal';
import { ProjectEditModal } from '../components/chat/ProjectEditModal';
import { GridPattern } from '../components/ui/grid-pattern';
import { useToast } from '../components/Toast';
// AgentTerminal removido — steps agora são inline
import { ChatSession, Message } from '../lib/chatStorage';
import { conversationApi } from '../lib/conversationApi';
import { withBackendUrl } from '../lib/backendUrl';

const DESIGN_ARTIFACT_SENTINEL = '__ARCCO_DESIGN_ARTIFACT__';
const MAX_CHAT_FILE_SIZE_BYTES = 100 * 1024 * 1024;
const DESIGN_SEPARATOR = '<!-- ARCCO_DESIGN_SEPARATOR -->';

interface FilePreviewCardProps {
  url: string;
  filename: string;
  type: 'pdf' | 'excel' | 'other';
  onOpenPreview?: () => void;
}

const FilePreviewCard: React.FC<FilePreviewCardProps> = ({ url, filename, type, onOpenPreview }) => {
  const { showToast } = useToast();

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
            className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-md bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition-colors"
          >
            <Eye size={13} /> Preview
          </button>
        )}
        <button
          onClick={handleDownload}
          className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-md border border-neutral-700 text-neutral-400 hover:text-neutral-200 hover:border-neutral-600 text-xs font-medium transition-colors"
        >
          <Download size={13} /> Baixar
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
  onConversationIdChange?: (conversationId: string) => void;
  onSessionUpdate?: (session: ChatSession) => void;
  initialMessage?: string | null;
  onClearInitialMessage?: () => void;
}

interface ChatModeConfig {
  id?: number;
  slot_number: number;
  model_name: string;
  openrouter_model_id: string;
  fast_model_id?: string;
  fast_system_prompt?: string;
  system_prompt?: string;
  is_active: boolean;
}

interface SessionAttachment {
  fileId: string;
  clientId?: string;
  name: string;
  sizeBytes: number;
  status: SessionFileStatus | 'uploading';
  error?: string | null;
  progressPercent?: number;
  loadedBytes?: number;
  source?: 'local' | 'server';
}

interface BrowserClarificationPayload {
  questions: Array<{
    type: 'choice' | 'open';
    text: string;
    options: string[];
    option_details?: Array<{ label: string; description?: string; recommended?: boolean }>;
    helper_text?: string;
  }>;
  helperText?: string;
  actionUrl?: string;
  actionLabel?: string;
  resumeToken?: string;
  originalPrompt?: string;
}

interface WorkflowStageView {
  stage_id: string;
  label: string;
  status: 'pending' | 'in_progress' | 'waiting_user' | 'completed' | 'skipped';
}

interface WorkflowSnapshotView {
  workflowId: string;
  message: string;
  stages: WorkflowStageView[];
}

interface PolicyDecisionView {
  decision_id: string;
  route: string;
  user_message: string;
  should_abort: boolean;
  continue_partial: boolean;
  retry_same_route: boolean;
}

interface ReplanDecisionView {
  from_route: string;
  to_route: string;
  to_tool_name: string;
  user_message: string;
}

const splitDesignsFromHtml = (rawHtml: string): string[] => {
  const normalized = (rawHtml || '').trim();
  if (!normalized) return [];
  return normalized.split(DESIGN_SEPARATOR).map(d => d.trim()).filter(Boolean);
};

const mergeUniqueDesigns = (current: string[] | null, next: string[]): string[] => {
  const merged = [...(current || [])];
  const seen = new Set(merged);
  for (const item of next) {
    const normalized = item.trim();
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    merged.push(normalized);
  }
  return merged;
};

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
  onConversationIdChange,
  onSessionUpdate,
  initialMessage,
  onClearInitialMessage,
}) => {
  const { showToast } = useToast();
  const [localSessionId] = useState(() => Date.now().toString());
  const [activeSessionId, setActiveSessionId] = useState(() => chatSessionId || localSessionId);
  const effectiveSessionId = activeSessionId;
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
  const [workflowSnapshots, setWorkflowSnapshots] = useState<WorkflowSnapshotView[]>([]);
  const [policyDecisions, setPolicyDecisions] = useState<PolicyDecisionView[]>([]);
  const [replanDecisions, setReplanDecisions] = useState<ReplanDecisionView[]>([]);
  const [isThoughtsExpanded, setIsThoughtsExpanded] = useState(true);
  const [browserAction, setBrowserAction] = useState<{ status: string; url: string; title: string; live_url?: string } | null>(null);
  const [showModelDropdown, setShowModelDropdown] = useState(false);
  const [showChatModelDropdown, setShowChatModelDropdown] = useState(false);
  const [chatModeConfigs, setChatModeConfigs] = useState<ChatModeConfig[]>([]);
  const [selectedChatSlot, setSelectedChatSlot] = useState<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const thoughtsStartTimeRef = useRef<number>(0);
  const [generatedFiles, setGeneratedFiles] = useState<Array<{ filename: string; url: string; type: 'pdf' | 'excel' | 'other' }>>([]);
  const [textDocArtifact, setTextDocArtifact] = useState<{ title: string; content: string } | null>(null);
  const [designArtifact, setDesignArtifact] = useState<string[] | null>(null);
  const [designPreviewIndex, setDesignPreviewIndex] = useState<number | null>(null);
  const [clarificationQuestions, setClarificationQuestions] = useState<BrowserClarificationPayload | null>(null);
  const clarificationBasePromptRef = useRef<string | null>(null);
  const [chatThinkingMessage, setChatThinkingMessage] = useState('');
  const [chatThinkingVisible, setChatThinkingVisible] = useState(false);
  const [chatThinkingDeep, setChatThinkingDeep] = useState(false);
  const chatThinkingStartRef = useRef<number>(0);
  const chatThinkingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastNarrativeThinkingRef = useRef('');
  const [modalPreview, setModalPreview] = useState<{ type: 'text_doc' | 'pdf' | 'excel' | 'other'; title: string; content?: string; url?: string } | null>(null);
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [isSearchEnabled, setIsSearchEnabled] = useState(false);
  const [spyPagesActive, setSpyPagesActive] = useState(false);
  const [spyPagesEnabled, setSpyPagesEnabled] = useState(false);
  const [spyPagesUrls, setSpyPagesUrls] = useState<string[]>([]);
  const [spyPagesLoading, setSpyPagesLoading] = useState(false);
  const [spyPagesPreviewData, setSpyPagesPreviewData] = useState<SpyPagesSite[] | null>(null);
  const [spyPagesResult, setSpyPagesResult] = useState<SpyPagesSite[] | null>(null);
  const [showToolsDropdown, setShowToolsDropdown] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const notifiedFailedFilesRef = useRef<Set<string>>(new Set());
  const lastInitialMessageRef = useRef<string | null>(null);
  const previousChatSessionIdRef = useRef<string | null>(null);
  const messagesRef = useRef<Message[]>([]);

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

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  const pushNarrativeThinking = (message: string) => {
    const text = message.trim();
    if (!text || text === lastNarrativeThinkingRef.current) return;
    lastNarrativeThinkingRef.current = text;
    setChatThinkingMessage(text);
    chatThinkingStartRef.current = Date.now();
    if (chatThinkingTimerRef.current) clearTimeout(chatThinkingTimerRef.current);
    setChatThinkingVisible(true);
  };

  const clearNarrativeThinking = () => {
    lastNarrativeThinkingRef.current = '';
    setChatThinkingMessage('');
    setChatThinkingVisible(false);
    setChatThinkingDeep(false);
    if (chatThinkingTimerRef.current) {
      clearTimeout(chatThinkingTimerRef.current);
      chatThinkingTimerRef.current = null;
    }
  };

  const finalizeAgentExecutionUi = useCallback((collapseDelay = 300, options?: { clearBrowserCard?: boolean }) => {
    setIsLoading(false);
    setAgentThoughts(prev =>
      prev.map(s => (s.status === 'running' ? { ...s, status: 'done' as const } : s))
    );
    if (options?.clearBrowserCard !== false) {
      setBrowserAction(null);
    }
    clearNarrativeThinking();
    window.setTimeout(() => setIsThoughtsExpanded(false), collapseDelay);
  }, [clearNarrativeThinking]);

  const normalizeThoughtForChat = (raw: string): string | null => {
    const text = raw.trim().replace(/\s+/g, ' ');
    if (!text) return null;
    if (text.length <= 140) return text;

    const short = text
      .replace(/^(vou|estou|agora vou|primeiro vou)\s+/i, (match) => match.charAt(0).toUpperCase() + match.slice(1))
      .slice(0, 157)
      .trim();
    return `${short}...`;
  };

  const narrativeThinkingFromBrowserAction = (data: { status?: string; url?: string; title?: string }) => {
    const host = (() => {
      try {
        return data.url ? new URL(data.url).hostname.replace(/^www\./, '') : '';
      } catch {
        return data.url || '';
      }
    })();

    switch (data.status) {
      case 'navigating':
        return host ? `Vou abrir ${host} e entender como a página está estruturada.` : 'Vou abrir o site e verificar a estrutura da página.';
      case 'reading':
        return data.title
          ? `Estou analisando a página "${data.title}" para extrair o que importa.`
          : 'Estou lendo a página e separando o que é relevante.';
      case 'acting':
        return 'Estou tentando interagir com a página para avançar na tarefa.';
      case 'awaiting_user':
        return 'Encontrei um bloqueio visual e preciso da sua ajuda para continuar.';
      case 'error':
        return 'A navegação falhou e estou tentando contornar isso.';
      default:
        return null;
    }
  };

  const openEditModal = () => {
    if (!project) return;
    setEditName(project.name);
    setEditInstructions(project.instructions || '');
    setDeleteConfirm(false);
    setShowEditModal(true);
    setIsLoadingFiles(true);
    if (!userId) {
      setIsLoadingFiles(false);
      return;
    }
    projectApi.listFiles(project.id, userId).then(files => {
      setEditFiles(files);
      setIsLoadingFiles(false);
    }).catch(() => setIsLoadingFiles(false));
  };

  const handleSaveProject = async () => {
    if (!project || !editName.trim()) return;
    setIsUpdatingProject(true);
    if (!userId) return;
    const updated = await projectApi.update(userId, project.id, {
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
    if (!userId) return;
    await projectApi.deleteFile(project.id, fileId, userId);
    setEditFiles(prev => prev.filter(f => f.id !== fileId));
  };

  const handleUploadProjectFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !project) return;
    setIsUploadingFile(true);
    if (!userId) return;
    const result = await projectApi.uploadFile(project.id, userId, file);
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
    if (!userId) return;
    await projectApi.delete(project.id, userId);
    setIsDeletingProject(false);
    setShowEditModal(false);
    onProjectDeleted?.();
    showToast('Projeto excluído', 'success');
  };

  // Location + Weather (IP-based, no permission needed)
  const [userLocation, setUserLocation] = useState<{
    city: string;
    temp?: number;
    weatherCode?: number;
    tempMin?: number;
    tempMax?: number;
    humidity?: number;
    windSpeed?: number;
  } | null>(null);

  useEffect(() => {
    const CACHE_KEY = 'arcco_location_v3';
    const CACHE_TTL = 30 * 60 * 1000; // 30 min
    const isLocalhost =
      typeof window !== 'undefined' &&
      (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

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
        // Proxied via backend — usa X-Forwarded-For para IP real do usuario
        const res = await fetch(withBackendUrl('/api/agent/location'));
        if (!res.ok) throw new Error('backend failed');
        const data = await res.json();
        if (!data.city) throw new Error('no city');

        const location: typeof userLocation = { city: data.city };
        if (data.temp !== undefined) location!.temp = data.temp;
        if (data.weather_code !== undefined) location!.weatherCode = data.weather_code;
        if (data.temp_min !== undefined) location!.tempMin = data.temp_min;
        if (data.temp_max !== undefined) location!.tempMax = data.temp_max;
        if (data.humidity !== undefined) location!.humidity = data.humidity;
        if (data.wind_speed !== undefined) location!.windSpeed = data.wind_speed;

        setUserLocation(location);
        localStorage.setItem(CACHE_KEY, JSON.stringify({ data: location, timestamp: Date.now() }));
      } catch {
        if (isLocalhost) {
          return;
        }
        // Fallback: API direta no browser (pode ser bloqueada por ad-blockers)
        try {
          const geo = await fetch('https://ipwho.is/');
          const geoData = await geo.json();
          if (geoData?.city) {
            const fallback: typeof userLocation = { city: geoData.city };
            // Tentar pegar clima tambem
            if (geoData.latitude && geoData.longitude) {
              try {
                const w = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${geoData.latitude}&longitude=${geoData.longitude}&current_weather=true&timezone=auto`);
                const wd = await w.json();
                const cw = wd?.current_weather;
                if (cw) {
                  fallback!.temp = Math.round(cw.temperature);
                  fallback!.weatherCode = cw.weathercode ?? 0;
                }
              } catch { /* sem clima, pelo menos tem cidade */ }
            }
            setUserLocation(fallback);
            localStorage.setItem(CACHE_KEY, JSON.stringify({ data: fallback, timestamp: Date.now() }));
          }
        } catch (e) {
          console.warn('[Arcco] Location fetch failed:', e);
        }
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

  const getWeatherDesc = (code: number) => {
    if (code === 0) return 'Ceu limpo';
    if (code <= 3) return 'Parcialmente nublado';
    if (code <= 48) return 'Nevoeiro';
    if (code <= 55) return 'Garoa';
    if (code <= 67) return 'Chuva';
    if (code <= 77) return 'Neve';
    if (code <= 82) return 'Pancadas de chuva';
    return 'Tempestade';
  };

  // Dynamic Greeting Logic

  // Seed determinístico por hora+dia — muda entre sessões/horas sem flickar durante a sessão
  const _greetSeed = (() => {
    const d = new Date();
    return d.getHours() * 7 + d.getDate() * 31 + d.getMonth() * 13;
  })();
  const _pick = <T,>(arr: T[]): T => arr[_greetSeed % arr.length];

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour >= 5 && hour < 12) return "Bom dia";
    if (hour >= 12 && hour < 18) return "Boa tarde";
    return "Boa noite";
  };

  const getWeatherSubtitle = (loc: typeof userLocation) => {
    if (!loc?.temp) return null;
    const code = loc.weatherCode ?? 0;
    const temp = loc.temp;
    const city = loc.city;
    const hour = new Date().getHours();
    const day = new Date().getDay();
    const isWeekend = day === 0 || day === 6;
    const isMorning = hour >= 5 && hour < 12;
    const isAfternoon = hour >= 12 && hour < 18;
    const isMidnight = hour >= 0 && hour < 5;

    if (isMidnight) return _pick([
      `Madrugada silenciosa em ${city}. O que criamos agora?`,
      `${temp}° e madrugada em ${city}. Qual é o plano?`,
      `O mundo dorme em ${city}. A gente não. O que saí hoje?`,
      `Madrugada produtiva em ${city}. Por onde começamos?`,
      `${city} descansando lá fora. E a gente aqui criando. Vamos?`,
    ]);

    if (code >= 95) return _pick([
      `Tempestade em ${city}. Dia perfeito para criar dentro.`,
      `Caindo o mundo lá fora em ${city}. O que fazemos agora?`,
      `${city} em modo tempestade. Melhor lugar é aqui. Vamos?`,
      `${temp}° e tempestade em ${city}. O que construímos hoje?`,
    ]);

    if (code >= 71 && code <= 77) return _pick([
      `Neve em ${city}! Dia raro para criar. O que saí hoje?`,
      `${city} coberta de neve com ${temp}°. O que fazemos?`,
      `Nevando em ${city}. Qual é o projeto de hoje?`,
    ]);

    if (code >= 51 && code <= 82) return _pick([
      `Chovendo em ${city} com ${temp}°. Dia perfeito para criar.`,
      `Chuva em ${city}. Que projeto tiramos do papel hoje?`,
      `${city} molhada lá fora. O que construímos enquanto chove?`,
      `Tempo fechado em ${city}. Vamos criar algo que vale a pena?`,
      `${temp}° e chuva em ${city}. Melhor lugar é aqui. Por onde vai?`,
      `Chuva e ${temp}° em ${city}. Tá na hora de produzir. Vamos?`,
    ]);

    if (code >= 45 && code <= 48) return _pick([
      `Neblina em ${city} com ${temp}°. Dia misterioso para criar. Vamos?`,
      `${city} encoberta. O que tiramos do papel hoje?`,
      `Tempo fechado em ${city}. O que criamos agora?`,
    ]);

    if (temp <= 10) return _pick([
      `Frio de verdade em ${city}, ${temp}°. Dia bom para produzir. Vamos?`,
      `${temp}° em ${city}. Friozinho inspira. O que criamos hoje?`,
      `Gelando em ${city}. Melhor ficar aqui criando. Por onde vai?`,
      isWeekend
        ? `Fim de semana gelado em ${city}. O que tiramos do papel?`
        : `${city} com ${temp}°. Que projeto saí hoje?`,
    ]);

    if (temp <= 18) return _pick([
      `Friozinho em ${city} com ${temp}°. Tá na hora de criar. Vamos?`,
      `${temp}° em ${city}. Dia bom para produzir. O que fazemos?`,
      `${city} fresca com ${temp}°. Por onde começamos?`,
      isWeekend
        ? `Fim de semana fresco em ${city}. O que criamos hoje?`
        : `Fresco em ${city} e ${temp}°. Que projeto saí hoje?`,
    ]);

    if (temp >= 35) return _pick([
      `${temp}° em ${city}. Calor pede resultado. O que vamos criar?`,
      `Calorzão em ${city} com ${temp}°. Vamos criar algo fora do comum?`,
      `${city} fervendo com ${temp}°. Tá na hora de produzir. Por onde vai?`,
      `${temp}° aí em ${city}? O que construímos hoje?`,
    ]);

    if (temp >= 28) return _pick([
      `Calor em ${city} com ${temp}°. O que criamos hoje?`,
      isWeekend
        ? `Fim de semana quente em ${city}. Vamos criar o quê?`
        : `${temp}° em ${city}. Que projeto saí hoje?`,
      isMorning
        ? `Manhã quente em ${city} com ${temp}°. Por onde começamos?`
        : isAfternoon
          ? `Como tá essa tarde em ${city}, ${temp}°? Vamos criar o quê?`
          : `Noite quente em ${city} com ${temp}°. O que fazemos agora?`,
      `${temp}° aí em ${city}. Dia de criar. Por onde vai?`,
    ]);

    if (code <= 3) return _pick([
      `Dia de sol aí em ${city}? O que vamos criar hoje?`,
      `${temp}° e céu aberto em ${city}. Por onde começamos?`,
      isMorning
        ? `Manhã de sol em ${city} com ${temp}°. Que projeto saí hoje?`
        : isAfternoon
          ? `Como tá essa tarde em ${city}, ${temp}°? Vamos criar o quê?`
          : `Noite clara em ${city}. Qual é o plano agora?`,
      isWeekend
        ? `Fim de semana de sol em ${city}. O que tiramos do papel hoje?`
        : day === 1
          ? `Segunda de sol em ${city}. Semana nova — o que construímos?`
          : day === 5
            ? `Sexta de sol em ${city}. Vamos fechar a semana com o quê?`
            : `Sol em ${city}, ${temp}°. Tá na hora de criar. Por onde vai?`,
      `${temp}° e sol em ${city}. O que saí hoje?`,
    ]);

    return _pick([
      `Nublado em ${city} com ${temp}°. O que criamos hoje?`,
      `${city} encoberta e ${temp}°. Que projeto saí hoje?`,
      isMorning
        ? `Manhã nublada em ${city}. Por onde começamos?`
        : isAfternoon
          ? `Tarde fechada em ${city}, ${temp}°. No que trabalhamos?`
          : `Noite em ${city} com ${temp}°. O que fazemos agora?`,
      isWeekend
        ? `Fim de semana nublado em ${city}. Vamos criar o quê?`
        : `${temp}° em ${city}. Tá na hora de produzir. Vamos?`,
    ]);
  };

  const getSubtitle = () => {
    const now = new Date();
    const hour = now.getHours();
    const day = now.getDay();
    const isWeekend = day === 0 || day === 6;

    if (hour >= 0 && hour < 5) return _pick([
      "Madrugada produtiva. O que iremos fazer?",
      "O mundo dorme. A gente não. Qual é o plano?",
      "Hora estranha, mas estamos aqui. Por onde vai?",
      "Silêncio da madrugada. Bom para criar. Vamos?",
      "Madrugada de criação. O que saí hoje?",
    ]);

    if (hour >= 5 && hour < 12) return _pick([
      day === 1 ? "Segunda de manhã. Semana nova — o que construímos?" :
      day === 5 ? "Sexta cedo. Vamos fechar a semana com o quê?" :
      isWeekend ? "Manhã de fim de semana. O que tiramos do papel?" :
      "Manhã boa para criar. Por onde começamos?",
      "Começo de dia. Que projeto saí hoje?",
      "Manhã. Vamos criar o quê?",
      "Dia novo em branco. O que fazemos?",
      "Hora do café e de criar. Por onde vai?",
    ]);

    if (hour >= 12 && hour < 18) return _pick([
      day === 5 ? "Tarde de sexta. Vamos fechar a semana com o quê?" :
      isWeekend ? "Tarde de fim de semana. O que criamos hoje?" :
      "A tarde pede resultado. No que trabalhamos?",
      "Meio do dia. Que projeto saí agora?",
      "Boa tarde. Vamos criar o quê?",
      "Tarde produtiva. Por onde vai?",
      "Como tá essa tarde? Vamos fazer o quê?",
    ]);

    return _pick([
      isWeekend ? "Noite de fim de semana. O que criamos?" : "Final de dia. Ainda tem tempo. O que fazemos?",
      "A noite também rende. Qual é o plano?",
      "Noite de trabalho. Por onde começamos?",
      "Encerrando o dia ou só aquecendo? Vamos criar o quê?",
      "Noite boa para produzir. O que saí hoje?",
    ]);
  };

  const displayName = userName.trim() || 'Usuario';
  const [greetingTime] = useState(getGreeting());
  const [greetingFallback] = useState(getSubtitle());
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
    progressPercent: file.status === 'ready' ? 100 : file.status === 'failed' ? 100 : 92,
    loadedBytes: file.size_bytes,
    source: 'server',
  });

  const mergeSessionAttachments = useCallback(
    (serverFiles: SessionFileItem[], currentAttachments: SessionAttachment[]) => {
      const serverMapped = serverFiles.map(mapSessionFile);
      const mergedById = new Map<string, SessionAttachment>();

      currentAttachments.forEach((attachment) => {
        if (attachment.status === 'uploading' && attachment.clientId) {
          mergedById.set(`client:${attachment.clientId}`, attachment);
          return;
        }
        mergedById.set(`file:${attachment.fileId}`, attachment);
      });

      serverMapped.forEach((attachment) => {
        mergedById.set(`file:${attachment.fileId}`, attachment);
      });

      return Array.from(mergedById.values()).sort((left, right) => left.name.localeCompare(right.name));
    },
    [],
  );

  const removeAttachment = useCallback(async (attachment: SessionAttachment) => {
    const attachmentKey = attachment.clientId || attachment.fileId;
    setAttachments(prev => prev.filter(att => (att.clientId || att.fileId) !== attachmentKey));

    if (attachment.fileId && !String(attachment.fileId).startsWith('uploading:')) {
      try {
        await agentApi.deleteSessionFile(effectiveSessionId, attachment.fileId);
      } catch (error) {
        console.error('Falha ao remover anexo da sessão:', error);
        showToast('Não foi possível remover o arquivo da sessão.', 'error');
      }
    }
  }, [effectiveSessionId, showToast]);

  const attachmentStatusLabel = (status: SessionAttachment['status']) => {
    switch (status) {
      case 'ready':
        return 'pronto';
      case 'failed':
        return 'falhou';
      case 'uploading':
        return 'enviando';
      case 'processing':
      case 'uploaded':
      default:
        return 'processando';
    }
  };

  const attachmentStatusClass = (status: SessionAttachment['status']) => {
    switch (status) {
      case 'ready':
        return 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300';
      case 'failed':
        return 'bg-red-500/10 border-red-500/30 text-red-300';
      case 'uploading':
        return 'bg-indigo-500/10 border-indigo-500/30 text-indigo-300';
      case 'processing':
      case 'uploaded':
      default:
        return 'bg-amber-500/10 border-amber-500/30 text-amber-300';
    }
  };

  const attachmentProgressValue = (attachment: SessionAttachment) => {
    if (attachment.status === 'ready' || attachment.status === 'failed') return 100;
    if (attachment.status === 'uploading') return Math.max(1, Math.min(100, attachment.progressPercent || 0));
    return Math.max(96, Math.min(99, attachment.progressPercent || 96));
  };

  const formatAttachmentProgress = (attachment: SessionAttachment) => {
    const loaded = attachment.loadedBytes || 0;
    const total = attachment.sizeBytes || 0;
    if (!total) return `${attachmentProgressValue(attachment)}%`;
    const loadedMb = (loaded / (1024 * 1024)).toFixed(1);
    const totalMb = (total / (1024 * 1024)).toFixed(1);
    return `${loadedMb} / ${totalMb} MB`;
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
        const res = await fetch(withBackendUrl('/api/agent/chat-models'));
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
    if (!chatSessionId) return;
    const hasLocalWork = attachmentsRef.current.length > 0 || messagesRef.current.length > 0;
    const currentIsUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(activeSessionId);
    const currentIsEphemeral = activeSessionId === localSessionId || !currentIsUuid;
    if (currentIsEphemeral && hasLocalWork) {
      return;
    }
    setActiveSessionId(chatSessionId);
  }, [chatSessionId, activeSessionId, localSessionId]);

  useEffect(() => {
    const currentSessionId = chatSessionId || '';
    const isUUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(currentSessionId);
    const previousSessionId = previousChatSessionIdRef.current;
    previousChatSessionIdRef.current = currentSessionId || null;

    const previousWasEphemeral =
      !!previousSessionId &&
      !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(previousSessionId);
    const promotedEphemeralConversation =
      !!currentSessionId &&
      isUUID &&
      previousWasEphemeral &&
      messagesRef.current.length > 0;

    if (!currentSessionId || !isUUID) {
      setGeneratedFiles([]);
      setConversationId(null);
      setMessages([]);
      setAttachments([]);
      notifiedFailedFilesRef.current.clear();
      return;
    }

    setConversationId(currentSessionId);
    const savedMode = getConvMode(currentSessionId);
    if (savedMode !== null) setIsAgentMode(savedMode);

    if (promotedEphemeralConversation) {
      return;
    }

    setGeneratedFiles([]);
    setMessages([]);
    setAttachments([]);
    notifiedFailedFilesRef.current.clear();
    if (!userId) return;

    let cancelled = false;

    conversationApi.getMessages(currentSessionId, userId).then(msgs => {
      if (cancelled) return;
      setMessages(msgs.map(m => ({
        id: m.id,
        role: m.role as 'user' | 'assistant',
        content: m.content,
        timestamp: m.created_at,
      })));
    }).catch((err) => {
      if (cancelled) return;
      console.error('[ArccoChat] Falha ao carregar histórico:', err);
      showToast('Não foi possível carregar o histórico desta conversa.', 'error');
      setMessages([]);
    });

    return () => { cancelled = true; };
  }, [chatSessionId, userId]);

  useEffect(() => {
    let cancelled = false;

    const loadSessionFiles = async () => {
      try {
        const files = await agentApi.listSessionFiles(effectiveSessionId);
        if (!cancelled) {
          setAttachments(prev => mergeSessionAttachments(files, prev));
        }
      } catch (error) {
        if (!cancelled) {
          console.warn('Falha ao carregar anexos da sessão:', error);
        }
      }
    };

    loadSessionFiles();

    return () => {
      cancelled = true;
    };
  }, [effectiveSessionId]);

  // Ref para rastrear se há anexos em processamento sem criar dep no useEffect
  const attachmentsRef = useRef(attachments);
  useEffect(() => { attachmentsRef.current = attachments; }, [attachments]);

  useEffect(() => {
    let cancelled = false;

    const interval = setInterval(async () => {
      const hasPending = attachmentsRef.current.some(
        att => att.status === 'processing' || att.status === 'uploaded' || att.status === 'uploading'
      );
      if (!hasPending) return;

      try {
        const files = await agentApi.listSessionFiles(effectiveSessionId);
        if (!cancelled) {
          setAttachments(prev => mergeSessionAttachments(files, prev));
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
  }, [effectiveSessionId]);

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
    if (!initialMessage) return;
    if (lastInitialMessageRef.current === initialMessage) return;
    if (!isApiKeyReady || isLoading) return;
    lastInitialMessageRef.current = initialMessage;
    handleSendMessage(initialMessage);
    onClearInitialMessage?.();
  }, [initialMessage, isApiKeyReady, isLoading, onClearInitialMessage]);

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

  const handleSendMessage = async (
    text: string = inputValue,
    options?: { browserResumeToken?: string }
  ) => {
    if (!text.trim() || isLoading || !isApiKeyReady) return;

    // Injeta dados do Spy Pages já coletados como contexto para o agente
    // Captura contexto Spy Pages antes de limpar o estado
    const spyContext = spyPagesPreviewData && spyPagesPreviewData.length > 0
      ? JSON.stringify(spyPagesPreviewData)
      : null;

    if (spyContext) {
      setSpyPagesPreviewData(null);
      setSpyPagesUrls([]);
    } else if (spyPagesUrls.length > 0) {
      setSpyPagesUrls([]);
    }

    // UI e histórico mostram APENAS a pergunta do usuário (sem o JSON de contexto)
    const userMsgId = Date.now().toString();
    const newUserMsg: Message = { id: userMsgId, role: 'user', content: text.trim(), timestamp: new Date().toISOString() };

    const newMessages = [...messages, newUserMsg];
    setMessages(newMessages);
    saveToSession(newMessages);

    setInputValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    setIsLoading(true);
    setAgentThoughts([]);
    setWorkflowSnapshots([]);
    setPolicyDecisions([]);
    setReplanDecisions([]);
    setGeneratedFiles([]);
    setBrowserAction(null);
    setTextDocArtifact(null);
    setDesignArtifact(null);
    setClarificationQuestions(null);
    setSpyPagesResult(null);
    clearNarrativeThinking();
    if (!isAgentMode) {
      setIsTerminalOpen(false);
      setTerminalContent('');
      chatThinkingStartRef.current = 0;
    }
    setIsThoughtsExpanded(true);
    setElapsedSeconds(0);
    thoughtsStartTimeRef.current = Date.now();

    const assistantMsgId = (Date.now() + 1).toString();
    const placeholderAiMsg: Message = { id: assistantMsgId, role: 'assistant', content: '', timestamp: new Date().toISOString() };

    setMessages(prev => [...prev, placeholderAiMsg]);

    try {

      // Injeta contexto Spy Pages na última mensagem do usuário (invisível no chat)
      const formattedMessages = newMessages.map((m, i) => {
        if (spyContext && i === newMessages.length - 1 && m.role === 'user') {
          return {
            role: m.role,
            content: `[CONTEXTO COLETADO VIA SIMILARWEB/APIFY — use estes dados para responder com precisão]\n${spyContext}\n\n[PERGUNTA DO USUÁRIO]\n${m.content}`,
          };
        }
        return { role: m.role, content: m.content };
      });

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
                finalizeAgentExecutionUi();
              }
            } catch { /* ignore parse errors */ }
            return;
          }

          if (type === 'design_artifact') {
            try {
              const payload = JSON.parse(content);
              if (Array.isArray(payload?.designs) && payload.designs.length > 0) {
                const nextDesigns = payload.designs.flatMap((item: string) => splitDesignsFromHtml(String(item)));
                setDesignArtifact(prev => mergeUniqueDesigns(prev, nextDesigns));
                setMessages(prev => prev.map(msg =>
                  msg.id === assistantMsgId ? { ...msg, content: DESIGN_ARTIFACT_SENTINEL } : msg
                ));
                finalizeAgentExecutionUi();
              }
            } catch { /* ignore parse errors */ }
            return;
          }

          if (type === 'clarification') {
            try {
              const questions = JSON.parse(content);
              if (Array.isArray(questions) && questions.length > 0) {
                const latestUserPrompt = [...messagesRef.current].reverse().find(msg => msg.role === 'user')?.content?.trim() || '';
                clarificationBasePromptRef.current = latestUserPrompt || clarificationBasePromptRef.current;
                setClarificationQuestions({
                  questions,
                  originalPrompt: latestUserPrompt || clarificationBasePromptRef.current || undefined,
                });
                finalizeAgentExecutionUi(0, { clearBrowserCard: false });
              }
            } catch { /* ignore parse errors */ }
            return;
          }

          if (type === 'needs_clarification') {
            try {
              const payload = JSON.parse(content);
              if (payload && Array.isArray(payload.questions) && payload.questions.length > 0) {
                const latestUserPrompt = [...messagesRef.current].reverse().find(msg => msg.role === 'user')?.content?.trim() || '';
                clarificationBasePromptRef.current = latestUserPrompt || clarificationBasePromptRef.current;
                setClarificationQuestions({
                  questions: payload.questions,
                  helperText: payload.message,
                  actionUrl: payload.action_url,
                  actionLabel: payload.action_label,
                  resumeToken: payload.resume_token,
                  originalPrompt: latestUserPrompt || clarificationBasePromptRef.current || undefined,
                });
                pushNarrativeThinking(payload.message || 'Encontrei um bloqueio visual e preciso da sua ajuda para continuar.');
                finalizeAgentExecutionUi(0, { clearBrowserCard: false });
              }
            } catch { /* ignore parse errors */ }
            return;
          }

          if (type === 'workflow_state') {
            try {
              const payload = JSON.parse(content);
              if (payload?.workflow_id && Array.isArray(payload?.stages)) {
                setWorkflowSnapshots(prev => {
                  const next = prev.filter(item => item.workflowId !== payload.workflow_id);
                  return [...next, {
                    workflowId: payload.workflow_id,
                    message: payload.message || payload.workflow_id,
                    stages: payload.stages,
                  }];
                });
                if (payload?.message) {
                  pushNarrativeThinking(payload.message);
                }
              }
            } catch { /* ignore parse errors */ }
            return;
          }

          if (type === 'policy_decision') {
            try {
              const payload = JSON.parse(content);
              if (payload?.decision_id) {
                setPolicyDecisions(prev => [...prev.slice(-3), {
                  decision_id: payload.decision_id,
                  route: payload.route || '',
                  user_message: payload.user_message || '',
                  should_abort: Boolean(payload.should_abort),
                  continue_partial: Boolean(payload.continue_partial),
                  retry_same_route: Boolean(payload.retry_same_route),
                }]);
                if (payload?.user_message) {
                  setAgentThoughts(prev => {
                    const updated = prev.map(s => s.status === 'running' ? { ...s, status: 'done' as const } : s);
                    return [...updated, { label: payload.user_message, status: 'running', kind: 'policy', meta: payload }];
                  });
                }
              }
            } catch { /* ignore parse errors */ }
            return;
          }

          if (type === 'step_replanned') {
            try {
              const payload = JSON.parse(content);
              if (payload?.from_route && payload?.to_route) {
                if (payload.from_route === 'browser') {
                  setBrowserAction(null);
                }
                setReplanDecisions(prev => [...prev.slice(-3), {
                  from_route: payload.from_route,
                  to_route: payload.to_route,
                  to_tool_name: payload.to_tool_name || '',
                  user_message: payload.user_message || '',
                }]);
                setAgentThoughts(prev => {
                  const updated = prev.map(s => s.status === 'running' ? { ...s, status: 'done' as const } : s);
                  return [...updated, {
                    label: payload.user_message || `${payload.from_route} → ${payload.to_route}`,
                    status: 'running',
                    kind: 'replan',
                    meta: payload,
                  }];
                });
                if (payload?.user_message) {
                  pushNarrativeThinking(payload.user_message);
                }
              }
            } catch { /* ignore parse errors */ }
            return;
          }

          // Escalada para modelo especialista — muda animação de thinking sutilmente
          if (type === 'thinking_upgrade') {
            pushNarrativeThinking('Elaborando a resposta...');
            setChatThinkingDeep(true);
            return;
          }

          // Pre-action acknowledgement — mostra no bubble do chat (fora do terminal)
          if (type === 'pre_action') {
            const text = content.trim();
            if (text) {
              pushNarrativeThinking(text);
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
              const narrativeThought = normalizeThoughtForChat(thought);
              if (narrativeThought) {
                pushNarrativeThinking(narrativeThought);
              }
            }
            return;
          }

          // Browser Agent Card — mostra card estilo Manus
          if (type === 'browser_action') {
            try {
              const data = JSON.parse(content);
              setBrowserAction(data);
              if (data?.status === 'done' || data?.status === 'error') {
                window.setTimeout(() => {
                  setBrowserAction(current => (
                    current?.status === data.status && current?.url === data.url ? null : current
                  ));
                }, 1200);
              }
              const narrativeThought = narrativeThinkingFromBrowserAction(data);
              if (narrativeThought) {
                pushNarrativeThinking(narrativeThought);
              }
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
            onConversationIdChange?.(content);
            saveConvMode(content, isAgentMode);
            return;
          }

          // Spy Pages result — dados SimilarWeb para o card interativo
          if (type === 'spy_pages_result') {
            try {
              const sites: SpyPagesSite[] = typeof content === 'string' ? JSON.parse(content) : content;
              setSpyPagesResult(sites);
              setSpyPagesEnabled(false);
              setSpyPagesUrls([]);
            } catch { /* ignore */ }
            return;
          }

          if (type === 'chunk') {
            if (!hasStartedTalking) {
              hasStartedTalking = true;
              clearNarrativeThinking();
              // Marca o último step como concluído e recolhe o painel com micro-delay
              setAgentThoughts(prev =>
                prev.map(s => s.status === 'running' ? { ...s, status: 'done' as const } : s)
              );
              // Esconde thinking panel — só no chat mode (no agent mode, o painel cuida)
              if (!isAgentMode && chatThinkingStartRef.current > 0) {
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
        isAgentMode && spyPagesEnabled,
        !isAgentMode ? (selectedChatConfig?.fast_model_id || undefined) : undefined,
        !isAgentMode ? (selectedChatConfig?.fast_system_prompt || undefined) : undefined,
        options?.browserResumeToken,
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
      clearNarrativeThinking();
    }
  };


  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSpyPagesSubmit = async (urls: string[]) => {
    setSpyPagesLoading(true);
    setSpyPagesUrls(urls);
    try {
      const results = await agentApi.prefetchSpyPages(urls);
      setSpyPagesPreviewData(results);
    } catch {
      setSpyPagesPreviewData(null);
      setSpyPagesActive(false);
      setSpyPagesUrls([]);
      showToast('Erro ao coletar dados do Apify. Verifique a API key.', 'error');
    } finally {
      setSpyPagesLoading(false);
    }
  };

  const handleSpyPagesReady = () => {
    setSpyPagesActive(false);
    setSpyPagesEnabled(false); // dados já coletados, agente não precisa chamar Apify
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    if (selectedFiles.length === 0) return;

    const oversizedFiles = selectedFiles.filter(file => file.size > MAX_CHAT_FILE_SIZE_BYTES);
    if (oversizedFiles.length > 0) {
      showToast(
        oversizedFiles.length === 1
          ? `O arquivo ${oversizedFiles[0].name} excede o limite de 100MB.`
          : `${oversizedFiles.length} arquivos excedem o limite de 100MB.`,
        'error',
      );
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    setIsFileLoading(true);

    try {
      const uploadTasks = selectedFiles.map(async (file) => {
        const clientId = `${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;

        setAttachments(prev => [
          ...prev,
          {
            fileId: `uploading:${clientId}`,
            clientId,
            name: file.name,
            sizeBytes: file.size,
            status: 'uploading',
            error: null,
            progressPercent: 1,
            loadedBytes: 0,
            source: 'local',
          },
        ]);

        try {
          const uploaded = await agentApi.uploadSessionFile(effectiveSessionId, file, {
            onProgress: (progressPercent, loadedBytes, totalBytes) => {
              setAttachments(prev => prev.map(att => (
                att.clientId === clientId
                  ? {
                      ...att,
                      progressPercent,
                      loadedBytes,
                      sizeBytes: totalBytes || att.sizeBytes,
                    }
                  : att
              )));
            },
          });

          setAttachments(prev => prev.map(att => (
            att.clientId === clientId
              ? {
                  ...att,
                  fileId: uploaded.file_id,
                  name: uploaded.original_name,
                  sizeBytes: uploaded.size_bytes,
                  status: uploaded.status,
                  progressPercent: uploaded.status === 'ready' ? 100 : 96,
                  loadedBytes: uploaded.size_bytes,
                  error: null,
                  source: 'server',
                }
              : att
          )));
          return { ok: true as const, fileName: file.name };
        } catch (err: any) {
          console.error('Erro no upload da sessão:', err);
          setAttachments(prev => prev.map(att => (
            att.clientId === clientId
              ? {
                  ...att,
                  status: 'failed',
                  error: err.message,
                  progressPercent: 100,
                }
              : att
          )));
          return { ok: false as const, fileName: file.name, error: err.message };
        }
      });

      const results = await Promise.all(uploadTasks);
      const successCount = results.filter(result => result.ok).length;
      const failed = results.filter(result => !result.ok);

      if (successCount > 0) {
        showToast(
          successCount === 1
            ? 'Arquivo anexado. Processamento iniciado em background.'
            : `${successCount} arquivos anexados. Processamento iniciado em background.`,
          'success',
        );
      }
      if (failed.length > 0) {
        showToast(
          failed.length === 1
            ? `Falha no upload de ${failed[0].fileName}.`
            : `${failed.length} arquivos falharam no upload.`,
          'error',
        );
      }
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
    if (content === DESIGN_ARTIFACT_SENTINEL) {
      return null;
    }

    // Detecta resposta que é uma apresentação HTML completa (terminal tool generate_web_page)
    const trimmedContent = content.trim();
    if (trimmedContent.startsWith('<!DOCTYPE') || trimmedContent.toLowerCase().startsWith('<html')) {
      const designs = splitDesignsFromHtml(trimmedContent);
      return <DesignGallery designs={designs.length > 0 ? designs : [trimmedContent]} isStreaming={isLoading} />;
    }

    const fencedDesignMatch = trimmedContent.match(/^```(?:html)?\s*([\s\S]*?)\s*```$/i);
    if (fencedDesignMatch) {
      const html = fencedDesignMatch[1].trim();
      if (html.startsWith('<!DOCTYPE') || html.toLowerCase().startsWith('<html')) {
        const designs = splitDesignsFromHtml(html);
        return <DesignGallery designs={designs.length > 0 ? designs : [html]} isStreaming={isLoading} />;
      }
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
    <div className={`relative group ${variant === 'centered' ? 'mx-auto w-[min(88vw,980px)] max-w-none px-2 md:px-6' : 'w-full max-w-4xl mx-auto px-2 md:px-0'}`}>

      {/* Spy Pages — card de entrada de URLs, aparece acima do input */}
      {spyPagesActive && !isLoading && (
        <div className="mb-2">
          <SpyPagesInputCard
            onSubmit={handleSpyPagesSubmit}
            onClose={() => { setSpyPagesActive(false); setSpyPagesLoading(false); setSpyPagesPreviewData(null); setSpyPagesUrls([]); }}
            isLoading={spyPagesLoading}
            previewData={spyPagesPreviewData}
            onConfirmReady={handleSpyPagesReady}
          />
        </div>
      )}

      <div className="absolute -inset-0.5 bg-gradient-to-r from-neutral-700/20 to-neutral-500/20 rounded-[24px] blur opacity-0 group-hover:opacity-100 transition duration-500 pointer-events-none"></div>
      <div className={`relative bg-[#121212]/95 border border-[#333] rounded-[24px] px-4 py-3 shadow-2xl ${variant === 'centered' ? 'min-h-[56px]' : ''}`}>

        {/* URLs carregadas — chips acima da textarea */}
        {spyPagesUrls.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap mb-2 pb-2 border-b border-[#222]">
            <span className="text-[10px] text-violet-500 uppercase tracking-wide font-medium flex-shrink-0">Spy Pages</span>
            {spyPagesUrls.map((url, i) => (
              <span key={i} className="flex items-center gap-1 px-2 py-0.5 bg-violet-500/10 border border-violet-500/25 rounded-full text-[11px] text-violet-300">
                <Eye size={9} />
                <span className="max-w-[140px] truncate">{url}</span>
                <button
                  onClick={() => {
                    const next = spyPagesUrls.filter((_, j) => j !== i);
                    setSpyPagesUrls(next);
                    if (next.length === 0) setSpyPagesEnabled(false);
                  }}
                  className="text-violet-500 hover:text-red-400 transition-colors ml-0.5"
                >
                  <X size={9} />
                </button>
              </span>
            ))}
            <button
              onClick={() => { setSpyPagesUrls([]); setSpyPagesEnabled(false); }}
              className="text-[10px] text-neutral-700 hover:text-neutral-500 transition-colors ml-1"
            >
              limpar
            </button>
          </div>
        )}

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
          disabled={spyPagesLoading}
          placeholder={spyPagesLoading ? "Coletando dados, aguarde..." : isFileLoading ? "Enviando arquivo..." : "Digite sua mensagem... (Shift+Enter para nova linha)"}
          className="flex-1 bg-transparent border-none outline-none text-white placeholder-neutral-500 focus:ring-0 resize-none overflow-hidden leading-relaxed py-0 disabled:opacity-40 disabled:cursor-not-allowed"
          autoFocus={variant === 'centered'}
        />

        <div className="relative group/send flex-shrink-0">
          <button
            onClick={() => handleSendMessage(inputValue)}
            disabled={isLoading || !isApiKeyReady || (!isAgentMode && !selectedChatConfig) || !inputValue.trim()}
            className="p-2 rounded-md text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors bg-white/[0.08] hover:bg-white/[0.13]"
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
            <input type="file" hidden multiple ref={fileInputRef} onChange={handleFileUpload} />
            <div className="relative group/add">
            <button
              onClick={() => setShowAddMenu(!showAddMenu)}
              disabled={isFileLoading}
              className="inline-flex h-7 w-7 items-center justify-center rounded-md text-neutral-500 hover:text-neutral-300 hover:bg-white/[0.05] transition-colors disabled:cursor-not-allowed"
            >
              {isFileLoading
                ? <Loader2 size={13} className="animate-spin text-indigo-400" />
                : <Plus size={14} />
              }
            </button>
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-[#1a1a1d] border border-[#2a2a2a] rounded-lg text-[11px] text-neutral-400 whitespace-nowrap opacity-0 invisible group-hover/add:opacity-100 group-hover/add:visible transition-all duration-150 pointer-events-none z-50">
              {isFileLoading ? 'Enviando arquivos...' : 'Anexar arquivo(s) ou link'}
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

          {isAgentMode && (
            <div className="relative">
              <button
                onClick={() => setShowToolsDropdown(p => !p)}
                className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] transition-all duration-200 ${
                  spyPagesActive
                    ? 'text-violet-400 bg-violet-500/10 hover:bg-violet-500/15'
                    : 'text-neutral-500 hover:text-neutral-300 hover:bg-white/[0.05]'
                }`}
              >
                <Wrench size={12} />
                <span>Tools</span>
                {spyPagesActive && <span className="w-1.5 h-1.5 rounded-full bg-violet-400 ml-0.5" />}
              </button>
              {showToolsDropdown && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowToolsDropdown(false)} />
                  <div className="absolute bottom-full left-0 mb-2 w-52 bg-[#1a1a1d] border border-[#333] rounded-xl shadow-2xl overflow-hidden z-50">
                    <div className="px-3 pt-2.5 pb-1.5">
                      <p className="text-[10px] text-neutral-600 uppercase tracking-wide">Ferramentas</p>
                    </div>
                    <button
                      onClick={() => {
                        setSpyPagesActive(true);
                        setShowToolsDropdown(false);
                      }}
                      className="w-full flex items-center gap-3 px-3 py-2.5 text-left hover:bg-white/[0.05] transition-colors"
                    >
                      <div className="w-7 h-7 rounded-lg bg-violet-500/15 flex items-center justify-center flex-shrink-0">
                        <Eye size={13} className="text-violet-400" />
                      </div>
                      <div>
                        <p className="text-sm text-neutral-300">Spy Pages</p>
                        <p className="text-[10px] text-neutral-600">Analise tráfego de sites</p>
                      </div>
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {!isAgentMode && (
            <div className="relative group/search">
              <button
                onClick={() => setIsSearchEnabled(p => !p)}
                className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] transition-all duration-200 ${
                  isSearchEnabled
                    ? 'text-indigo-400 bg-indigo-500/10 hover:bg-indigo-500/15'
                    : 'text-neutral-500 hover:text-neutral-300 hover:bg-white/[0.05]'
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
        <div className="mt-3 px-1 space-y-2">
          {attachments.map((att, i) => (
            <div
              key={att.clientId || att.fileId || i}
              className={`rounded-2xl border px-3 py-2 ${attachmentStatusClass(att.status)}`}
              title={att.error || `${att.name} • ${attachmentStatusLabel(att.status)}`}
            >
              <div className="flex items-center gap-2">
                {att.status === 'uploading' || att.status === 'processing' || att.status === 'uploaded' ? (
                  <Loader2 size={12} className="animate-spin flex-shrink-0" />
                ) : att.status === 'ready' ? (
                  <Check size={12} className="flex-shrink-0" />
                ) : (
                  <AlertTriangle size={12} className="flex-shrink-0" />
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-3">
                    <span className="truncate text-xs font-medium">{att.name}</span>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className="uppercase text-[10px] opacity-80">{attachmentStatusLabel(att.status)}</span>
                      <button
                        type="button"
                        onClick={() => { void removeAttachment(att); }}
                        className="inline-flex items-center justify-center rounded-full hover:bg-black/10 p-0.5 opacity-80 hover:opacity-100 transition-colors"
                        aria-label={`Remover ${att.name}`}
                        title={`Remover ${att.name}`}
                      >
                        <X size={12} />
                      </button>
                    </div>
                  </div>
                  <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-black/20">
                    <div
                      className={`h-full rounded-full transition-all duration-300 ${
                        att.status === 'failed'
                          ? 'bg-red-400'
                          : att.status === 'ready'
                            ? 'bg-emerald-400'
                            : att.status === 'uploading'
                              ? 'bg-indigo-400'
                              : 'bg-amber-400'
                      }`}
                      style={{ width: `${attachmentProgressValue(att)}%` }}
                    />
                  </div>
                  <div className="mt-1 flex items-center justify-between gap-3 text-[10px] opacity-80">
                    <span>{formatAttachmentProgress(att)}</span>
                    {att.error ? <span className="truncate text-right">{att.error}</span> : null}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  const renderAgentActivityPanel = () => {
    if (!isAgentMode) return null;

    const hasSteps = agentThoughts.length > 0;
    const hasWorkflow = workflowSnapshots.length > 0;
    const hasPolicies = policyDecisions.length > 0;
    const hasReplans = replanDecisions.length > 0;
    const allDone = hasSteps && agentThoughts.every(s => s.status === 'done');
    const actionSteps = agentThoughts.filter(s => !s.isThought);
    const hasHarnessData = hasWorkflow || hasPolicies || hasReplans;
    const stepsCollapsed = allDone && !isThoughtsExpanded && !hasHarnessData;

    if (!hasSteps && !hasHarnessData && !isLoading) return null;

    if (!hasSteps && !hasHarnessData && isLoading) {
      return (
        <div className="w-full max-w-[95%] sm:max-w-[85%] md:max-w-[80%] pl-0 md:pl-[62px] py-1 animate-in fade-in duration-300">
          <div className="flex items-center gap-2.5">
            <img src={arccoEmblemUrl} alt="" className="w-3.5 h-3.5 object-contain animate-pulse-soft flex-shrink-0 opacity-40" />
            <span className="text-sm text-neutral-600 animate-pulse-soft">Analisando...</span>
          </div>
        </div>
      );
    }

    if (stepsCollapsed) {
      return (
        <div className="w-full max-w-[95%] sm:max-w-[85%] md:max-w-[80%] pl-0 md:pl-[62px]">
          <button
            onClick={() => setIsThoughtsExpanded(true)}
            className="flex items-center gap-2 text-xs text-neutral-700 hover:text-neutral-500 transition-colors py-1.5 group"
          >
            <svg width="9" height="9" viewBox="0 0 9 9" fill="none" className="flex-shrink-0 text-neutral-700 group-hover:text-neutral-500 transition-colors">
              <path d="M2.5 1.5L6.5 4.5L2.5 7.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <span>{actionSteps.length} etapa{actionSteps.length !== 1 ? 's' : ''}</span>
            <span className="text-neutral-800">·</span>
            <span className="tabular-nums">{elapsedSeconds}s</span>
          </button>
        </div>
      );
    }

    return (
      <div className="w-full max-w-[95%] sm:max-w-[85%] md:max-w-[80%] pl-0 md:pl-[62px]">
        <div className="overflow-hidden rounded-2xl border border-[#25252d] bg-[linear-gradient(180deg,rgba(18,18,23,0.96),rgba(11,11,15,0.98))] shadow-[0_18px_48px_rgba(0,0,0,0.28)]">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[#1e1e25]">
            <div className="flex items-center gap-2.5">
              <div className={`h-2 w-2 rounded-full ${isLoading ? 'bg-emerald-400 shadow-[0_0_14px_rgba(52,211,153,0.8)]' : 'bg-neutral-500'}`} />
              <span className="text-[11px] uppercase tracking-[0.24em] text-neutral-500">Arcco Runtime</span>
            </div>
            <div className="text-[11px] text-neutral-500 tabular-nums">{elapsedSeconds}s</div>
          </div>

          {hasHarnessData && (
            <div className="px-4 py-3 border-b border-[#191920] space-y-3">
              {hasWorkflow && workflowSnapshots.map((snapshot, index) => (
                <div key={`${snapshot.workflowId}-${index}`} className="space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[11px] text-neutral-200">{snapshot.message}</span>
                    <span className="text-[10px] uppercase tracking-[0.18em] text-neutral-600">{snapshot.workflowId.replaceAll('_', ' ')}</span>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                    {snapshot.stages.map(stage => (
                      <div key={stage.stage_id} className="rounded-xl border border-[#2a2a34] bg-[#14141b] px-2.5 py-2">
                        <div className="text-[10px] uppercase tracking-[0.16em] text-neutral-600">{stage.label}</div>
                        <div className={`mt-1 text-[11px] ${
                          stage.status === 'completed'
                            ? 'text-emerald-300'
                            : stage.status === 'waiting_user'
                              ? 'text-amber-300'
                              : stage.status === 'in_progress'
                                ? 'text-sky-300'
                                : 'text-neutral-500'
                        }`}>
                          {stage.status}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}

              {(hasPolicies || hasReplans) && (
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                  {hasPolicies && (
                    <div className="rounded-xl border border-[#31213a] bg-[#18131d] px-3 py-3">
                      <div className="text-[10px] uppercase tracking-[0.18em] text-fuchsia-300/80 mb-2">Policy</div>
                      <div className="space-y-2">
                        {policyDecisions.map((decision, index) => (
                          <div key={`${decision.decision_id}-${index}`} className="text-[11px]">
                            <div className="text-neutral-200">{decision.user_message}</div>
                            <div className="text-neutral-500">{decision.route || 'route'} • retry={String(decision.retry_same_route)} • partial={String(decision.continue_partial)}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {hasReplans && (
                    <div className="rounded-xl border border-[#203341] bg-[#12191f] px-3 py-3">
                      <div className="text-[10px] uppercase tracking-[0.18em] text-cyan-300/80 mb-2">Replan</div>
                      <div className="space-y-2">
                        {replanDecisions.map((decision, index) => (
                          <div key={`${decision.from_route}-${decision.to_route}-${index}`} className="text-[11px]">
                            <div className="text-neutral-200">{decision.user_message}</div>
                            <div className="text-neutral-500">{decision.from_route} → {decision.to_route} • {decision.to_tool_name}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          <div className="px-4 py-3 space-y-1.5">
          {agentThoughts.map((step, i) => {
            const isStepRunning = step.status === 'running';
            const label = step.label.replace(/[\p{Emoji_Presentation}\p{Extended_Pictographic}\u200d\ufe0f]/gu, '').trim();
            const stepKind = step.kind || (step.isThought ? 'thought' : 'step');

            if (step.isThought) {
              return (
                <div key={i} className="pl-[22px] animate-step-enter" style={{ animationDelay: `${i * 35}ms` }}>
                  <span className={`text-xs leading-relaxed italic ${isStepRunning ? 'text-neutral-500' : 'text-neutral-700'}`}>
                    {label}
                  </span>
                </div>
              );
            }

            return (
              <div key={i} className="flex items-center gap-2.5 animate-step-enter" style={{ animationDelay: `${i * 35}ms` }}>
                <span className="flex-shrink-0 w-[14px] flex justify-center">
                  {stepKind === 'policy' ? (
                    <span className="text-[11px] text-fuchsia-300 leading-none">◆</span>
                  ) : stepKind === 'replan' ? (
                    <span className="text-[11px] text-cyan-300 leading-none">↺</span>
                  ) : step.status === 'done' ? (
                    <span className="text-[11px] text-emerald-600/60 animate-check-pop leading-none">✓</span>
                  ) : isStepRunning ? (
                    <div className="w-[5px] h-[5px] rounded-full bg-indigo-400 animate-ring-pulse" />
                  ) : (
                    <span className="text-[10px] text-neutral-800 leading-none">·</span>
                  )}
                </span>
                <span className={`text-sm leading-snug ${
                  stepKind === 'policy'
                    ? 'text-fuchsia-200'
                    : stepKind === 'replan'
                      ? 'text-cyan-200'
                      : isStepRunning
                    ? 'shimmer-text text-neutral-400'
                    : step.status === 'done'
                    ? 'text-neutral-500'
                    : 'text-neutral-700'
                }`}>
                  {label}
                </span>
              </div>
            );
          })}

          {chatThinkingVisible && chatThinkingMessage && !allDone && (
            <div className="flex items-center gap-2.5 animate-in fade-in duration-300 pt-0.5">
              <span className="flex-shrink-0 w-[14px] flex justify-center">
                <div className="w-[11px] h-[11px] rounded-full border border-indigo-400/40 border-t-transparent animate-spin" />
              </span>
              <span className="text-sm text-neutral-500 leading-snug">{chatThinkingMessage}</span>
            </div>
          )}
          </div>
        </div>

        {allDone && (
          <button
            onClick={() => setIsThoughtsExpanded(false)}
            className="flex items-center gap-1.5 text-xs text-neutral-800 hover:text-neutral-600 transition-colors mt-2 group"
          >
            <svg width="9" height="9" viewBox="0 0 9 9" fill="none" className="flex-shrink-0 group-hover:text-neutral-600 transition-colors">
              <path d="M1.5 6.5L4.5 2.5L7.5 6.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <span>Recolher</span>
            <span className="text-neutral-900">·</span>
            <span className="tabular-nums">{elapsedSeconds}s</span>
          </button>
        )}
      </div>
    );
  };

  const renderNarrativeThinkingBubble = () => {
    if (!chatThinkingVisible || !chatThinkingMessage) return null;

    return (
      <div className="flex items-start gap-3 animate-in fade-in duration-300">
        <div className="flex-shrink-0 pt-0.5">
          <img
            src={arccoEmblemUrl}
            alt="Arcco"
            className={`w-8 h-8 md:w-[50px] md:h-[50px] object-contain opacity-75 ${chatThinkingDeep ? 'animate-pulse' : 'animate-pulse-soft'}`}
          />
        </div>
        <div className="max-w-[95%] sm:max-w-[85%] md:max-w-[80%] rounded-2xl px-5 py-4 bg-transparent text-neutral-300">
          <span className="text-[15px] leading-7 text-neutral-400">{chatThinkingMessage}</span>
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-row h-full w-full overflow-hidden" style={{ backgroundColor: 'var(--bg-base)' }}>
      <div className="flex flex-col h-full bg-transparent text-white relative w-full">
        {/* Header */}
        <div className="h-14 md:h-16 border-b border-[#222] flex items-center pl-14 md:pl-6 pr-3 md:pr-6 bg-[#0a0a0a]/80 backdrop-blur-md relative z-20 transition-opacity duration-500">

          {/* Projeto ativo — badge + botões de edição */}
          {project && (
            <div className="flex items-center gap-2 mr-4">
              <div className="flex items-center gap-1.5 px-2 md:px-3 py-1 md:py-1.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs md:text-sm font-medium max-w-[120px] md:max-w-[180px]">
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
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-200 ${
                messages.length > 0
                  ? 'text-neutral-700 cursor-not-allowed opacity-40'
                  : 'text-neutral-500 hover:text-neutral-200 hover:bg-white/[0.05]'
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
            <div className="h-full flex flex-col items-center justify-center p-4 -mt-16 relative overflow-hidden">
              <div className="pointer-events-none absolute inset-0 z-0">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(99,102,241,0.14),transparent_28%),radial-gradient(circle_at_bottom_right,rgba(139,92,246,0.08),transparent_30%)]" />
                <GridPattern
                  width={36}
                  height={36}
                  x={-1}
                  y={-1}
                  squares={[
                    [5, 4],
                    [6, 8],
                    [10, 5],
                    [13, 9],
                    [9, 12],
                    [15, 6],
                  ]}
                  className="[mask-image:radial-gradient(520px_circle_at_center,white,transparent)] fill-indigo-400/10 stroke-white/8"
                />
              </div>

              <div className="relative z-10 flex flex-col items-center text-center mb-10">

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
                      {getWeatherSubtitle(userLocation) || greetingFallback}
                    </p>
                  </>
                )}
              </div>

              <div className="relative z-10 w-full flex justify-center">
                {renderInputArea('centered')}
              </div>

              <div className="relative z-10 flex flex-wrap gap-2 justify-center max-w-2xl mt-8 opacity-60 hover:opacity-100 transition-opacity">
                {suggestionHints.map(hint => (
                  <button
                    key={hint}
                    onClick={() => handleSendMessage(hint)}
                    className="px-3 py-1.5 bg-[#1a1a1a] hover:bg-[#222] border border-[#2a2a2a] rounded-md text-xs text-neutral-400 hover:text-neutral-200 transition-colors"
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
                  const shouldRenderAgentPanel = isAgentMode && isLastAssistant;
                  const shouldRenderInlineDesignArtifact =
                    msg.role === 'assistant' &&
                    msg.content === DESIGN_ARTIFACT_SENTINEL &&
                    !!designArtifact &&
                    designArtifact.length > 0;

                  // Esconde balão vazio quando thinking está ativo, mas mantém o painel acima
                  if (isLastAssistant && !msg.content && (chatThinkingVisible || isLoading)) {
                    if (shouldRenderAgentPanel) {
                      return (
                        <React.Fragment key={msg.id}>
                          {renderAgentActivityPanel()}
                          {renderNarrativeThinkingBubble()}
                        </React.Fragment>
                      );
                    }
                    return null;
                  }

                  if (shouldRenderInlineDesignArtifact) {
                    return (
                      <React.Fragment key={msg.id}>
                        {shouldRenderAgentPanel && renderAgentActivityPanel()}
                        <div className="w-full max-w-[95%] sm:max-w-[85%] md:max-w-[80%]">
                          <DesignGallery designs={designArtifact} isStreaming={false} onOpenPreview={(i) => setDesignPreviewIndex(i)} />
                        </div>
                      </React.Fragment>
                    );
                  }

                  return (
                    <React.Fragment key={msg.id}>
                      {shouldRenderAgentPanel && renderAgentActivityPanel()}
                      <div
                        className={`flex items-start gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
                      >
                        {msg.role === 'assistant' && (
                          <div className="flex-shrink-0 pt-0.5">
                            <img
                              src={arccoEmblemUrl}
                              alt="Arcco"
                              className={`w-8 h-8 md:w-[50px] md:h-[50px] object-contain opacity-75 ${isStreaming ? 'animate-pulse' : ''}`}
                            />
                          </div>
                        )}
                        <div className={`max-w-[95%] sm:max-w-[85%] md:max-w-[80%] rounded-2xl px-5 py-4 relative group
                                    ${msg.role === 'user'
                            ? 'bg-[#222] text-white rounded-tr-sm shadow-md'
                            : 'bg-transparent text-neutral-200'
                          } ${msg.isError ? 'border border-red-500/30 bg-red-500/10' : ''} ${isStreaming ? 'animate-typing-border' : ''
                          }`}
                        >
                          {renderContent(msg.content)}
                        </div>
                      </div>
                    </React.Fragment>
                  );
                })}

                {/* ── Activity Panel — steps do agente flutuando no chat (sem card) ── */}
                {(() => {
                  // Non-agent mode: indicador de thinking minimalista
                  if (!isAgentMode && isLoading) {
                    return (
                      <div className="w-full max-w-[95%] sm:max-w-[85%] md:max-w-[80%] pl-0 md:pl-[62px] py-1 animate-in fade-in duration-300">
                        <div className="flex items-center gap-2.5">
                          <img
                            src={arccoEmblemUrl}
                            alt=""
                            className="w-4 h-4 object-contain flex-shrink-0 opacity-70 animate-pulse"
                          />
                          {chatThinkingVisible && chatThinkingMessage ? (
                            <span className="text-sm text-neutral-500">{chatThinkingMessage}</span>
                          ) : null}
                        </div>
                      </div>
                    );
                  }

                  return null;
                })()}

                {/* Browser Agent Card — mostra card estilo Manus quando o agente navega */}
                {browserAction && (
                  <div className="w-full max-w-[95%] sm:max-w-[85%] md:max-w-[80%]">
                    <BrowserAgentCard action={browserAction as any} />
                  </div>
                )}

                {generatedFiles.length > 0 && (
                  <div className="w-full max-w-[95%] sm:max-w-[85%] md:max-w-[80%] flex flex-col gap-3">
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
                  <div className="w-full max-w-[95%] sm:max-w-[85%] md:max-w-[80%]">
                    <ClarificationCard
                      questions={clarificationQuestions.questions}
                      helperText={clarificationQuestions.helperText}
                      actionUrl={clarificationQuestions.actionUrl}
                      actionLabel={clarificationQuestions.actionLabel}
                      onSubmit={(answers) => {
                        const basePrompt = (
                          clarificationQuestions.originalPrompt
                          || clarificationBasePromptRef.current
                          || [...messagesRef.current].reverse().find(msg => msg.role === 'user')?.content?.trim()
                          || ''
                        ).trim();
                        const answerText = clarificationQuestions.questions.map((q, i) =>
                          `${q.text} ${answers[i]}`
                        ).join('\n');
                        const compactAnswer = answers.filter(Boolean).join(', ').trim();
                        const responseText = basePrompt
                          ? `${basePrompt}\nFormato escolhido: ${compactAnswer || answerText}`
                          : answerText;
                        const resumeToken = clarificationQuestions.resumeToken;
                        setClarificationQuestions(null);
                        clarificationBasePromptRef.current = null;
                        handleSendMessage(responseText, { browserResumeToken: resumeToken });
                      }}
                    />
                  </div>
                )}

                {/* Text Document Artifact — botões DOCX / PDF para documentos escritos */}
                {textDocArtifact && !isLoading && (
                  <div className="w-full max-w-[95%] sm:max-w-[85%] md:max-w-[80%]">
                    <TextDocCard
                      title={textDocArtifact.title}
                      content={textDocArtifact.content}
                      onOpenPreview={(title, content) => setModalPreview({ type: 'text_doc', title, content })}
                    />
                  </div>
                )}

                {designArtifact && designArtifact.length > 0 && !isLoading && !messages.some(msg => msg.content === DESIGN_ARTIFACT_SENTINEL) && (
                  <div className="w-full max-w-[95%] sm:max-w-[85%] md:max-w-[80%]">
                    <DesignGallery designs={designArtifact} isStreaming={false} onOpenPreview={(i) => setDesignPreviewIndex(i)} />
                  </div>
                )}

                {/* Spy Pages Result Card */}
                {spyPagesResult && spyPagesResult.length > 0 && (
                  <SpyPagesResultCard
                    data={spyPagesResult}
                    onGenerateReport={(prompt) => handleSendMessage(prompt)}
                  />
                )}

                {/* Loading state agora integrado no Activity Panel acima */}


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
                      className="flex items-center gap-2 px-4 py-1.5 bg-[#141414] hover:bg-[#1e1e1e] border border-[#2a2a2a] hover:border-neutral-700 rounded-lg text-[11px] text-neutral-500 hover:text-neutral-300 transition-all duration-200"
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
          <div className="p-3 md:p-4 bg-transparent border-t border-[#222] z-10 relative backdrop-blur-sm flex flex-col gap-4">
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

      {/* Design Preview Modal */}
      {designPreviewIndex !== null && designArtifact && designArtifact.length > 0 && (
        <DesignPreviewModal
          designs={designArtifact}
          initialIndex={designPreviewIndex}
          onClose={() => setDesignPreviewIndex(null)}
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
    </div >
  );
};

export default ArccoChatPage;
