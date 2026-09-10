import { ensureProjectFiles, loadProfile, loadResume } from "./storage.mjs";
import { createAnalysisModel } from "./provider.mjs";
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

  const checkBrowser = async () => {
    try {
      const { checkBrowserAutomation } = await import("./browser.mjs");
      return await checkBrowserAutomation();
    } catch (error) {
      return `Browser automation is not ready: ${error.message}`;
    }
  };

  const [modelStatus, browserStatus] = await Promise.all([
    model.healthcheck(),
    checkBrowser()
  ]);
  process.stdout.write(`${modelStatus}\n`);
  process.stdout.write(`${browserStatus}\n`);
}

