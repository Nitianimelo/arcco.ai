export interface TavilySearchResult {
    title: string;
    url: string;
    content: string;
    score: number;
}

export interface TavilyResponse {
    results: TavilySearchResult[];
    answer?: string;
    query: string;
}

const TAVILY_API_URL = 'https://api.tavily.com/search';

export class TavilyService {
    private apiKey: string | null = null;

    setApiKey(key: string) {
        this.apiKey = key;
    }

    async search(query: string, searchDepth: 'basic' | 'advanced' = 'basic'): Promise<TavilyResponse> {
        // Check for API key (could be in env or set dynamically)
        const apiKey = this.apiKey || import.meta.env.VITE_TAVILY_API_KEY;

        if (!apiKey) {
            console.warn('Tavily API Key missing. Returning empty results.');
            return { query, results: [] };
        }

        try {
            const response = await fetch(TAVILY_API_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    api_key: apiKey,
                    query,
                    search_depth: searchDepth,
                    include_answer: true,
                    include_images: false,
                    max_results: 5
                })
            });

            if (!response.ok) {
                throw new Error(`Tavily API error: ${response.statusText}`);
            }

            const data = await response.json();
            return data as TavilyResponse;
        } catch (error) {
            console.error('Error searching Tavily:', error);
            return { query, results: [] };
        }
    }
}

export const tavilyService = new TavilyService();
