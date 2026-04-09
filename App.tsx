import React, { useState, useEffect } from 'react';
import { Menu } from 'lucide-react';
import { Sidebar } from './components/Sidebar';
import ArccoChatPage from './pages/ArccoChat';
import { AdminPage } from './pages/AdminPage';
import ToolsStorePage from './pages/ToolsStorePage';
import MyToolsPage from './pages/MyToolsPage';
import { ViewState } from './types';
import { useToast } from './components/Toast';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { supabase } from './lib/supabase';
import { openRouterService } from './lib/openrouter';
import { projectApi, Project } from './lib/projectApi';
import { conversationApi } from './lib/conversationApi';
import { preferencesApi } from './lib/preferencesApi';

function isAdminRoute(): boolean {
  return window.location.pathname === '/admin' || window.location.pathname === '/admin/';
}

function getFirstName(name: string): string {
  return name.trim().split(/\s+/)[0] || 'Usuário';
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authView, setAuthView] = useState<'login' | 'register'>('login');

  const [currentView, setCurrentView] = useState<ViewState>('ARCCO_CHAT');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(typeof window !== 'undefined' && window.innerWidth < 768);

  useEffect(() => {
    const handler = () => {
      const mobile = window.innerWidth < 768;
      setIsMobile(mobile);
      if (!mobile) setIsMobileSidebarOpen(false);
    };
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);
  const [initialChatIntent, setInitialChatIntent] = useState<string | null>(null);

  // New: Chat Session ID to force reset
  const [chatSessionId, setChatSessionId] = useState<string>(Date.now().toString());

  // Attempt to use toast (assuming wrapped in provider)
  const { showToast } = useToast();

  const [userName, setUserName] = useState("Usuário");
  const [preferredDisplayName, setPreferredDisplayName] = useState<string | null>(null);
  const [userPlan, setUserPlan] = useState("Free");
  const [userId, setUserId] = useState(() => localStorage.getItem('arcco_user_id') || '');
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [activeProject, setActiveProject] = useState<Project | null>(null);

  // Authentication Check
  useEffect(() => {
    const storedUserId = localStorage.getItem('arcco_user_id');
    const storedPlan = localStorage.getItem('arcco_user_plan');
    const storedName = localStorage.getItem('arcco_user_name');
    const cachedPrefs = preferencesApi.getCached();

    if (storedUserId) {
      setIsAuthenticated(true);
      if (storedPlan) setUserPlan(storedPlan);
      if (storedName) setUserName(storedName);
      if (cachedPrefs.display_name?.trim()) {
        setPreferredDisplayName(cachedPrefs.display_name.trim());
      }
    }
  }, []);

  useEffect(() => {
    if (!userId) {
      setPreferredDisplayName(null);
      return;
    }

    preferencesApi.get(userId).then((prefs) => {
      const trimmedDisplayName = prefs.display_name?.trim();
      setPreferredDisplayName(trimmedDisplayName ? trimmedDisplayName : null);
    }).catch(() => {
      const cachedPrefs = preferencesApi.getCached();
      const trimmedDisplayName = cachedPrefs.display_name?.trim();
      setPreferredDisplayName(trimmedDisplayName ? trimmedDisplayName : null);
    });
  }, [userId]);

  // Load API keys from Supabase on startup
  useEffect(() => {
    const loadApiKeys = async () => {
      try {
        const { data, error } = await supabase
          .from('ApiKeys')
          .select('*')
          .eq('is_active', true);

        if (error || !data) return;

        const openRouterKey = data.find(k => k.provider === 'openrouter');
        if (openRouterKey) {
          openRouterService.setApiKey(openRouterKey.api_key);
        }
      } catch (e) {
        console.warn('[App] Falha ao carregar API keys:', e);
      }
    };

    loadApiKeys();
  }, []);

  // Quando um projeto é selecionado: carrega detalhes e busca conversa existente
  useEffect(() => {
    if (!selectedProjectId || !userId) {
      setActiveProject(null);
      return;
    }
    projectApi.get(selectedProjectId, userId).then(proj => setActiveProject(proj));
    conversationApi.findByProject(userId, selectedProjectId).then(conv => {
      if (conv) {
        setChatSessionId(conv.id);
      } else {
        setChatSessionId(Date.now().toString());
      }
      setCurrentView('ARCCO_CHAT');
    });
  }, [selectedProjectId, userId]);

  const handleNavigate = (view: ViewState) => {
    setCurrentView(view);
  };

  const handleNewInteraction = () => {
    setSelectedProjectId(null);
    setActiveProject(null);
    setChatSessionId(Date.now().toString());
    setCurrentView('ARCCO_CHAT');
    setInitialChatIntent(null);
  };

  const handleTriggerUpsell = (feature: string) => {
    console.log(`Upsell triggered for ${feature}`);
    // In a real app, this would open a modal
  };

  // Listen for custom events from legacy components
  useEffect(() => {
    const handleOpenPreview = (event: CustomEvent) => {
      console.log("Preview Requested", event.detail);
    };

    window.addEventListener('openPreview', handleOpenPreview as EventListener);
    return () => window.removeEventListener('openPreview', handleOpenPreview as EventListener);
  }, []);

  const handleLogin = (name: string, email: string) => {
    setIsAuthenticated(true);
    setUserName(name);
    setPreferredDisplayName(null);
    localStorage.setItem('arcco_user_name', name);

    // Refresh plan directly from local storage after LoginPage sets it
    const storedPlan = localStorage.getItem('arcco_user_plan');
    if (storedPlan) setUserPlan(storedPlan);

    if (showToast) showToast(`Bem-vindo de volta, ${name}!`, 'success');
  };

  const handleLogout = () => {
    localStorage.removeItem('arcco_user_id');
    localStorage.removeItem('arcco_user_plan');
    localStorage.removeItem('arcco_user_name');
    setIsAuthenticated(false);
    setPreferredDisplayName(null);
    if (showToast) showToast('Sessão encerrada com sucesso', 'success');
  };

  const greetingName = preferredDisplayName || getFirstName(userName);
  const sidebarDisplayName = preferredDisplayName || userName;

  const handleLoadSession = (sessionId: string) => {
    setChatSessionId(sessionId);
    setCurrentView('ARCCO_CHAT');
  };

  const renderContent = () => {
    switch (currentView) {
      case 'ARCCO_CHAT':
        return (
          <ArccoChatPage
            chatSessionId={chatSessionId}
            userName={greetingName}
            userId={userId}
            projectId={selectedProjectId}
            project={activeProject}
            onConversationIdChange={setChatSessionId}
            onProjectUpdated={(updated) => setActiveProject(updated)}
            onProjectDeleted={() => {
              setSelectedProjectId(null);
              setActiveProject(null);
              setChatSessionId(Date.now().toString());
            }}
            initialMessage={initialChatIntent}
            onClearInitialMessage={() => setInitialChatIntent(null)}
          />
        );
      case 'TOOLS_STORE':
        return <ToolsStorePage />;
      case 'TOOLS_MY':
        return <MyToolsPage onNavigateToStore={() => setCurrentView('TOOLS_STORE')} />;
      default:
        return (
          <div className="flex flex-col items-center justify-center h-full text-neutral-500">
            <p>View not found: {currentView}</p>
            <button onClick={() => setCurrentView('ARCCO_CHAT')} className="mt-4 text-indigo-400 hover:underline">Go Home</button>
          </div>
        );
    }
  };

  if (isAdminRoute()) {
    return <AdminPage />;
  }

  if (!isAuthenticated) {
    if (authView === 'login') {
      return <LoginPage onLogin={handleLogin} onGoToRegister={() => setAuthView('register')} />;
    } else {
      return <RegisterPage onRegister={handleLogin} onBackToLogin={() => setAuthView('login')} />;
    }
  }

  return (
    <div className="flex h-screen text-white font-sans overflow-hidden selection:bg-indigo-500/30" style={{ backgroundColor: 'var(--bg-elevated)' }}>
      <Sidebar
        currentView={currentView}
        userName={sidebarDisplayName}
        userPlan={userPlan}
        userId={userId}
        selectedProjectId={selectedProjectId}
        onSelectProject={setSelectedProjectId}
        onNavigate={handleNavigate}
        onNewInteraction={handleNewInteraction}
        onLoadSession={handleLoadSession}
        onTriggerUpsell={handleTriggerUpsell}
        onLogout={handleLogout}
        onCollapsedChange={setIsSidebarCollapsed}
        onDisplayNameChange={setPreferredDisplayName}
        isMobile={isMobile}
        isMobileOpen={isMobileSidebarOpen}
        onMobileClose={() => setIsMobileSidebarOpen(false)}
      />

      {isMobile && !isMobileSidebarOpen && (
        <button
          onClick={() => setIsMobileSidebarOpen(true)}
          className="fixed top-4 left-4 z-40 p-2 bg-[#111113] border border-[#262629] rounded-lg text-neutral-400 hover:text-white transition-colors md:hidden"
          aria-label="Abrir menu"
        >
          <Menu size={20} />
        </button>
      )}

      <main className={`flex-1 relative transition-all duration-300 ${isMobile ? 'ml-0' : (isSidebarCollapsed ? 'ml-16' : 'ml-64')}`}>
        {renderContent()}
      </main>
    </div>
  );
}

export default App;
