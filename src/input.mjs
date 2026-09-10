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
      "user-agent": "job-agent-local/0.1 (compatible; local job application bot)"
    }
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch job URL: ${response.status} ${response.statusText}`);
  }

  const html = await response.text();
  const titleHint = extractTitleFromHtml(html);
  const companyHint = extractCompanyFromHtml(html, url);
  const text = stripHtml(html);
  return buildJobFromText(text, url, { titleHint, companyHint });
}

export function buildJobFromText(text, source, hints = {}) {
  const cleanText = normalizeWhitespace(text);
  const title = hints.titleHint || extractFirstLine(cleanText) || "Untitled role";
  const company = hints.companyHint || inferCompany(cleanText, source);
  return {
    source,
    title,
    company,
    text: cleanText
  };
}

export function looksLikeUrl(value) {
  return /^https?:\/\//i.test(value);
}

export function normalizeWhitespace(text) {
  return text
    .replace(/\r\n/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function extractFirstLine(text) {
  return text.split("\n").map((line) => line.trim()).find(Boolean) ?? "";
}

export function inferCompany(text, source = "") {
  const match = text.match(/\b(?:at|at\s+the|with|join)\s+([A-Z][A-Za-z0-9&.-]{1,40})/);
  if (match?.[1]) {
    return match[1];
  }

  if (source && looksLikeUrl(source)) {
    try {
      const hostname = new URL(source).hostname.replace(/^www\./, "");
      const part = hostname.split(".")[0];
      if (part && part.length > 2) {
        return part.charAt(0).toUpperCase() + part.slice(1);
      }
    } catch {}
  }

  return "Unknown company";
}

export function extractTitleFromHtml(html) {
  const ogTitleMatch = html.match(/<meta\s+[^>]*property=["']og:title["'][^>]*content=["']([^"']+)["']/i) ||
    html.match(/<meta\s+[^>]*content=["']([^"']+)["'][^>]*property=["']og:title["']/i);
  if (ogTitleMatch?.[1]) {
    return cleanTitle(ogTitleMatch[1]);
  }

  const h1Match = html.match(/<h1[^>]*>([\s\S]*?)<\/h1>/i);
  if (h1Match?.[1]) {
    const text = stripHtml(h1Match[1]);
    if (text && text.length < 120) {
      return cleanTitle(text);
    }
  }

  const titleTagMatch = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  if (titleTagMatch?.[1]) {
    return cleanTitle(stripHtml(titleTagMatch[1]));
  }

  return "";
}

function cleanTitle(raw) {
  const clean = raw
    .replace(/\s*[-|–—•]\s*(?:careers?|jobs?|linkedin|greenhouse|lever|workday|remote).*$/i, "")
    .trim();
  return clean || raw.trim();
}

export function extractCompanyFromHtml(html, url = "") {
  const ogSiteMatch = html.match(/<meta\s+[^>]*property=["']og:site_name["'][^>]*content=["']([^"']+)["']/i) ||
    html.match(/<meta\s+[^>]*content=["']([^"']+)["'][^>]*property=["']og:site_name["']/i);
  if (ogSiteMatch?.[1]) {
    return ogSiteMatch[1].trim();
  }

  if (url && looksLikeUrl(url)) {
    try {
      const host = new URL(url).hostname.replace(/^www\./, "");
      const name = host.split(".")[0];
      if (name && name.length > 1) {
        return name.charAt(0).toUpperCase() + name.slice(1);
      }
    } catch {}
  }

  return "";
}

export function stripHtml(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<noscript[\s\S]*?<\/noscript>/gi, " ")
    .replace(/<svg[\s\S]*?<\/svg>/gi, " ")
    .replace(/<nav[\s\S]*?<\/nav>/gi, " ")
    .replace(/<footer[\s\S]*?<\/footer>/gi, " ")
    .replace(/<header[\s\S]*?<\/header>/gi, " ")
    .replace(/<(?:br\s*\/?|\/?p|\/?div|\/?h[1-6]|\/?li|\/?tr|\/?section|\/?article)>/gi, "\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, "\"")
    .replace(/&#39;/gi, "'")
    .replace(/&mdash;/gi, " - ")
    .replace(/&ndash;/gi, "-")
    .replace(/[ \t]+/g, " ")
    .replace(/\n\s*\n+/g, "\n\n")
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

