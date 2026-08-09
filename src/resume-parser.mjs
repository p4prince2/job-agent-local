import { parseIsoDateRange, splitBullets, uniqueStrings } from "./utils.mjs";

export function parseResume({ profile, resumeMarkdown }) {
  const sections = splitResumeSections(resumeMarkdown);
  const experience = parseExperienceSection(sections.Experience ?? "");
  const projects = parseProjectsSection(sections.Projects ?? "");
  const skills = parseSkillsSection(sections.Skills ?? "", profile);
  const education = parseEducationSection(sections.Education ?? "");

  return {
    name: profile.name ?? "",
    headline: profile.headline ?? "",
    summary: sections.Summary?.trim() || profile.summary || "",
    education,
    experience,
    projects,
    skills,
    yearsExperience: estimateExperienceMonths(experience) / 12,
    monthsExperience: estimateExperienceMonths(experience),
    rawSections: sections
  };
}

function splitResumeSections(markdown) {
  const lines = String(markdown).replace(/\r\n/g, "\n").split("\n");
  const sections = {};
  let current = "Preamble";

  for (const line of lines) {
    const heading = line.match(/^##\s+(.+)$/);
    if (heading) {
      current = heading[1].trim();
      sections[current] = sections[current] ? `${sections[current]}\n` : "";
      continue;
    }
    sections[current] = `${sections[current] ?? ""}${line}\n`;
  }

  return sections;
}

function parseExperienceSection(sectionText) {
  const lines = String(sectionText).split("\n").map((line) => line.trim()).filter(Boolean);
  const experiences = [];
  let current = null;

  for (const line of lines) {
    const cleanLine = line.replace(/\*\*/g, "").trim();
    const heading = cleanLine.match(/^###\s+(.+)$/);
    if (heading && !line.startsWith("- ")) {
      if (current) {
        experiences.push(current);
      }
      const headingText = heading[1].trim();
      const parts = headingText.split(/\s+[—–-]\s+/);
      current = {
        title: parts[parts.length - 1].trim(),
        company: parts.length > 1 ? parts[0].trim() : "",
        bullets: [],
        dates: ""
      };
      continue;
    }

    const dateMatch = cleanLine.match(/([A-Za-z]{3,9}\s+\d{4})\s*[–—-]\s*([A-Za-z]{3,9}\s+\d{4}|present|current)/i);
    if (current && dateMatch && !current.dates) {
      current.dates = cleanLine;
      continue;
    }

    if (current && cleanLine.startsWith("*")) {
      current.bullets.push(cleanLine.replace(/^\*\s*/, ""));
      continue;
    }

    if (current && cleanLine.startsWith("-")) {
      current.bullets.push(cleanLine.replace(/^-+\s*/, ""));
      continue;
    }
  }

  if (current) {
    experiences.push(current);
  }

  return experiences.map((item) => {
    const range = parseIsoDateRange(item.dates || item.title);
    return {
      title: item.title,
      company: item.company ?? "",
      dates: item.dates ?? "",
      months: range.months,
      bullets: item.bullets
    };
  });
}

function parseProjectsSection(sectionText) {
  const lines = String(sectionText).split("\n");
  const projects = [];
  let current = null;

  for (const rawLine of lines) {
    const line = rawLine.trim();
    const heading = line.match(/^###\s+(.+)$/);
    if (heading) {
      if (current) {
        projects.push(current);
      }
      current = { title: heading[1].trim(), bullets: [] };
      continue;
    }

    if (!current) {
      continue;
    }

    if (line.startsWith("-") || line.startsWith("*")) {
      current.bullets.push(line.replace(/^[-*]\s*/, ""));
    }
  }

  if (current) {
    projects.push(current);
  }

  return projects;
}

function parseSkillsSection(sectionText, profile) {
  const fromResume = splitBullets(sectionText).flatMap((item) => normalizeSkillLine(item));
  const fromProfile = Array.isArray(profile?.strengths) ? profile.strengths : [];
  const fromTargetRoles = Array.isArray(profile?.target_roles) ? profile.target_roles : [];
  return uniqueStrings([...fromResume, ...fromProfile, ...fromTargetRoles]).map((item) => item.trim());
}

function parseEducationSection(sectionText) {
  return splitBullets(sectionText);
}

function estimateExperienceMonths(experience) {
  return experience.reduce((total, item) => total + (Number.isFinite(item.months) ? item.months : 0), 0);
}

function normalizeSkillLine(line) {
  return String(line)
    .replace(/\*\*/g, "")
    .replace(/^[^:]+:\s*/, "")
    .split(/[,/|]/)
    .map((item) => item.trim())
    .filter(Boolean);
}
