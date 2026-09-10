import { loadProfile, loadResume } from "./storage.mjs";
import { parseResume } from "./resume-parser.mjs";
import { fetchJobsForQuery } from "./job-sources.mjs";
import { scoreJobMatch } from "./matcher.mjs";
import { batchAppendTrackerRecords, isDuplicateJob, loadTracker } from "./tracker.mjs";

export async function searchJobs({ query, limit = 20 }) {
  const profile = await loadProfile();
  const resumeMarkdown = await loadResume();
  const resume = parseResume({ profile, resumeMarkdown });
  const tracker = await loadTracker();
  const searchQuery = query || buildDefaultQuery(profile);
  const { jobs, diagnostics } = await fetchJobsForQuery(searchQuery, { profile, resume });
  const newRecords = [];

  for (const job of jobs.slice(0, limit * 2)) {
    const match = scoreJobMatch({ job, resume, profile });
    const status = match.decision === "apply" ? "REVIEW" : match.decision === "review" ? "REVIEW" : "SKIPPED";

    const record = {
      kind: "discovery",
      company: job.company,
      title: job.title,
      location: job.location,
      remote: job.remote,
      jobUrl: job.jobUrl,
      applicationUrl: job.applicationUrl,
      source: job.source,
      sourceJobId: job.jobId,
      createdAt: job.createdAt || new Date().toISOString(),
      discoveredAt: new Date().toISOString(),
      status,
      score: match.score,
      matchingSkills: match.matchingSkills,
      missingSkills: match.missingSkills,
      experienceRequirement: match.experienceRequirement,
      myRelevantExperience: match.myRelevantExperience,
      notes: match.reason
    };

    if (isDuplicateJob([...tracker, ...newRecords], record)) {
      continue;
    }

    newRecords.push(record);
  }

  const results = await batchAppendTrackerRecords(newRecords);

  const strongMatches = results.filter((item) => Number(item.score) >= 75);
  const skipped = results.filter((item) => item.status === "SKIPPED");
  const review = results.filter((item) => item.status === "REVIEW");

  return {
    query: searchQuery,
    resume,
    diagnostics,
    results,
    strongMatches,
    skipped,
    review,
    report: buildReport({ query: searchQuery, results, strongMatches, skipped, review, resume, diagnostics })
  };
}

function buildDefaultQuery(profile) {
  const terms = Array.isArray(profile.target_roles) && profile.target_roles.length ? profile.target_roles : ["AI Engineer"];
  return terms.slice(0, 4).join(" OR ");
}

function buildReport({ query, results, strongMatches, skipped, review, resume, diagnostics }) {
  const missingSkills = collectMissingSkills(results);
  const sourceLines = buildSourceLines(diagnostics);
  const top = results
    .slice()
    .sort((left, right) => Number(right.score) - Number(left.score))
    .slice(0, 10)
    .map((item) => `${item.company} | ${item.title} | ${item.score} | ${item.location} | ${item.status}`)
    .join("\n");

  return [
    `# Search Report`,
    "",
    `Query: ${query}`,
    `Jobs found: ${results.length}`,
    `Strong matches: ${strongMatches.length}`,
    `Review list: ${review.length}`,
    `Skipped: ${skipped.length}`,
    "",
    "## Sources",
    "",
    ...(sourceLines.length ? sourceLines : ["- No source diagnostics available."]),
    "",
    "## Top Applications",
    "",
    top || "No results found.",
    "",
    "## Common Missing Skills",
    "",
    ...(missingSkills.length ? missingSkills.map((item) => `- ${item}`) : ["- None recorded yet"]),
    "",
    "## Resume Snapshot",
    "",
    `- Experience entries: ${resume.experience.length}`,
    `- Projects: ${resume.projects.length}`,
    `- Skills extracted: ${resume.skills.length}`,
    ""
  ].join("\n");
}

function buildSourceLines(diagnostics = []) {
  return diagnostics.map((item) =>
    item.ok
      ? `- ${item.source}: ok (${item.count} jobs)`
      : `- ${item.source}: failed (${item.message})`
  );
}

function collectMissingSkills(results) {
  const counts = new Map();
  for (const item of results) {
    for (const skill of item.missingSkills ?? []) {
      counts.set(skill, (counts.get(skill) ?? 0) + 1);
    }
  }
  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1])
    .slice(0, 8)
    .map(([skill]) => skill);
}
