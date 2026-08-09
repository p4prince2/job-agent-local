const pageWidth = 612;
const pageHeight = 792;
const marginLeft = 54;
const marginTop = 54;
const marginBottom = 54;
const fontSize = 11;
const lineHeight = 14;
const maxLinesPerPage = Math.floor((pageHeight - marginTop - marginBottom) / lineHeight);

export function createTextPdf({ title, lines }) {
  const safeLines = normalizeLines([title, "", ...toLineArray(lines)]);
  const pages = paginateLines(safeLines);
  const objects = [];
  const pageObjectIds = [];

  const fontObjectId = 3;
  let nextObjectId = 4;

  for (const pageLines of pages) {
    const contentObjectId = nextObjectId++;
    const pageObjectId = nextObjectId++;
    pageObjectIds.push(pageObjectId);
    objects.push(buildContentObject(contentObjectId, pageLines));
    objects.push(buildPageObject(pageObjectId, contentObjectId, fontObjectId));
  }

  const catalogObjectId = 1;
  const pagesObjectId = 2;
  const header = "%PDF-1.4\n";

  const pagesObject = `${pagesObjectId} 0 obj\n<< /Type /Pages /Kids [${pageObjectIds.map((id) => `${id} 0 R`).join(" ")}] /Count ${pageObjectIds.length} >>\nendobj\n`;
  const catalogObject = `${catalogObjectId} 0 obj\n<< /Type /Catalog /Pages ${pagesObjectId} 0 R >>\nendobj\n`;
  const fontObject = `${fontObjectId} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n`;

  const orderedObjects = [catalogObject, pagesObject, fontObject, ...objects];
  const { body, offsets } = assemblePdfBody(header, orderedObjects);
  const xref = buildXref(offsets);
  const trailer = `trailer\n<< /Size ${offsets.length + 1} /Root ${catalogObjectId} 0 R >>\nstartxref\n${body.length}\n%%EOF\n`;
  return Buffer.from(body + xref + trailer, "latin1");
}

function buildContentObject(objectId, lines) {
  const yStart = pageHeight - marginTop;
  const commands = [
    "BT",
    `/F1 ${fontSize} Tf`,
    `${lineHeight} TL`,
    `${marginLeft} ${yStart} Td`
  ];

  lines.forEach((line, index) => {
    if (index > 0) {
      commands.push("T*");
    }
    commands.push(`(${escapePdfText(line)}) Tj`);
  });
  commands.push("ET");

  const stream = commands.join("\n");
  return `${objectId} 0 obj\n<< /Length ${stream.length} >>\nstream\n${stream}\nendstream\nendobj\n`;
}

function buildPageObject(pageObjectId, contentObjectId, fontObjectId) {
  return `${pageObjectId} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pageWidth} ${pageHeight}] /Resources << /Font << /F1 ${fontObjectId} 0 R >> >> /Contents ${contentObjectId} 0 R >>\nendobj\n`;
}

function assemblePdfBody(header, objects) {
  let body = header;
  const offsets = [0];
  for (const object of objects) {
    offsets.push(body.length);
    body += object;
  }
  return { body, offsets };
}

function buildXref(offsets) {
  const lines = ["xref", `0 ${offsets.length}`, "0000000000 65535 f "];
  for (let index = 1; index < offsets.length; index += 1) {
    lines.push(`${String(offsets[index]).padStart(10, "0")} 00000 n `);
  }
  return `${lines.join("\n")}\n`;
}

function paginateLines(lines) {
  const pages = [];
  for (let index = 0; index < lines.length; index += maxLinesPerPage) {
    pages.push(lines.slice(index, index + maxLinesPerPage));
  }
  return pages.length ? pages : [[]];
}

function toLineArray(lines) {
  if (Array.isArray(lines)) {
    return lines.flatMap((line) => String(line).split(/\r?\n/));
  }
  return String(lines).split(/\r?\n/);
}

function normalizeLines(lines) {
  return lines.flatMap((line) => wrapLine(String(line)));
}

function wrapLine(line) {
  const cleaned = sanitizeText(line);
  if (!cleaned) {
    return [""];
  }

  const limit = 88;
  if (cleaned.length <= limit) {
    return [cleaned];
  }

  const wrapped = [];
  let remaining = cleaned;
  while (remaining.length > limit) {
    let breakIndex = remaining.lastIndexOf(" ", limit);
    if (breakIndex < 20) {
      breakIndex = limit;
    }
    wrapped.push(remaining.slice(0, breakIndex).trim());
    remaining = remaining.slice(breakIndex).trimStart();
  }
  if (remaining) {
    wrapped.push(remaining);
  }
  return wrapped;
}

function sanitizeText(value) {
  return String(value)
    .replace(/\r/g, "")
    .replace(/[^\x20-\x7E]/g, "?")
    .replace(/\(/g, "\\(")
    .replace(/\)/g, "\\)")
    .replace(/\\/g, "\\\\")
    .trimEnd();
}

function escapePdfText(value) {
  return sanitizeText(value);
}

