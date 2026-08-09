export function tokenize(text) {
  const words = String(text).toLowerCase().match(/[a-z0-9]+/g) ?? [];
  return new Set(words.filter((word) => word.length >= 3));
}

export function uniqueStrings(values) {
  return [...new Set(values.map((value) => String(value).trim()).filter(Boolean))];
}

export function splitBullets(text) {
  return String(text)
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.startsWith("-") || line.startsWith("*"))
    .map((line) => line.replace(/^[-*]\s*/, ""));
}

export function slugifyText(value) {
  return String(value)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export function parseIsoDateRange(text) {
  const match = String(text).match(/([A-Za-z]{3,9}\s+\d{4}).*?([A-Za-z]{3,9}\s+\d{4}|present|current)/i);
  if (!match) {
    return { months: 0 };
  }

  const start = parseMonthYear(match[1]);
  const end = /present|current/i.test(match[2]) ? new Date() : parseMonthYear(match[2]);
  if (!start || !end) {
    return { months: 0 };
  }

  const months = Math.max(0, (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth()));
  return { months: months || 0 };
}

function parseMonthYear(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

