import { tokenize, uniqueStrings } from "./utils.mjs";

const roleSignals = ["ai", "ml", "machine learning", "llm", "genai", "generative ai", "rag", "agent", "python", "nlu", "nlp"];

export function scoreJobMatch({ job, resume, profile }) {
  const jobText = `${job.title}\n${job.description}\n${job.location}\n${(job.tags ?? []).join(" ")}`;
  const resumeText = `${resume.summary}\n${resume.skills.join(" ")}\n${resume.projects.map((item) => item.title).join(" ")}\n${profile.summary ?? ""}`;

  const jobTokens = tokenize(jobText);
  const resumeTokens = tokenize(resumeText);
  const overlap = intersectionSize(jobTokens, resumeTokens);
  const skillOverlap = overlap / Math.max(jobTokens.size, 1);
 
  const matchingSkills = pickMatches(resume.skills, jobText);
  const missingSkills = pickMissing(profile, jobText);
  const roleFit = roleSignals.some((signal) => jobText.toLowerCase().includes(signal)) ? 1 : 0;
  const remoteFit = /remote/i.test(job.location || job.description || "") ? 1 : 0;
  const indiaFit = /india|hyderabad|bengaluru|bangalore|pune|delhi|gurgaon|gurugram|noida|mumbai|chennai/i.test(job.location || job.description || "") ? 1 : 0;
  const experienceFit = estimateExperienceFit(job.description, resume.monthsExperience);

  const rawScore =
    skillOverlap * 45 +
    roleFit * 20 +
    remoteFit * 10 +
    indiaFit * 10 +
    experienceFit * 15;

  const score = Math.max(0, Math.min(100, Math.round(rawScore)));
  const decision = score >= 75 ? "apply" : score >= 55 ? "review" : "skip";

  return {
    score,
    decision,
    matchingSkills,
    missingSkills,
    reason: buildReason(score, matchingSkills, missingSkills, job),
    experienceRequirement: extractExperienceRequirement(job.description),
    myRelevantExperience: summarizeRelevantExperience(resume),
    locationFit: remoteFit || indiaFit
  };
}

function pickMatches(resumeSkills, jobText) {
  const normalizedJob = jobText.toLowerCase();
  return uniqueStrings(
    resumeSkills.filter((skill) => normalizedJob.includes(String(skill).toLowerCase()))
  );
}

function pickMissing(profile, jobText) {
  const normalizedJob = jobText.toLowerCase();
  const important = [
    ...(Array.isArray(profile?.target_roles) ? profile.target_roles : []),
    ...(Array.isArray(profile?.strengths) ? profile.strengths : [])
  ];

  return uniqueStrings(
    important.filter((item) => !normalizedJob.includes(String(item).toLowerCase()))
  ).slice(0, 8);
}

function estimateExperienceFit(description, monthsExperience) {
  const yearMatch = String(description).match(/(\d+)\+?\s+years?/i);
  if (!yearMatch) {
    return 1;
  }

  const years = Number(yearMatch[1]);
  const requiredMonths = years * 12;
  if (!Number.isFinite(requiredMonths) || requiredMonths <= 0) {
    return 1;
  }

  if (monthsExperience >= requiredMonths) {
    return 1;
  }

  const ratio = monthsExperience / requiredMonths;
  return Math.max(0, ratio);
}

function extractExperienceRequirement(description) {
  const match = String(description).match(/(\d+\+?\s+years?[^.\n]*)/i);
  return match?.[1] ?? "";
}

function summarizeRelevantExperience(resume) {
  const items = [];
  for (const experience of resume.experience ?? []) {
    if (experience.title) {
      items.push(`${experience.title}${experience.company ? ` at ${experience.company}` : ""}`);
    }
  }
  return items.slice(0, 3).join("; ");
}

function buildReason(score, matchingSkills, missingSkills, job) {
  if (score >= 75) {
    return `Strong match for ${job.title} with overlap in ${matchingSkills.slice(0, 3).join(", ") || "core skills"}.`;
  }
  if (score >= 55) {
    return `Related role, but there are gaps in ${missingSkills.slice(0, 3).join(", ") || "some requirements"}.`;
  }
  return `Low fit against the current resume for ${job.title}.`;
}

function intersectionSize(a, b) {
  let count = 0;
  for (const item of a) {
    if (b.has(item)) {
      count += 1;
    }
  }
  return count;
}

