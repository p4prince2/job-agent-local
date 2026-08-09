import { buildOutputDir, savePacket } from "./storage.mjs";
import { createAnalysisModel } from "./provider.mjs";
import { analyzeLocally, buildReportMarkdown, buildDraftMarkdown, buildTailoredResumeMarkdown, buildBrowserHandoffMarkdown, buildWorkflowSteps, toAnalysisScore } from "./scoring.mjs";
import { createTextPdf } from "./pdf.mjs";

export async function analyzeJob({ job, profile, resume }) {
  const model = createAnalysisModel();
  const localSignals = analyzeLocally({ job, profile, resume });
  const prompt = buildAnalysisPrompt({ job, profile, resume, localSignals });

  let raw = "";
  let modelOutput = null;

  try {
    raw = await model.generate({
      model: model.modelName,
      messages: [
        {
          role: "system",
          content: "You are a careful job-application analyst. Return only valid JSON with keys: decision, score, summary, strengths, gaps, resume_focus, application_answers, follow_up_questions."
        },
        {
          role: "user",
          content: prompt
        }
      ]
    });
    modelOutput = parseJsonLoose(raw);
  } catch (error) {
    modelOutput = null;
  }

  const analysis = buildAnalysisObject({ job, profile, resume, localSignals, modelOutput });
  analysis.workflow_steps = buildWorkflowSteps(analysis.decision);
  return {
    ...analysis,
    reportMarkdown: buildReportMarkdown({ job, profile, resume, analysis })
  };
}

export async function createDraftPacket({ job, profile, resume, analysis }) {
  const outputDir = buildOutputDir(job);
  const draftMarkdown = buildDraftMarkdown({ job, profile, resume, analysis });
  const reportMarkdown = buildReportMarkdown({ job, profile, resume, analysis });
  const tailoredResumeMarkdown = buildTailoredResumeMarkdown({ profile, analysis, resume, job });
  const browserHandoffMarkdown = buildBrowserHandoffMarkdown({ job, analysis, profile });
  const resumePdf = createTextPdf({
    title: `${profile.name || "Your Name"} - ${job.title}`,
    lines: tailoredResumeMarkdown
  });
  const packet = {
    job,
    profile,
    resume,
    analysis,
    outputDir,
    reportMarkdown,
    draftMarkdown,
    tailoredResumeMarkdown,
    browserHandoffMarkdown
  };

  await savePacket(outputDir, {
    "analysis.json": JSON.stringify(packet, null, 2) + "\n",
    "report.md": reportMarkdown,
    "draft.md": draftMarkdown,
    "resume-tailored.md": tailoredResumeMarkdown,
    "browser-handoff.md": browserHandoffMarkdown,
    "resume.pdf": resumePdf
  });

  return packet;
}

function buildAnalysisPrompt({ job, profile, resume, localSignals }) {
  return [
    `Job title: ${job.title}`,
    `Company: ${job.company}`,
    "",
    "Job description:",
    job.text,
    "",
    "Candidate profile:",
    JSON.stringify(profile, null, 2),
    "",
    "Resume:",
    resume,
    "",
    "Local signals:",
    JSON.stringify(localSignals, null, 2),
    "",
    "Instructions:",
    "- Recommend apply / hold / skip.",
    "- Score from 1.0 to 5.0.",
    "- Use short, practical bullets.",
    "- Tailor the resume focus to the role.",
    "- Draft answers that stay honest and specific.",
    "- Include a decision-ready workflow path.",
    "- Return JSON only."
  ].join("\n");
}

function buildAnalysisObject({ job, profile, resume, localSignals, modelOutput }) {
  const baseScore = toAnalysisScore(localSignals);
  const analysis = {
    decision: "hold",
    score: baseScore,
    summary: localSignals.summary,
    strengths: localSignals.strengths,
    gaps: localSignals.gaps,
    resume_focus: localSignals.resumeFocus,
    application_answers: {
      why_this_role: "I am interested in this role because it aligns with my current direction and the kind of work I want to do.",
      why_us: `I am drawn to ${job.company} because the role appears to combine technical depth with meaningful product work.`,
      project_example: "I would share a specific project where I built a useful system, owned the outcome, and improved the workflow end to end."
    },
    follow_up_questions: [
      "What would success in the first 90 days look like?",
      "What are the biggest constraints on this role?",
      "How does the team measure quality for AI-assisted work?"
    ]
  };

  if (modelOutput) {
    analysis.decision = normalizeDecision(modelOutput.decision, analysis.score);
    analysis.score = normalizeScore(modelOutput.score, analysis.score);
    analysis.summary = normalizeText(modelOutput.summary, analysis.summary);
    analysis.strengths = normalizeList(modelOutput.strengths, analysis.strengths);
    analysis.gaps = normalizeList(modelOutput.gaps, analysis.gaps);
    analysis.resume_focus = normalizeList(modelOutput.resume_focus, analysis.resume_focus);
    analysis.application_answers = {
      ...analysis.application_answers,
      ...normalizeObject(modelOutput.application_answers)
    };
    analysis.follow_up_questions = normalizeList(modelOutput.follow_up_questions, analysis.follow_up_questions);
  }

  analysis.workflow_steps = buildWorkflowSteps(analysis.decision);
  return analysis;
}

function parseJsonLoose(text) {
  const start = text.indexOf("{");
  const end = text.lastIndexOf("}");
  if (start === -1 || end === -1 || end <= start) {
    throw new Error("Model did not return JSON");
  }
  return JSON.parse(text.slice(start, end + 1));
}

function normalizeDecision(value, score) {
  const normalized = String(value || "").toLowerCase();
  if (normalized === "apply" || normalized === "hold" || normalized === "skip") {
    return normalized;
  }
  if (score >= 4.0) return "apply";
  if (score >= 3.0) return "hold";
  return "skip";
}

function normalizeScore(value, fallback) {
  const score = Number(value);
  if (Number.isFinite(score) && score >= 1 && score <= 5) {
    return Math.round(score * 10) / 10;
  }
  return fallback;
}

function normalizeText(value, fallback) {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function normalizeList(value, fallback) {
  if (Array.isArray(value)) {
    const cleaned = value.map((item) => String(item).trim()).filter(Boolean);
    if (cleaned.length > 0) {
      return cleaned;
    }
  }
  return fallback;
}

function normalizeObject(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  const output = {};
  for (const [key, item] of Object.entries(value)) {
    if (typeof item === "string" && item.trim()) {
      output[key] = item.trim();
    }
  }
  return output;
}

