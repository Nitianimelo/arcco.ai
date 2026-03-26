"""
Serviço de análise de sites via Apify SimilarWeb Scraper.

Actor: tri_angle~similarweb-scraper
Endpoint: POST /v2/acts/{ACTOR_ID}/run-sync-get-dataset-items
Auth: Authorization: Bearer <token>  (header recomendado pela doc)
"""

import logging
from urllib.parse import urlparse

import httpx

from backend.core.config import get_config

logger = logging.getLogger(__name__)

ACTOR_ID = "tri_angle~similarweb-scraper"
BASE_URL = "https://api.apify.com/v2"


def _extract_domain(url: str) -> str:
    """Extrai domínio limpo de uma URL ou string de domínio."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    domain = parsed.netloc or url
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _normalize_site(raw: dict) -> dict:
    """Normaliza os campos do actor SimilarWeb para estrutura padrão."""
    # Domain — actor returns clean domain in "name" field
    domain = (
        raw.get("name") or raw.get("domain") or raw.get("Domain")
        or raw.get("website") or raw.get("Website")
        or raw.get("url") or ""
    )

    # Visitas mensais
    visits = (
        raw.get("visits") or raw.get("Visits")
        or raw.get("totalVisits") or raw.get("TotalVisits")
        or raw.get("monthlyVisits") or raw.get("MonthlyVisits") or 0
    )

    # Bounce rate
    bounce = (
        raw.get("bounceRate") or raw.get("BounceRate")
        or raw.get("bounce_rate") or 0
    )
    if isinstance(bounce, str):
        try:
            bounce = float(bounce.replace("%", "").strip())
        except (ValueError, TypeError):
            bounce = 0

    # Pages per visit
    pages = (
        raw.get("pagesPerVisit") or raw.get("PagesPerVisit")
        or raw.get("pages_per_visit") or 0
    )

    # Avg visit duration
    duration = (
        raw.get("avgVisitDuration") or raw.get("AvgVisitDuration")
        or raw.get("avg_visit_duration") or ""
    )

    # Global rank
    rank = (
        raw.get("globalRank") or raw.get("GlobalRank")
        or raw.get("global_rank") or 0
    )

    # Top countries
    countries_raw = (
        raw.get("topCountries") or raw.get("TopCountries")
        or raw.get("top_countries") or []
    )
    top_countries = []
    if isinstance(countries_raw, list):
        for c in countries_raw[:5]:
            if isinstance(c, dict):
                top_countries.append({
                    "code": c.get("countryAlpha2Code") or c.get("countryCode") or c.get("code") or c.get("country") or "",
                    "name": c.get("countryUrlCode") or c.get("countryName") or c.get("name") or "",
                    "share": float(c.get("visitsShare") or c.get("share") or c.get("percentage") or 0),
                })

    # Top pages
    pages_raw = (
        raw.get("topPages") or raw.get("TopPages")
        or raw.get("top_pages") or []
    )
    top_pages = []
    if isinstance(pages_raw, list):
        for p in pages_raw[:5]:
            if isinstance(p, dict):
                top_pages.append({
                    "url": p.get("url") or p.get("page") or "",
                    "share": float(p.get("share") or p.get("percentage") or 0),
                })

    # Competitors — actor returns in "topSimilarityCompetitors"
    comps_raw = (
        raw.get("topSimilarityCompetitors") or raw.get("competitors") or raw.get("Competitors")
        or raw.get("similarSites") or raw.get("SimilarSites") or []
    )
    competitors = []
    if isinstance(comps_raw, list):
        for c in comps_raw[:5]:
            if isinstance(c, dict):
                competitors.append(c.get("domain") or c.get("website") or str(c))
            elif isinstance(c, str):
                competitors.append(c)

    # Keywords
    kw_raw = (
        raw.get("topKeywords") or raw.get("TopKeywords")
        or raw.get("keywords") or []
    )
    keywords = []
    if isinstance(kw_raw, list):
        for k in kw_raw[:8]:
            if isinstance(k, dict):
                keywords.append({
                    "keyword": k.get("name") or k.get("keyword") or k.get("term") or "",
                    "share": float(k.get("share") or k.get("percentage") or 0),
                })
            elif isinstance(k, str):
                keywords.append({"keyword": k, "share": 0})

    # Images
    icon_url        = raw.get("icon") or ""
    preview_desktop = raw.get("previewDesktop") or ""

    # Company
    company_name     = raw.get("companyName") or ""
    description      = raw.get("description") or ""
    year_founded     = raw.get("companyYearFounded")
    employees_min    = raw.get("companyEmployeesMin")
    employees_max    = raw.get("companyEmployeesMax")
    revenue_min      = raw.get("companyAnnualRevenueMin")
    hq_country       = raw.get("companyHeadquarterCountryCode") or ""
    hq_state         = raw.get("companyHeadquarterStateCode") or ""
    hq_city          = raw.get("companyHeadquarterCity") or ""

    # Extra ranks
    country_rank  = raw.get("countryRank") or 0
    category_rank = raw.get("categoryRank") or 0
    category_id   = raw.get("categoryId") or ""

    # Top referrals
    top_referrals = []
    for ref in (raw.get("topReferrals") or [])[:10]:
        if isinstance(ref, dict):
            top_referrals.append({
                "domain": ref.get("domain") or ref.get("site") or "",
                "share":  float(ref.get("share") or ref.get("visitsShare") or 0),
            })

    # Technologies
    technologies = []
    for tech in (raw.get("technologies") or [])[:20]:
        if isinstance(tech, dict):
            technologies.append(tech.get("name") or tech.get("technology") or str(tech))
        elif isinstance(tech, str):
            technologies.append(tech)

    # Traffic channels
    traffic_sources = []
    for ts in (raw.get("trafficSources") or []):
        if isinstance(ts, dict):
            pct = ts.get("percentage")
            traffic_sources.append({
                "source":     ts.get("source") or "",
                "percentage": float(pct) if pct is not None else None,
                "rank":       ts.get("rank"),
            })

    organic_traffic = raw.get("organicTraffic")
    paid_traffic    = raw.get("paidTraffic")

    # Social network distribution
    social_networks = []
    for sn in (raw.get("socialNetworkDistribution") or [])[:5]:
        if isinstance(sn, dict):
            social_networks.append({
                "name":  sn.get("name") or "",
                "share": float(sn.get("visitsShare") or 0),
                "icon":  sn.get("icon") or "",
            })

    # Demographics
    male_dist   = raw.get("maleDistribution")
    female_dist = raw.get("femaleDistribution")

    age_distribution = []
    for age in (raw.get("ageDistribution") or []):
        if isinstance(age, dict):
            age_distribution.append({
                "min_age": age.get("minAge"),
                "max_age": age.get("maxAge"),
                "value":   float(age.get("value") or 0),
            })

    return {
        # Identificação
        "domain":             domain,
        "company_name":       company_name,
        "description":        description,
        # Rankings
        "global_rank":        rank,
        "country_rank":       country_rank,
        "category_rank":      category_rank,
        "category_id":        category_id,
        # Métricas de engajamento
        "monthly_visits":     visits,
        "bounce_rate":        bounce,
        "pages_per_visit":    float(pages) if pages else 0,
        "avg_visit_duration": str(duration),
        # Tráfego por canal
        "traffic_sources":    traffic_sources,
        "organic_traffic":    float(organic_traffic) if organic_traffic is not None else None,
        "paid_traffic":       float(paid_traffic) if paid_traffic is not None else None,
        # Audiência
        "top_countries":      top_countries,
        "male_distribution":  float(male_dist) if male_dist is not None else None,
        "female_distribution": float(female_dist) if female_dist is not None else None,
        "age_distribution":   age_distribution,
        # Conteúdo e descoberta
        "keywords":           keywords,
        "top_referrals":      top_referrals,
        "social_networks":    social_networks,
        "top_pages":          top_pages,
        # Competidores
        "competitors":        competitors,
        # Empresa
        "year_founded":       year_founded,
        "employees_min":      employees_min,
        "employees_max":      employees_max,
        "revenue_min":        revenue_min,
        "hq_country":         hq_country,
        "hq_state":           hq_state,
        "hq_city":            hq_city,
        "technologies":       technologies,
        # Imagens (para UI, não relevante para o agente)
        "icon_url":           icon_url,
        "preview_desktop":    preview_desktop,
        "raw_available":      bool(domain),
    }


async def analyze_pages(urls: list[str]) -> list[dict]:
    """
    Analisa sites via Apify SimilarWeb Scraper.

    Args:
        urls: Lista de URLs/domínios (máx. 4)

    Returns:
        Lista de dicts com métricas normalizadas por site
    """
    config = get_config()
    api_key = config.apify_api_key

    if not api_key:
        logger.error("[APIFY] APIFY_API_KEY não configurada")
        return [
            {"domain": _extract_domain(url), "error": "APIFY_API_KEY não configurada", "raw_available": False}
            for url in urls
        ]

    domains = [_extract_domain(url) for url in urls[:4]]

    actor_input = {"websites": domains}
    endpoint = f"{BASE_URL}/acts/{ACTOR_ID}/run-sync-get-dataset-items"
    # Autenticação via header (recomendado pela doc Apify — mais seguro que query param)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    params = {"timeout": 120}

    try:
        async with httpx.AsyncClient(timeout=130.0) as client:
            logger.info(f"[APIFY] Iniciando análise: {domains}")
            response = await client.post(endpoint, json=actor_input, headers=headers, params=params)

            if response.status_code == 401:
                return [{"domain": d, "error": "API key Apify inválida", "raw_available": False} for d in domains]

            if response.status_code == 400:
                err = response.text[:300]
                logger.error(f"[APIFY] Input inválido: {err}")
                return [{"domain": d, "error": f"Input inválido: {err}", "raw_available": False} for d in domains]

            if not response.is_success:
                logger.error(f"[APIFY] HTTP {response.status_code}: {response.text[:200]}")
                return [{"domain": d, "error": f"Erro Apify HTTP {response.status_code}", "raw_available": False} for d in domains]

            data = response.json()

            if not isinstance(data, list):
                logger.error(f"[APIFY] Resposta inesperada (tipo {type(data)})")
                return [{"domain": d, "error": "Formato inesperado", "raw_available": False} for d in domains]

            if not data:
                return [{"domain": d, "error": "Nenhum dado retornado", "raw_available": False} for d in domains]

            results = [_normalize_site(item) for item in data]

            # Preenche resultados faltantes
            while len(results) < len(domains):
                idx = len(results)
                results.append({
                    "domain": domains[idx] if idx < len(domains) else "",
                    "error": "Dados não disponíveis para este site",
                    "raw_available": False,
                })

            logger.info(f"[APIFY] Análise concluída: {len(results)} site(s)")
            return results

    except httpx.TimeoutException:
        logger.error("[APIFY] Timeout (>120s)")
        return [{"domain": d, "error": "Timeout na análise (>120s)", "raw_available": False} for d in domains]
    except Exception as exc:
        logger.error(f"[APIFY] Erro inesperado: {exc}")
        return [{"domain": d, "error": str(exc), "raw_available": False} for d in domains]
