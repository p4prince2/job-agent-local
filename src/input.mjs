import { access, readFile, stat } from "node:fs/promises";
import { isAbsolute, resolve } from "node:path";

export async function resolveInput(value) {
  if (looksLikeUrl(value)) {
    return fetchJobUrl(value);
  }

  if (value === "-") {
    return readStdin();
  }

  const maybeFile = isAbsolute(value) ? value : resolve(process.cwd(), value);
  if (await isReadableFile(maybeFile)) {
    const content = await readFile(maybeFile, "utf8");
    return buildJobFromText(content, maybeFile); 
  }

  return buildJobFromText(value, "pasted-text");
}

async function fetchJobUrl(url) {
  const response = await fetch(url, {
    headers: {
      "user-agent": "job-agent-local/0.1"
    }
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch job URL: ${response.status} ${response.statusText}`);
  }

  const html = await response.text();
  const text = stripHtml(html);
  return buildJobFromText(text, url);
}

function buildJobFromText(text, source) {
  const cleanText = normalizeWhitespace(text);
  const title = extractFirstLine(cleanText) || "Untitled role";
  const company = inferCompany(cleanText);
  return {
    source,
    title,
    company,
    text: cleanText
  };
}

function looksLikeUrl(value) {
  return /^https?:\/\//i.test(value);
}

function normalizeWhitespace(text) {
  return text.replace(/\r\n/g, "\n").replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
}

function extractFirstLine(text) {
  return text.split("\n").map((line) => line.trim()).find(Boolean) ?? "";
}

function inferCompany(text) {
  const match = text.match(/\b(at|at\s+the)\s+([A-Z][A-Za-z0-9&.-]{1,40})/);
  return match?.[2] ?? "Unknown company";
}

function stripHtml(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, "\"")
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, " ")
    .trim();
}

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  return buildJobFromText(Buffer.concat(chunks).toString("utf8"), "stdin");
}

async function isReadableFile(path) {
  try {
    await access(path);
    return (await stat(path)).isFile();
  } catch {
    return false;
  }
}

