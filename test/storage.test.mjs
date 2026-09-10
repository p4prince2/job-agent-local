import test from "node:test";
import assert from "node:assert/strict";
import { ensureProjectFiles, loadProfile, loadResume, paths } from "../src/storage.mjs";
import { readFile } from "node:fs/promises";

test("ensureProjectFiles does not overwrite existing customized user files", async () => {
  await ensureProjectFiles({ forceExamples: false });

  const profile = await loadProfile();
  const resume = await loadResume();

  assert.ok(profile.name, "Profile should have a name");
  assert.ok(resume.length > 0, "Resume should not be empty");

  // Calling with forceExamples: true should not wipe out customized user data (e.g. Prince Kushwaha)
  await ensureProjectFiles({ forceExamples: true });

  const profileAfter = await loadProfile();
  assert.equal(profileAfter.name, profile.name, "Customized profile name should not be overwritten");
});
