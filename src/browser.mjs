import { chromium } from "playwright";
import { access, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";

const namedFieldPatterns = [
  { key: "fullName", valueKey: "name", patterns: [/full name/i, /^name$/i, /applicant name/i] },
  { key: "email", valueKey: "email", patterns: [/email/i] },
  { key: "phone", valueKey: "phone", patterns: [/phone/i, /mobile/i, /cell/i] },
  { key: "location", valueKey: "location", patterns: [/location/i, /city/i, /current location/i] },
  { key: "linkedin", valueKey: "linkedin", patterns: [/linkedin/i] },
  { key: "github", valueKey: "github", patterns: [/github/i] },
  { key: "portfolio", valueKey: "portfolio", patterns: [/portfolio/i, /website/i, /personal site/i] },
  { key: "headline", valueKey: "headline", patterns: [/headline/i, /current title/i, /desired title/i] },
  { key: "summary", valueKey: "summary", patterns: [/summary/i, /about you/i, /bio/i, /profile/i] },
  { key: "salary", valueKey: "salary", patterns: [/salary/i, /compensation/i, /expected pay/i, /desired salary/i] }
];

const essayFieldPatterns = [
  { valueKey: "why_this_role", patterns: [/why.*role/i, /why.*apply/i, /why are you interested/i, /interest in this role/i] },
  { valueKey: "why_us", patterns: [/why.*company/i, /why.*us/i, /why do you want to work here/i] },
  { valueKey: "project_example", patterns: [/project/i, /experience/i, /challenge/i, /tell us about/i] }
];

export async function runBrowserAssist({ packet, applicationUrl }) {
  const browser = await launchBrowser();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1200 }
  });
  const page = await context.newPage();
  await page.goto(applicationUrl, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle").catch(() => {});

  const fieldsFilled = [];
  const profile = packet.profile ?? {};
  const analysis = packet.analysis ?? {};
  const applicationAnswers = analysis.application_answers ?? {};

  for (const field of namedFieldPatterns) {
    const value = profile[field.valueKey];
    if (typeof value === "string" && value.trim()) {
      const filled = await fillFirstMatch(page, field.patterns, value.trim());
      if (filled) {
        fieldsFilled.push(field.key);
      }
    }
  }

  for (const field of essayFieldPatterns) {
    const value = applicationAnswers[field.valueKey];
    if (typeof value === "string" && value.trim()) {
      const filled = await fillFirstMatch(page, field.patterns, value.trim());
      if (filled) {
        fieldsFilled.push(field.valueKey);
      }
    }
  }

  const resumePdf = join(packet.outputDir, "resume.pdf");
  if (await exists(resumePdf)) {
    const fileInput = page.locator('input[type="file"]').first();
    if (await fileInput.count()) {
      await fileInput.setInputFiles(resumePdf).catch(() => {});
      fieldsFilled.push("resume-upload");
    }
  }

  const screenshotPath = join(packet.outputDir, "browser-preview.png");
  await page.screenshot({ path: screenshotPath, fullPage: true }).catch(() => {});

  await writeFile(
    join(packet.outputDir, "browser-run-summary.txt"),
    [
      `Application URL: ${applicationUrl}`,
      `Page title: ${await page.title().catch(() => "")}`,
      `Fields filled: ${fieldsFilled.length ? fieldsFilled.join(", ") : "none"}`,
      `Screenshot: ${screenshotPath}`,
      "",
      "Stop here and review the page before clicking submit."
    ].join("\n"),
    "utf8"
  );

  return {
    browser,
    context,
    page,
    screenshotPath,
    fieldsFilled
  };
}

async function launchBrowser() {
  const headless = process.env.BROWSER_HEADLESS === "1";
  const candidates = [
    { channel: "msedge" },
    { channel: "chrome" },
    {}
  ];

  let lastError = null;
  for (const candidate of candidates) {
    try {
      return await chromium.launch({
        headless,
        ...candidate
      });
    } catch (error) {
      lastError = error;
    }
  }

  throw new Error(`Unable to launch a browser for automation: ${lastError?.message ?? "unknown error"}`);
}

async function fillFirstMatch(page, patterns, value) {
  for (const pattern of patterns) {
    const targets = [
      page.getByLabel(pattern, { exact: false }),
      page.getByPlaceholder(pattern),
      page.getByRole("textbox", { name: pattern })
    ];

    for (const locator of targets) {
      if ((await locator.count()) === 0) {
        continue;
      }

      const candidate = locator.first();
      if (!(await candidate.isVisible().catch(() => false))) {
        continue;
      }

      const tagName = await candidate.evaluate((element) => element.tagName.toLowerCase()).catch(() => "");
      if (tagName === "textarea" || tagName === "input") {
        await candidate.fill(value).catch(() => {});
        return true;
      }
    }
  }

  return false;
}

async function exists(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}
