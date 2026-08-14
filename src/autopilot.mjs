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
  const { jobs, diagnostics } = await fetchJobsForQuery(searchQuery, { profile, resume });

  const scoredJobs = jobs
    .map((job) => ({
      ...job,
      match: scoreJobMatch({ job, resume, profile })
    }))
    .sort((left, right) => Number(right.match.score) - Number(left.match.score));

  if (scoredJobs.length === 0) {
    throw new Error(buildNoJobsMessage(searchQuery, diagnostics));
  }

  const chosen = selectPreferredJob(scoredJobs);
  const applicationUrlStatus = describeApplicationUrl(chosen);
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
  if (job.applicationUrl) {
    browserSession = await runBrowserAssist({ packet, applicationUrl: job.applicationUrl });
  }

  return {
    query: searchQuery,
    chosenJob: job,
    analysis,
    packet,
    record,
    browserSession,
    diagnostics,
    report: buildAutopilotReport({
      query: searchQuery,
      chosenJob: job,
      analysis,
      packet,
      autoSubmitEnabled,
      browserOpened: Boolean(browserSession),
      browserReviewRequired: Boolean(browserSession) && !autoSubmitEnabled,
      diagnostics,
      applicationUrlStatus
    })
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
  try {
    return normalizeApplicationUrl(url);
  } catch {
    return "";
  }
}

function buildAutopilotReport({ query, chosenJob, analysis, packet, autoSubmitEnabled, browserOpened, browserReviewRequired, diagnostics, applicationUrlStatus }) {
  return [
    "# Autopilot Run",
    "",
    `Search query: ${query}`,
    `Selected role: ${chosenJob.company} | ${chosenJob.title}`,
    `Match score: ${chosenJob.match.score}`,
    `Decision: ${analysis.decision}`,
    `Application URL: ${chosenJob.applicationUrl || chosenJob.jobUrl || "n/a"}`,
    `Application URL status: ${applicationUrlStatus}`,
    `Packet: ${packet.outputDir}`,
    `Auto submit: ${autoSubmitEnabled ? "enabled" : "disabled"}`,
    `Sources: ${formatSourceSummary(diagnostics)}`,
    "",
    !browserOpened
      ? "Autopilot prepared the packet, but this role did not expose a usable application URL."
      : autoSubmitEnabled
        ? "Autopilot filled the application page and attempted submit if a matching button was found."
        : "Autopilot filled the application page and left the browser open for your review before submit.",
    browserReviewRequired ? "Press Enter in the terminal after reviewing the browser page." : ""
  ].join("\n");
}

function buildNoJobsMessage(query, diagnostics = []) {
  const failures = diagnostics.filter((item) => !item.ok);
  if (failures.length === diagnostics.length && diagnostics.length > 0) {
    return [
      `No jobs found for "${query}" because every job source failed.`,
      ...failures.map((item) => `- ${item.source}: ${item.message}`)
    ].join("\n");
  }

  return `No jobs found for "${query}". Try a broader search term. Sources: ${formatSourceSummary(diagnostics)}`;
}

function formatSourceSummary(diagnostics = []) {
  if (!diagnostics.length) {
    return "no source diagnostics";
  }

  return diagnostics
    .map((item) => (item.ok ? `${item.source} ok` : `${item.source} failed`))
    .join(", ");
}

function selectPreferredJob(scoredJobs) {
  const applyWithUsableUrl = scoredJobs.find((job) => job.match.decision === "apply" && hasUsableApplicationUrl(job));
  if (applyWithUsableUrl) {
    return applyWithUsableUrl;
  }

  const bestWithUsableUrl = scoredJobs.find((job) => hasUsableApplicationUrl(job));
  if (bestWithUsableUrl) {
    return bestWithUsableUrl;
  }

  return scoredJobs.find((job) => job.match.decision === "apply") ?? scoredJobs[0];
}

function hasUsableApplicationUrl(job) {
  return Boolean(safeApplicationUrl(job));
}

function describeApplicationUrl(job) {
  const rawUrl = job.applicationUrl || job.jobUrl || "";
  if (!rawUrl) {
    return "missing";
  }

  try {
    normalizeApplicationUrl(rawUrl);
    return "usable";
  } catch (error) {
    return `invalid (${error.message})`;
  }
}
