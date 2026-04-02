import re


CANVAS_PRESETS = {
    "instagram-square": {"width": 1080, "height": 1080, "safe_pad": 72, "format_class": "format-ig-post-square", "format_badge": "Post quadrado"},
    "instagram-portrait": {"width": 1080, "height": 1350, "safe_pad": 84, "format_class": "format-ig-post-portrait", "format_badge": "Post retrato"},
    "story": {"width": 1080, "height": 1920, "safe_pad": 96, "format_class": "format-ig-story", "format_badge": "Story"},
    "a4-portrait": {"width": 794, "height": 1122, "safe_pad": 72, "format_class": "format-a4", "format_badge": "A4 retrato"},
    "a4-landscape": {"width": 1122, "height": 794, "safe_pad": 72, "format_class": "format-a4", "format_badge": "A4 paisagem"},
    "banner": {"width": 1920, "height": 1080, "safe_pad": 96, "format_class": "format-slide-16-9", "format_badge": "Banner"},
    "widescreen": {"width": 1280, "height": 720, "safe_pad": 72, "format_class": "format-slide-16-9", "format_badge": "Slide"},
}


def strip_html_fences(src: str) -> str:
    trimmed = (src or "").strip()
    match = re.match(r"^```html\s*([\s\S]*?)\s*```$", trimmed, flags=re.IGNORECASE)
    return match.group(1).strip() if match else trimmed


def ensure_html_document(src: str) -> str:
    if re.search(r"<!doctype html>|<html[\s>]", src, flags=re.IGNORECASE):
        return src
    return (
        "<!DOCTYPE html><html lang=\"pt-BR\"><head><meta charset=\"UTF-8\">"
        "<title>Design</title></head><body>"
        f"{src}</body></html>"
    )


def _escape_html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _truncate_text(value: str, limit: int) -> str:
    value = _collapse_whitespace(value)
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def _strip_tags(value: str) -> str:
    return _collapse_whitespace(re.sub(r"<[^>]+>", " ", value or ""))


def _extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    return _strip_tags(match.group(1)) if match else ""


def _extract_first_text(html: str, patterns: list[str], minimum: int = 0) -> str:
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            text = _strip_tags(match.group(1))
            if len(text) >= minimum:
                return text
    return ""


def _extract_scaffold_content(html: str, preset: str) -> dict[str, str]:
    spec = CANVAS_PRESETS.get(preset, CANVAS_PRESETS["instagram-square"])
    headline = (
        _extract_first_text(
            html,
            [
                r'<[^>]*data-role="headline"[^>]*>(.*?)</[^>]+>',
                r"<h1[^>]*>(.*?)</h1>",
                r"<h2[^>]*>(.*?)</h2>",
            ],
            minimum=4,
        )
        or _extract_title(html)
        or "Título do Design"
    )
    body = _extract_first_text(
        html,
        [
            r'<[^>]*data-role="subheadline"[^>]*>(.*?)</[^>]+>',
            r'<[^>]*class="[^"]*(?:subtitle|subheadline|description)[^"]*"[^>]*>(.*?)</[^>]+>',
            r"<p[^>]*>(.*?)</p>",
            r"<li[^>]*>(.*?)</li>",
            r"<blockquote[^>]*>(.*?)</blockquote>",
            r"<div[^>]*>(.*?)</div>",
        ],
        minimum=24,
    ) or f"Adapte a mensagem principal para {spec['format_badge']} sem perder hierarquia e legibilidade."
    cta = _extract_first_text(
        html,
        [
            r"<button[^>]*>(.*?)</button>",
            r"<a[^>]*>(.*?)</a>",
            r'<[^>]*data-role="cta"[^>]*>(.*?)</[^>]+>',
        ],
        minimum=6,
    ) or "Personalize a marca e finalize o CTA antes de exportar."
    media_match = re.search(
        r"(<(?:img|svg|canvas|video|figure)\b[\s\S]*?</(?:svg|canvas|video|figure)>|<(?:img)\b[^>]*>)",
        html,
        flags=re.IGNORECASE,
    )
    media_html = (
        f'<div class="embedded-media">{media_match.group(1)}</div>'
        if media_match
        else f'<div class="placeholder-media"><span>{_escape_html(spec["format_badge"])}</span></div>'
    )
    return {
        "kicker": spec["format_badge"],
        "headline": _truncate_text(headline, 96),
        "body": _truncate_text(body, 220),
        "cta": _truncate_text(cta, 96),
        "media_html": media_html,
    }


def _build_adaptive_scaffold(content: dict[str, str], preset: str) -> str:
    spec = CANVAS_PRESETS.get(preset, CANVAS_PRESETS["instagram-square"])
    return f"""
    <div id="arcco-design-stage" class="container-base {spec["format_class"]}" data-arcco-safe-block="true">
      <div id="arcco-design-content" class="content-shell auto-scaffold">
        <div class="content-copy">
          <span class="cq-kicker">{_escape_html(content["kicker"])}</span>
          <h1 class="cq-title" data-role="headline">{_escape_html(content["headline"])}</h1>
          <p class="cq-body" data-role="subheadline">{_escape_html(content["body"])}</p>
          <div class="content-actions">
            <span class="content-chip">{_escape_html(content["cta"])}</span>
          </div>
        </div>
        <div class="content-media">
          <div class="content-card">{content["media_html"]}</div>
        </div>
      </div>
    </div>
    """.strip()


def is_multi_slide_design(html: str) -> bool:
    slide_elements = re.findall(
        r'<(?:section|div)[^>]*class="[^"]*\bslide\b[^"]*"',
        html,
        flags=re.IGNORECASE,
    )
    return len(slide_elements) > 1


def infer_canvas_preset(html: str) -> str:
    haystack = strip_html_fences(html).lower()
    if any(token in haystack for token in ("1080x1920", "9:16", "story", "stories")):
        return "story"
    if any(token in haystack for token in ("1080x1350", "4:5", "portrait", "retrato")):
        return "instagram-portrait"
    if "a4 portrait" in haystack or "a4-portrait" in haystack:
        return "a4-portrait"
    if "a4 landscape" in haystack or "a4-landscape" in haystack or "a4" in haystack:
        return "a4-landscape"
    if any(token in haystack for token in ("1920x1080", "16:9", "banner", "hero")):
        return "banner"
    return "instagram-square"


def _build_style(preset: str) -> str:
    spec = CANVAS_PRESETS.get(preset, CANVAS_PRESETS["instagram-square"])
    return f"""
    <style id="arcco-design-contract">
      :root {{
        --arcco-canvas-width: {spec["width"]}px;
        --arcco-canvas-height: {spec["height"]}px;
        --arcco-safe-pad: {spec["safe_pad"]}px;
        --arcco-page-bg: #0b0b0d;
        --arcco-copy-max: min(100%, 34ch);
        --arcco-body-max: min(100%, 42ch);
        --arcco-copy-align: left;
        --arcco-copy-items: flex-start;
        --arcco-shell-justify: center;
        --arcco-title-fluid: 5cqw;
        --arcco-title-max: 84px;
        --arcco-body-fluid: 1.55cqw;
        --arcco-body-max-size: 28px;
      }}
      @page {{
        size: A4;
        margin: 0;
      }}
      html, body {{
        margin: 0;
        padding: 0;
        min-width: 100%;
        min-height: 100%;
        background: var(--arcco-page-bg);
      }}
      * {{
        box-sizing: border-box;
      }}
      body {{
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 24px;
        overflow: hidden;
      }}
      .container-base {{
        container-type: inline-size;
        position: relative;
        overflow: hidden;
        box-sizing: border-box;
        width: min(100%, var(--arcco-canvas-width));
        margin: 0 auto;
        isolation: isolate;
      }}
      .format-ig-post-square {{
        width: min(100%, 1080px);
        aspect-ratio: 1 / 1;
      }}
      .format-ig-post-portrait {{
        width: min(100%, 1080px);
        aspect-ratio: 4 / 5;
      }}
      .format-ig-story {{
        width: min(100%, 1080px);
        aspect-ratio: 9 / 16;
      }}
      .format-a4 {{
        width: 210mm;
        height: 297mm;
      }}
      .format-slide-16-9 {{
        width: min(100%, 1920px);
        aspect-ratio: 16 / 9;
      }}
      .content-shell {{
        width: 100%;
        height: 100%;
        padding: max(24px, 6cqw);
        display: grid;
        grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
        align-items: center;
        justify-items: stretch;
        justify-content: var(--arcco-shell-justify);
        gap: max(20px, 4cqw);
      }}
      .content-copy {{
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: var(--arcco-copy-items);
        text-align: var(--arcco-copy-align);
        gap: max(12px, 1.8cqw);
        min-width: 0;
        width: 100%;
      }}
      .content-copy > * {{
        max-inline-size: var(--arcco-copy-max);
      }}
      .content-actions {{
        display: flex;
        flex-wrap: wrap;
        justify-content: var(--arcco-copy-items);
        gap: max(10px, 1.2cqw);
      }}
      .content-chip {{
        display: inline-flex;
        align-items: center;
        min-height: max(32px, 3.4cqw);
        padding: 0.75em 1.05em;
        border-radius: 999px;
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.14);
        font-size: clamp(12px, 1.15cqw, 20px);
        line-height: 1.15;
      }}
      .content-media {{
        display: flex;
        align-items: center;
        justify-content: center;
        min-width: 0;
        min-height: 0;
        width: 100%;
      }}
      .content-card {{
        width: 100%;
        height: 100%;
        min-height: min(42cqh, 44cqw);
        padding: max(18px, 2cqw);
        border-radius: max(22px, 2.6cqw);
        background:
          linear-gradient(180deg, rgba(255,255,255,0.10), rgba(255,255,255,0.04)),
          rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.10);
        box-shadow: 0 24px 80px rgba(0,0,0,0.22);
        overflow: hidden;
        display: flex;
        align-items: stretch;
        justify-content: stretch;
      }}
      .embedded-media {{
        width: 100%;
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
      }}
      .embedded-media > * {{
        width: 100% !important;
        height: 100% !important;
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
      }}
      .placeholder-media {{
        width: 100%;
        height: min(42cqh, 44cqw);
        border-radius: max(18px, 2.4cqw);
        display: grid;
        place-items: center;
        background:
          linear-gradient(135deg, rgba(255,255,255,0.12), rgba(255,255,255,0.04)),
          linear-gradient(160deg, rgba(255,255,255,0.12), transparent 60%);
        border: 1px solid rgba(255,255,255,0.12);
      }}
      .placeholder-media span {{
        font-size: clamp(18px, 2.4cqw, 36px);
        opacity: 0.68;
      }}
      .cq-title {{
        font-size: clamp(22px, var(--arcco-title-fluid), var(--arcco-title-max));
        line-height: 0.96;
        letter-spacing: -0.04em;
        margin: 0;
      }}
      .cq-body {{
        font-size: clamp(13px, var(--arcco-body-fluid), var(--arcco-body-max-size));
        line-height: 1.35;
        margin: 0;
        opacity: 0.88;
        max-inline-size: var(--arcco-body-max);
      }}
      .cq-kicker {{
        font-size: clamp(11px, 1cqw, 18px);
        letter-spacing: 0.18em;
        text-transform: uppercase;
        opacity: 0.6;
      }}
      .content-shell.is-vertical,
      .format-ig-story .content-shell,
      .format-ig-post-portrait .content-shell,
      .format-a4 .content-shell {{
        grid-template-columns: 1fr;
        grid-template-rows: auto minmax(0, 1fr);
      }}
      .format-ig-post-square {{
        --arcco-copy-max: min(100%, 18ch);
        --arcco-body-max: min(100%, 28ch);
        --arcco-title-fluid: 4.05cqw;
        --arcco-title-max: 66px;
        --arcco-body-fluid: 1.35cqw;
        --arcco-body-max-size: 22px;
      }}
      .format-ig-post-portrait,
      .format-ig-story {{
        --arcco-copy-max: min(100%, 16ch);
        --arcco-body-max: min(100%, 22ch);
        --arcco-copy-align: center;
        --arcco-copy-items: center;
      }}
      .format-ig-post-portrait {{
        --arcco-title-fluid: 3.8cqw;
        --arcco-title-max: 58px;
        --arcco-body-fluid: 1.25cqw;
        --arcco-body-max-size: 20px;
      }}
      .format-ig-story {{
        --arcco-title-fluid: 3.4cqw;
        --arcco-title-max: 54px;
        --arcco-body-fluid: 1.15cqw;
        --arcco-body-max-size: 18px;
      }}
      .format-a4 {{
        --arcco-copy-max: min(100%, 24ch);
        --arcco-body-max: min(100%, 36ch);
        --arcco-title-fluid: 4.2cqw;
        --arcco-title-max: 70px;
      }}
      .format-slide-16-9 {{
        --arcco-copy-max: min(100%, 20ch);
        --arcco-body-max: min(100%, 30ch);
        --arcco-title-fluid: 3.6cqw;
        --arcco-title-max: 62px;
      }}
      @container (max-width: 760px) {{
        .content-shell {{
          grid-template-columns: 1fr;
          grid-template-rows: auto minmax(0, 1fr);
        }}
        .content-card {{
          min-height: 34cqh;
        }}
      }}
      @container (max-width: 520px) {{
        .content-shell {{
          padding: max(18px, 5.2cqw);
          gap: max(16px, 3cqw);
        }}
        .content-actions {{
          gap: 10px;
        }}
      }}
      #arcco-design-stage,
      .slide,
      .slide-container,
      [data-arcco-slide="true"],
      .container-base {{
        width: var(--arcco-canvas-width) !important;
        height: var(--arcco-canvas-height) !important;
        min-width: var(--arcco-canvas-width) !important;
        min-height: var(--arcco-canvas-height) !important;
        max-width: var(--arcco-canvas-width) !important;
        max-height: var(--arcco-canvas-height) !important;
        overflow: hidden !important;
        position: relative !important;
        isolation: isolate;
        margin: 0 auto !important;
        flex: none !important;
      }}
      #arcco-design-content {{
        position: relative;
        width: 100%;
        height: 100%;
        overflow: hidden;
        transform-origin: center center;
      }}
      img, svg, canvas, video {{
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
      }}
      h1, h2, h3, h4, h5, h6, p, li, span, a, button, div {{
        overflow-wrap: anywhere;
        word-break: break-word;
      }}
      h1, h2, [class*="title"], [class*="headline"], [data-role="headline"] {{
        text-wrap: balance;
        max-width: 100%;
      }}
      [class*="subtitle"], [data-role="subheadline"], p, li {{
        text-wrap: pretty;
        max-width: 100%;
      }}
      #arcco-design-content :is(h1, h2, h3, h4, h5, h6, [class*="title"], [class*="headline"], [data-role="headline"]) {{
        max-inline-size: var(--arcco-copy-max);
        margin-inline: auto;
      }}
      #arcco-design-content :is(p, li, blockquote, [class*="subtitle"], [class*="description"], [data-role="subheadline"]) {{
        max-inline-size: var(--arcco-body-max);
        margin-inline: auto;
      }}
      [data-arcco-safe-block="true"] {{
        max-width: calc(100% - (var(--arcco-safe-pad) * 2));
        max-height: calc(100% - (var(--arcco-safe-pad) * 2));
      }}
      [data-arcco-fit="tight"] .content-shell {{
        padding: max(18px, 4.4cqw);
        gap: max(14px, 2.4cqw);
      }}
      [data-arcco-fit="tight"] .content-card {{
        min-height: min(30cqh, 32cqw);
      }}
      [data-arcco-fit="tight"] .content-copy {{
        gap: max(10px, 1.2cqw);
      }}
      [data-arcco-fit="tight"] .content-chip {{
        font-size: clamp(11px, 1cqw, 18px);
        padding: 0.68em 0.92em;
      }}
      @media print {{
        html, body {{
          background: white !important;
        }}
        .container-base {{
          box-shadow: none !important;
          border: none !important;
        }}
      }}
    </style>
    """


def _build_script() -> str:
    return """
    <script id="arcco-design-contract-script">
      (function () {
        function rootCanvas(node) {
          return node.closest('#arcco-design-stage, .slide, .slide-container') || document.body;
        }

        function fitText(el, rootRect) {
          const style = window.getComputedStyle(el);
          let fontSize = parseFloat(style.fontSize || '16');
          let lineHeight = parseFloat(style.lineHeight || String(fontSize * 1.2));
          let attempts = 0;
          while (attempts < 8) {
            const rect = el.getBoundingClientRect();
            const overflowsSelf = el.scrollWidth > el.clientWidth + 2 || el.scrollHeight > el.clientHeight + 2;
            const escapesRoot =
              rect.left < rootRect.left - 2 ||
              rect.right > rootRect.right + 2 ||
              rect.top < rootRect.top - 2 ||
              rect.bottom > rootRect.bottom + 2;
            if (!overflowsSelf && !escapesRoot) break;
            fontSize = Math.max(12, fontSize * 0.94);
            lineHeight = Math.max(fontSize * 1.1, lineHeight * 0.96);
            el.style.fontSize = fontSize.toFixed(2) + 'px';
            el.style.lineHeight = lineHeight.toFixed(2) + 'px';
            attempts += 1;
          }
        }

        function rootOverflows(root) {
          return root.scrollWidth > root.clientWidth + 2 || root.scrollHeight > root.clientHeight + 2;
        }

        function tightenRoot(root) {
          root.setAttribute('data-arcco-fit', 'tight');
          const shell = root.querySelector('.content-shell');
          const copy = root.querySelector('.content-copy');
          const media = root.querySelector('.content-card');
          if (shell) {
            shell.style.padding = 'max(16px, 4cqw)';
            shell.style.gap = 'max(12px, 2cqw)';
          }
          if (copy) {
            copy.style.gap = 'max(8px, 1cqw)';
          }
          if (media) {
            media.style.minHeight = 'min(26cqh, 28cqw)';
          }
        }

        function scaleRootContent(root) {
          const content = root.querySelector('#arcco-design-content') || root.firstElementChild;
          if (!content) return;
          let attempts = 0;
          while (attempts < 4 && rootOverflows(root)) {
            const existing = parseFloat(content.getAttribute('data-arcco-scale') || '1');
            const next = Math.max(0.72, existing * 0.95);
            content.setAttribute('data-arcco-scale', String(next));
            content.style.transform = 'scale(' + next.toFixed(3) + ')';
            attempts += 1;
          }
        }

        function runPreflight() {
          const roots = Array.from(document.querySelectorAll('#arcco-design-stage, .slide, .slide-container'));
          const candidates = Array.from(document.querySelectorAll(
            'h1, h2, h3, p, li, span, a, button, [class*="title"], [class*="headline"], [class*="subtitle"], [data-role="headline"], [data-role="subheadline"]'
          ));
          candidates.forEach(function (node) {
            const root = roots.find(function (r) { return r.contains(node); }) || rootCanvas(node);
            fitText(node, root.getBoundingClientRect());
          });
          roots.forEach(function (root) {
            if (rootOverflows(root)) tightenRoot(root);
            const localCandidates = Array.from(root.querySelectorAll(
              'h1, h2, h3, p, li, span, a, button, [class*="title"], [class*="headline"], [class*="subtitle"], [data-role="headline"], [data-role="subheadline"]'
            ));
            localCandidates.forEach(function (node) { fitText(node, root.getBoundingClientRect()); });
            if (rootOverflows(root)) scaleRootContent(root);
            root.style.overflow = 'hidden';
          });
          document.documentElement.style.overflow = 'hidden';
          document.body.style.overflow = 'hidden';
        }

        if (document.readyState === 'complete') {
          setTimeout(runPreflight, 120);
        } else {
          window.addEventListener('load', function () { setTimeout(runPreflight, 120); });
        }
      })();
    </script>
    """


def _inject_into_head(html: str, snippet: str) -> str:
    if re.search(r"</head>", html, flags=re.IGNORECASE):
        return re.sub(r"</head>", snippet + "</head>", html, count=1, flags=re.IGNORECASE)
    if re.search(r"<html[\s>]", html, flags=re.IGNORECASE):
        return re.sub(r"(<html[^>]*>)", r"\1<head>" + snippet + "</head>", html, count=1, flags=re.IGNORECASE)
    return snippet + html


def normalize_design_html(html: str, canvas_preset: str | None = None) -> str:
    normalized = ensure_html_document(strip_html_fences(html))
    preset = canvas_preset or infer_canvas_preset(normalized)
    spec = CANVAS_PRESETS.get(preset, CANVAS_PRESETS["instagram-square"])
    is_slides = is_multi_slide_design(normalized)

    if not re.search(r'id="arcco-design-contract"', normalized, flags=re.IGNORECASE):
      normalized = _inject_into_head(normalized, _build_style(preset))
    if not re.search(r'id="arcco-design-contract-script"', normalized, flags=re.IGNORECASE):
      normalized = re.sub(r"</body>", _build_script() + "</body>", normalized, count=1, flags=re.IGNORECASE)

    if not is_slides and not re.search(r'class="[^"]*container-base', normalized, flags=re.IGNORECASE):
        body_match = re.search(r"<body[^>]*>([\s\S]*?)</body>", normalized, flags=re.IGNORECASE)
        body_inner = body_match.group(1) if body_match else ""
        scaffold = _build_adaptive_scaffold(_extract_scaffold_content(body_inner, preset), preset)
        normalized = re.sub(
            r"<body([^>]*)>[\s\S]*?</body>",
            rf"<body\1 data-arcco-mode=\"single\">{scaffold}</body>",
            normalized,
            count=1,
            flags=re.IGNORECASE,
        )
    elif is_slides:
        normalized = re.sub(
            r"<body([^>]*)>",
            r'<body\1 data-arcco-mode="slides">',
            normalized,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        normalized = re.sub(
            r'(class="[^"]*container-base)([^"]*)"',
            rf'\1 {spec["format_class"]}\2"',
            normalized,
            count=1,
            flags=re.IGNORECASE,
        )

    return normalized
