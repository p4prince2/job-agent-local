export function formatHelp() {
  return [
    "Job Agent Local",
    "",
    "Commands:",
    "  init                Create local config and example files", 
    "  doctor              Check Ollama and project setup",
    "  profile             Print parsed resume structure",
    "  search [query]      Search public job sources and score matches",
    "  autopilot [query]   Search, draft, fill, and review or submit the best match",
    "  analyze <input>     Score a job and print a report",
    "  draft <input>       Generate a tailored packet, PDF resume, and log it",
    "  apply <input>       Alias for draft",
    "  browser-apply <url>  Open browser, fill fields, and pause before submit",
    "  track               Show saved applications",
    "",
    "Input can be a file path, URL, or pasted job text.",
    ""
  ].join("\n");
}

