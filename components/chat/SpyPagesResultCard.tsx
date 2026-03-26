import React, { useState } from 'react';
import { Eye, Globe, Users, BarChart3, TrendingUp, FileText, ChevronDown } from 'lucide-react';

export interface SpyPagesSite {
  domain: string;
  global_rank: number;
  monthly_visits: number;
  bounce_rate: number;
  pages_per_visit: number;
  avg_visit_duration: string;
  top_countries: Array<{ code: string; name: string; share: number }>;
  top_pages: Array<{ url: string; share: number }>;
  competitors: string[];
  keywords: Array<{ keyword: string; share: number }>;
  raw_available: boolean;
  error?: string;
  // Novos campos
  icon_url?: string;
  preview_desktop?: string;
  company_name?: string;
  description?: string;
  traffic_sources?: Array<{ source: string; percentage: number | null; rank: number | null }>;
  organic_traffic?: number | null;
  paid_traffic?: number | null;
  social_networks?: Array<{ name: string; share: number; icon: string }>;
  male_distribution?: number | null;
  female_distribution?: number | null;
  age_distribution?: Array<{ min_age: number; max_age: number | null; value: number }>;
}

interface SpyPagesResultCardProps {
  data: SpyPagesSite[];
  onGenerateReport?: (prompt: string) => void;
}

type Tab = 'overview' | 'audience' | 'competitors';

const formatVisits = (n: number): string => {
  if (!n) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
};

const formatBounce = (n: number): string => {
  if (!n) return '—';
  return `${(n * 100).toFixed(1)}%`;
};

const FLAG_MAP: Record<string, string> = {
  BR: '🇧🇷', US: '🇺🇸', PT: '🇵🇹', AR: '🇦🇷', MX: '🇲🇽', CO: '🇨🇴',
  FR: '🇫🇷', DE: '🇩🇪', GB: '🇬🇧', ES: '🇪🇸', IT: '🇮🇹', JP: '🇯🇵',
  IN: '🇮🇳', CN: '🇨🇳', CA: '🇨🇦', AU: '🇦🇺', RU: '🇷🇺', KR: '🇰🇷',
};

const getFlag = (code: string) => FLAG_MAP[code?.toUpperCase()] ?? '🌍';

const SpyPagesResultCard: React.FC<SpyPagesResultCardProps> = ({ data, onGenerateReport }) => {
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [selectedSite, setSelectedSite] = useState(0);
  const [showSiteDropdown, setShowSiteDropdown] = useState(false);

  const site = data[selectedSite];
  if (!site) return null;

  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: 'overview', label: 'Visão Geral', icon: <BarChart3 size={12} /> },
    { id: 'audience', label: 'Audiência', icon: <Users size={12} /> },
    { id: 'competitors', label: 'Concorrentes', icon: <TrendingUp size={12} /> },
  ];

  return (
    <div className="w-full max-w-[90%] md:max-w-[85%] bg-[#0f0f0f] border border-[#262626] rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#1e1e1e]">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-violet-500/15 flex items-center justify-center">
            <Eye size={12} className="text-violet-400" />
          </div>
          <span className="text-xs font-medium text-neutral-300">Spy Pages</span>
          {data.length > 1 && (
            <span className="text-[10px] text-neutral-600">{data.length} sites analisados</span>
          )}
        </div>

        {/* Site selector */}
        {data.length > 1 && (
          <div className="relative">
            <button
              onClick={() => setShowSiteDropdown(p => !p)}
              className="flex items-center gap-1.5 text-xs text-neutral-400 hover:text-neutral-200 transition-colors px-2 py-1 rounded-md hover:bg-white/[0.05] border border-[#262626]"
            >
              <Globe size={10} />
              <span className="max-w-[120px] truncate">{site.domain || `Site ${selectedSite + 1}`}</span>
              <ChevronDown size={10} className={`transition-transform ${showSiteDropdown ? 'rotate-180' : ''}`} />
            </button>
            {showSiteDropdown && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowSiteDropdown(false)} />
                <div className="absolute right-0 top-full mt-1 w-48 bg-[#1a1a1d] border border-[#333] rounded-lg shadow-xl z-50 overflow-hidden">
                  {data.map((s, i) => (
                    <button
                      key={i}
                      onClick={() => { setSelectedSite(i); setShowSiteDropdown(false); }}
                      className={`w-full text-left px-3 py-2 text-xs transition-colors ${
                        i === selectedSite
                          ? 'text-violet-400 bg-violet-500/10'
                          : 'text-neutral-400 hover:text-neutral-200 hover:bg-white/[0.05]'
                      }`}
                    >
                      {s.domain || `Site ${i + 1}`}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* Error state */}
      {site.error && (
        <div className="px-4 py-6 text-center">
          <p className="text-sm text-neutral-500">{site.domain}</p>
          <p className="text-xs text-red-400 mt-1">{site.error}</p>
        </div>
      )}

      {!site.error && (
        <>
          {/* Domain */}
          <div className="px-4 pt-4 pb-2">
            <h3 className="text-base font-semibold text-neutral-100">{site.domain || '—'}</h3>
            {site.global_rank > 0 && (
              <p className="text-[11px] text-neutral-600 mt-0.5">Rank global #{site.global_rank.toLocaleString()}</p>
            )}
          </div>

          {/* Tabs */}
          <div className="flex items-center gap-1 px-4 py-2 border-b border-[#1e1e1e]">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] transition-colors ${
                  activeTab === tab.id
                    ? 'text-violet-400 bg-violet-500/10'
                    : 'text-neutral-500 hover:text-neutral-300 hover:bg-white/[0.05]'
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="px-4 py-4">

            {activeTab === 'overview' && (
              <div>
                <div className="grid grid-cols-3 gap-3 mb-4">
                  <div className="bg-[#1a1a1a] rounded-lg p-3">
                    <p className="text-[10px] text-neutral-600 mb-1">Visitas/mês</p>
                    <p className="text-lg font-semibold text-neutral-100">{formatVisits(site.monthly_visits)}</p>
                  </div>
                  <div className="bg-[#1a1a1a] rounded-lg p-3">
                    <p className="text-[10px] text-neutral-600 mb-1">Bounce rate</p>
                    <p className="text-lg font-semibold text-neutral-100">{formatBounce(site.bounce_rate)}</p>
                  </div>
                  <div className="bg-[#1a1a1a] rounded-lg p-3">
                    <p className="text-[10px] text-neutral-600 mb-1">Pág/visita</p>
                    <p className="text-lg font-semibold text-neutral-100">
                      {site.pages_per_visit ? site.pages_per_visit.toFixed(1) : '—'}
                    </p>
                  </div>
                </div>

                {site.avg_visit_duration && (
                  <div className="flex items-center gap-2 text-xs text-neutral-500">
                    <span>Duração média:</span>
                    <span className="text-neutral-300">{site.avg_visit_duration}</span>
                  </div>
                )}

                {site.keywords.length > 0 && (
                  <div className="mt-4">
                    <p className="text-[10px] text-neutral-600 mb-2 uppercase tracking-wide">Palavras-chave top</p>
                    <div className="flex flex-wrap gap-1.5">
                      {site.keywords.slice(0, 6).map((kw, i) => (
                        <span key={i} className="px-2 py-0.5 bg-[#1e1e1e] rounded-md text-[11px] text-neutral-400">
                          {kw.keyword}
                          {kw.share > 0 && (
                            <span className="text-neutral-600 ml-1">{(kw.share * 100).toFixed(1)}%</span>
                          )}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'audience' && (
              <div>
                {site.top_countries.length > 0 ? (
                  <div className="mb-4">
                    <p className="text-[10px] text-neutral-600 mb-3 uppercase tracking-wide">Top países</p>
                    <div className="space-y-2">
                      {site.top_countries.map((c, i) => (
                        <div key={i} className="flex items-center gap-2">
                          <span className="text-base leading-none">{getFlag(c.code)}</span>
                          <span className="text-xs text-neutral-300 flex-1">{c.name || c.code}</span>
                          <div className="flex items-center gap-2 flex-shrink-0">
                            <div className="h-1 bg-[#1e1e1e] rounded-full w-20 overflow-hidden">
                              <div
                                className="h-full bg-violet-500/60 rounded-full"
                                style={{ width: `${Math.min((c.share || 0) * 100, 100)}%` }}
                              />
                            </div>
                            <span className="text-[11px] text-neutral-500 w-10 text-right">
                              {c.share ? `${(c.share * 100).toFixed(1)}%` : '—'}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-neutral-600">Dados de países não disponíveis.</p>
                )}

                {site.top_pages.length > 0 && (
                  <div>
                    <p className="text-[10px] text-neutral-600 mb-2 uppercase tracking-wide">Páginas mais visitadas</p>
                    <div className="space-y-1">
                      {site.top_pages.map((p, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs">
                          <span className="text-neutral-600 w-4 text-right flex-shrink-0">{i + 1}</span>
                          <span className="text-neutral-400 truncate flex-1">{p.url || '/'}</span>
                          {p.share > 0 && (
                            <span className="text-neutral-600 flex-shrink-0">{(p.share * 100).toFixed(1)}%</span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'competitors' && (
              <div>
                {site.competitors.length > 0 ? (
                  <>
                    <p className="text-[10px] text-neutral-600 mb-3 uppercase tracking-wide">Sites concorrentes</p>
                    <div className="space-y-2">
                      {site.competitors.map((comp, i) => (
                        <div key={i} className="flex items-center gap-2 py-1.5 border-b border-[#1a1a1a] last:border-0">
                          <div className="w-5 h-5 rounded bg-[#1e1e1e] flex items-center justify-center flex-shrink-0">
                            <Globe size={10} className="text-neutral-600" />
                          </div>
                          <span className="text-sm text-neutral-300 truncate">{comp}</span>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <p className="text-xs text-neutral-600">Dados de concorrentes não disponíveis.</p>
                )}
              </div>
            )}
          </div>

          {/* Footer */}
          {onGenerateReport && (
            <div className="px-4 pb-4">
              <button
                onClick={() => onGenerateReport(
                  `Gere um relatório completo de análise competitiva para ${data.map(s => s.domain).join(', ')} com base nos dados do SimilarWeb obtidos.`
                )}
                className="w-full flex items-center justify-center gap-2 py-2 rounded-lg border border-[#2a2a2a] text-xs text-neutral-400 hover:text-neutral-200 hover:border-[#3a3a3a] hover:bg-white/[0.03] transition-all"
              >
                <FileText size={12} />
                Gerar relatório completo
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default SpyPagesResultCard;
