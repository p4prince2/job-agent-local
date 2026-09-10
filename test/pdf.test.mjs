import test from "node:test";
import assert from "node:assert/strict";
import { cleanMarkdownForPdf, escapePdfText, createTextPdf } from "../src/pdf.mjs";

test("cleanMarkdownForPdf maps Unicode dashes, bullets, and strips markdown symbols", () => {
  const input = "### Senior AI Engineer — Acme Corp (2024)\n* Built **94% precision** model – deployed to production.";
  const cleaned = cleanMarkdownForPdf(input);

  assert.ok(!cleaned.includes("###"), "Should strip markdown headings");
  assert.ok(!cleaned.includes("**"), "Should strip markdown bold asterisks");
  assert.ok(cleaned.includes(" - Acme Corp (2024)"), "Should convert em dash to space-dash-space");
  assert.ok(cleaned.includes("94% precision model - deployed"), "Should convert en dash to hyphen");
  assert.ok(!cleaned.includes("?"), "Should not have converted unicode to question mark");
});

test("escapePdfText properly escapes backslashes and parentheses without double-escaping", () => {
  assert.equal(escapePdfText("Hello (World)"), "Hello \\(World\\)");
  assert.equal(escapePdfText("Path\\To\\File"), "Path\\\\To\\\\File");
  assert.equal(escapePdfText("Test (with \\ backslash)"), "Test \\(with \\\\ backslash\\)");
});

test("createTextPdf produces a valid PDF buffer with header and trailer", () => {
  const pdfBuffer = createTextPdf({
    title: "Jane Doe - AI Engineer",
    lines: [
      "## Summary",
      "Experienced AI developer.",
      "## Experience",
      "- Built multi-agent system"
    ]
  });

  assert.ok(Buffer.isBuffer(pdfBuffer));
  const text = pdfBuffer.toString("latin1");
  assert.ok(text.startsWith("%PDF-1.4"), "Must start with %PDF-1.4 header");
  assert.ok(text.includes("%%EOF"), "Must contain %%EOF trailer");
  assert.ok(text.includes("/Type /Catalog"), "Must contain catalog");
  assert.ok(text.includes("/Type /Pages"), "Must contain pages");
});
