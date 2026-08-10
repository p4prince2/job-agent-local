# Job Agent Local

A local-first job application agent you can run with free AI models like Ollama.

This scaffold is meant to mirror the useful parts of projects like `career-ops` without depending on a paid model provider:

- score a job against your CV
- draft tailored answers and a resume focus
- generate a per-job PDF resume packet
- create a browser handoff with a review-first default
- keep a simple application log
- keep auto-submit optional behind an explicit setting

## What you need

- Node.js 18 or newer
- Ollama installed locally
- a model that can follow structured prompts well

## Install first

If you are starting from a fresh machine, install these in this order:

1. Install Node.js from [nodejs.org/en/download](https://nodejs.org/en/download/).
   - Node.js includes `npm`, so you do not need a separate JavaScript installer.
2. Install Ollama from [ollama.com/download/windows](https://ollama.com/download/windows) on Windows.
   - On Windows, the official PowerShell install command is:

   ```powershell
   irm https://ollama.com/install.ps1 | iex
   ```

3. Open a new terminal and verify both tools:

   ```bash
   node -v
   npm -v
   ollama -v
   ```

4. Start Ollama and make sure it is reachable at `http://localhost:11434`.
5. Pull at least one model, for example:

   ```bash
   ollama pull llama3.1:8b
   ```

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

If you pass a placeholder like `https://the-job-application-hcl`, the browser will fail because that is not a real application URL. Use a real job page or let `autopilot` pick one from search results.

Run a fully automated pass that searches, scores, prepares the packet, and then fills the best match:

```bash
$env:AUTO_SUBMIT="1"
node src/cli.mjs autopilot "AI Engineer"
```

Without `AUTO_SUBMIT=1`, the autopilot will still search and prepare the packet, but it will stop before submitting.

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
$env:OLLAMA_MODEL="qwen2.5-coder:32b"
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
- `browser-preview.png` when browser assist runs
- `browser-run-summary.txt` when browser assist runs

Applications are appended to `data/applications.json`.
Search discoveries are also recorded there with match scores and statuses.

## Next step

This scaffold is intentionally conservative. The natural next upgrade is browser-assisted form filling with a review gate, so the agent drafts and prepares actions but still waits for your approval before any submission.

The `browser-apply` command does the assisted part: it fills common fields, uploads the saved resume when possible, takes a screenshot, and stops before clicking submit unless `AUTO_SUBMIT=1` is set.

The `search` command is the first autonomous slice: it scans public sources, scores the matches, and stores a queue of jobs to review or skip.

