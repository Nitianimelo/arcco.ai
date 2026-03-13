// OpenRouter API Integration Service

const OPENROUTER_API_URL = 'https://openrouter.ai/api/v1';

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface ChatCompletionRequest {
  model: string;
  messages: ChatMessage[];
  temperature?: number;
  max_tokens?: number;
  stream?: boolean;
}

export interface ChatCompletionResponse {
  id: string;
  choices: {
    index: number;
    message: {
      role: string;
      content: string;
    };
    finish_reason: string;
  }[];
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    cost?: number;
  };
}

export interface OpenRouterModel {
  id: string;
  name: string;
  description?: string;
  context_length: number;
  pricing: {
    prompt: string;
    completion: string;
  };
  top_provider?: {
    max_completion_tokens?: number;
  };
  architecture?: {
    modality: string;
    tokenizer: string;
    instruct_type?: string;
  };
}

class OpenRouterService {
  private apiKey: string | null = null;
  private modelsCache: OpenRouterModel[] = [];
  private modelsCacheTime: number = 0;
  private readonly CACHE_DURATION = 5 * 60 * 1000; // 5 minutes
  private readonly STORAGE_KEY = 'arcco-openrouter-key';

  constructor() {
    // Restore API key from localStorage if available (survives HMR)
    try {
      const savedKey = localStorage.getItem(this.STORAGE_KEY);
      if (savedKey) {
        this.apiKey = savedKey;
        console.log('[OpenRouterService] API Key restored from localStorage');
      }
    } catch (e) {
      console.warn('[OpenRouterService] Could not restore key from localStorage:', e);
    }
  }

  setApiKey(key: string) {
    if (this.apiKey === key) return; // Prevent redundant updates and console logs

    this.apiKey = key;
    // Also save to localStorage for persistence across HMR
    try {
      localStorage.setItem(this.STORAGE_KEY, key);
    } catch (e) {
      console.warn('[OpenRouterService] Could not save key to localStorage:', e);
    }
    console.log('[OpenRouterService] API Key set:', key ? key.substring(0, 12) + '...' : 'undefined');
  }

  getApiKey(): string | null {
    return this.apiKey;
  }

  hasApiKey(): boolean {
    return !!this.apiKey;
  }

  private getHeaders(): Record<string, string> {
    if (!this.apiKey) {
      throw new Error('API Key não configurada');
    }

    return {
      'Authorization': `Bearer ${this.apiKey}`,
      'HTTP-Referer': 'https://arcco.ai', // Use a valid public domain to avoid "localhost" policy issues
      'X-Title': 'Arcco.ai',
      'Content-Type': 'application/json'
    };
  }

  async testConnection(): Promise<{ success: boolean; error?: string }> {
    if (!this.apiKey) {
      return { success: false, error: 'API Key não configurada' };
    }

    try {
      const response = await fetch(`${OPENROUTER_API_URL}/models`, {
        method: 'GET',
        headers: this.getHeaders()
      });

      if (!response.ok) {
        const error = await response.json();
        return { success: false, error: error.error?.message || 'Erro ao validar API Key' };
      }

      return { success: true };
    } catch {
      return { success: false, error: 'Erro de conexão com OpenRouter' };
    }
  }

  async getModels(forceRefresh = false): Promise<OpenRouterModel[]> {
    // Return cached models if valid
    if (!forceRefresh && this.modelsCache.length > 0 && Date.now() - this.modelsCacheTime < this.CACHE_DURATION) {
      return this.modelsCache;
    }

    try {
      const response = await fetch(`${OPENROUTER_API_URL}/models`, {
        method: 'GET',
        headers: this.getHeaders()
      });

      if (!response.ok) {
        throw new Error('Erro ao buscar modelos');
      }

      const data = await response.json();
      this.modelsCache = data.data || [];
      this.modelsCacheTime = Date.now();

      // Sort by name for better UX
      this.modelsCache.sort((a, b) => a.name.localeCompare(b.name));

      return this.modelsCache;
    } catch (error) {
      console.error('Erro ao buscar modelos:', error);
      return this.modelsCache; // Return cached data on error
    }
  }

  // Get popular/recommended models for quick selection
  getRecommendedModels(): string[] {
    return [
      'openai/gpt-4o',
      'openai/gpt-4o-mini',
      'anthropic/claude-3.5-sonnet',
      'anthropic/claude-3-haiku',
      'google/gemini-pro-1.5',
      'google/gemini-flash-1.5',
      'meta-llama/llama-3.1-70b-instruct',
      'mistralai/mistral-large'
    ];
  }

  async chat(request: ChatCompletionRequest): Promise<ChatCompletionResponse> {
    if (!this.apiKey) {
      throw new Error('API Key não configurada');
    }

    const response = await fetch(`${OPENROUTER_API_URL}/chat/completions`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({
        model: request.model,
        messages: request.messages,
        temperature: request.temperature ?? 0.7,
        max_tokens: request.max_tokens ?? 8192,
        stream: request.stream ?? false
      })
    });

    if (!response.ok) {
      if (response.status === 401) {
        console.warn('[OpenRouterService] 401 Unauthorized - clearing invalid key from localStorage');
        localStorage.removeItem(this.STORAGE_KEY);
        this.apiKey = null;
        throw new Error('API Key inválida ou expirada. Recarregue a página para buscar uma nova chave.');
      }

      const error = await response.json();
      const errorMessage = error.error?.message || 'Erro na requisição';

      if (errorMessage.includes('data policy')) {
        throw new Error('Erro de Política de Dados: Para usar modelos gratuitos no OpenRouter, você deve habilitar a coleta de dados em https://openrouter.ai/settings/privacy ou usar um modelo pago.');
      }

      throw new Error(errorMessage);
    }

    return response.json();
  }

  // New Streaming Method
  async streamChat(
    request: ChatCompletionRequest,
    onChunk: (chunk: string) => void
  ): Promise<string> {
    console.log('[OpenRouterService.streamChat] Starting stream', {
      hasApiKey: !!this.apiKey,
      apiKeyPrefix: this.apiKey ? this.apiKey.substring(0, 12) + '...' : 'null',
      model: request.model,
      messagesCount: request.messages?.length || 0
    });

    if (!this.apiKey) {
      throw new Error('API Key não configurada');
    }

    const response = await fetch(`${OPENROUTER_API_URL}/chat/completions`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({
        model: request.model,
        messages: request.messages,
        temperature: request.temperature ?? 0.7,
        max_tokens: request.max_tokens ?? 8192,
        stream: true // Force stream
      })
    });

    if (!response.ok) {
      if (response.status === 401) {
        console.warn('[OpenRouterService] 401 Unauthorized - clearing invalid key from localStorage');
        localStorage.removeItem(this.STORAGE_KEY);
        this.apiKey = null;
        throw new Error('API Key inválida ou expirada. Recarregue a página para buscar uma nova chave.');
      }

      const error = await response.json();
      const errorMessage = error.error?.message || 'Erro na requisição';
      if (errorMessage.includes('data policy')) {
        throw new Error('Erro de Política de Dados: Habilite a coleta de dados em https://openrouter.ai/settings/privacy');
      }
      throw new Error(errorMessage);
    }

    if (!response.body) {
      throw new Error('ReadableStream not supported in this browser.');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let fullContent = '';

    try {
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;

        // Split into lines; the LAST element may be incomplete, keep it in buffer
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data: ')) continue;

          const data = trimmed.slice(6);
          if (data === '[DONE]') continue;
          if (!data || data.length < 10) continue;

          try {
            const parsed = JSON.parse(data);
            const content = parsed.choices?.[0]?.delta?.content || '';
            if (content) {
              fullContent += content;
              onChunk(content);
            }
          } catch (e) {
            console.warn('[OpenRouter] Skipping malformed SSE chunk:', (e as Error).message);
          }
        }
      }

      // Process any remaining data left in buffer after stream ends
      if (buffer.trim().startsWith('data: ')) {
        const data = buffer.trim().slice(6);
        if (data && data !== '[DONE]' && data.length >= 10) {
          try {
            const parsed = JSON.parse(data);
            const content = parsed.choices?.[0]?.delta?.content || '';
            if (content) {
              fullContent += content;
              onChunk(content);
            }
          } catch { /* final fragment, safe to ignore */ }
        }
      }
    } catch (error) {
      console.error("Stream reading error", error);
      throw error;
    } finally {
      reader.releaseLock();
    }

    return fullContent;
  }

  async sendMessage(
    model: string,
    systemPrompt: string,
    userMessage: string,
    conversationHistory: ChatMessage[] = [],
    maxTokens: number = 4096
  ): Promise<string> {
    const messages: ChatMessage[] = [
      { role: 'system', content: systemPrompt },
      ...conversationHistory,
      { role: 'user', content: userMessage }
    ];

    const response = await this.chat({
      model,
      messages,
      temperature: 0.7,
      max_tokens: maxTokens
    });

    return response.choices[0]?.message?.content || '';
  }
}

export const openRouterService = new OpenRouterService();
