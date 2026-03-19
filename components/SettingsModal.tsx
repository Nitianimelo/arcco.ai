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
  { id: 'dark',     label: 'Dark',      desc: 'Padrão',           bg: '#050505', line: 'rgba(255,255,255,0.07)' },
  { id: 'dim',      label: 'Dim',       desc: 'Azul escuro',      bg: '#0a0f1c', line: 'rgba(160,185,255,0.08)' },
  { id: 'midnight', label: 'Midnight',  desc: 'Preto OLED',       bg: '#000000', line: 'rgba(255,255,255,0.09)' },
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
      <div className="flex gap-3">
        {themes.map(t => (
          <button
            key={t.id}
            onClick={() => apply(t.id)}
            className={`flex-1 flex flex-col items-center gap-2 p-3 rounded-xl border transition-all ${
              current === t.id
                ? 'border-indigo-500/50 bg-indigo-500/5'
                : 'border-[#313134] bg-[#1a1a1d] hover:border-neutral-600'
            }`}
          >
            <div
              className="w-full h-10 rounded-lg relative overflow-hidden"
              style={{
                backgroundColor: t.bg,
                backgroundImage: `linear-gradient(to right, ${t.line} 1px, transparent 1px), linear-gradient(to bottom, ${t.line} 1px, transparent 1px)`,
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
const PersonalizacaoTab: React.FC<{ userName: string; userId: string }> = ({ userName, userId }) => {
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
    await preferencesApi.save(userId, {
      theme,
      display_name: displayName,
      custom_instructions: customInstructions,
      logo_url: logoUrl,
      occupation,
    });
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
            className="w-full bg-[#1a1a1d] border border-[#313134] text-neutral-200 text-sm rounded-xl px-3 py-2.5 outline-none focus:border-indigo-500/50"
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
              className="flex-1 bg-[#1a1a1d] border border-[#313134] text-neutral-200 text-sm rounded-xl px-3 py-2.5 outline-none focus:border-indigo-500/50"
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
            className="w-full bg-[#1a1a1d] border border-[#313134] text-neutral-200 text-sm rounded-xl px-3 py-2.5 outline-none focus:border-indigo-500/50"
          />
        </div>
      </div>

      <div className="pt-4 border-t border-[#1e1e21] flex justify-end">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium rounded-xl transition-colors flex items-center gap-2"
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
        <input type="password" placeholder="••••••••" className="w-full bg-[#1a1a1d] border border-[#313134] text-neutral-200 text-sm rounded-xl px-3 py-2.5 outline-none focus:border-indigo-500/50" />
      </div>
      <div>
        <label className="block text-xs text-neutral-500 mb-1.5 font-medium uppercase tracking-wider">Nova Senha</label>
        <input type="password" placeholder="••••••••" className="w-full bg-[#1a1a1d] border border-[#313134] text-neutral-200 text-sm rounded-xl px-3 py-2.5 outline-none focus:border-indigo-500/50" />
      </div>
    </div>

    <div className="pt-4 border-t border-[#1e1e21] flex justify-between items-center">
      <button className="text-sm text-indigo-400 hover:text-indigo-300 font-medium transition-colors">Resgate de senha (Esqueci minha senha)</button>
      <button className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-xl transition-colors">Atualizar Senha</button>
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
        <p className="text-neutral-500 text-sm">
          Plano atual: <span className="text-indigo-400 font-medium capitalize">{userPlan}</span>
        </p>
      </div>

      <div className="relative overflow-hidden rounded-3xl border border-indigo-500/20 bg-[radial-gradient(circle_at_top_left,rgba(99,102,241,0.22),transparent_38%),linear-gradient(180deg,#1a1b22_0%,#121319_100%)] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.35)]">
        <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(135deg,rgba(255,255,255,0.06),transparent_35%,transparent_70%,rgba(99,102,241,0.08))]" />
        <div className="relative flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-indigo-400/20 bg-indigo-500/[0.12] text-indigo-300 shadow-[0_0_30px_rgba(99,102,241,0.12)]">
                <CreditCard size={18} />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="text-xl font-semibold text-white">Starter</h4>
                  {isStarter && (
                    <span className="rounded-full border border-emerald-400/20 bg-emerald-500/[0.12] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-300">
                      Ativo
                    </span>
                  )}
                </div>
                <p className="text-sm text-neutral-400">Plano ideal para começar com a Arcco.</p>
              </div>
            </div>

            <div className="flex items-end gap-2">
              <span className="text-4xl font-semibold tracking-tight text-white">R$ 99,90</span>
              <span className="pb-1 text-sm text-neutral-500">/mês</span>
            </div>

            <div className="flex flex-wrap gap-2 text-xs text-neutral-300">
              <span className="rounded-full border border-white/[0.08] bg-white/[0.06] px-3 py-1.5">Uso essencial da plataforma</span>
              <span className="rounded-full border border-white/[0.08] bg-white/[0.06] px-3 py-1.5">Experiência completa do chat</span>
            </div>
          </div>

          <div className="flex w-full max-w-xs flex-col gap-3">
            <button
              disabled={isStarter}
              className={`w-full rounded-2xl px-5 py-3.5 text-sm font-semibold transition-all ${
                isStarter
                  ? 'cursor-not-allowed border border-white/10 bg-white/[0.06] text-neutral-500'
                  : isFree
                    ? 'bg-gradient-to-r from-indigo-500 via-indigo-400 to-sky-400 text-white shadow-[0_12px_35px_rgba(99,102,241,0.35)] hover:-translate-y-0.5 hover:shadow-[0_18px_45px_rgba(99,102,241,0.4)]'
                    : 'border border-indigo-400/20 bg-indigo-500/10 text-indigo-200 hover:bg-indigo-500/15'
              }`}
            >
              {isStarter ? 'Plano atual' : 'Assinar Starter'}
            </button>

            <div className="rounded-2xl border border-white/[0.08] bg-black/[0.15] px-4 py-3 text-sm text-neutral-400">
              {isStarter
                ? 'Seu acesso Starter já está ativo.'
                : isFree
                  ? 'Faça o upgrade para liberar o plano Starter.'
                  : `Plano detectado: ${userPlan}.`}
            </div>
          </div>
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
      <button className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-xl transition-colors flex items-center gap-2">
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
export const SettingsModal: React.FC<SettingsModalProps> = ({ open, onClose, userName, userPlan, userId }) => {
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
      <div className="relative bg-[#111113] border border-[#262629] rounded-2xl shadow-2xl w-[860px] max-h-[85vh] flex flex-col overflow-hidden">
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
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all text-left border ${activeTab === tab.id
                  ? 'bg-indigo-500/10 text-white border-indigo-500/20'
                  : 'text-neutral-500 hover:text-white hover:bg-white/[0.04] border-transparent'
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
            {activeTab === 'personalizacao' && <PersonalizacaoTab userName={userName} userId={userId} />}
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
