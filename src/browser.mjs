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
  const normalizedUrl = normalizeApplicationUrl(applicationUrl);
  const browser = await launchBrowser();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1200 }
  });
  const page = await context.newPage();
  await page.goto(normalizedUrl, { waitUntil: "domcontentloaded" });
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

  if (process.env.AUTO_SUBMIT === "1") {
    const submitted = await tryClickSubmit(page);
    if (submitted) {
      fieldsFilled.push("auto-submit");
    }
  }

  const screenshotPath = join(packet.outputDir, "browser-preview.png");
  await page.screenshot({ path: screenshotPath, fullPage: true }).catch(() => {});

  await writeFile(
    join(packet.outputDir, "browser-run-summary.txt"),
    [
      `Application URL: ${normalizedUrl}`,
      `Page title: ${await page.title().catch(() => "")}`,
      `Fields filled: ${fieldsFilled.length ? fieldsFilled.join(", ") : "none"}`,
      `Screenshot: ${screenshotPath}`,
      `Auto submit: ${process.env.AUTO_SUBMIT === "1" ? "enabled" : "disabled"}`,
      "",
      process.env.AUTO_SUBMIT === "1"
        ? "Autopilot attempted submit if a matching button was found."
        : "Stop here and review the page before clicking submit."
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

export function normalizeApplicationUrl(applicationUrl) {
  let parsed;
  try {
    parsed = new URL(applicationUrl);
  } catch {
    throw new Error(`Invalid application URL: ${applicationUrl}`);
  }

  const hostname = parsed.hostname.toLowerCase();
  const looksLikeLocalhost = hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
  const hasPublicTld = hostname.includes(".");

  if (!looksLikeLocalhost && !hasPublicTld) {
    throw new Error(
      `That looks like a placeholder URL, not a real job page: ${applicationUrl}\nUse a full application link such as https://company.com/careers/...`
    );
  }

  return parsed.toString();
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

async function tryClickSubmit(page) {
  const patterns = [
    /submit/i,
    /apply now/i,
    /submit application/i,
    /send application/i,
    /complete application/i,
    /finish/i
  ];

  for (const pattern of patterns) {
    const candidates = [
      page.getByRole("button", { name: pattern }),
      page.getByRole("link", { name: pattern }),
      page.getByText(pattern, { exact: false }),
      page.locator('input[type="submit"]'),
      page.locator('button[type="submit"]')
    ];

    for (const locator of candidates) {
      const count = await locator.count().catch(() => 0);
      if (count === 0) {
        continue;
      }

      const candidate = locator.first();
      const visible = await candidate.isVisible().catch(() => false);
      if (!visible) {
        continue;
      }

      await candidate.click({ force: true }).catch(() => {});
      return true;
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
