import { ensureProjectFiles } from "./storage.mjs";
import { createAnalysisModel } from "./provider.mjs";

export async function doctor() {
  await ensureProjectFiles({ forceExamples: false });
  const model = createAnalysisModel();

  process.stdout.write(`Project files: ready\n`);
  process.stdout.write(`AI provider: ${model.provider}\n`);
  process.stdout.write(`Model: ${model.modelName}\n`);

  const status = await model.healthcheck();
  process.stdout.write(`${status}\n`);
}

