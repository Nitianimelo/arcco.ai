import fs from "node:fs";
import path from "node:path";
import PptxGenJS from "pptxgenjs";

function die(message) {
  process.stderr.write(`${message}\n`);
  process.exit(1);
}

const manifestPath = process.argv[2];
const outputPath = process.argv[3];

if (!manifestPath || !outputPath) {
  die("Uso: node design_source_to_pptx.mjs <manifest.json> <output.pptx>");
}

if (!fs.existsSync(manifestPath)) {
  die(`Manifest não encontrado: ${manifestPath}`);
}

const raw = fs.readFileSync(manifestPath, "utf-8");
const manifest = JSON.parse(raw);
const images = Array.isArray(manifest.images) ? manifest.images : [];
if (images.length === 0) {
  die("Manifest sem imagens para montar o PPTX.");
}

const widthPx = Number(manifest.width_px || 1920);
const heightPx = Number(manifest.height_px || 1080);
const dpi = Number(manifest.dpi || 96);

if (widthPx <= 0 || heightPx <= 0 || dpi <= 0) {
  die("Manifest inválido: width_px, height_px e dpi devem ser > 0.");
}

const layoutWIn = widthPx / dpi;
const layoutHIn = heightPx / dpi;

const pptx = new PptxGenJS();
pptx.author = "Arcco";
pptx.company = "Arcco";
pptx.subject = "Design Source Export";
pptx.title = String(manifest.title || "Apresentacao");
pptx.layout = "LAYOUT_CUSTOM";
pptx.defineLayout({ name: "LAYOUT_CUSTOM", width: layoutWIn, height: layoutHIn });

for (const imagePath of images) {
  if (!fs.existsSync(imagePath)) {
    die(`Imagem não encontrada para PPTX: ${imagePath}`);
  }
  const slide = pptx.addSlide();
  slide.addImage({
    path: path.resolve(imagePath),
    x: 0,
    y: 0,
    w: layoutWIn,
    h: layoutHIn,
  });
}

await pptx.writeFile({ fileName: outputPath });
process.stdout.write(outputPath);

