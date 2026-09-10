export function analyzeLocally({ job, profile, resume }) {
  const jobTokens = tokenize(`${job.title}\n${job.text}`);
  const profileTokens = tokenize(JSON.stringify(profile));
  const resumeTokens = tokenize(resume);
  const overlap = intersectionSize(jobTokens, new Set([...profileTokens, ...resumeTokens]));
  const jobUnique = Math.max(jobTokens.size, 1);
  const ratio = overlap / jobUnique;
  const score = clamp(1 + ratio * 4, 1, 5);

  const strengths = [];
  if (matchesAny(jobTokens, ["agent", "automation", "workflow", "llm", "ai"])) {
    strengths.push("The role appears aligned with AI / automation work.");
  }
  if (matchesAny(jobTokens, ["node", "javascript", "typescript", "python"])) {
    strengths.push("The stack overlaps with common agent development tools.");
  }
  if (profile.summary) {
    strengths.push("Your profile summary gives the model a clear narrative to tailor from.");
  }

  const gaps = [];
  if (!matchesAny(profileTokens, jobTokens)) {
    gaps.push("There is limited direct overlap between the pasted profile and this job description.");
  }
  const hasQuantifiedMetrics = /\d+[%xX]|\b\d+\s*(?:k|m|million|billion|users|clients|hours|days|percent)\b|\$\d+/i.test(resume);
  if (!hasQuantifiedMetrics) {
    gaps.push("The resume may benefit from more quantified outcomes and business impact metrics.");
  }

  const resumeFocus = [
    "Lead with the most relevant AI/automation experience.",
    "Mirror the role's exact tools and problem space where truthful.",
    "Keep evidence specific and outcome-driven."
  ];

  const summary = `Local overlap score is ${(score).toFixed(1)} / 5 based on keyword overlap between the job, profile, and resume.`;

  return {
    score: Math.round(score * 10) / 10,
    summary,
    strengths: strengths.length ? strengths : ["The model should inspect the job for role fit and tailoring opportunities."],
    gaps: gaps.length ? gaps : ["No obvious red flags from the basic local scan."],
    resumeFocus
  };
}

export function toAnalysisScore(localSignals) {
  return localSignals.score;
}

export function buildWorkflowSteps(decision) {
  if (decision === "apply") {
    return [
      { title: "Confirm fit", status: "done" },
      { title: "Tailor resume and answers", status: "ready" },
      { title: "Generate PDF packet", status: "ready" },
      { title: "Prepare browser handoff", status: "ready" },
      { title: "Wait for your approval", status: "blocked" }
    ];
  }

  if (decision === "hold") {
    return [
      { title: "Review missing evidence", status: "ready" },
      { title: "Strengthen resume bullets", status: "ready" },
      { title: "Re-run fit score", status: "ready" },
      { title: "Hold until stronger match", status: "blocked" }
    ];
  }

  return [
    { title: "Archive this role", status: "done" },
    { title: "Search for better fit", status: "ready" },
    { title: "Skip browser handoff", status: "done" }
  ];
}

export function buildReportMarkdown({ job, analysis }) {
  return [
    `# ${job.title}`,
    "",
    `Company: ${job.company}`,
    `Source: ${job.source}`,
    "",
    `Decision: ${analysis.decision}`,
    `Score: ${analysis.score.toFixed(1)} / 5`,
    "",
    "## Summary",
    "",
    analysis.summary,
    "",
    "## Strengths",
    "",
    ...analysis.strengths.map((item) => `- ${item}`),
    "",
    "## Gaps",
    "",
    ...analysis.gaps.map((item) => `- ${item}`),
    "",
    "## Resume Focus",
    "",
    ...analysis.resume_focus.map((item) => `- ${item}`),
    "",
    "## Draft Answers",
    "",
    `### Why this role`,
    "",
    analysis.application_answers.why_this_role,
    "",
    `### Why us`,
    "",
    analysis.application_answers.why_us,
    "",
    `### Project example`,
    "",
    analysis.application_answers.project_example,
    "",
    "## Follow-up Questions",
    "",
    ...analysis.follow_up_questions.map((item) => `- ${item}`),
    "",
    "## Workflow",
    "",
    ...analysis.workflow_steps.map((step) => `- [${step.status}] ${step.title}`),
    ""
  ].join("\n");
}

export function buildDraftMarkdown({ job, analysis }) {
  return [
    `# Draft Packet: ${job.title}`,
    "",
    `Company: ${job.company}`,
    "",
    "## Suggested Message",
    "",
    analysis.application_answers.why_this_role,
    "",
    "## Tailoring Notes",
    "",
    ...analysis.resume_focus.map((item) => `- ${item}`),
    "",
    "## Submission Check",
    "",
    "- Review every factual claim.",
    "- Confirm compensation and location constraints.",
    "- Only submit manually after you are satisfied.",
    "",
    "## Workflow",
    "",
    ...analysis.workflow_steps.map((step) => `- [${step.status}] ${step.title}`),
    ""
  ].join("\n");
}

export function buildTailoredResumeMarkdown({ profile, analysis, resume, job }) {
  return [
    `# ${profile.name || "Your Name"}`,
    "",
    `Role target: ${job.title} at ${job.company}`,
    "",
    "## Tailored Summary",
    "",
    analysis.summary,
    "",
    "## Best-Fit Highlights",
    "",
    ...analysis.strengths.map((item) => `- ${item}`),
    "",
    "## Resume Focus",
    "",
    ...analysis.resume_focus.map((item) => `- ${item}`),
    "",
    "## Source Resume",
    "",
    resume.trim(),
    ""
  ].join("\n");
}

export function buildBrowserHandoffMarkdown({ job, analysis, profile }) {
  return [
    `# Browser Handoff`,
    "",
    `Approval gate: ${analysis.decision === "apply" ? "required before submit" : "not ready"}`,
    `Target role: ${job.title}`,
    `Target company: ${job.company}`,
    "",
    "## What to review",
    "",
    "- Resume wording is truthful and job-specific.",
    "- Application answers match the posted role.",
    "- Compensation, location, and work authorization constraints are acceptable.",
    "",
    "## Suggested browser fill fields",
    "",
    `- Name: ${profile.name || "Your Name"}`,
    `- Headline: ${profile.headline || "N/A"}`,
    `- Location: ${profile.location || "N/A"}`,
    `- Why this role: ${analysis.application_answers.why_this_role}`,
    `- Why us: ${analysis.application_answers.why_us}`,
    "",
    "## Approval rule",
    "",
    "- Do not submit the form until you have manually reviewed every field.",
    "- If anything looks wrong, stop and revise the packet first.",
    ""
  ].join("\n");
}

function tokenize(text) {
  const words = String(text).toLowerCase().match(/[a-z0-9]+/g) ?? [];
  return new Set(words.filter((word) => word.length >= 3));
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

function matchesAny(source, terms) {
  for (const term of terms) {
    if (source.has(term)) {
      return true;
    }
  }
  return false;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

