export type CanvasPreset =
  | 'instagram-square'
  | 'instagram-portrait'
  | 'story'
  | 'a4-portrait'
  | 'a4-landscape'
  | 'banner'
  | 'widescreen';

export interface CanvasPresetSpec {
  width: number;
  height: number;
  safePad: number;
  label: string;
  shortLabel: string;
  description: string;
  formatClass: string;
  formatBadge: string;
}

export const CANVAS_PRESETS: Record<CanvasPreset, CanvasPresetSpec> = {
  'instagram-square': {
    width: 1080, height: 1080, safePad: 72,
    label: 'Instagram Post 1080 x 1080',
    shortLabel: 'Instagram 1:1',
    description: 'Post quadrado para feed e carrossel.',
    formatClass: 'format-ig-post-square',
    formatBadge: 'Post quadrado',
  },
  'instagram-portrait': {
    width: 1080, height: 1350, safePad: 84,
    label: 'Instagram Retrato 1080 x 1350',
    shortLabel: 'Instagram 4:5',
    description: 'Post retrato com mais área útil no feed.',
    formatClass: 'format-ig-post-portrait',
    formatBadge: 'Post retrato',
  },
  story: {
    width: 1080, height: 1920, safePad: 96,
    label: 'Story 1080 x 1920',
    shortLabel: 'Story 9:16',
    description: 'Tela vertical para stories e telas mobile.',
    formatClass: 'format-ig-story',
    formatBadge: 'Story',
  },
  'a4-portrait': {
    width: 794, height: 1122, safePad: 72,
    label: 'A4 Retrato 794 x 1122',
    shortLabel: 'A4 Retrato',
    description: 'Folha A4 vertical para PDFs e materiais impressos.',
    formatClass: 'format-a4',
    formatBadge: 'A4 retrato',
  },
  'a4-landscape': {
    width: 1122, height: 794, safePad: 72,
    label: 'A4 Paisagem 1122 x 794',
    shortLabel: 'A4 Paisagem',
    description: 'Folha A4 horizontal para relatórios e slides.',
    formatClass: 'format-a4',
    formatBadge: 'A4 paisagem',
  },
  banner: {
    width: 1920, height: 1080, safePad: 96,
    label: 'Banner 1920 x 1080',
    shortLabel: 'Banner 16:9',
    description: 'Hero, capa e peça horizontal ampla.',
    formatClass: 'format-slide-16-9',
    formatBadge: 'Banner',
  },
  widescreen: {
    width: 1280, height: 720, safePad: 72,
    label: 'Apresentação 1280 x 720',
    shortLabel: 'Slide 16:9',
    description: 'Slide widescreen para apresentações.',
    formatClass: 'format-slide-16-9',
    formatBadge: 'Slide',
  },
};

export const SINGLE_DESIGN_PRESETS: CanvasPreset[] = [
  'instagram-square',
  'instagram-portrait',
  'story',
  'a4-portrait',
  'banner',
  'widescreen',
];

export const PRESENTATION_PRESETS: CanvasPreset[] = [
  'instagram-square',
  'instagram-portrait',
  'widescreen',
  'a4-landscape',
  'a4-portrait',
];

function stripHtmlFences(src: string): string {
  const trimmed = src.trim();
  const match = trimmed.match(/^```html\s*([\s\S]*?)\s*```$/i);
  return match ? match[1].trim() : trimmed;
}

function ensureHtmlDocument(src: string): string {
  if (/<!doctype html>/i.test(src) || /<html[\s>]/i.test(src)) return src;
  return `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><title>Design</title></head><body>${src}</body></html>`;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function collapseWhitespace(value: string): string {
  return value.replace(/\s+/g, ' ').trim();
}

function truncateText(value: string, limit: number): string {
  if (value.length <= limit) return value;
  return `${value.slice(0, Math.max(0, limit - 1)).trimEnd()}…`;
}

interface ScaffoldContent {
  kicker: string;
  headline: string;
  body: string;
  cta: string;
  mediaHtml: string;
}

function extractScaffoldContent(doc: Document, preset: CanvasPreset): ScaffoldContent {
  const spec = CANVAS_PRESETS[preset];
  const textFrom = (selector: string): string => {
    const node = doc.body.querySelector(selector);
    return collapseWhitespace(node?.textContent || '');
  };

  const titleText = collapseWhitespace(doc.title || '');
  const headline =
    textFrom('[data-role="headline"]') ||
    textFrom('h1') ||
    textFrom('h2') ||
    titleText ||
    'Título do Design';

  const subtitleCandidates = Array.from(
    doc.body.querySelectorAll(
      '[data-role="subheadline"], .subtitle, .subheadline, .description, p, li, blockquote, h3, h4, div'
    )
  )
    .map((node) => collapseWhitespace(node.textContent || ''))
    .filter((text) => text && text !== headline && text.length > 24);

  const body =
    truncateText(subtitleCandidates[0] || `Adapte a mensagem principal para ${spec.shortLabel} sem perder hierarquia e legibilidade.`, 220);

  const cta =
    truncateText(
      textFrom('button') ||
        textFrom('a') ||
        textFrom('[data-role="cta"]') ||
        'Personalize a marca e finalize o CTA antes de exportar.',
      96,
    );

  const mediaNode = doc.body.querySelector('img, svg, canvas, video, figure');
  const mediaHtml = mediaNode
    ? `<div class="embedded-media">${mediaNode.outerHTML}</div>`
    : `<div class="placeholder-media"><span>${escapeHtml(spec.formatBadge)}</span></div>`;

  return {
    kicker: spec.formatBadge,
    headline: truncateText(headline, 96),
    body,
    cta,
    mediaHtml,
  };
}

function buildAdaptiveScaffold(content: ScaffoldContent, preset: CanvasPreset): string {
  const formatClass = CANVAS_PRESETS[preset].formatClass;
  return `
    <div id="arcco-design-stage" class="container-base ${formatClass}" data-arcco-safe-block="true">
      <div id="arcco-design-content" class="content-shell auto-scaffold">
        <div class="content-copy">
          <span class="cq-kicker">${escapeHtml(content.kicker)}</span>
          <h1 class="cq-title" data-role="headline">${escapeHtml(content.headline)}</h1>
          <p class="cq-body" data-role="subheadline">${escapeHtml(content.body)}</p>
          <div class="content-actions">
            <span class="content-chip">${escapeHtml(content.cta)}</span>
          </div>
        </div>
        <div class="content-media">
          <div class="content-card">${content.mediaHtml}</div>
        </div>
      </div>
    </div>
  `.trim();
}

export function isMultiSlideDesign(html: string): boolean {
  const normalized = stripHtmlFences(html);
  const slideElements = normalized.match(/<(?:section|div)[^>]*class="[^"]*\bslide\b[^"]*"/gi);
  return !!slideElements && slideElements.length > 1;
}

export function inferCanvasPreset(html: string): CanvasPreset {
  const haystack = stripHtmlFences(html).toLowerCase();
  if (
    haystack.includes('1080x1920') ||
    haystack.includes('9:16') ||
    haystack.includes('story') ||
    haystack.includes('stories')
  ) {
    return 'story';
  }
  if (
    haystack.includes('1080x1350') ||
    haystack.includes('4:5') ||
    haystack.includes('portrait') ||
    haystack.includes('retrato')
  ) {
    return 'instagram-portrait';
  }
  if (haystack.includes('a4 portrait') || haystack.includes('a4-portrait')) {
    return 'a4-portrait';
  }
  if (haystack.includes('a4 landscape') || haystack.includes('a4-landscape') || haystack.includes('a4')) {
    return 'a4-landscape';
  }
  if (
    haystack.includes('1920x1080') ||
    haystack.includes('16:9') ||
    haystack.includes('banner') ||
    haystack.includes('hero')
  ) {
    return 'banner';
  }
  if (isMultiSlideDesign(haystack)) {
    return 'instagram-square';
  }
  return 'instagram-square';
}

function buildContractStyle(preset: CanvasPreset): string {
  const spec = CANVAS_PRESETS[preset];
  return `
    <style id="arcco-design-contract">
      :root {
        --arcco-canvas-width: ${spec.width}px;
        --arcco-canvas-height: ${spec.height}px;
        --arcco-safe-pad: ${spec.safePad}px;
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
      }
      @page {
        size: A4;
        margin: 0;
      }
      html, body {
        margin: 0;
        padding: 0;
        min-width: 100%;
        min-height: 100%;
        background: var(--arcco-page-bg);
      }
      * {
        box-sizing: border-box;
      }
      body {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 24px;
        overflow: hidden;
      }
      .container-base {
        container-type: inline-size;
        position: relative;
        overflow: hidden;
        box-sizing: border-box;
        width: min(100%, var(--arcco-canvas-width));
        margin: 0 auto;
        isolation: isolate;
      }
      .format-ig-post-square {
        width: min(100%, 1080px);
        aspect-ratio: 1 / 1;
      }
      .format-ig-post-portrait {
        width: min(100%, 1080px);
        aspect-ratio: 4 / 5;
      }
      .format-ig-story {
        width: min(100%, 1080px);
        aspect-ratio: 9 / 16;
      }
      .format-a4 {
        width: 210mm;
        height: 297mm;
      }
      .format-slide-16-9 {
        width: min(100%, 1920px);
        aspect-ratio: 16 / 9;
      }
      .content-shell {
        width: 100%;
        height: 100%;
        padding: max(24px, 6cqw);
        display: grid;
        grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
        align-items: center;
        justify-items: stretch;
        justify-content: var(--arcco-shell-justify);
        gap: max(20px, 4cqw);
      }
      .content-copy {
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: var(--arcco-copy-items);
        text-align: var(--arcco-copy-align);
        gap: max(12px, 1.8cqw);
        min-width: 0;
        width: 100%;
      }
      .content-copy > * {
        max-inline-size: var(--arcco-copy-max);
      }
      .content-actions {
        display: flex;
        flex-wrap: wrap;
        justify-content: var(--arcco-copy-items);
        gap: max(10px, 1.2cqw);
      }
      .content-chip {
        display: inline-flex;
        align-items: center;
        min-height: max(32px, 3.4cqw);
        padding: 0.75em 1.05em;
        border-radius: 999px;
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.14);
        font-size: clamp(12px, 1.15cqw, 20px);
        line-height: 1.15;
      }
      .content-media {
        display: flex;
        align-items: center;
        justify-content: center;
        min-width: 0;
        min-height: 0;
        width: 100%;
      }
      .content-card {
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
      }
      .embedded-media {
        width: 100%;
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .embedded-media > * {
        width: 100% !important;
        height: 100% !important;
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
      }
      .placeholder-media {
        width: 100%;
        height: min(42cqh, 44cqw);
        border-radius: max(18px, 2.4cqw);
        display: grid;
        place-items: center;
        background:
          linear-gradient(135deg, rgba(255,255,255,0.12), rgba(255,255,255,0.04)),
          linear-gradient(160deg, rgba(255,255,255,0.12), transparent 60%);
        border: 1px solid rgba(255,255,255,0.12);
      }
      .placeholder-media span {
        font-size: clamp(18px, 2.4cqw, 36px);
        opacity: 0.68;
      }
      .cq-title {
        font-size: clamp(22px, var(--arcco-title-fluid), var(--arcco-title-max));
        line-height: 0.96;
        letter-spacing: -0.04em;
        margin: 0;
      }
      .cq-body {
        font-size: clamp(13px, var(--arcco-body-fluid), var(--arcco-body-max-size));
        line-height: 1.35;
        margin: 0;
        opacity: 0.88;
        max-inline-size: var(--arcco-body-max);
      }
      .cq-kicker {
        font-size: clamp(11px, 1cqw, 18px);
        letter-spacing: 0.18em;
        text-transform: uppercase;
        opacity: 0.6;
      }
      .content-shell.is-vertical,
      .format-ig-story .content-shell,
      .format-ig-post-portrait .content-shell,
      .format-a4 .content-shell {
        grid-template-columns: 1fr;
        grid-template-rows: auto minmax(0, 1fr);
      }
      .format-ig-post-square {
        --arcco-copy-max: min(100%, 18ch);
        --arcco-body-max: min(100%, 28ch);
        --arcco-title-fluid: 4.05cqw;
        --arcco-title-max: 66px;
        --arcco-body-fluid: 1.35cqw;
        --arcco-body-max-size: 22px;
      }
      .format-ig-post-portrait,
      .format-ig-story {
        --arcco-copy-max: min(100%, 16ch);
        --arcco-body-max: min(100%, 22ch);
        --arcco-copy-align: center;
        --arcco-copy-items: center;
      }
      .format-ig-post-portrait {
        --arcco-title-fluid: 3.8cqw;
        --arcco-title-max: 58px;
        --arcco-body-fluid: 1.25cqw;
        --arcco-body-max-size: 20px;
      }
      .format-ig-story {
        --arcco-title-fluid: 3.4cqw;
        --arcco-title-max: 54px;
        --arcco-body-fluid: 1.15cqw;
        --arcco-body-max-size: 18px;
      }
      .format-a4 {
        --arcco-copy-max: min(100%, 24ch);
        --arcco-body-max: min(100%, 36ch);
        --arcco-title-fluid: 4.2cqw;
        --arcco-title-max: 70px;
      }
      .format-slide-16-9 {
        --arcco-copy-max: min(100%, 20ch);
        --arcco-body-max: min(100%, 30ch);
        --arcco-title-fluid: 3.6cqw;
        --arcco-title-max: 62px;
      }
      @container (max-width: 760px) {
        .content-shell {
          grid-template-columns: 1fr;
          grid-template-rows: auto minmax(0, 1fr);
        }
        .content-card {
          min-height: 34cqh;
        }
      }
      @container (max-width: 520px) {
        .content-shell {
          padding: max(18px, 5.2cqw);
          gap: max(16px, 3cqw);
        }
        .content-actions {
          gap: 10px;
        }
      }
      body[data-arcco-mode="single"] {
        min-height: calc(var(--arcco-canvas-height) + 48px);
      }
      #arcco-design-stage,
      .slide,
      .slide-container,
      [data-arcco-slide="true"],
      .container-base {
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
      }
      #arcco-design-content {
        position: relative;
        width: 100%;
        height: 100%;
        overflow: hidden;
        transform-origin: center center;
      }
      img, svg, canvas, video {
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
      }
      h1, h2, h3, h4, h5, h6, p, li, span, a, button, div {
        overflow-wrap: anywhere;
        word-break: break-word;
      }
      h1, h2, [class*="title"], [class*="headline"], [data-role="headline"] {
        text-wrap: balance;
        max-width: 100%;
      }
      [class*="subtitle"], [data-role="subheadline"], p, li {
        text-wrap: pretty;
        max-width: 100%;
      }
      #arcco-design-content :is(h1, h2, h3, h4, h5, h6, [class*="title"], [class*="headline"], [data-role="headline"]) {
        max-inline-size: var(--arcco-copy-max);
        margin-inline: auto;
      }
      #arcco-design-content :is(p, li, blockquote, [class*="subtitle"], [class*="description"], [data-role="subheadline"]) {
        max-inline-size: var(--arcco-body-max);
        margin-inline: auto;
      }
      [data-arcco-safe-block="true"] {
        max-width: calc(100% - (var(--arcco-safe-pad) * 2));
        max-height: calc(100% - (var(--arcco-safe-pad) * 2));
      }
      [data-arcco-fit="tight"] .content-shell {
        padding: max(18px, 4.4cqw);
        gap: max(14px, 2.4cqw);
      }
      [data-arcco-fit="tight"] .content-card {
        min-height: min(30cqh, 32cqw);
      }
      [data-arcco-fit="tight"] .content-copy {
        gap: max(10px, 1.2cqw);
      }
      [data-arcco-fit="tight"] .content-chip {
        font-size: clamp(11px, 1cqw, 18px);
        padding: 0.68em 0.92em;
      }
      .slide,
      .slide-container {
        scroll-snap-align: start;
      }
      @media print {
        html, body {
          background: white !important;
        }
        .container-base {
          box-shadow: none !important;
          border: none !important;
        }
      }
    </style>
  `;
}

function buildContractScript(): string {
  return `
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
          candidates.forEach(function (el) {
            const node = el;
            const root = roots.find(function (r) { return r.contains(node); }) || rootCanvas(node);
            const rootRect = root.getBoundingClientRect();
            fitText(node, rootRect);
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
  `;
}

function injectIntoHead(html: string, snippet: string): string {
  if (/<\/head>/i.test(html)) return html.replace(/<\/head>/i, `${snippet}</head>`);
  if (/<html[\s>]/i.test(html)) return html.replace(/<html([^>]*)>/i, `<html$1><head>${snippet}</head>`);
  return `${snippet}${html}`;
}

export function normalizeDesignHtml(html: string, overridePreset?: CanvasPreset): string {
  const clean = ensureHtmlDocument(stripHtmlFences(html));
  const preset = overridePreset || inferCanvasPreset(clean);
  const isSlides = isMultiSlideDesign(clean);
  const doc = new DOMParser().parseFromString(clean, 'text/html');

  if (!doc.head.querySelector('meta[charset]')) {
    const meta = doc.createElement('meta');
    meta.setAttribute('charset', 'UTF-8');
    doc.head.prepend(meta);
  }

  doc.documentElement.setAttribute('data-arcco-preset', preset);
  doc.body.setAttribute('data-arcco-mode', isSlides ? 'slides' : 'single');

  if (!isSlides && !doc.querySelector('.container-base')) {
    const scaffold = extractScaffoldContent(doc, preset);
    doc.body.innerHTML = buildAdaptiveScaffold(scaffold, preset);
  } else if (!isSlides) {
    const stage = doc.querySelector<HTMLElement>('.container-base');
    if (stage && !stage.className.includes(CANVAS_PRESETS[preset].formatClass)) {
      stage.classList.add(CANVAS_PRESETS[preset].formatClass);
    }
  }

  const styleMarkup = buildContractStyle(preset);
  const scriptMarkup = buildContractScript();
  let normalized = '<!DOCTYPE html>\n' + doc.documentElement.outerHTML;

  if (!normalized.includes('id="arcco-design-contract"')) {
    normalized = injectIntoHead(normalized, styleMarkup);
  }
  if (!normalized.includes('id="arcco-design-contract-script"')) {
    normalized = normalized.replace(/<\/body>/i, `${scriptMarkup}</body>`);
  }
  return normalized;
}
