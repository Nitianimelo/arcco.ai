"""
Exportação backend de design source (arcco.design-source/v1).

Fluxo:
- Source JSON (fonte da verdade)
- Render em canvas via Fabric.js no Playwright (backend)
- Export para PNG/PDF
- Export para PPTX via pptxgenjs (Node no backend)
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import subprocess
import tempfile
import zipfile
from functools import lru_cache
from pathlib import Path
from typing import Optional

from backend.services.design_source_contract import (
    DesignSourceDocument,
    frame_to_fabric_json,
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def _load_fabric_bundle() -> str:
    candidates = [
        _project_root() / "backend" / "js" / "node_modules" / "fabric" / "dist" / "fabric.min.js",
        _project_root() / "node_modules" / "fabric" / "dist" / "fabric.min.js",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    raise RuntimeError(
        "Fabric.js não encontrado no backend. Instale dependências JS em backend/js "
        "para habilitar export de design-source."
    )


def _build_frame_html(doc: DesignSourceDocument, frame_index: int) -> str:
    frame = doc.frames[frame_index]
    scene = frame_to_fabric_json(frame, doc.canvas)
    fabric_js = _load_fabric_bundle()
    scene_json = json.dumps(scene, ensure_ascii=False)
    title = (doc.title or "Design Source").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width={doc.canvas.width}, initial-scale=1" />
  <title>{title}</title>
  <style>
    html, body {{
      margin: 0;
      padding: 0;
      width: {doc.canvas.width}px;
      height: {doc.canvas.height}px;
      overflow: hidden;
      background: transparent;
    }}
    #arcco-canvas {{
      display: block;
      width: {doc.canvas.width}px;
      height: {doc.canvas.height}px;
    }}
  </style>
</head>
<body>
  <canvas id="arcco-canvas" width="{doc.canvas.width}" height="{doc.canvas.height}"></canvas>
  <script>{fabric_js}</script>
  <script>
    window.__ARCCO_READY__ = false;
    (function() {{
      try {{
        const scene = {scene_json};
        const canvas = new fabric.StaticCanvas('arcco-canvas', {{
          width: {doc.canvas.width},
          height: {doc.canvas.height},
          renderOnAddRemove: false,
          selection: false
        }});
        canvas.loadFromJSON(scene, function() {{
          canvas.renderAll();
          window.__ARCCO_READY__ = true;
        }});
        setTimeout(function() {{
          if (!window.__ARCCO_READY__) window.__ARCCO_READY__ = true;
        }}, 15000);
      }} catch (e) {{
        console.error('fabric-render-error', e);
        window.__ARCCO_READY__ = true;
      }}
    }})();
  </script>
</body>
</html>"""


def _render_png_frames_sync(doc: DesignSourceDocument, frame_indexes: list[int]) -> list[bytes]:
    from playwright.sync_api import sync_playwright

    images: list[bytes] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            page = browser.new_page(viewport={"width": doc.canvas.width, "height": doc.canvas.height})
            for frame_index in frame_indexes:
                page.set_viewport_size({"width": doc.canvas.width, "height": doc.canvas.height})
                page.set_content(_build_frame_html(doc, frame_index), wait_until="domcontentloaded", timeout=45_000)
                page.wait_for_function("window.__ARCCO_READY__ === true", timeout=30_000)
                images.append(page.screenshot(type="png", full_page=False))
        finally:
            browser.close()
    return images


async def render_design_source_png(
    source: dict,
    frame_index: Optional[int] = None,
) -> bytes | tuple[bytes, str, str]:
    doc = DesignSourceDocument.model_validate(source)
    if not doc.frames:
        raise ValueError("Design source sem frames para exportar.")

    if frame_index is None:
        indexes = list(range(len(doc.frames)))
    else:
        bounded = max(0, min(frame_index, len(doc.frames) - 1))
        indexes = [bounded]

    images = await asyncio.to_thread(_render_png_frames_sync, doc, indexes)
    if len(images) == 1:
        return images[0]

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, image_bytes in enumerate(images, start=1):
            zf.writestr(f"frame_{idx}.png", image_bytes)
    return zip_buf.getvalue(), "application/zip", "zip"


async def render_design_source_pdf(
    source: dict,
    frame_index: Optional[int] = None,
) -> bytes:
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as pdf_canvas

    doc = DesignSourceDocument.model_validate(source)
    if not doc.frames:
        raise ValueError("Design source sem frames para exportar.")

    if frame_index is None:
        indexes = list(range(len(doc.frames)))
    else:
        bounded = max(0, min(frame_index, len(doc.frames) - 1))
        indexes = [bounded]

    images = await asyncio.to_thread(_render_png_frames_sync, doc, indexes)

    page_w = doc.canvas.width * 72.0 / max(doc.canvas.dpi, 1)
    page_h = doc.canvas.height * 72.0 / max(doc.canvas.dpi, 1)
    out = io.BytesIO()
    c = pdf_canvas.Canvas(out, pagesize=(page_w, page_h))
    for img_bytes in images:
        c.drawImage(ImageReader(io.BytesIO(img_bytes)), 0, 0, width=page_w, height=page_h)
        c.showPage()
    c.save()
    return out.getvalue()


async def render_design_source_pptx(
    source: dict,
    title: str = "Apresentacao",
    frame_index: Optional[int] = None,
) -> bytes:
    doc = DesignSourceDocument.model_validate(source)
    if not doc.frames:
        raise ValueError("Design source sem frames para exportar.")

    if frame_index is None:
        indexes = list(range(len(doc.frames)))
    else:
        bounded = max(0, min(frame_index, len(doc.frames) - 1))
        indexes = [bounded]

    images = await asyncio.to_thread(_render_png_frames_sync, doc, indexes)

    script_path = _project_root() / "backend" / "js" / "design_source_to_pptx.mjs"
    if not script_path.exists():
        raise RuntimeError("Script de export PPTX (pptxgenjs) não encontrado.")

    with tempfile.TemporaryDirectory(prefix="arcco-source-pptx-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        image_paths: list[str] = []
        for idx, image_bytes in enumerate(images, start=1):
            frame_path = tmp_path / f"frame_{idx}.png"
            frame_path.write_bytes(image_bytes)
            image_paths.append(str(frame_path))

        manifest = {
            "title": title,
            "width_px": doc.canvas.width,
            "height_px": doc.canvas.height,
            "dpi": doc.canvas.dpi,
            "images": image_paths,
        }
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        output_path = tmp_path / "output.pptx"

        cmd = ["node", str(script_path), str(manifest_path), str(output_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            stdout = (proc.stdout or "").strip()
            raise RuntimeError(
                "Falha no export PPTX via pptxgenjs. "
                f"stdout='{stdout[:400]}' stderr='{stderr[:400]}'"
            )
        if not output_path.exists():
            raise RuntimeError("PPTX não foi gerado pelo script pptxgenjs.")
        return output_path.read_bytes()

