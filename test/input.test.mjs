import test from "node:test";
import assert from "node:assert/strict";
import { stripHtml, extractTitleFromHtml, extractCompanyFromHtml, inferCompany, buildJobFromText } from "../src/input.mjs";

test("stripHtml preserves paragraph line breaks and cleans whitespace", () => {
  const html = `
    <html>
      <head><title>Job Title</title></head>
      <body>
        <h1>Lead AI Engineer</h1>
        <p>We are hiring an AI Engineer to join our team at Acme Labs.</p>
        <br/>
        <p>Requirements: Python &amp; LLMs.</p>
      </body>
    </html>
  `;

  const text = stripHtml(html);
  assert.ok(text.includes("Lead AI Engineer"));
  assert.ok(text.includes("We are hiring an AI Engineer"));
  assert.ok(text.includes("Requirements: Python & LLMs."));
  assert.ok(text.includes("\n"), "Should retain line breaks between blocks");
});

test("extractTitleFromHtml extracts title from og:title, h1, or title tag", () => {
  const htmlOg = `<meta property="og:title" content="Staff ML Engineer - Careers" />`;
  assert.equal(extractTitleFromHtml(htmlOg), "Staff ML Engineer");

  const htmlH1 = `<h1>Principal Agent Developer</h1>`;
  assert.equal(extractTitleFromHtml(htmlH1), "Principal Agent Developer");

  const htmlTitle = `<title>Senior Product Manager | Remote Jobs</title>`;
  assert.equal(extractTitleFromHtml(htmlTitle), "Senior Product Manager");
});

test("extractCompanyFromHtml and inferCompany detect company correctly", () => {
  const html = `<meta property="og:site_name" content="Stripe" />`;
  assert.equal(extractCompanyFromHtml(html), "Stripe");

  assert.equal(inferCompany("Join our engineering team at Databricks today!"), "Databricks");
  assert.equal(inferCompany("Looking for engineers with Anthropic", "https://anthropic.com/jobs/123"), "Anthropic");
});

test("buildJobFromText constructs a structured job object", () => {
  const raw = "AI Research Scientist\nat DeepMind\nBuilding frontier models.";
  const job = buildJobFromText(raw, "manual");
  assert.equal(job.title, "AI Research Scientist");
  assert.equal(job.company, "DeepMind");
  assert.ok(job.text.includes("Building frontier models."));
});
