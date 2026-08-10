import { analyzeJob, createDraftPacket } from "./workflow.mjs";
import { ensureProjectFiles, loadProfile, loadResume, writeApplicationRecord } from "./storage.mjs";
import { parseResume } from "./resume-parser.mjs";
import { fetchJobsForQuery } from "./job-sources.mjs";
import { scoreJobMatch } from "./matcher.mjs";
import { runBrowserAssist, normalizeApplicationUrl } from "./browser.mjs";

export async function runAutopilot({ query }) {
  await ensureProjectFiles({ forceExamples: false });

  const profile = await loadProfile();
  const resumeMarkdown = await loadResume();
  const resume = parseResume({ profile, resumeMarkdown });
  const searchQuery = (query || buildDefaultQuery(profile)).trim();
  const jobs = await fetchJobsForQuery(searchQuery, { profile, resume });

  const scoredJobs = jobs
    .map((job) => ({
      ...job,
      match: scoreJobMatch({ job, resume, profile })
    }))
    .filter((job) => Boolean(job.applicationUrl || job.jobUrl))
    .sort((left, right) => Number(right.match.score) - Number(left.match.score));

  if (scoredJobs.length === 0) {
    throw new Error(`No jobs found for "${searchQuery}". Try a broader search term.`);
  }

  const chosen = scoredJobs.find((job) => job.match.decision === "apply") ?? scoredJobs[0];
  const job = {
    ...chosen,
    text: chosen.description ?? chosen.text ?? "",
    applicationUrl: safeApplicationUrl(chosen)
  };

  const analysis = await analyzeJob({ job, profile, resume: resumeMarkdown });
  const packet = await createDraftPacket({ job, profile, resume: resumeMarkdown, analysis });
  const record = await writeApplicationRecord(packet);

  const autoSubmitEnabled = process.env.AUTO_SUBMIT === "1";
  let browserSession = null;
  if (autoSubmitEnabled && job.applicationUrl) {
    browserSession = await runBrowserAssist({ packet, applicationUrl: job.applicationUrl });
    await browserSession.browser.close().catch(() => {});
  }

  return {
    query: searchQuery,
    chosenJob: job,
    analysis,
    packet,
    record,
    browserSession,
    report: buildAutopilotReport({ query: searchQuery, chosenJob: job, analysis, packet, autoSubmitEnabled })
  };
}

function buildDefaultQuery(profile) {
  const roles = Array.isArray(profile.target_roles) && profile.target_roles.length ? profile.target_roles : ["AI Engineer"];
  return roles.slice(0, 4).join(" OR ");
}

function safeApplicationUrl(job) {
  const url = job.applicationUrl || job.jobUrl || "";
  if (!url) {
    return "";
  }
  return normalizeApplicationUrl(url);
}

function buildAutopilotReport({ query, chosenJob, analysis, packet, autoSubmitEnabled }) {
  return [
    "# Autopilot Run",
    "",
    `Search query: ${query}`,
    `Selected role: ${chosenJob.company} | ${chosenJob.title}`,
    `Match score: ${chosenJob.match.score}`,
    `Decision: ${analysis.decision}`,
    `Application URL: ${chosenJob.applicationUrl || chosenJob.jobUrl || "n/a"}`,
    `Packet: ${packet.outputDir}`,
    `Auto submit: ${autoSubmitEnabled ? "enabled" : "disabled"}`,
    "",
    autoSubmitEnabled
      ? "Autopilot filled the application page and attempted submit if a matching button was found."
      : "Autopilot prepared everything and left the browser step in review mode."
  ].join("\n");
}
