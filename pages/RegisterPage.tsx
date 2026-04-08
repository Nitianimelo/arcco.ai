import React, { useState } from 'react';
import {
  User,
  Mail,
  Phone,
  Briefcase,
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Lock,
  Eye,
  EyeOff
} from 'lucide-react';
import { userService } from '../lib/supabase';
import { DottedSurface } from '../components/ui/dotted-surface';

interface RegisterPageProps {
  onRegister: (userName: string, userEmail: string) => void;
  onBackToLogin: () => void;
}

export const RegisterPage: React.FC<RegisterPageProps> = ({ onRegister, onBackToLogin }) => {
  const [step, setStep] = useState<'form' | 'success'>('form');
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    occupation: '',
    phone: ''
  });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleInputChange = (field: keyof typeof formData, value: string) => {
    setFormData({ ...formData, [field]: value });
    setError('');
  };

  const formatPhone = (value: string) => {
    const numbers = value.replace(/\D/g, '');

    // Prevent more than 11 digits
    if (numbers.length > 11) return value;

    if (numbers.length <= 2) return numbers;

    // Format area code: (XX)
    if (numbers.length <= 6) return `(${numbers.slice(0, 2)}) ${numbers.slice(2)}`;

    // Format landline: (XX) XXXX-XXXX (Wait until 10 digits to hyphenate properly or while typing)
    if (numbers.length <= 10) {
      if (numbers.length > 6) {
        return `(${numbers.slice(0, 2)}) ${numbers.slice(2, 6)}-${numbers.slice(6)}`;
      }
      return `(${numbers.slice(0, 2)}) ${numbers.slice(2)}`;
    }

    // Format mobile: (XX) XXXXX-XXXX
    return `(${numbers.slice(0, 2)}) ${numbers.slice(2, 7)}-${numbers.slice(7, 11)}`;
  };

  const handlePhoneChange = (value: string) => {
    // Only allow numbers to be typed
    const numbers = value.replace(/\D/g, '');
    if (numbers.length > 11) return;

    const formatted = formatPhone(numbers);
    handleInputChange('phone', formatted);
  };

  const validateForm = () => {
    if (!formData.name.trim()) {
      setError('Por favor, insira seu nome');
      return false;
    }
    if (!formData.email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      setError('Por favor, insira um email valido');
      return false;
    }
    if (!formData.password.trim() || formData.password.length < 6) {
      setError('A senha deve ter pelo menos 6 caracteres');
      return false;
    }
    if (!formData.occupation.trim()) {
      setError('Por favor, insira sua ocupacao');
      return false;
    }
    // Allow 10 (landline) or 11 (mobile) digits
    if (!formData.phone.trim() || formData.phone.replace(/\D/g, '').length < 10) {
      setError('Por favor, insira um telefone valido com DDD (Fixo ou Celular)');
      return false;
    }
    return true;
  };

  const handleSubmitForm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    setIsLoading(true);
    setError('');

    try {
      // Salvar usuario no Supabase
      const userData = {
        nome: formData.name,
        email: formData.email,
        senha: formData.password,
        plano: 'free',
        telefone: formData.phone,
        ocupacao: formData.occupation
      };

      const { data, error: dbError } = await userService.createUser(userData);

      if (dbError) {
        console.error('Erro ao salvar usuario:', dbError);
        setError(dbError.message || 'Erro ao criar conta. Tente novamente.');
        setIsLoading(false);
        return;
      }

      console.log('Usuario criado com sucesso no Supabase:', data);

      // Salvar no localStorage tambem
      localStorage.setItem('arcco_user_phone', formData.phone);
      localStorage.setItem('arcco_user_occupation', formData.occupation);
      localStorage.setItem('arcco_user_plan', 'free');

      setIsLoading(false);
      setStep('success');
    } catch (err) {
      console.error('Erro:', err);
      setError('Erro ao criar conta. Verifique sua conexão e tente novamente.');
      setIsLoading(false);
    }
  };

  const handleFinish = () => {
    onRegister(formData.name, formData.email);
  };

  const renderForm = () => (
    <form onSubmit={handleSubmitForm} className="space-y-5">
      {/* Nome */}
      <div>
        <label htmlFor="name" className="block text-sm font-medium text-neutral-300 mb-2">
          Nome completo
        </label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <User size={18} className="text-neutral-500" />
          </div>
          <input
            id="name"
            type="text"
            value={formData.name}
            onChange={(e) => handleInputChange('name', e.target.value)}
            className="w-full bg-[#141414] border border-[#262626] rounded-xl pl-10 pr-4 py-3 text-white placeholder-neutral-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
            placeholder="Seu nome completo"
            disabled={isLoading}
          />
        </div>
      </div>

      {/* Email */}
      <div>
        <label htmlFor="email" className="block text-sm font-medium text-neutral-300 mb-2">
          E-mail
        </label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Mail size={18} className="text-neutral-500" />
          </div>
          <input
            id="email"
            type="email"
            value={formData.email}
            onChange={(e) => handleInputChange('email', e.target.value)}
            className="w-full bg-[#141414] border border-[#262626] rounded-xl pl-10 pr-4 py-3 text-white placeholder-neutral-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
            placeholder="seu@email.com"
            disabled={isLoading}
          />
        </div>
      </div>

      {/* Senha */}
      <div>
        <label htmlFor="password" className="block text-sm font-medium text-neutral-300 mb-2">
          Senha
        </label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Lock size={18} className="text-neutral-500" />
          </div>
          <input
            id="password"
            type={showPassword ? 'text' : 'password'}
            value={formData.password}
            onChange={(e) => handleInputChange('password', e.target.value)}
            className="w-full bg-[#141414] border border-[#262626] rounded-xl pl-10 pr-12 py-3 text-white placeholder-neutral-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
            placeholder="Minimo 6 caracteres"
            disabled={isLoading}
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute inset-y-0 right-0 pr-3 flex items-center text-neutral-500 hover:text-white transition-colors"
          >
            {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        </div>
      </div>

      {/* Ocupacao */}
      <div>
        <label htmlFor="occupation" className="block text-sm font-medium text-neutral-300 mb-2">
          Ocupacao
        </label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Briefcase size={18} className="text-neutral-500" />
          </div>
          <input
            id="occupation"
            type="text"
            value={formData.occupation}
            onChange={(e) => handleInputChange('occupation', e.target.value)}
            className="w-full bg-[#141414] border border-[#262626] rounded-xl pl-10 pr-4 py-3 text-white placeholder-neutral-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
            placeholder="Ex: Empresario, Medico, Advogado..."
            disabled={isLoading}
          />
        </div>
      </div>

      {/* Telefone WhatsApp */}
      <div>
        <label htmlFor="phone" className="block text-sm font-medium text-neutral-300 mb-2">
          Telefone com WhatsApp
        </label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Phone size={18} className="text-neutral-500" />
          </div>
          <input
            id="phone"
            type="tel"
            value={formData.phone}
            onChange={(e) => handlePhoneChange(e.target.value)}
            className="w-full bg-[#141414] border border-[#262626] rounded-xl pl-10 pr-4 py-3 text-white placeholder-neutral-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
            placeholder="(11) 99999-9999"
            disabled={isLoading}
          />
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-950/30 border border-red-900/50 rounded-xl p-3 flex items-start gap-2">
          <AlertCircle size={18} className="text-red-400 shrink-0 mt-0.5" />
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={isLoading}
        className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-900 disabled:cursor-not-allowed text-white font-semibold py-3 px-4 rounded-xl transition-all shadow-lg shadow-indigo-900/50 flex items-center justify-center gap-2"
      >
        {isLoading ? (
          <>
            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
            Criando conta...
          </>
        ) : (
          'Criar conta'
        )}
      </button>
    </form>
  );

  const renderSuccess = () => (
    <div className="text-center space-y-6">
      <div className="w-20 h-20 rounded-full bg-green-600/10 border border-green-500/20 flex items-center justify-center mx-auto">
        <CheckCircle2 size={40} className="text-green-400" />
      </div>
      <div>
        <h3 className="text-xl font-bold text-white mb-2">Cadastro concluido!</h3>
        <p className="text-neutral-400">
          Bem-vindo ao Arcco, <span className="text-white font-medium">{formData.name.split(' ')[0]}</span>!
          <br />
          Sua conta foi criada com sucesso.
        </p>
      </div>
      <button
        onClick={handleFinish}
        className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 px-4 rounded-xl transition-all shadow-lg shadow-indigo-900/50"
      >
        Acessar Plataforma
      </button>
    </div>
  );

  return (
    <div className="min-h-screen flex items-center justify-center p-4 max-sm:p-3 relative overflow-hidden" style={{ backgroundColor: 'var(--bg-base)' }}>
      <DottedSurface />
      <div className="pointer-events-none absolute inset-0 z-0 bg-[radial-gradient(circle_at_top,rgba(99,102,241,0.14),transparent_34%),radial-gradient(circle_at_bottom_right,rgba(139,92,246,0.10),transparent_32%)]" />

      {/* Grid */}
      <div
        className="absolute inset-0 z-0 opacity-[0.015]"
        style={{
          backgroundImage: `
            linear-gradient(to right, #fff 1px, transparent 1px),
            linear-gradient(to bottom, #fff 1px, transparent 1px)
          `,
          backgroundSize: '60px 60px'
        }}
      />

      {/* Card */}
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
          {/* Back Button */}
          {step === 'form' && (
            <button
              onClick={onBackToLogin}
              className="flex items-center gap-2 text-sm max-sm:text-xs text-neutral-500 hover:text-white mb-6 max-sm:mb-4 transition-colors"
            >
              <ArrowLeft size={16} />
              Voltar ao login
            </button>
          )}

          {/* Title */}
          {step === 'form' && (
            <div className="mb-6 max-sm:mb-4">
              <h2 className="text-2xl max-sm:text-xl font-bold text-white mb-1">Criar conta</h2>
              <p className="text-neutral-400 text-sm max-sm:text-xs">
                Preencha seus dados para comecar
              </p>
            </div>
          )}

          {/* Content */}
          {step === 'form' && renderForm()}
          {step === 'success' && renderSuccess()}
        </div>

        {/* Footer */}
        <div className="mt-8 max-sm:mt-5 text-center">
          <p className="text-xs max-sm:text-[11px] text-neutral-600 leading-relaxed max-w-sm mx-auto">
            Ao criar sua conta, voce concorda com nossos Termos de Uso e Politica de Privacidade.
          </p>
        </div>
      </div>
    </div>
  );
};
