import { mkdir, readFile, writeFile, access, readdir, stat } from "node:fs/promises";
import { dirname, join } from "node:path";
import { randomUUID } from "node:crypto";

const root = process.cwd();
const dataDir = join(root, "data");
const outputDir = join(root, "output");
const applicationsPath = join(dataDir, "applications.json");
const profilePath = join(dataDir, "profile.json");
const resumePath = join(dataDir, "resume.md");

export const paths = {
  root,
  dataDir,
  outputDir,
  applicationsPath,
  profilePath,
  resumePath
};

export async function ensureProjectFiles({ forceExamples }) {
  await mkdir(dataDir, { recursive: true });
  await mkdir(outputDir, { recursive: true });

  if (forceExamples || !(await exists(profilePath))) {
    await writeFile(profilePath, JSON.stringify(await defaultProfile(), null, 2) + "\n", "utf8");
  }

  if (forceExamples || !(await exists(resumePath))) {
    await writeFile(resumePath, defaultResume(), "utf8");
  }

  if (!(await exists(applicationsPath))) {
    await writeFile(applicationsPath, "[]\n", "utf8");
  }
}

export async function loadProfile() {
  const text = await readFile(profilePath, "utf8");
  return JSON.parse(text);
}

export async function loadResume() {
  return readFile(resumePath, "utf8");
}

export async function readApplications() {
  await ensureProjectFiles({ forceExamples: false });
  const text = await readFile(applicationsPath, "utf8");
  return JSON.parse(text);
}

export function printApplications(applications) {
  if (applications.length === 0) {
    return "No saved applications yet.\n";
  }

  return applications
    .slice()
    .reverse()
    .map((item) => `${item.createdAt} | ${item.company} | ${item.title} | score ${item.score?.toFixed?.(1) ?? item.score ?? "n/a"} | ${item.decision}`)
    .join("\n") + "\n";
}

export async function writeApplicationRecord(packet) {
  const applications = await readApplications();
  const record = {
    id: randomUUID(),
    createdAt: new Date().toISOString(),
    company: packet.job.company,
    title: packet.job.title,
    source: packet.job.source,
    score: packet.analysis.score,
    decision: packet.analysis.decision,
    outputDir: packet.outputDir
  };

  applications.push(record);
  await writeFile(applicationsPath, JSON.stringify(applications, null, 2) + "\n", "utf8");
  return record;
}

export async function savePacket(outputDirPath, files) {
  await mkdir(outputDirPath, { recursive: true });
  for (const [name, content] of Object.entries(files)) {
    const filePath = join(outputDirPath, name);
    if (Buffer.isBuffer(content) || content instanceof Uint8Array) {
      await writeFile(filePath, content);
    } else {
      await writeFile(filePath, content, "utf8");
    }
  }
}

export async function loadLatestPacket() {
  const latestOutputDir = await getLatestOutputDir();
  if (!latestOutputDir) {
    throw new Error("No output packet found. Run `draft` first.");
  }

  const text = await readFile(join(latestOutputDir, "analysis.json"), "utf8");
  const packet = JSON.parse(text);
  return {
    ...packet,
    outputDir: latestOutputDir
  };
}

async function getLatestOutputDir() {
  if (!(await exists(outputDir))) {
    return null;
  }

  const entries = await readdir(outputDir, { withFileTypes: true });
  const directories = [];

  for (const entry of entries) {
    if (!entry.isDirectory()) {
      continue;
    }
    const fullPath = join(outputDir, entry.name);
    const stats = await stat(fullPath);
    directories.push({ path: fullPath, mtimeMs: stats.mtimeMs });
  }

  directories.sort((left, right) => right.mtimeMs - left.mtimeMs);
  return directories[0]?.path ?? null;
}

export function buildOutputDir(job) {
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const slug = slugify(`${job.company}-${job.title}`) || "job";
  return join(outputDir, `${stamp}-${slug}`);
}

async function exists(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

async function defaultProfile() {
  return {
    name: "Your Name",
    headline: "AI / Automation / Product",
    location: "Remote",
    target_roles: ["AI Engineer", "Agent Engineer", "Product Engineer"],
    summary: "Short summary of your background, strengths, and the kind of roles you want.",
    strengths: ["Built automation workflows", "Worked with LLM APIs", "Shipped user-facing products"],
    must_haves: ["Remote work", "Good compensation", "Interesting technical problem"],
    deal_breakers: ["Low-quality hiring process", "No clear role scope"]
  };
}

function defaultResume() {
  return [
    "# Your Name",
    "",
    "## Summary",
    "",
    "Write a short professional summary here.",
    "",
    "## Experience",
    "",
    "### Company Name - Role",
    "",
    "- Impact statement",
    "- Another achievement",
    "",
    "## Skills",
    "",
    "- Node.js",
    "- Python",
    "- LLM workflows",
    ""
  ].join("\n");
}

function slugify(value) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

