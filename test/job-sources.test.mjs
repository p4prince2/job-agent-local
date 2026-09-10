import test from "node:test";
import assert from "node:assert/strict";
import { matchesJobQuery } from "../src/job-sources.mjs";

test("matchesJobQuery matches single terms and complex disjunctive OR queries", () => {
  const job = {
    title: "Generative AI Engineer",
    company: "Anthropic",
    description: "Work on LLM alignment, RLHF, and agentic workflows.",
    tags: ["llm", "ai"],
    location: "Remote"
  };

  assert.equal(matchesJobQuery(job, "AI Engineer"), true);
  assert.equal(matchesJobQuery(job, "Generative AI"), true);
  assert.equal(matchesJobQuery(job, "Python Developer OR Generative AI Engineer"), true);
  assert.equal(matchesJobQuery(job, "Data Scientist | Agentic Workflows"), true);
  assert.equal(matchesJobQuery(job, "Java Backend Developer"), false);
});
