#!/usr/bin/env node

import { analyzeJob, createDraftPacket } from "./workflow.mjs";
import { ensureProjectFiles, loadProfile, loadResume, writeApplicationRecord, loadLatestPacket } from "./storage.mjs";
import { doctor } from "./doctor.mjs";
import { formatHelp } from "./help.mjs";
import { resolveInput } from "./input.mjs";
import { runBrowserAssist } from "./browser.mjs";
import { runAutopilot } from "./autopilot.mjs";
import { stdin as input, stdout as output } from "node:process";
import { createInterface } from "node:readline/promises";
import { parseResume } from "./resume-parser.mjs";
import { searchJobs } from "./search.mjs";
import { loadTracker, printTracker } from "./tracker.mjs";

const command = process.argv[2] ?? "help";
const args = process.argv.slice(3);
const target = args[0];

async function main() {
  if (command === "help" || command === "--help" || command === "-h") {
    process.stdout.write(formatHelp());
    return;
  }

  if (command === "init") {
    await ensureProjectFiles({ forceExamples: true });
    process.stdout.write("Initialized local job-agent scaffold.\n");
    return;
  }

  if (command === "doctor") {
    await doctor();
    return;
  }

  if (command === "track") {
    const applications = await loadTracker();
    process.stdout.write(printTracker(applications));
    return;
  }

  if (command === "profile") {
    await ensureProjectFiles({ forceExamples: false });
    const profile = await loadProfile();
    const resume = parseResume({ profile, resumeMarkdown: await loadResume() });
    process.stdout.write(JSON.stringify(resume, null, 2) + "\n");
    return;
  }

  if (command === "search") {
    await ensureProjectFiles({ forceExamples: false });
    const query = args.join(" ").trim();
    const result = await searchJobs({ query, limit: 20 });
    process.stdout.write(result.report + "\n");
    return;
  }

  if (command === "autopilot") {
    const query = args.join(" ").trim();
    const result = await runAutopilot({ query });
    process.stdout.write(result.report + "\n");

    if (result.browserSession && process.env.AUTO_SUBMIT !== "1") {
      process.stdout.write("Review the page in the browser. I will wait here until you press Enter.\n");
      await waitForEnter();
      await result.browserSession.browser.close().catch(() => {});
    } else if (result.browserSession) {
      await result.browserSession.browser.close().catch(() => {});
    }

    return;
  }

  if (command === "analyze" || command === "draft" || command === "apply") {
    if (!target) {
      throw new Error(`Missing input for ${command}. Provide a file path, URL, or pasted job text.`);
    }

    await ensureProjectFiles({ forceExamples: false });
    const profile = await loadProfile();
    const resume = await loadResume();
    const job = await resolveInput(target);
    const analysis = await analyzeJob({ job, profile, resume });

    if (command === "analyze") {
      process.stdout.write(analysis.reportMarkdown);
      return;
    }

    const packet = await createDraftPacket({ job, profile, resume, analysis });
    const record = await writeApplicationRecord(packet);
    process.stdout.write(packet.reportMarkdown);
    process.stdout.write(`\nSaved to ${packet.outputDir}\n`);
    process.stdout.write(`Generated: resume-tailored.md, resume.pdf, browser-handoff.md\n`);
    process.stdout.write(`Logged application: ${record.id}\n`);
    return;
  }

  if (command === "browser-apply") {
    if (!target) {
      throw new Error("Missing application URL for browser-apply.");
    }

    await ensureProjectFiles({ forceExamples: false });
    const packet = await loadLatestPacket();
    const browserSession = await runBrowserAssist({ packet, applicationUrl: target });

    process.stdout.write(`Opened and filled: ${target}\n`);
    process.stdout.write(`Fields filled: ${browserSession.fieldsFilled.length ? browserSession.fieldsFilled.join(", ") : "none"}\n`);
    process.stdout.write(`Screenshot saved: ${browserSession.screenshotPath}\n`);
    process.stdout.write("Review the page in the browser. I will wait here until you press Enter.\n");
    await waitForEnter();
    await browserSession.browser.close().catch(() => {});
    return;
  }

  throw new Error(`Unknown command: ${command}\n\n${formatHelp()}`);
}

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 1;
});

async function waitForEnter() {
  const rl = createInterface({ input, output });
  await rl.question("");
  rl.close();
}

