

function pdfEscape(text: string): string {
  return text
    .replace(/\\/g, "\\\\")
    .replace(/\(/g, "\\(")
    .replace(/\)/g, "\\)")
    .replace(/[^\x20-\x7E]/g, (ch) => {
      const code = ch.charCodeAt(0);
      if (code === 9 || code === 10 || code === 13) return " ";
      return "?";
    });
}

function truncate(text: string, max: number): string {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (cleaned.length <= max) return cleaned;
  return `${cleaned.slice(0, Math.max(0, max - 3))}...`;
}

function buildPdf(
  title: string,
  headers: string[],
  rows: string[][],
  subtitle?: string,
): Uint8Array {
  const pageWidth = 842; 
  const pageHeight = 595;
  const marginX = 36;
  const marginTop = 40;
  const marginBottom = 36;
  const titleSize = 14;
  const metaSize = 9;
  const cellSize = 8;
  const rowH = 16;
  const headerH = 18;
  const usableWidth = pageWidth - marginX * 2;
  const colCount = Math.max(headers.length, 1);
  const colW = usableWidth / colCount;
  const charsPerCol = Math.max(8, Math.floor(colW / 4.6));

  const pages: string[] = [];
  let y = pageHeight - marginTop;
  let content = "";

  function flushPage() {
    pages.push(content);
    content = "";
    y = pageHeight - marginTop;
  }

  function writeText(x: number, atY: number, size: number, text: string, bold = false) {
    const font = bold ? "F2" : "F1";
    content += `BT /${font} ${size} Tf ${x.toFixed(2)} ${atY.toFixed(2)} Td (${pdfEscape(text)}) Tj ET\n`;
  }

  function drawLine(x1: number, y1: number, x2: number, y2: number) {
    content += `${x1.toFixed(2)} ${y1.toFixed(2)} m ${x2.toFixed(2)} ${y2.toFixed(2)} l S\n`;
  }

  function drawHeaderBand() {
    writeText(marginX, y, titleSize, title, true);
    y -= 16;
    const meta = subtitle || `Exported ${new Date().toLocaleString()} · ${rows.length} row(s)`;
    writeText(marginX, y, metaSize, meta);
    y -= 14;
    drawLine(marginX, y, pageWidth - marginX, y);
    y -= 12;

    for (let i = 0; i < headers.length; i++) {
      writeText(
        marginX + i * colW,
        y,
        cellSize,
        truncate(headers[i] ?? "", charsPerCol),
        true,
      );
    }
    y -= headerH;
    drawLine(marginX, y + 6, pageWidth - marginX, y + 6);
  }

  drawHeaderBand();

  for (const row of rows) {
    if (y < marginBottom + rowH) {
      flushPage();
      drawHeaderBand();
    }
    for (let i = 0; i < headers.length; i++) {
      writeText(
        marginX + i * colW,
        y,
        cellSize,
        truncate(row[i] ?? "", charsPerCol),
      );
    }
    y -= rowH;
  }

  flushPage();

  const objects: string[] = [];
  objects.push("1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n");

  const pageObjectIds: number[] = [];
  let nextId = 3;
  const fontRegularId = nextId++;
  const fontBoldId = nextId++;

  const contentIds: number[] = [];
  for (let i = 0; i < pages.length; i++) {
    contentIds.push(nextId++);
    pageObjectIds.push(nextId++);
  }

  const kids = pageObjectIds.map((id) => `${id} 0 R`).join(" ");
  objects.push(
    `2 0 obj\n<< /Type /Pages /Kids [${kids}] /Count ${pageObjectIds.length} >>\nendobj\n`,
  );
  objects.push(
    `${fontRegularId} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n`,
  );
  objects.push(
    `${fontBoldId} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n`,
  );

  for (let i = 0; i < pages.length; i++) {
    const stream = pages[i] ?? "";
    const contentId = contentIds[i]!;
    const pageId = pageObjectIds[i]!;
    objects.push(
      `${contentId} 0 obj\n<< /Length ${stream.length} >>\nstream\n${stream}endstream\nendobj\n`,
    );
    objects.push(
      `${pageId} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pageWidth} ${pageHeight}] ` +
        `/Resources << /Font << /F1 ${fontRegularId} 0 R /F2 ${fontBoldId} 0 R >> >> ` +
        `/Contents ${contentId} 0 R >>\nendobj\n`,
    );
  }

  const encoder = new TextEncoder();
  const header = encoder.encode("%PDF-1.4\n");
  const parts: Uint8Array[] = [header];
  const xrefOffsets: number[] = [0];
  let size = header.length;

  for (const obj of objects) {
    xrefOffsets.push(size);
    const bytes = encoder.encode(obj);
    parts.push(bytes);
    size += bytes.length;
  }

  let xref = `xref\n0 ${objects.length + 1}\n`;
  xref += "0000000000 65535 f \n";
  for (let i = 1; i < xrefOffsets.length; i++) {
    xref += `${String(xrefOffsets[i]).padStart(10, "0")} 00000 n \n`;
  }
  xref += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${size}\n%%EOF`;

  const xrefBytes = encoder.encode(xref);
  parts.push(xrefBytes);

  const out = new Uint8Array(size + xrefBytes.length);
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}

export function downloadPdf(
  filename: string,
  headers: string[],
  rows: string[][],
  options?: { title?: string; subtitle?: string },
) {
  const title = options?.title ?? "TradeBay export";
  const bytes = buildPdf(title, headers, rows, options?.subtitle);
  const copy = new Uint8Array(bytes.byteLength);
  copy.set(bytes);
  const blob = new Blob([copy], { type: "application/pdf" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename.endsWith(".pdf") ? filename : `${filename}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}
