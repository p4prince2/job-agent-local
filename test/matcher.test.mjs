import test from "node:test";
import assert from "node:assert/strict";
import { scoreJobMatch, estimateLocationFit } from "../src/matcher.mjs";

test("scoreJobMatch scores strong matching job with apply decision", () => {
  const job = {
    title: "Senior AI Engineer",
    company: "Future AI",
    location: "Remote",
    description: "Looking for an AI Engineer with Python, LLM, LangChain, and RAG experience. 2+ years required.",
    tags: ["ai", "python", "llm"],
    remote: true
  };

  const resume = {
    summary: "AI/ML Engineer with extensive LLM, RAG, and Python experience.",
    skills: ["Python", "LLM", "RAG", "LangChain", "PyTorch"],
    projects: [{ title: "Conversational AI Platform" }],
    monthsExperience: 36
  };

  const profile = {
    location: "Remote",
    target_roles: ["AI Engineer"],
    strengths: ["LLMs", "RAG"],
    must_haves: ["Remote work"]
  };

  const result = scoreJobMatch({ job, resume, profile });

  assert.ok(result.score >= 70, `Expected score >= 70, got ${result.score}`);
  assert.equal(result.decision, "apply");
  assert.ok(result.matchingSkills.length >= 3);
  assert.equal(result.locationFit, true);
});

test("scoreJobMatch scores irrelevant job with skip decision", () => {
  const job = {
    title: "Senior Accountant",
    company: "Tax Corp",
    location: "Onsite Chicago",
    description: "Financial auditing, tax preparation, CPA required. 8+ years experience.",
    tags: ["accounting", "finance"],
    remote: false
  };

  const resume = {
    summary: "AI Engineer with Python experience.",
    skills: ["Python", "PyTorch"],
    projects: [],
    monthsExperience: 12
  };

  const profile = {
    location: "Remote",
    target_roles: ["AI Engineer"],
    strengths: ["LLMs"]
  };

  const result = scoreJobMatch({ job, resume, profile });
  assert.ok(result.score < 45, `Expected score < 45, got ${result.score}`);
  assert.equal(result.decision, "skip");
});

test("estimateLocationFit handles remote preferences and location matches", () => {
  assert.equal(estimateLocationFit({ location: "Remote" }, { location: "Remote" }), 1);
  assert.equal(estimateLocationFit({ location: "Bengaluru, India" }, { location: "Bengaluru, India" }), 1);
  assert.equal(estimateLocationFit({ location: "Austin, TX", remote: false }, { location: "Remote", must_haves: ["Remote"] }), 0.3);
});
