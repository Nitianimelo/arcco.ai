import React from 'react';
import { Calendar, Check, Database, Loader2, Mail, Trash2 } from 'lucide-react';

interface UserRow {
  id: string;
  nome: string;
  email: string;
  senha?: string;
  plano: string;
  cpf?: string;
  content?: { telefone?: string; ocupacao?: string };
  created_at?: string;
  updated_at?: string;
}

interface AdminUsersTabProps {
  users: UserRow[];
  plans: string[];
  planColors: Record<string, string>;
  savingPlan: string | null;
  savedPlan: string | null;
  deletingUserId: string | null;
  onUpdatePlan: (userId: string, newPlan: string) => void;
  onDeleteUser: (user: UserRow) => void;
  formatDateTime: (dateStr?: string) => string;
}

export const AdminUsersTab: React.FC<AdminUsersTabProps> = ({
  users,
  plans,
  planColors,
  savingPlan,
  savedPlan,
  deletingUserId,
  onUpdatePlan,
  onDeleteUser,
  formatDateTime,
}) => {
  return (
    <div className="bg-[#0f0f0f] border border-neutral-900 rounded-xl overflow-hidden">
      <div className="px-5 py-4 border-b border-neutral-900 flex items-center gap-2">
        <Database size={15} className="text-neutral-500" />
        <span className="text-sm font-medium text-neutral-300">Tabela: User</span>
        <span className="ml-auto text-xs text-neutral-600">{users.length} registros</span>
      </div>
      {users.length === 0 ? (
        <div className="py-16 text-center text-neutral-600 text-sm">Nenhum usuário encontrado</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-900">
                <th className="text-left px-5 py-3 text-xs font-medium text-neutral-600 uppercase tracking-wider">Usuário</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-neutral-600 uppercase tracking-wider">Contato</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-neutral-600 uppercase tracking-wider">Plano</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-neutral-600 uppercase tracking-wider">Acesso</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-neutral-600 uppercase tracking-wider">Datas</th>
                <th className="text-left px-5 py-3 text-xs font-medium text-neutral-600 uppercase tracking-wider">Content</th>
                <th className="text-right px-5 py-3 text-xs font-medium text-neutral-600 uppercase tracking-wider">Ações</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user, idx) => (
                <tr
                  key={user.id}
                  className={`border-b border-neutral-900/50 hover:bg-white/[0.02] transition-colors ${idx % 2 === 0 ? '' : 'bg-white/[0.01]'}`}
                >
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-xs font-bold text-white shrink-0">
                        {user.nome?.charAt(0)?.toUpperCase() || '?'}
                      </div>
                      <div className="min-w-0">
                        <p className="text-white font-medium">{user.nome || '—'}</p>
                        <p className="text-[11px] text-neutral-600 font-mono truncate">{user.id}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-1.5 text-neutral-400">
                        <Mail size={12} className="text-neutral-600" />
                        <span>{user.email || '—'}</span>
                      </div>
                      <div className="text-xs text-neutral-500">CPF: {user.cpf || '—'}</div>
                      <div className="text-xs text-neutral-500">Telefone: {user.content?.telefone || '—'}</div>
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <select
                        value={user.plano}
                        disabled={savingPlan === user.id}
                        onChange={(e) => onUpdatePlan(user.id, e.target.value)}
                        className={`text-xs font-medium rounded-lg px-2.5 py-1.5 border outline-none cursor-pointer transition-all
                          ${planColors[user.plano] || 'bg-neutral-800 text-neutral-400'}
                          border-white/10 hover:border-white/20 disabled:opacity-60 disabled:cursor-not-allowed`}
                      >
                        {plans.map((plan) => (
                          <option key={plan} value={plan} className="bg-[#1a1a1a] text-white capitalize">
                            {plan.charAt(0).toUpperCase() + plan.slice(1)}
                          </option>
                        ))}
                      </select>
                      {savingPlan === user.id && <Loader2 size={13} className="animate-spin text-neutral-500" />}
                      {savedPlan === user.id && <Check size={13} className="text-green-400" />}
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    <div className="space-y-1.5 text-xs">
                      <div className="text-neutral-500">Senha: <span className="font-mono text-neutral-400">{user.senha || '—'}</span></div>
                      <div className="text-neutral-500">Ocupação: {user.content?.ocupacao || '—'}</div>
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    <div className="space-y-1.5 text-xs">
                      <div className="flex items-center gap-1.5 text-neutral-600">
                        <Calendar size={11} />
                        <span>Cadastro: {formatDateTime(user.created_at)}</span>
                      </div>
                      <div className="text-neutral-600">Atualizado: {formatDateTime(user.updated_at)}</div>
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    <pre className="max-w-[280px] overflow-x-auto rounded-lg border border-white/5 bg-black/20 p-2 text-[11px] leading-5 text-neutral-500">
                      {user.content ? JSON.stringify(user.content, null, 2) : '—'}
                    </pre>
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex justify-end">
                      <button
                        onClick={() => onDeleteUser(user)}
                        disabled={deletingUserId === user.id}
                        className="inline-flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs font-medium text-red-300 transition-colors hover:bg-red-500/15 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {deletingUserId === user.id ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
                        Excluir
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
