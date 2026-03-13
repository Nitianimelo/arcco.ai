import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import ArccoChatPage from './pages/ArccoChat';
import { ArccoDrivePage } from './pages/ArccoDrive';
import { AdminPage } from './pages/AdminPage';
import { ViewState } from './types';
import { useToast } from './components/Toast';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { supabase } from './lib/supabase';
import { openRouterService } from './lib/openrouter';

function isAdminRoute(): boolean {
  return window.location.pathname === '/admin' || window.location.pathname === '/admin/';
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authView, setAuthView] = useState<'login' | 'register'>('login');

  const [currentView, setCurrentView] = useState<ViewState>('ARCCO_CHAT');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [initialChatIntent, setInitialChatIntent] = useState<string | null>(null);

  // New: Chat Session ID to force reset
  const [chatSessionId, setChatSessionId] = useState<string>(Date.now().toString());

  // Attempt to use toast (assuming wrapped in provider)
  const { showToast } = useToast();

  const [userName, setUserName] = useState("Usuário");
  const [userPlan, setUserPlan] = useState("Free");

  // Authentication Check
  useEffect(() => {
    const storedUserId = localStorage.getItem('arcco_user_id');
    const storedPlan = localStorage.getItem('arcco_user_plan');
    const storedName = localStorage.getItem('arcco_user_name');

    if (storedUserId) {
      setIsAuthenticated(true);
      if (storedPlan) setUserPlan(storedPlan);
      if (storedName) setUserName(storedName);
    }
  }, []);

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

  const handleNavigate = (view: ViewState) => {
    setCurrentView(view);
  };

  const handleNewInteraction = () => {
    setChatSessionId(Date.now().toString());
    setCurrentView('ARCCO_CHAT');
    setInitialChatIntent(null);
    if (showToast) showToast('Nova interação iniciada', 'success');
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
    if (showToast) showToast('Sessão encerrada com sucesso', 'success');
  };

  const handleLoadSession = (sessionId: string) => {
    setChatSessionId(sessionId);
    setCurrentView('ARCCO_CHAT');
  };

  const renderContent = () => {
    switch (currentView) {
      case 'ARCCO_CHAT':
        return (
          <ArccoChatPage
            key={chatSessionId}
            chatSessionId={chatSessionId}
            userName={userName}
            initialMessage={initialChatIntent}
            onClearInitialMessage={() => setInitialChatIntent(null)}
          />
        );
      case 'ARCCO_DRIVE':
        return <ArccoDrivePage />;
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
        userName={userName}
        userPlan={userPlan}
        onNavigate={handleNavigate}
        onNewInteraction={handleNewInteraction}
        onLoadSession={handleLoadSession}
        onTriggerUpsell={handleTriggerUpsell}
        onLogout={handleLogout}
        onCollapsedChange={setIsSidebarCollapsed}
      />

      <main className={`flex-1 relative transition-all duration-300 ${isSidebarCollapsed ? 'ml-16' : 'ml-64'}`}>
        {renderContent()}
      </main>
    </div>
  );
}

export default App;
