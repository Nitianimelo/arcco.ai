import { LucideIcon } from 'lucide-react';

// ==========================================
// PLATFORM NAVIGATION TYPES
// ==========================================

export type ViewState =
  | 'DASHBOARD'           // Home - Início (só saudação)
  | 'FERRAMENTAS'         // Página de Ferramentas
  | 'PROJETOS'            // Projetos
  | 'TOOLS_MY'            // Minhas Tools
  | 'TOOLS_STORE'         // Loja de Tools
  | 'ARCCO_DRIVE'         // Arcco Drive - Cofre de Arquivos
  | 'ARCCO_CHAT'          // Arcco Chat - Chat com IA
  | 'AULAS'               // Aulas (em breve)
  | 'SUPORTE'             // Suporte
  | 'PROFILE'             // Minha Conta
  | 'SETTINGS'            // Configurações
  | 'ESPECIALISTAS';      // Especialistas (em breve)

// ==========================================
// PLATFORM & TOOLS TYPES
// ==========================================

export type ToolId = 'arcco_flow' | 'arcco_learn' | 'arcco_analytics';

export interface PlatformTool {
  id: ToolId;
  name: string;
  description: string;
  icon: string;
  color: string;
  bgGradient: string;
  status: 'active' | 'coming_soon' | 'beta';
  features: string[];
}

// ==========================================
// USER TYPES
// ==========================================

export interface User {
  id: string;
  name: string;
  email: string;
  avatar?: string;
  role: 'admin' | 'manager' | 'operator';
  plan: 'free' | 'starter' | 'pro' | 'enterprise';
  createdAt: string;
}

// ==========================================
// ARCCO CHAT TYPES
// ==========================================

export interface ChatConfig {
  id?: number;
  slot_number: number;  // 1-5
  model_name: string;
  openrouter_model_id: string;
  system_prompt?: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface ChatMessageLocal {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  model: string;
  timestamp: number;
}

export interface ArccoChatSession {
  id: string;
  title: string;
  date: string;
  messages: ChatMessageLocal[];
  selectedModel: string;
  createdAt: number;
  updatedAt: number;
}

// ==========================================
// NAVIGATION TYPES
// ==========================================

export interface NavItem {
  id: ViewState;
  label: string;
  icon: LucideIcon;
  badge?: number;
  disabled?: boolean;
  comingSoon?: boolean;
}

export interface NavSection {
  title: string;
  items: NavItem[];
}
