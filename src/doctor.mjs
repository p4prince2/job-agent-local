import { ensureProjectFiles, loadProfile, loadResume } from "./storage.mjs";
import { createAnalysisModel } from "./provider.mjs";
import { checkBrowserAutomation } from "./browser.mjs";
import { loadTracker } from "./tracker.mjs";

export async function doctor() {
  await ensureProjectFiles({ forceExamples: false });
  const model = createAnalysisModel();
  const [profile, resumeMarkdown, tracker] = await Promise.all([
    loadProfile(),
    loadResume(),
    loadTracker()
  ]); 

  process.stdout.write(`Project files: ready\n`);
  process.stdout.write(`Profile: ${profile.name || "Unknown"}\n`);
  process.stdout.write(`Resume: ${resumeMarkdown.trim() ? "loaded" : "empty"}\n`);
  process.stdout.write(`Tracker records: ${tracker.length}\n`);
  process.stdout.write(`AI provider: ${model.provider}\n`);
  process.stdout.write(`Model: ${model.modelName}\n`);

  const [modelStatus, browserStatus] = await Promise.all([
    model.healthcheck(),
    checkBrowserAutomation()
  ]);
  process.stdout.write(`${modelStatus}\n`);
  process.stdout.write(`${browserStatus}\n`);
}

