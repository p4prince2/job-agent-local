import { readFile, writeFile, access } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { paths } from "./storage.mjs";

export async function loadTracker() {
  await ensureTrackerFile();
  const text = await readFile(paths.applicationsPath, "utf8");
  const parsed = JSON.parse(text);
  return Array.isArray(parsed) ? parsed : [];
}

export async function appendTrackerRecord(record) {
  return (await batchAppendTrackerRecords([record]))[0];
}

export async function batchAppendTrackerRecords(records) {
  if (!records || records.length === 0) {
    return [];
  }
  const existing = await loadTracker();
  const nextRecords = records.map((record) => ({
    id: record.id ?? randomUUID(),
    createdAt: record.createdAt ?? new Date().toISOString(),
    kind: record.kind ?? "discovery",
    ...record
  }));

  const combined = [...existing, ...nextRecords];
  await writeFile(paths.applicationsPath, JSON.stringify(combined, null, 2) + "\n", "utf8");
  return nextRecords;
}

export async function replaceTrackerRecords(records) {
  await writeFile(paths.applicationsPath, JSON.stringify(records, null, 2) + "\n", "utf8");
}

export function isDuplicateJob(existingRecords, job) {
  const fingerprint = buildFingerprint(job);
  return existingRecords.some((record) => buildFingerprint(record) === fingerprint);
}

export function buildFingerprint(job) {
  return [
    normalize(job.company),
    normalize(job.title),
    normalize(job.jobUrl ?? job.applicationUrl ?? job.source ?? ""),
    normalize(job.jobId ?? job.requisitionId ?? "")
  ].join("|");
}

export function printTracker(records) {
  if (!records.length) {
    return "No tracker records yet.\n";
  }

  return records
    .slice()
    .reverse()
    .map((record) => {
      const score = typeof record.score === "number" ? `${record.score}` : "n/a";
      const status = record.status ?? record.decision ?? "unknown";
      return `${record.createdAt ?? ""} | ${record.company ?? "Unknown"} | ${record.title ?? "Untitled"} | ${score} | ${status}`;
    })
    .join("\n") + "\n";
}

async function ensureTrackerFile() {
  try {
    await access(paths.applicationsPath);
  } catch {
    await writeFile(paths.applicationsPath, "[]\n", "utf8");
  }
}

function normalize(value) {
  return String(value ?? "").trim().toLowerCase();
}

