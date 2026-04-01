import { createClient } from '@supabase/supabase-js';

const DEFAULT_SUPABASE_URL = 'https://gfkycxdbbzczrwikhcpr.supabase.co';
const DEFAULT_SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imdma3ljeGRiYnpjenJ3aWtoY3ByIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk3ODI1OTMsImV4cCI6MjA4NTM1ODU5M30.DbXQr0nL8cfsRskYy-j4mHsgblgd1Zo5Ka5ccFmSYV8';

const supabaseUrl =
  (import.meta.env.VITE_SUPABASE_URL as string | undefined) ||
  DEFAULT_SUPABASE_URL;

// No frontend, sempre use a anon key. Service role não deve ir para produção no browser.
const supabaseKey =
  (import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined) ||
  DEFAULT_SUPABASE_ANON_KEY;

export const supabase = createClient(supabaseUrl, supabaseKey);

// Types for the User table
export interface UserData {
  nome: string;
  email: string;
  plano: string;
  cpf?: string;
  content?: {
    telefone?: string;
    ocupacao?: string;
  };
}

export interface UserRecord {
  id?: string;
  nome: string;
  email: string;
  senha?: string;
  plano: string;
  cpf?: string;
  content?: {
    telefone?: string;
    ocupacao?: string;
  };
  created_at?: string;
}

// Input type for creating user
export interface CreateUserInput {
  nome: string;
  email: string;
  senha: string;
  plano: string;
  cpf?: string;
  telefone?: string;
  ocupacao?: string;
}

// User service functions
export const userService = {
  // Create a new user
  async createUser(userData: CreateUserInput): Promise<{ data: UserRecord | null; error: Error | null }> {
    try {
      console.log('Salvando usuario no Supabase:', userData);

      // Separar dados: colunas diretas vs content (jsonb)
      const insertData = {
        nome: userData.nome,
        email: userData.email,
        senha: userData.senha,
        plano: userData.plano,
        cpf: userData.cpf || null,
        content: {
          telefone: userData.telefone,
          ocupacao: userData.ocupacao
        }
      };

      console.log('Dados para inserir:', insertData);

      const { data, error } = await supabase
        .from('User')
        .insert([insertData])
        .select()
        .single();

      if (error) {
        console.error('Erro ao criar usuario:', error);
        return { data: null, error: new Error(error.message) };
      }

      console.log('Usuario criado com sucesso:', data);
      return { data, error: null };
    } catch (err) {
      console.error('Erro ao criar usuario:', err);
      return { data: null, error: err as Error };
    }
  },

  // Get user by email
  async getUserByEmail(email: string): Promise<{ data: UserRecord | null; error: Error | null }> {
    try {
      const { data, error } = await supabase
        .from('User')
        .select('*')
        .eq('email', email)
        .single();

      if (error && error.code !== 'PGRST116') {
        console.error('Erro ao buscar usuario:', error);
        return { data: null, error: new Error(error.message) };
      }

      return { data, error: null };
    } catch (err) {
      console.error('Erro ao buscar usuario:', err);
      return { data: null, error: err as Error };
    }
  },

  // Check if email exists
  async emailExists(email: string): Promise<boolean> {
    const { data } = await this.getUserByEmail(email);
    return data !== null;
  },

  // Update user
  async updateUser(id: string, userData: Partial<CreateUserInput>): Promise<{ data: UserRecord | null; error: Error | null }> {
    try {
      // Buscar usuario atual
      const { data: currentUser, error: fetchError } = await supabase
        .from('User')
        .select('*')
        .eq('id', id)
        .single();

      if (fetchError) {
        return { data: null, error: new Error(fetchError.message) };
      }

      // Preparar dados para atualizar
      const updateData: Record<string, unknown> = {};

      if (userData.nome) updateData.nome = userData.nome;
      if (userData.email) updateData.email = userData.email;
      if (userData.plano) updateData.plano = userData.plano;
      if (userData.cpf) updateData.cpf = userData.cpf;

      // Atualizar content (jsonb) com telefone e ocupacao
      if (userData.telefone || userData.ocupacao) {
        updateData.content = {
          ...currentUser.content,
          telefone: userData.telefone || currentUser.content?.telefone,
          ocupacao: userData.ocupacao || currentUser.content?.ocupacao
        };
      }

      const { data, error } = await supabase
        .from('User')
        .update(updateData)
        .eq('id', id)
        .select()
        .single();

      if (error) {
        console.error('Erro ao atualizar usuario:', error);
        return { data: null, error: new Error(error.message) };
      }

      return { data, error: null };
    } catch (err) {
      console.error('Erro ao atualizar usuario:', err);
      return { data: null, error: err as Error };
    }
  }
};
