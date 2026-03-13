// Heavy libs loaded on-demand to avoid bloating the initial bundle

export interface ParsingResult {
    text: string;
    images: Blob[];
    truncated?: boolean;
}

const MAX_CHARS = 50000; // ~15k tokens Safety Limit

export const parseFileContent = async (file: File): Promise<ParsingResult> => {
    const fileType = file.type;
    const fileName = file.name.toLowerCase();

    try {
        if (fileType === 'application/pdf' || fileName.endsWith('.pdf')) {
            return await parsePDF(file);
        } else if (
            fileType === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
            fileType === 'application/vnd.ms-excel' ||
            fileName.endsWith('.xlsx') ||
            fileName.endsWith('.xls')
        ) {
            return await parseExcel(file);
        } else if (
            fileType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
            fileName.endsWith('.docx')
        ) {
            return await parseWord(file);
        } else if (fileType.startsWith('image/') || fileName.endsWith('.png') || fileName.endsWith('.jpg') || fileName.endsWith('.jpeg') || fileName.endsWith('.webp')) {
            return await parseImage(file);
        } else if (fileType.startsWith('text/') || fileName.endsWith('.txt') || fileName.endsWith('.md') || fileName.endsWith('.csv') || fileName.endsWith('.json') || fileName.endsWith('.js') || fileName.endsWith('.ts') || fileName.endsWith('.py')) {
            return await parseText(file);
        } else {
            return { text: `[Erro: Tipo de arquivo não suportado: ${fileType}]`, images: [] };
        }
    } catch (error) {
        console.error('Error parsing file:', error);
        return { text: `[Erro ao ler arquivo: ${error instanceof Error ? error.message : 'Desconhecido'}]`, images: [] };
    }
};

const parsePDF = async (file: File): Promise<ParsingResult> => {
    const pdfjsLib = await import('pdfjs-dist');
    const pdfWorker = (await import('pdfjs-dist/build/pdf.worker.min.mjs?url')).default;
    pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker;

    const arrayBuffer = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    let text = '';
    const images: Blob[] = [];
    let truncated = false;

    // Smart Scanning: Track text density per page to find "Visual Pages"
    for (let i = 1; i <= pdf.numPages; i++) {
        // Stop if we hit safety limit
        if (text.length > MAX_CHARS) {
            text = text.slice(0, MAX_CHARS) + "\n\n[...TRUNCADO POR SEGURANÇA - LIMITE DE TOKENS ATINGIDO...]";
            truncated = true;
            break;
        }

        const page = await pdf.getPage(i);
        const content = await page.getTextContent();
        const strings = content.items.map((item: any) => item.str);
        const pageText = strings.join(' ').trim();

        text += `--- Page ${i} ---\n${pageText}\n\n`;

        // Dynamic Vision Logic:
        // If page has very little text (< 200 chars) BUT has content (it's not empty),
        // it might be a chart, image, or scanned doc. Render it!
        // Limit to 3 visual pages to save tokens/bandwidth.
        if (pageText.length < 200 && pageText.length > 5 && images.length < 3) {
            // Check for image operators to be sure (optional, but good optimization)
            const ops = await page.getOperatorList();
            let hasImgOps = false;
            for (let j = 0; j < ops.fnArray.length; j++) {
                if (ops.fnArray[j] === pdfjsLib.OPS.paintImageXObject || ops.fnArray[j] === pdfjsLib.OPS.paintInlineImageXObject) {
                    hasImgOps = true;
                    break;
                }
            }

            if (hasImgOps) {
                console.log(`Dynamic Vision: Page ${i} is visual. Rendering...`);
                const viewport = page.getViewport({ scale: 1.5 });
                const canvas = document.createElement('canvas');
                const context = canvas.getContext('2d');
                if (context) {
                    canvas.height = viewport.height;
                    canvas.width = viewport.width;
                    await page.render({ canvasContext: context, viewport: viewport } as any).promise;
                    const blob = await new Promise<Blob | null>(r => canvas.toBlob(r, 'image/png'));
                    if (blob) images.push(blob);
                }
            }
        }
    }

    // Heuristic for Scanned Docs (Global)
    if (text.length < 500 && images.length === 0 && pdf.numPages > 0) {
        // Likely a full scan without OCR layer. Render Page 1 at least.
        console.log("PDF seems scanned. Rendering Page 1 fallback.");
        const page = await pdf.getPage(1);
        const viewport = page.getViewport({ scale: 1.5 });
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        if (context) {
            canvas.height = viewport.height;
            canvas.width = viewport.width;
            await page.render({ canvasContext: context, viewport: viewport } as any).promise;
            const blob = await new Promise<Blob | null>(r => canvas.toBlob(r, 'image/png'));
            if (blob) images.push(blob);
        }
        text += "\n[AVISO: Documento escaneado detectado. Visualização enviada.]";
    }

    return { text, images, truncated };
};

const parseImage = async (file: File): Promise<ParsingResult> => {
    // For images, we return the text (OCR) AND the image itself (Logic in ArccoChat will handle upload)
    // But wait, parseImage usually does OCR locally. 
    // In Hybrid mode, we want to send the Image URL to Vision.
    // So we return text="[Imagem Anexada]" and images=[file]
    // But existing logic might rely on OCR text. Let's keep OCR as backup text.

    // We can just return the file blob as an image to be uploaded.
    return {
        text: "[Imagem preparada para Vision AI]",
        images: [file] // ArccoChat will upload this
    };
};

const parseExcel = async (file: File): Promise<ParsingResult> => {
    const XLSX = await import('xlsx');
    const arrayBuffer = await file.arrayBuffer();
    const workbook = XLSX.read(arrayBuffer, { type: 'array' });
    let text = '';
    let truncated = false;

    for (const sheetName of workbook.SheetNames) {
        if (text.length > MAX_CHARS) {
            text += "\n\n[...TRUNCADO...]";
            truncated = true;
            break;
        }
        const sheet = workbook.Sheets[sheetName];
        const jsonData = XLSX.utils.sheet_to_json(sheet, { header: 1 });

        text += `### Planilha: ${sheetName}\n\n`;

        if (jsonData.length > 0) {
            const headers = jsonData[0] as any[];
            text += `| ${headers.join(' | ')} |\n`;
            text += `| ${headers.map(() => '---').join(' | ')} |\n`;

            for (let i = 1; i < jsonData.length; i++) {
                if (text.length > MAX_CHARS) break;
                const row = jsonData[i] as any[];
                const safeRow = headers.map((_, idx) => row[idx] || '');
                text += `| ${safeRow.join(' | ')} |\n`;
            }
        }
        text += '\n\n';
    }
    return { text, images: [], truncated };
};

const parseWord = async (file: File): Promise<ParsingResult> => {
    const mammoth = (await import('mammoth')).default;
    const arrayBuffer = await file.arrayBuffer();
    const result = await mammoth.extractRawText({ arrayBuffer });
    let text = `[CONTEÚDO DO DOCUMENTO WORD]\n\n${result.value}`;

    let truncated = false;
    if (text.length > MAX_CHARS) {
        text = text.slice(0, MAX_CHARS) + "\n\n[...TRUNCADO...]";
        truncated = true;
    }

    return { text, images: [], truncated };
};

const parseText = async (file: File): Promise<ParsingResult> => {
    let text = await file.text();
    let truncated = false;

    if (text.length > MAX_CHARS) {
        text = text.slice(0, MAX_CHARS) + "\n\n[...TRUNCADO...]";
        truncated = true;
    }
    return { text, images: [], truncated };
};

// Removed renderPdfFirstPage export as it is now integrated into parsePDF logic 
// or we can keep it if needed by other components, but logic is now inside parsePDF dynamic vision.
export const renderPdfFirstPage = async (file: File): Promise<Blob | null> => {
    // Kept for backward compatibility if ArccoChat imports it directly
    const res = await parsePDF(file);
    return res.images[0] || null;
};
