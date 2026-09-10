import test from "node:test";
import assert from "node:assert/strict";
import { parseResume } from "../src/resume-parser.mjs";

test("parseResume parses sections, experience, bullets, and skills correctly", () => {
  const resumeMarkdown = `
# Jane Doe

## Summary

Experienced AI Engineer specializing in LLMs and agent systems.

## Experience

### Acme Corp — Senior AI Engineer
Jan 2023 – Dec 2024 | Remote

- Developed LLM multi-agent workflow reducing latency by 40%.
- Implemented RAG pipeline with vector search.

### Beta Tech — Machine Learning Intern
Jun 2022 – Dec 2022 | Hybrid

- Trained computer vision models with 92% accuracy.

## Projects

### Local Agent CLI
- Built open source developer agent.

## Skills

- Python, TypeScript, Node.js
- PyTorch, LangChain, FAISS
`;

  const profile = {
    name: "Jane Doe",
    headline: "Senior AI Engineer",
    summary: "Candidate summary",
    strengths: ["LLM Workflows"],
    target_roles: ["AI Engineer"]
  };

  const parsed = parseResume({ profile, resumeMarkdown });

  assert.equal(parsed.name, "Jane Doe");
  assert.equal(parsed.headline, "Senior AI Engineer");
  assert.ok(parsed.summary.includes("Experienced AI Engineer"));
  assert.equal(parsed.experience.length, 2);
  assert.equal(parsed.experience[0].company, "Acme Corp");
  assert.equal(parsed.experience[0].title, "Senior AI Engineer");
  assert.equal(parsed.experience[0].bullets.length, 2);
  assert.ok(parsed.experience[0].months >= 20); // Jan 2023 to Dec 2024 is 23-24 months
  assert.equal(parsed.projects.length, 1);
  assert.equal(parsed.projects[0].title, "Local Agent CLI");
  assert.ok(parsed.skills.includes("Python"));
  assert.ok(parsed.skills.includes("TypeScript"));
  assert.ok(parsed.skills.includes("LangChain"));
});
