# Job Agent Local

A local-first job application agent you can run with free AI models like Ollama.

This scaffold is meant to mirror the useful parts of projects like `career-ops` without depending on a paid model provider:

- score a job against your CV
- draft tailored answers and a resume focus
- generate a per-job PDF resume packet
- create an approval-gated browser handoff
- keep a simple application log
- never auto-submit anything without you reviewing it first

## What you need

- Node.js 18 or newer
- Ollama installed locally
- a model that can follow structured prompts well

Good starting models:

- `qwen2.5-coder:32b`
- `llama3.1:8b`
- `gemma3:27b`

## Setup

```bash
npm install
npm run init
```

Then edit the generated files:

- `data/profile.json`
- `data/resume.md`

## Run

Analyze a job description from a file or URL:

```bash
node src/cli.mjs analyze ./examples/job-posting.txt
node src/cli.mjs analyze "https://example.com/job-posting"
```

Create a draft packet and log the application:

```bash
node src/cli.mjs draft ./examples/job-posting.txt
```

Open an application page, auto-fill common fields from your latest packet, and pause before submit:

```bash
node src/cli.mjs browser-apply "https://example.com/apply"
```

Run `draft` first so the browser helper has the latest packet to use.

Check your local setup:

```bash
npm run doctor
```

See the parsed resume structure:

```bash
node src/cli.mjs profile
```

Search public job sources and save the results into the tracker:

```bash
node src/cli.mjs search "AI Engineer"
```

## Environment

You can keep the defaults and only set the model name:

```bash
set OLLAMA_MODEL=qwen2.5-coder:32b
```

Optional settings:

- `AI_PROVIDER=ollama`
- `OLLAMA_BASE_URL=http://localhost:11434`
- `OLLAMA_MODEL=llama3.1:8b`

## Output

Each run writes a folder under `output/` with:

- `report.md`
- `draft.md`
- `resume-tailored.md`
- `resume.pdf`
- `browser-handoff.md`
- `analysis.json`

Applications are appended to `data/applications.json`.
Search discoveries are also recorded there with match scores and statuses.

## Next step

This scaffold is intentionally conservative. The natural next upgrade is browser-assisted form filling with a review gate, so the agent drafts and prepares actions but still waits for your approval before any submission.

The `browser-apply` command does the assisted part: it fills common fields, uploads the saved resume when possible, takes a screenshot, and stops before clicking submit.

The `search` command is the first autonomous slice: it scans public sources, scores the matches, and stores a queue of jobs to review or skip.

