import React, { useState, useRef, useEffect } from 'react';
import { Eye, X, Plus, Check, Loader2, ArrowRight } from 'lucide-react';
import type { SpyPagesSite } from './SpyPagesResultCard';

interface SpyPagesInputCardProps {
  onSubmit: (urls: string[]) => void;
  onClose: () => void;
  isLoading?: boolean;
  previewData?: SpyPagesSite[] | null;
  onConfirmReady?: () => void;
}

// ─── helpers ────────────────────────────────────────────────────────────────

const fmt = (n: number): string => {
  if (!n) return '—';
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
};

const pct = (n: number | null | undefined): string =>
  n != null ? `${(n * 100).toFixed(1)}%` : '—';

const FLAG: Record<string, string> = {
  BR: '🇧🇷', US: '🇺🇸', PT: '🇵🇹', AR: '🇦🇷', MX: '🇲🇽', GB: '🇬🇧',
  FR: '🇫🇷', DE: '🇩🇪', ES: '🇪🇸', IT: '🇮🇹', JP: '🇯🇵', IN: '🇮🇳',
  CN: '🇨🇳', CA: '🇨🇦', AU: '🇦🇺', RU: '🇷🇺', KR: '🇰🇷', CO: '🇨🇴',
  NG: '🇳🇬', EG: '🇪🇬', TR: '🇹🇷', ID: '🇮🇩', SA: '🇸🇦', PK: '🇵🇰',
};
const flag = (code: string) => FLAG[code?.toUpperCase()] ?? '🌍';

const CHANNEL: Record<string, { label: string; color: string; bg: string }> = {
  direct:   { label: 'Direto',    color: 'bg-blue-500',    bg: 'bg-blue-500/10'    },
  organic:  { label: 'Orgânico',  color: 'bg-emerald-500', bg: 'bg-emerald-500/10' },
  referrals:{ label: 'Referência',color: 'bg-violet-500',  bg: 'bg-violet-500/10'  },
  social:   { label: 'Social',    color: 'bg-orange-400',  bg: 'bg-orange-400/10'  },
  mail:     { label: 'E-mail',    color: 'bg-pink-500',    bg: 'bg-pink-500/10'    },
  paid:     { label: 'Pago',      color: 'bg-yellow-500',  bg: 'bg-yellow-500/10'  },
  ads:      { label: 'Anúncios',  color: 'bg-red-500',     bg: 'bg-red-500/10'     },
};

// ─── SitePreviewCard ─────────────────────────────────────────────────────────

const SitePreviewCard: React.FC<{ site: SpyPagesSite }> = ({ site }) => {
  const [imgError, setImgError] = useState(false);
  const [previewError, setPreviewError] = useState(false);

  const channels = (site.traffic_sources ?? []).filter(
    t => t.percentage != null && t.percentage > 0
  );

  return (
    <div className="bg-[#0e0e0e] rounded-xl overflow-hidden border border-[#1e1e1e]">

      {/* ── Banner preview + favicon overlay ── */}
      {site.preview_desktop && !previewError ? (
        <div className="relative w-full h-28 bg-[#1a1a1a] overflow-hidden">
          <img
            src={site.preview_desktop}
            alt="preview"
            className="w-full h-full object-cover object-top"
            onError={() => setPreviewError(true)}
          />
          {/* Gradiente inferior para legibilidade */}
          <div className="absolute inset-0 bg-gradient-to-t from-[#0e0e0e] via-transparent to-transparent" />
          {/* Favicon sobreposto bottom-left */}
          <div className="absolute bottom-2.5 left-3 flex items-center gap-2">
            <div className="w-9 h-9 rounded-xl bg-[#111]/90 border border-[#333] flex items-center justify-center overflow-hidden shadow-lg backdrop-blur-sm">
              {site.icon_url && !imgError ? (
                <img src={site.icon_url} alt={site.domain} className="w-6 h-6 object-contain"
                  onError={() => setImgError(true)} />
              ) : (
                <Eye size={14} className="text-violet-400" />
              )}
            </div>
            <div className="min-w-0">
              <p className="text-sm font-bold text-white drop-shadow">{site.domain}</p>
              {site.company_name && site.company_name !== site.domain && (
                <p className="text-[10px] text-neutral-400 leading-tight">{site.company_name}</p>
              )}
            </div>
          </div>
          {/* Rank badge top-right */}
          {site.global_rank > 0 && (
            <div className="absolute top-2.5 right-3">
              <span className="text-[10px] font-semibold text-violet-300 bg-[#111]/80 border border-violet-500/30 px-2 py-0.5 rounded-full backdrop-blur-sm">
                #{site.global_rank.toLocaleString()} global
              </span>
            </div>
          )}
        </div>
      ) : (
        /* Fallback sem preview: header normal com favicon */
        <div className="flex items-center gap-3 px-4 py-3">
          <div className="flex-shrink-0 w-9 h-9 rounded-xl bg-[#1a1a1a] border border-[#2a2a2a] flex items-center justify-center overflow-hidden">
            {site.icon_url && !imgError ? (
              <img src={site.icon_url} alt={site.domain} className="w-6 h-6 object-contain"
                onError={() => setImgError(true)} />
            ) : (
              <Eye size={14} className="text-violet-400" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <span className="text-sm font-semibold text-white">{site.domain}</span>
            {site.company_name && site.company_name !== site.domain && (
              <span className="text-[11px] text-neutral-500 ml-2">{site.company_name}</span>
            )}
          </div>
          {site.global_rank > 0 && (
            <span className="text-[10px] font-medium text-violet-400 bg-violet-500/10 border border-violet-500/20 px-2 py-0.5 rounded-full">
              #{site.global_rank.toLocaleString()} global
            </span>
          )}
        </div>
      )}

      {/* Descrição (quando há preview, fica abaixo do banner) */}
      {site.description && site.preview_desktop && !previewError && (
        <p className="text-[11px] text-neutral-500 px-4 pt-2 pb-0 line-clamp-1">{site.description}</p>
      )}

      {/* ── Métricas principais ── */}
      <div className="grid grid-cols-4 gap-px bg-[#1a1a1a] border-t border-[#1a1a1a]">
        {[
          { label: 'Visitas/mês',  value: fmt(site.monthly_visits) },
          { label: 'Bounce',       value: pct(site.bounce_rate) },
          { label: 'Pgs/visita',   value: site.pages_per_visit ? site.pages_per_visit.toFixed(1) : '—' },
          { label: 'Duração',      value: site.avg_visit_duration || '—' },
        ].map(m => (
          <div key={m.label} className="bg-[#0e0e0e] px-2 py-2.5 text-center">
            <p className="text-[10px] text-neutral-600 mb-0.5">{m.label}</p>
            <p className="text-sm font-semibold text-neutral-100">{m.value}</p>
          </div>
        ))}
      </div>

      {/* ── Canais de tráfego ── */}
      {channels.length > 0 && (
        <div className="px-4 py-3 border-t border-[#1a1a1a]">
          <p className="text-[10px] text-neutral-600 uppercase tracking-wider font-medium mb-2.5">Canais de tráfego</p>
          <div className="space-y-1.5">
            {channels.map(ch => {
              const cfg = CHANNEL[ch.source] ?? { label: ch.source, color: 'bg-neutral-500', bg: 'bg-neutral-500/10' };
              const barWidth = `${Math.min((ch.percentage ?? 0) * 100, 100).toFixed(1)}%`;
              return (
                <div key={ch.source} className="flex items-center gap-2">
                  <span className="w-16 text-[11px] text-neutral-500 flex-shrink-0">{cfg.label}</span>
                  <div className="flex-1 h-1.5 rounded-full bg-[#1e1e1e] overflow-hidden">
                    <div
                      className={`h-full rounded-full ${cfg.color} transition-all`}
                      style={{ width: barWidth }}
                    />
                  </div>
                  <span className="text-[11px] text-neutral-400 w-10 text-right flex-shrink-0">
                    {pct(ch.percentage)}
                  </span>
                </div>
              );
            })}
          </div>
          {(site.organic_traffic != null || (site.paid_traffic != null && site.paid_traffic > 0)) && (
            <div className="flex items-center gap-2 mt-2.5 pt-2 border-t border-[#1a1a1a]">
              {site.organic_traffic != null && (
                <span className="text-[10px] text-emerald-400">Orgânico {pct(site.organic_traffic)}</span>
              )}
              {site.organic_traffic != null && site.paid_traffic != null && site.paid_traffic > 0 && (
                <span className="text-[10px] text-neutral-700">·</span>
              )}
              {site.paid_traffic != null && site.paid_traffic > 0 && (
                <span className="text-[10px] text-yellow-400">Pago {pct(site.paid_traffic)}</span>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Países + Audiência ── */}
      <div className="grid grid-cols-2 gap-px bg-[#1a1a1a] border-t border-[#1a1a1a]">

        {/* Países */}
        {site.top_countries.length > 0 && (
          <div className="bg-[#0e0e0e] px-3 py-3">
            <p className="text-[10px] text-neutral-600 uppercase tracking-wider font-medium mb-2">
              Top países
            </p>
            <div className="space-y-1.5">
              {site.top_countries.slice(0, 5).map((c, i) => (
                <div key={i} className="flex items-center gap-1.5">
                  <span className="text-sm leading-none">{flag(c.code)}</span>
                  <div className="flex-1 h-1 rounded-full bg-[#1e1e1e] overflow-hidden">
                    <div
                      className="h-full rounded-full bg-blue-500/60"
                      style={{ width: `${(c.share * 100).toFixed(0)}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-neutral-500 w-8 text-right">{pct(c.share)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Audiência: gênero + idade */}
        <div className="bg-[#0e0e0e] px-3 py-3">
          <p className="text-[10px] text-neutral-600 uppercase tracking-wider font-medium mb-2">
            Audiência
          </p>
          {/* Gênero — dois blocos lado a lado */}
          <div className="grid grid-cols-2 gap-1.5 mb-3">
            <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg px-2.5 py-2 text-center">
              <p className="text-[10px] text-blue-400/70 mb-0.5">♂ Masculino</p>
              <p className="text-sm font-bold text-blue-300">
                {site.male_distribution != null ? pct(site.male_distribution) : '—'}
              </p>
            </div>
            <div className="bg-pink-500/10 border border-pink-500/20 rounded-lg px-2.5 py-2 text-center">
              <p className="text-[10px] text-pink-400/70 mb-0.5">♀ Feminino</p>
              <p className="text-sm font-bold text-pink-300">
                {site.female_distribution != null ? pct(site.female_distribution) : '—'}
              </p>
            </div>
          </div>
          {/* Idade — barras horizontais com % visível */}
          {site.age_distribution && site.age_distribution.length > 0 && (() => {
            const maxVal = Math.max(...site.age_distribution.map(x => x.value));
            return (
              <div className="space-y-1.5">
                {site.age_distribution.map((a, i) => {
                  const label = a.max_age ? `${a.min_age}-${a.max_age}` : `${a.min_age}+`;
                  const barWidth = `${((a.value / maxVal) * 100).toFixed(0)}%`;
                  return (
                    <div key={i} className="flex items-center gap-1.5">
                      <span className="text-[9px] text-neutral-600 w-9 flex-shrink-0 text-right">{label}</span>
                      <div className="flex-1 h-1 rounded-full bg-[#1e1e1e] overflow-hidden">
                        <div
                          className="h-full rounded-full bg-violet-500/60 transition-all"
                          style={{ width: barWidth }}
                        />
                      </div>
                      <span className="text-[9px] text-neutral-500 w-8 text-right flex-shrink-0">
                        {pct(a.value)}
                      </span>
                    </div>
                  );
                })}
              </div>
            );
          })()}
        </div>
      </div>

      {/* ── Keywords + Social ── */}
      <div className="grid grid-cols-2 gap-px bg-[#1a1a1a] border-t border-[#1a1a1a]">

        {/* Keywords */}
        {site.keywords.length > 0 && (
          <div className="bg-[#0e0e0e] px-3 py-3">
            <p className="text-[10px] text-neutral-600 uppercase tracking-wider font-medium mb-2">
              Keywords
            </p>
            <div className="flex flex-wrap gap-1">
              {site.keywords.slice(0, 6).map((k, i) => (
                <span
                  key={i}
                  className="text-[10px] text-neutral-400 bg-[#1a1a1a] border border-[#2a2a2a] px-2 py-0.5 rounded-md"
                >
                  {k.keyword}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Redes sociais */}
        {site.social_networks && site.social_networks.length > 0 && (
          <div className="bg-[#0e0e0e] px-3 py-3">
            <p className="text-[10px] text-neutral-600 uppercase tracking-wider font-medium mb-2">
              Social
            </p>
            <div className="space-y-1.5">
              {site.social_networks.slice(0, 4).map((sn, i) => (
                <div key={i} className="flex items-center gap-1.5">
                  {sn.icon ? (
                    <img src={sn.icon} alt={sn.name} className="w-3.5 h-3.5 rounded-sm flex-shrink-0" onError={e => (e.currentTarget.style.display = 'none')} />
                  ) : (
                    <div className="w-3.5 h-3.5 rounded-sm bg-[#2a2a2a] flex-shrink-0" />
                  )}
                  <span className="text-[10px] text-neutral-500 flex-1 truncate">{sn.name}</span>
                  <span className="text-[10px] text-neutral-400">{pct(sn.share)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// ─── SpyPagesInputCard ───────────────────────────────────────────────────────

const SpyPagesInputCard: React.FC<SpyPagesInputCardProps> = ({
  onSubmit,
  onClose,
  isLoading = false,
  previewData = null,
  onConfirmReady,
}) => {
  const [urls, setUrls] = useState<string[]>(['']);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    if (!isLoading && !previewData) inputRefs.current[0]?.focus();
  }, [isLoading, previewData]);

  const handleChange = (i: number, v: string) =>
    setUrls(prev => prev.map((u, j) => (j === i ? v : u)));

  const handleAdd = () => {
    if (urls.length >= 4) return;
    setUrls(prev => {
      const next = [...prev, ''];
      setTimeout(() => inputRefs.current[next.length - 1]?.focus(), 0);
      return next;
    });
  };

  const handleRemove = (i: number) =>
    setUrls(prev => {
      const next = prev.filter((_, j) => j !== i);
      return next.length === 0 ? [''] : next;
    });

  const handleKeyDown = (e: React.KeyboardEvent, i: number) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (i === urls.length - 1 && urls.length < 4 && urls[i].trim()) handleAdd();
      else if (validCount > 0) handleSubmit();
    }
    if (e.key === 'Backspace' && urls[i] === '' && urls.length > 1) {
      e.preventDefault();
      handleRemove(i);
      setTimeout(() => inputRefs.current[Math.max(0, i - 1)]?.focus(), 0);
    }
  };

  const handleSubmit = () => {
    const valid = urls.map(u => u.trim()).filter(Boolean);
    if (valid.length > 0) onSubmit(valid);
  };

  const validCount = urls.filter(u => u.trim()).length;

  // ── LOADING ──────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="w-full bg-[#0e0e0e] border border-violet-500/20 rounded-2xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#1a1a1a]">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-violet-500/15 flex items-center justify-center">
              <Eye size={12} className="text-violet-400" />
            </div>
            <span className="text-xs font-medium text-neutral-300">Spy Pages</span>
            <span className="text-[10px] text-neutral-600">— coletando dados</span>
          </div>
          <Loader2 size={13} className="text-violet-400 animate-spin" />
        </div>
        <div className="flex flex-col items-center justify-center py-10 gap-4">
          <div className="relative w-12 h-12">
            <div className="absolute inset-0 rounded-full border-2 border-violet-500/15" />
            <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-violet-500 animate-spin" />
            <Eye size={16} className="text-violet-400 absolute inset-0 m-auto" />
          </div>
          <div className="text-center">
            <p className="text-sm font-medium text-neutral-200">Coletando dados via SimilarWeb</p>
            <p className="text-[11px] text-neutral-600 mt-1">Apify está processando · até 2 minutos</p>
          </div>
          <div className="flex gap-1.5">
            {[0, 1, 2, 3].map(i => (
              <div key={i} className="w-1.5 h-1.5 rounded-full bg-violet-500/40 animate-pulse"
                style={{ animationDelay: `${i * 150}ms` }} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  // ── PREVIEW ───────────────────────────────────────────────────────────────
  if (previewData && previewData.length > 0) {
    const valid = previewData.filter(s => !s.error);
    return (
      <div className="w-full bg-[#0e0e0e] border border-violet-500/20 rounded-2xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#1a1a1a]">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-violet-500/15 flex items-center justify-center">
              <Eye size={12} className="text-violet-400" />
            </div>
            <span className="text-xs font-medium text-neutral-300">Spy Pages</span>
            <span className="flex items-center gap-1 text-[10px] text-emerald-400 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" />
              {valid.length} site{valid.length !== 1 ? 's' : ''} coletado{valid.length !== 1 ? 's' : ''}
            </span>
          </div>
          <button onClick={onClose}
            className="text-neutral-600 hover:text-neutral-400 transition-colors p-1 rounded-md hover:bg-white/[0.05]">
            <X size={13} />
          </button>
        </div>

        <div className="max-h-[70vh] overflow-y-auto">
          <div className="p-3 space-y-3">
            {previewData.map((site, i) =>
              site.error ? (
                <div key={i} className="bg-[#1a1a1a] border border-red-500/20 rounded-xl px-4 py-3 flex items-center gap-3">
                  <Eye size={14} className="text-neutral-600 flex-shrink-0" />
                  <span className="text-sm text-neutral-400">{site.domain}</span>
                  <span className="text-xs text-red-400 ml-auto">{site.error}</span>
                </div>
              ) : (
                <SitePreviewCard key={i} site={site} />
              )
            )}
          </div>
        </div>

        <div className="px-4 py-3 border-t border-[#1a1a1a] flex items-center justify-between bg-[#0a0a0a]">
          <p className="text-[11px] text-neutral-600">Dados prontos · faça sua pergunta no chat</p>
          <button
            onClick={onConfirmReady}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold transition-colors"
          >
            Fazer pergunta
            <ArrowRight size={12} />
          </button>
        </div>
      </div>
    );
  }

  // ── INPUT ─────────────────────────────────────────────────────────────────
  return (
    <div className="w-full bg-[#0e0e0e] border border-violet-500/20 rounded-2xl overflow-hidden shadow-lg shadow-violet-500/5">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#1a1a1a]">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-violet-500/15 flex items-center justify-center">
            <Eye size={12} className="text-violet-400" />
          </div>
          <span className="text-xs font-medium text-neutral-300">Spy Pages</span>
          <span className="text-[10px] text-neutral-600">— cole os domínios para analisar</span>
        </div>
        <button onClick={onClose}
          className="text-neutral-600 hover:text-neutral-400 transition-colors p-1 rounded-md hover:bg-white/[0.05]">
          <X size={13} />
        </button>
      </div>

      <div className="px-4 py-3 space-y-2">
        {urls.map((url, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="flex-shrink-0 text-[10px] text-neutral-700 w-3 text-center">{i + 1}</span>
            <input
              ref={el => { inputRefs.current[i] = el; }}
              type="text"
              value={url}
              onChange={e => handleChange(i, e.target.value)}
              onKeyDown={e => handleKeyDown(e, i)}
              placeholder={i === 0 ? 'google.com' : 'outro-site.com'}
              className="flex-1 bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg px-3 py-1.5 text-sm text-neutral-200 placeholder-neutral-700 focus:outline-none focus:border-violet-500/40 focus:bg-[#161616] transition-all"
            />
            {urls.length > 1 && (
              <button onClick={() => handleRemove(i)}
                className="flex-shrink-0 text-neutral-700 hover:text-red-400 transition-colors p-1 rounded">
                <X size={11} />
              </button>
            )}
          </div>
        ))}
        {urls.length < 4 && (
          <button type="button" onClick={handleAdd}
            className="flex items-center gap-1.5 text-[11px] text-neutral-600 hover:text-violet-400 transition-colors pl-5 pt-0.5">
            <Plus size={11} /> Adicionar site
          </button>
        )}
      </div>

      <div className="flex items-center justify-between px-4 py-3 border-t border-[#1a1a1a]">
        <span className="text-[11px] text-neutral-700">
          {validCount === 0
            ? 'Até 4 sites · Enter para confirmar'
            : `${validCount} site${validCount > 1 ? 's' : ''} · clique Confirmar ou pressione Enter`}
        </span>
        <button
          onClick={handleSubmit}
          disabled={validCount === 0}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:opacity-30 disabled:cursor-not-allowed text-white text-xs font-semibold transition-colors"
        >
          <Check size={12} /> Confirmar
        </button>
      </div>
    </div>
  );
};

export default SpyPagesInputCard;
