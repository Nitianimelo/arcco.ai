import React, { useState } from 'react';
import {
  User,
  Mail,
  Phone,
  Briefcase,
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Lock,
  Eye,
  EyeOff
} from 'lucide-react';
import { userService } from '../lib/supabase';
import { DottedSurface } from '../components/ui/dotted-surface';

type StepId = 'email' | 'name' | 'whatsapp' | 'password' | 'success';

const STEPS: StepId[] = ['email', 'name', 'whatsapp', 'password'];

interface RegisterPageProps {
  onRegister: (userName: string, userEmail: string) => void;
  onBackToLogin: () => void;
}

export const RegisterPage: React.FC<RegisterPageProps> = ({ onRegister, onBackToLogin }) => {
  const [currentStep, setCurrentStep] = useState<StepId>('email');
  const [animKey, setAnimKey] = useState(0);
  const [formData, setFormData] = useState({
    email: '',
    name: '',
    occupation: '',
    phone: '',
    password: '',
    confirmPassword: ''
  });
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const stepIndex = STEPS.indexOf(currentStep as any);

  const handleChange = (field: keyof typeof formData, value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    setError('');
  };

  const formatPhone = (numbers: string) => {
    if (numbers.length <= 2) return numbers;
    if (numbers.length <= 6) return `(${numbers.slice(0, 2)}) ${numbers.slice(2)}`;
    if (numbers.length <= 10) return `(${numbers.slice(0, 2)}) ${numbers.slice(2, 6)}-${numbers.slice(6)}`;
    return `(${numbers.slice(0, 2)}) ${numbers.slice(2, 7)}-${numbers.slice(7, 11)}`;
  };

  const handlePhoneChange = (value: string) => {
    const numbers = value.replace(/\D/g, '');
    if (numbers.length > 11) return;
    handleChange('phone', formatPhone(numbers));
  };

  const goToStep = (step: StepId) => {
    setError('');
    setAnimKey(k => k + 1);
    setCurrentStep(step);
  };

  const goBack = () => {
    const idx = STEPS.indexOf(currentStep as any);
    if (idx > 0) goToStep(STEPS[idx - 1]);
    else onBackToLogin();
  };

  const validateAndNext = () => {
    if (currentStep === 'email') {
      if (!formData.email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
        setError('Insira um email válido');
        return;
      }
      goToStep('name');
    } else if (currentStep === 'name') {
      if (!formData.name.trim()) {
        setError('Insira seu nome completo');
        return;
      }
      goToStep('whatsapp');
    } else if (currentStep === 'whatsapp') {
      if (formData.phone.replace(/\D/g, '').length < 10) {
        setError('Insira um WhatsApp válido com DDD');
        return;
      }
      goToStep('password');
    }
  };

  const handleSubmit = async () => {
    if (formData.password.length < 6) {
      setError('A senha deve ter pelo menos 6 caracteres');
      return;
    }
    if (formData.password !== formData.confirmPassword) {
      setError('As senhas não conferem');
      return;
    }

    setIsLoading(true);
    try {
      const { data, error: dbError } = await userService.createUser({
        nome: formData.name,
        email: formData.email,
        senha: formData.password,
        plano: 'free',
        telefone: formData.phone,
        ocupacao: formData.occupation
      });

      if (dbError) {
        setError(dbError.message || 'Erro ao criar conta. Tente novamente.');
        setIsLoading(false);
        return;
      }

      console.log('Usuario criado com sucesso no Supabase:', data);
      localStorage.setItem('arcco_user_phone', formData.phone);
      localStorage.setItem('arcco_user_occupation', formData.occupation);
      localStorage.setItem('arcco_user_plan', 'free');

      setIsLoading(false);
      goToStep('success');
    } catch (err) {
      console.error('Erro:', err);
      setError('Erro ao criar conta. Verifique sua conexão e tente novamente.');
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      if (currentStep === 'password') handleSubmit();
      else validateAndNext();
    }
  };

  const getPasswordStrength = () => {
    const p = formData.password;
    if (!p) return null;
    if (p.length < 6) return { label: 'Fraca', colorBar: 'bg-red-500', colorText: 'text-red-400', width: '33%' };
    if (p.length < 10 || !/[0-9]/.test(p) || !/[A-Z]/.test(p)) {
      return { label: 'Média', colorBar: 'bg-amber-500', colorText: 'text-amber-400', width: '66%' };
    }
    return { label: 'Forte', colorBar: 'bg-green-500', colorText: 'text-green-400', width: '100%' };
  };

  const strength = getPasswordStrength();

  const stepConfig: Record<StepId, { icon: React.ReactNode; title: string; subtitle: string }> = {
    email: {
      icon: <Mail size={26} className="text-indigo-400" />,
      title: 'Qual é o seu email?',
      subtitle: 'Vamos começar com o seu endereço de email'
    },
    name: {
      icon: <User size={26} className="text-indigo-400" />,
      title: 'Como você se chama?',
      subtitle: 'Nos conte um pouco sobre você'
    },
    whatsapp: {
      icon: <Phone size={26} className="text-indigo-400" />,
      title: 'Qual é o seu WhatsApp?',
      subtitle: 'Para suporte e notificações importantes'
    },
    password: {
      icon: <Lock size={26} className="text-indigo-400" />,
      title: 'Crie sua senha',
      subtitle: 'Escolha uma senha segura para sua conta'
    },
    success: { icon: null, title: '', subtitle: '' }
  };

  const inputClass =
    'w-full bg-white/[0.04] border border-white/[0.08] rounded-xl pl-10 pr-4 py-3 text-white/90 text-sm placeholder-neutral-600 focus:outline-none focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/40 transition-all';

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4 max-sm:p-3 relative overflow-hidden"
      style={{ backgroundColor: 'var(--bg-base)' }}
    >
      <DottedSurface />
      <div className="pointer-events-none absolute inset-0 z-0 bg-[radial-gradient(circle_at_top,rgba(99,102,241,0.14),transparent_34%),radial-gradient(circle_at_bottom_right,rgba(139,92,246,0.10),transparent_32%)]" />
      <div
        className="absolute inset-0 z-0 opacity-[0.015]"
        style={{
          backgroundImage: `linear-gradient(to right, #fff 1px, transparent 1px), linear-gradient(to bottom, #fff 1px, transparent 1px)`,
          backgroundSize: '60px 60px'
        }}
      />

      <div className="relative z-10 w-full max-w-[28rem] max-sm:max-w-[15.5rem]">
        {/* Logo */}
        <div className="text-center mb-7 max-sm:mb-5">
          <img
            src="https://qscezcbpwvnkqoevulbw.supabase.co/storage/v1/object/public/Chipro%20calculadora/arcco%20(1).png"
            alt="Arcco"
            className="h-[92px] max-sm:h-[72px] w-auto object-contain mx-auto drop-shadow-[0_0_40px_rgba(99,102,241,0.3)]"
          />
        </div>

        {/* Card */}
        <div className="bg-[#0F0F0F]/90 border border-[#262626] rounded-2xl p-7 max-sm:p-5 shadow-2xl shadow-black/40 backdrop-blur-xl">

          {/* ── STEPS ── */}
          {currentStep !== 'success' && (
            <>
              {/* Top row: back + counter */}
              <div className="flex items-center justify-between mb-5">
                <button
                  onClick={goBack}
                  className="flex items-center gap-1.5 text-sm text-neutral-500 hover:text-white transition-colors"
                >
                  <ArrowLeft size={15} />
                  {currentStep === 'email' ? 'Voltar ao login' : 'Voltar'}
                </button>
                <span className="text-xs text-neutral-600 tabular-nums">
                  {stepIndex + 1} / {STEPS.length}
                </span>
              </div>

              {/* Progress bar */}
              <div className="flex gap-1.5 mb-8 max-sm:mb-6">
                {STEPS.map((s, i) => (
                  <div key={s} className="flex-1 h-1 rounded-full bg-[#262626] overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${i <= stepIndex ? 'bg-indigo-500' : ''}`}
                      style={{ width: i <= stepIndex ? '100%' : '0%' }}
                    />
                  </div>
                ))}
              </div>

              {/* Icon + title (re-animates on step change) */}
              <div key={`header-${animKey}`} className="mb-6 register-step-in">
                <div className="w-11 h-11 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center mb-4">
                  {stepConfig[currentStep].icon}
                </div>
                <h2 className="text-xl max-sm:text-lg font-medium text-white/90 mb-1 tracking-tight">
                  {stepConfig[currentStep].title}
                </h2>
                <p className="text-sm text-neutral-500">
                  {stepConfig[currentStep].subtitle}
                </p>
              </div>

              {/* Fields (re-animates on step change) */}
              <div key={`fields-${animKey}`} className="space-y-4 register-step-in-delay">

                {/* ── EMAIL ── */}
                {currentStep === 'email' && (
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <Mail size={18} className="text-neutral-500" />
                    </div>
                    <input
                      autoFocus
                      type="email"
                      value={formData.email}
                      onChange={e => handleChange('email', e.target.value)}
                      onKeyDown={handleKeyDown}
                      className={inputClass}
                      placeholder="seu@email.com"
                      autoComplete="email"
                    />
                  </div>
                )}

                {/* ── NAME ── */}
                {currentStep === 'name' && (
                  <>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <User size={18} className="text-neutral-500" />
                      </div>
                      <input
                        autoFocus
                        type="text"
                        value={formData.name}
                        onChange={e => handleChange('name', e.target.value)}
                        onKeyDown={handleKeyDown}
                        className={inputClass}
                        placeholder="Seu nome completo"
                        autoComplete="name"
                      />
                    </div>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <Briefcase size={18} className="text-neutral-500" />
                      </div>
                      <input
                        type="text"
                        value={formData.occupation}
                        onChange={e => handleChange('occupation', e.target.value)}
                        onKeyDown={handleKeyDown}
                        className={inputClass}
                        placeholder="Ocupação (opcional) — Ex: Empresário, Médico..."
                      />
                    </div>
                  </>
                )}

                {/* ── WHATSAPP ── */}
                {currentStep === 'whatsapp' && (
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <Phone size={18} className="text-neutral-500" />
                    </div>
                    <input
                      autoFocus
                      type="tel"
                      value={formData.phone}
                      onChange={e => handlePhoneChange(e.target.value)}
                      onKeyDown={handleKeyDown}
                      className={inputClass}
                      placeholder="(11) 99999-9999"
                      autoComplete="tel"
                    />
                  </div>
                )}

                {/* ── PASSWORD ── */}
                {currentStep === 'password' && (
                  <>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <Lock size={18} className="text-neutral-500" />
                      </div>
                      <input
                        autoFocus
                        type={showPassword ? 'text' : 'password'}
                        value={formData.password}
                        onChange={e => handleChange('password', e.target.value)}
                        className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl pl-10 pr-12 py-3 text-white/90 text-sm placeholder-neutral-600 focus:outline-none focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/40 transition-all"
                        placeholder="Mínimo 6 caracteres"
                        autoComplete="new-password"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute inset-y-0 right-0 pr-3 flex items-center text-neutral-500 hover:text-white transition-colors"
                      >
                        {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                      </button>
                    </div>

                    {/* Strength indicator */}
                    {strength && (
                      <div className="space-y-1.5">
                        <div className="h-1 bg-[#262626] rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-300 ${strength.colorBar}`}
                            style={{ width: strength.width }}
                          />
                        </div>
                        <p className="text-xs text-neutral-500">
                          Força:{' '}
                          <span className={strength.colorText}>{strength.label}</span>
                        </p>
                      </div>
                    )}

                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <Lock size={18} className="text-neutral-500" />
                      </div>
                      <input
                        type={showConfirm ? 'text' : 'password'}
                        value={formData.confirmPassword}
                        onChange={e => handleChange('confirmPassword', e.target.value)}
                        onKeyDown={handleKeyDown}
                        className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl pl-10 pr-12 py-3 text-white/90 text-sm placeholder-neutral-600 focus:outline-none focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/40 transition-all"
                        placeholder="Confirme sua senha"
                        autoComplete="new-password"
                      />
                      <button
                        type="button"
                        onClick={() => setShowConfirm(!showConfirm)}
                        className="absolute inset-y-0 right-0 pr-3 flex items-center text-neutral-500 hover:text-white transition-colors"
                      >
                        {showConfirm ? <EyeOff size={18} /> : <Eye size={18} />}
                      </button>
                    </div>
                  </>
                )}

                {/* Error */}
                {error && (
                  <div className="bg-red-950/30 border border-red-900/50 rounded-xl p-3 flex items-start gap-2">
                    <AlertCircle size={16} className="text-red-400 shrink-0 mt-0.5" />
                    <p className="text-sm text-red-400">{error}</p>
                  </div>
                )}

                {/* CTA */}
                {currentStep !== 'password' ? (
                  <button
                    onClick={validateAndNext}
                    className="w-full bg-indigo-600/90 hover:bg-indigo-600 text-white/90 font-medium py-2.5 px-4 rounded-xl transition-all shadow-sm shadow-indigo-900/30 flex items-center justify-center gap-2 text-sm"
                  >
                    Continuar
                    <ArrowRight size={15} />
                  </button>
                ) : (
                  <button
                    onClick={handleSubmit}
                    disabled={isLoading}
                    className="w-full bg-indigo-600/90 hover:bg-indigo-600 disabled:bg-indigo-900/60 disabled:cursor-not-allowed text-white/90 font-medium py-2.5 px-4 rounded-xl transition-all shadow-sm shadow-indigo-900/30 disabled:shadow-none flex items-center justify-center gap-2 text-sm"
                  >
                    {isLoading ? (
                      <>
                        <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Criando conta...
                      </>
                    ) : (
                      'Criar conta'
                    )}
                  </button>
                )}
              </div>
            </>
          )}

          {/* ── SUCCESS ── */}
          {currentStep === 'success' && (
            <div key="success" className="text-center space-y-6 py-4 register-step-in">
              <div className="w-20 h-20 rounded-full bg-green-600/10 border border-green-500/20 flex items-center justify-center mx-auto register-pop-in">
                <CheckCircle2 size={40} className="text-green-400" />
              </div>
              <div>
                <h3 className="text-xl font-medium text-white/90 mb-2 tracking-tight">Cadastro concluído!</h3>
                <p className="text-neutral-500 text-sm leading-relaxed">
                  Bem-vindo ao Arcco,{' '}
                  <span className="text-white font-medium">{formData.name.split(' ')[0]}</span>!
                  <br />
                  Sua conta foi criada com sucesso.
                </p>
              </div>
              <button
                onClick={() => onRegister(formData.name, formData.email)}
                className="w-full bg-indigo-600/90 hover:bg-indigo-600 text-white/90 font-medium py-2.5 px-4 rounded-xl transition-all shadow-sm shadow-indigo-900/30 text-sm"
              >
                Acessar Plataforma
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="mt-8 max-sm:mt-5 text-center">
          <p className="text-xs text-neutral-600 leading-relaxed max-w-sm mx-auto">
            Ao criar sua conta, você concorda com nossos Termos de Uso e Política de Privacidade.
          </p>
        </div>
      </div>

      <style>{`
        @keyframes registerStepIn {
          from { opacity: 0; transform: translateY(14px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes registerPopIn {
          from { opacity: 0; transform: scale(0.5); }
          to   { opacity: 1; transform: scale(1); }
        }
        .register-step-in {
          animation: registerStepIn 0.32s ease both;
        }
        .register-step-in-delay {
          animation: registerStepIn 0.38s ease 0.05s both;
        }
        .register-pop-in {
          animation: registerPopIn 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275) both;
        }
      `}</style>
    </div>
  );
};
