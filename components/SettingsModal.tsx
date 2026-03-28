import React, { useState, useEffect } from 'react';
import {
  X,
  Settings,
  User,
  CreditCard,
  BarChart3,
  Bell,
  Check,
  Loader2,
} from 'lucide-react';
import { preferencesApi } from '../lib/preferencesApi';

// ── Theme Picker ──────────────────────────────────────────────────
const themes = [
  { id: 'dark',  label: 'Dark',  desc: 'Padrão',      bg: '#050505', line: 'rgba(255,255,255,0.07)' },
  { id: 'ghost', label: 'Ghost', desc: 'Flat dark',   bg: '#0c0c0c', line: 'transparent' },
  { id: 'light', label: 'Light', desc: 'Clean claro', bg: '#ededef', line: 'transparent' },
];

const ThemePicker: React.FC<{ current: string; onChange: (id: string) => void }> = ({ current, onChange }) => {
  const apply = (id: string) => {
    localStorage.setItem('arcco_theme', id);
    document.documentElement.setAttribute('data-theme', id);
    onChange(id);
  };

  return (
    <div>
      <label className="block text-xs text-neutral-500 mb-2 font-medium uppercase tracking-wider">Tema da interface</label>
      <div className="grid grid-cols-3 gap-3">
        {themes.map(t => (
          <button
            key={t.id}
            onClick={() => apply(t.id)}
            className={`flex flex-col items-center gap-2 p-2.5 rounded-xl border transition-all ${
              current === t.id
                ? 'border-indigo-500/50 bg-indigo-500/5'
                : 'border-[#313134] bg-[#1a1a1d] hover:border-neutral-600'
            }`}
          >
            <div
              className="w-full h-9 rounded-lg relative overflow-hidden"
              style={{
                backgroundColor: t.bg,
                backgroundImage: t.line !== 'transparent'
                  ? `linear-gradient(to right, ${t.line} 1px, transparent 1px), linear-gradient(to bottom, ${t.line} 1px, transparent 1px)`
                  : 'none',
                backgroundSize: '10px 10px',
              }}
            >
              {current === t.id && (
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="w-4 h-4 rounded-full bg-indigo-500 flex items-center justify-center">
                    <Check size={10} className="text-white" />
                  </div>
                </div>
              )}
            </div>
            <div className="text-center">
              <p className={`text-xs font-medium ${current === t.id ? 'text-white' : 'text-neutral-400'}`}>{t.label}</p>
              <p className="text-[10px] text-neutral-600">{t.desc}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
};

type Tab = 'personalizacao' | 'conta' | 'plano' | 'uso' | 'tarefas';

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
  userName: string;
  userPlan: string;
  userId: string;
  onDisplayNameChange?: (displayName: string | null) => void;
}

// ── Toggle helper ────────────────────────────────────────
const Toggle: React.FC<{ value: boolean; onChange: (v: boolean) => void }> = ({ value, onChange }) => (
  <button
    onClick={() => onChange(!value)}
    className={`w-10 h-6 rounded-full relative transition-colors duration-200 ${value ? 'bg-indigo-500' : 'bg-neutral-700'}`}
  >
    <span
      className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-200 ${value ? 'translate-x-4' : 'translate-x-0'}`}
    />
  </button>
);

// ── Tab: Personalização ────────────────────────────────────────────
const PersonalizacaoTab: React.FC<{ userName: string; userId: string; onDisplayNameChange?: (displayName: string | null) => void }> = ({ userName, userId, onDisplayNameChange }) => {
  const [theme, setTheme] = useState(() => localStorage.getItem('arcco_theme') || 'dark');
  const [displayName, setDisplayName] = useState(userName);
  const [customInstructions, setCustomInstructions] = useState('');
  const [logoUrl, setLogoUrl] = useState('');
  const [occupation, setOccupation] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Carrega preferências do Supabase ao montar
  useEffect(() => {
    if (!userId) { setLoading(false); return; }
    preferencesApi.get(userId).then(prefs => {
      if (prefs.theme)               setTheme(prefs.theme);
      if (prefs.display_name)        setDisplayName(prefs.display_name);
      if (prefs.custom_instructions) setCustomInstructions(prefs.custom_instructions);
      if (prefs.logo_url)            setLogoUrl(prefs.logo_url);
      if (prefs.occupation)          setOccupation(prefs.occupation);
      setLoading(false);
    });
  }, [userId]);

  const handleSave = async () => {
    setSaving(true);
    const trimmedDisplayName = displayName.trim();
    await preferencesApi.save(userId, {
      theme,
      display_name: trimmedDisplayName,
      custom_instructions: customInstructions,
      logo_url: logoUrl,
      occupation,
    });
    onDisplayNameChange?.(trimmedDisplayName || null);
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40">
        <Loader2 size={20} className="text-neutral-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-white font-semibold mb-1">Personalização</h3>
        <p className="text-neutral-500 text-sm">Configure como a interface se comporta para você.</p>
      </div>

      <div className="space-y-4">
        <ThemePicker current={theme} onChange={setTheme} />

        <div>
          <label className="block text-xs text-neutral-500 mb-1.5 font-medium uppercase tracking-wider">Como a Arcco deveria te chamar</label>
          <input
            type="text"
            value={displayName}
            onChange={e => setDisplayName(e.target.value)}
            placeholder="Ex: Master, User..."
            className="w-full bg-[#1a1a1d] border border-[#313134] text-neutral-200 text-sm rounded-lg px-3 py-2.5 outline-none focus:border-indigo-500/50"
          />
        </div>
        <div>
          <label className="block text-xs text-neutral-500 mb-1.5 font-medium uppercase tracking-wider">Instruções personalizadas</label>
          <textarea
            value={customInstructions}
            onChange={e => setCustomInstructions(e.target.value)}
            placeholder="Ex: Seja objetivo, use metáforas..."
            className="w-full h-20 bg-[#1a1a1d] border border-[#313134] text-neutral-200 text-sm rounded-xl px-3 py-2.5 outline-none focus:border-indigo-500/50 resize-none"
          />
        </div>
        <div>
          <label className="block text-xs text-neutral-500 mb-1.5 font-medium uppercase tracking-wider">Logomarca para designs</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={logoUrl}
              onChange={e => setLogoUrl(e.target.value)}
              placeholder="URL da Logo"
              className="flex-1 bg-[#1a1a1d] border border-[#313134] text-neutral-200 text-sm rounded-lg px-3 py-2.5 outline-none focus:border-indigo-500/50"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs text-neutral-500 mb-1.5 font-medium uppercase tracking-wider">Ocupação</label>
          <input
            type="text"
            value={occupation}
            onChange={e => setOccupation(e.target.value)}
            placeholder="Ex: Analista, UI/UX, Founder..."
            className="w-full bg-[#1a1a1d] border border-[#313134] text-neutral-200 text-sm rounded-lg px-3 py-2.5 outline-none focus:border-indigo-500/50"
          />
        </div>
      </div>

      <div className="pt-4 border-t border-[#1e1e21] flex justify-end">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium rounded-md transition-colors flex items-center gap-2"
        >
          {saving ? (
            <><Loader2 size={14} className="animate-spin" /> Salvando...</>
          ) : saved ? (
            <><Check size={14} /> Salvo!</>
          ) : (
            'Salvar preferências'
          )}
        </button>
      </div>
    </div>
  );
};

// ── Tab: Conta ────────────────────────────────────────────
const ContaTab: React.FC = () => (
  <div className="space-y-6">
    <div>
      <h3 className="text-white font-semibold mb-1">Informações de Login</h3>
      <p className="text-neutral-500 text-sm">Gerencie seu acesso à plataforma.</p>
    </div>

    <div className="space-y-4">
      <div>
        <label className="block text-xs text-neutral-500 mb-1.5 font-medium uppercase tracking-wider">E-mail de Login</label>
        <input type="email" placeholder="seu@email.com" className="w-full bg-[#1a1a1d] border border-[#313134] text-neutral-200 text-sm rounded-xl px-3 py-2.5 outline-none focus:border-indigo-500/50 cursor-not-allowed opacity-70" disabled />
      </div>
      <div>
        <label className="block text-xs text-neutral-500 mb-1.5 font-medium uppercase tracking-wider">Senha Atual</label>
        <input type="password" placeholder="••••••••" className="w-full bg-[#1a1a1d] border border-[#313134] text-neutral-200 text-sm rounded-lg px-3 py-2.5 outline-none focus:border-indigo-500/50" />
      </div>
      <div>
        <label className="block text-xs text-neutral-500 mb-1.5 font-medium uppercase tracking-wider">Nova Senha</label>
        <input type="password" placeholder="••••••••" className="w-full bg-[#1a1a1d] border border-[#313134] text-neutral-200 text-sm rounded-lg px-3 py-2.5 outline-none focus:border-indigo-500/50" />
      </div>
    </div>

    <div className="pt-4 border-t border-[#1e1e21] flex justify-between items-center">
      <button className="text-sm text-indigo-400 hover:text-indigo-300 font-medium transition-colors">Resgate de senha (Esqueci minha senha)</button>
      <button className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-md transition-colors">Atualizar Senha</button>
    </div>
  </div>
);

// ── Tab: Plano ────────────────────────────────────────────
const PlanoTab: React.FC<{ userPlan: string }> = ({ userPlan }) => {
  const normalizedPlan = userPlan.trim().toLowerCase();
  const isStarter = normalizedPlan === 'starter';
  const isFree = normalizedPlan === 'free';

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-white font-semibold mb-1">Seu Plano</h3>
        <p className="text-neutral-500 text-sm">Gerencie sua assinatura.</p>
      </div>

      <div className="rounded-2xl border border-[#262629] bg-[#141416] p-5 space-y-5">
        {/* Cabeçalho do plano */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
              <CreditCard size={15} className="text-indigo-400" />
            </div>
            <div>
              <p className="text-sm font-medium text-white capitalize">{userPlan}</p>
              <p className="text-xs text-neutral-500 mt-1">R$ 99,90 / mês</p>
            </div>
          </div>
          {isStarter && (
            <span className="text-[10px] font-medium uppercase tracking-wider text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 rounded-full">
              Ativo
            </span>
          )}
          {isFree && (
            <span className="text-[10px] font-medium uppercase tracking-wider text-neutral-500 bg-white/[0.04] border border-white/[0.08] px-2.5 py-1 rounded-full">
              Gratuito
            </span>
          )}
        </div>

        <div className="border-t border-[#262629]" />

        {/* CTA */}
        <div className="flex items-center justify-between gap-4">
          <p className="text-xs text-neutral-500">
            {isStarter ? 'Seu acesso já está ativo.' : 'Faça upgrade para liberar todos os recursos.'}
          </p>
          <button
            disabled={isStarter}
            className={`flex-shrink-0 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              isStarter
                ? 'cursor-not-allowed text-neutral-600 bg-white/[0.03] border border-white/[0.06]'
                : 'bg-indigo-600 hover:bg-indigo-500 text-white'
            }`}
          >
            {isStarter ? 'Plano atual' : 'Assinar Starter'}
          </button>
        </div>
      </div>
    </div>
  );
};

// ── Tab: Uso ──────────────────────────────────────────────
const UsoTab: React.FC = () => {
  const used = 47;
  const total = 100;
  const pct = Math.round((used / total) * 100);

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-white font-semibold mb-1">Uso da Plataforma</h3>
        <p className="text-neutral-500 text-sm">Acompanhe seu limite de uso mensal.</p>
      </div>

      <div className="pt-4">
        <div className="flex justify-between items-center mb-3">
          <span className="text-sm text-neutral-300 font-medium">Uso atual ({pct}%)</span>
        </div>
      </div>
    </div>
  );
};

// ── Tab: Tarefas Agendadas ────────────────────────────────
const TarefasTab: React.FC = () => (
  <div className="space-y-6">
    <div className="flex justify-between items-start">
      <div>
        <h3 className="text-white font-semibold mb-1">Tarefas Agendadas</h3>
        <p className="text-neutral-500 text-sm">Gerencie automações e tarefas programadas para os agentes.</p>
      </div>
      <button className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-md transition-colors flex items-center gap-2">
        <Bell size={14} />
        Nova Tarefa
      </button>
    </div>

    <div className="bg-[#1a1a1d] border border-[#313134] rounded-xl p-8 text-center flex flex-col items-center justify-center">
      <Bell size={32} className="text-neutral-600 mb-3" />
      <h4 className="text-white font-medium mb-1">Nenhuma tarefa agendada</h4>
      <p className="text-neutral-500 text-sm max-w-sm mx-auto">
        Você pode configurar os agentes para executar rotinas automaticamente em horários específicos.
      </p>
    </div>
  </div>
);

// ── Modal Principal ───────────────────────────────────────
export const SettingsModal: React.FC<SettingsModalProps> = ({ open, onClose, userName, userPlan, userId, onDisplayNameChange }) => {
  const [activeTab, setActiveTab] = useState<Tab>('personalizacao');

  if (!open) return null;

  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: 'personalizacao', label: 'Personalização', icon: <Settings size={15} /> },
    { id: 'conta', label: 'Conta', icon: <User size={15} /> },
    { id: 'plano', label: 'Plano', icon: <CreditCard size={15} /> },
    { id: 'uso', label: 'Uso', icon: <BarChart3 size={15} /> },
    { id: 'tarefas', label: 'Tarefas agendadas', icon: <Bell size={15} /> },
  ];

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-[#111113] border border-[#262629] rounded-2xl shadow-2xl w-full max-w-[90vw] md:w-[860px] max-h-[85vh] flex flex-col overflow-hidden m-4 md:m-0">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#262629] shrink-0">
          <div className="flex items-center gap-2.5">
            <Settings size={17} className="text-indigo-400" />
            <h2 className="text-white font-semibold text-base">Configurações</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-neutral-500 hover:text-white hover:bg-white/[0.05] rounded-lg transition-colors"
          >
            <X size={17} />
          </button>
        </div>

        <div className="flex flex-1 min-h-0">
          {/* Tabs laterais */}
          <div className="w-44 border-r border-[#262629] p-3 flex flex-col gap-1 shrink-0">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all text-left ${activeTab === tab.id
                  ? 'bg-white/[0.07] text-white'
                  : 'text-neutral-500 hover:text-white hover:bg-white/[0.04]'
                  }`}
              >
                <span className={activeTab === tab.id ? 'text-indigo-400' : ''}>
                  {tab.icon}
                </span>
                {tab.label}
              </button>
            ))}
          </div>

          {/* Conteúdo */}
          <div className="flex-1 overflow-y-auto p-6 scrollbar-hide">
            {activeTab === 'personalizacao' && <PersonalizacaoTab userName={userName} userId={userId} onDisplayNameChange={onDisplayNameChange} />}
            {activeTab === 'conta' && <ContaTab />}
            {activeTab === 'plano' && <PlanoTab userPlan={userPlan} />}
            {activeTab === 'uso' && <UsoTab />}
            {activeTab === 'tarefas' && <TarefasTab />}
          </div>
        </div>
      </div>
    </div>
  );
};
