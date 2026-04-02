import React, { useState } from 'react';
import { Lock, Mail, AlertCircle, Eye, EyeOff } from 'lucide-react';
import { userService } from '../lib/supabase';
import { DottedSurface } from '../components/ui/dotted-surface';

interface LoginPageProps {
  onLogin: (userName: string, userEmail: string) => void;
  onGoToRegister: () => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onLogin, onGoToRegister }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError('Por favor, insira um email valido');
      return;
    }

    if (!password.trim()) {
      setError('Por favor, insira sua senha');
      return;
    }

    setIsLoading(true);

    try {
      // Buscar usuario no Supabase
      const { data: user, error: fetchError } = await userService.getUserByEmail(email);

      if (fetchError) {
        setError('Erro ao conectar. Tente novamente.');
        setIsLoading(false);
        return;
      }

      if (!user) {
        setError('Email não encontrado');
        setIsLoading(false);
        return;
      }

      // Verificar senha
      if (user.senha !== password) {
        setError('Senha incorreta');
        setIsLoading(false);
        return;
      }

      // Login bem-sucedido
      localStorage.setItem('arcco_user_plan', user.plano || 'free');
      localStorage.setItem('arcco_user_id', user.id?.toString() || '');

      setIsLoading(false);
      onLogin(user.nome, user.email);
    } catch (err) {
      console.error('Erro no login:', err);
      setError('Erro ao fazer login. Tente novamente.');
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden" style={{ backgroundColor: 'var(--bg-base)' }}>
      <DottedSurface />
      <div className="pointer-events-none absolute inset-0 z-0 bg-[radial-gradient(circle_at_top,rgba(99,102,241,0.14),transparent_34%),radial-gradient(circle_at_bottom_right,rgba(139,92,246,0.10),transparent_32%)]" />

      {/* Login Card */}
      <div className="relative z-10 w-full max-w-md">
        {/* Logo/Brand */}
        <div className="text-center mb-8 animate-fade-in">
          <div className="inline-flex items-center justify-center">
            <img
              src="https://qscezcbpwvnkqoevulbw.supabase.co/storage/v1/object/public/Chipro%20calculadora/arcco%20(1).png"
              alt="Arcco"
              className="h-[120px] w-auto object-contain drop-shadow-[0_0_40px_rgba(99,102,241,0.3)]"
            />
          </div>
        </div>

        {/* Login Form */}
        <div className="bg-[#0F0F0F]/90 border border-[#262626] rounded-2xl p-8 shadow-2xl shadow-black/40 backdrop-blur-xl animate-fade-in">
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-white mb-1">Entrar</h2>
            <p className="text-neutral-400 text-sm">
              Acesse sua conta para continuar
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
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
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-[#141414] border border-[#262626] rounded-xl pl-10 pr-4 py-3 text-white placeholder-neutral-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                  placeholder="seu@email.com"
                  disabled={isLoading}
                  autoComplete="email"
                />
              </div>
            </div>

            {/* Password */}
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
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-[#141414] border border-[#262626] rounded-xl pl-10 pr-12 py-3 text-white placeholder-neutral-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                  placeholder="Digite sua senha"
                  disabled={isLoading}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-neutral-500 hover:text-white transition-colors"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
              <div className="flex justify-end mt-1.5">
                <button
                  type="button"
                  className="text-xs text-neutral-500 hover:text-indigo-400 transition-colors"
                >
                  Esqueceu sua senha?
                </button>
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <div className="bg-red-950/30 border border-red-900/50 rounded-xl p-3 flex items-start gap-2 animate-fade-in">
                <AlertCircle size={18} className="text-red-400 shrink-0 mt-0.5" />
                <p className="text-sm text-red-400">{error}</p>
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-900 disabled:cursor-not-allowed text-white font-semibold py-3 px-4 rounded-xl transition-all transform hover:scale-[1.02] active:scale-[0.98] shadow-lg shadow-indigo-900/50 disabled:shadow-none flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                  Entrando...
                </>
              ) : (
                'Entrar'
              )}
            </button>
          </form>

          {/* Register Link */}
          <div className="mt-6 pt-6 border-t border-[#262626] text-center">
            <p className="text-neutral-400 text-sm">
              Ainda não tem cadastro?{' '}
              <button
                onClick={onGoToRegister}
                className="text-indigo-400 hover:text-indigo-300 font-medium transition-colors"
              >
                Faça seu cadastro agora
              </button>
            </p>
          </div>
        </div>

        {/* Footer Disclaimer */}
        <div className="mt-8 text-center">
          <p className="text-xs text-neutral-700 mt-2">
            © {new Date().getFullYear()} Arcco Agents. Todos os direitos reservados.
          </p>
        </div>
      </div>
    </div>
  );
};
