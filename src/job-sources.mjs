import { uniqueStrings } from "./utils.mjs";

export async function fetchJobsForQuery(query, options = {}) {
  const sources = [
    { name: "remotive", fetcher: fetchRemotiveJobs },
    { name: "arbeitnow", fetcher: fetchArbeitnowJobs }
  ];

  const results = [];
  const diagnostics = [];

  for (const source of sources) {
    try {
      const jobs = await source.fetcher(query, options);
      results.push(...jobs);
      diagnostics.push({
        source: source.name,
        ok: true,
        count: jobs.length,
        message: `${source.name} returned ${jobs.length} jobs.`
      });
    } catch (error) {
      diagnostics.push({
        source: source.name,
        ok: false,
        count: 0,
        message: normalizeErrorMessage(error)
      });
    }
  }

  return {
    jobs: dedupeJobs(results),
    diagnostics
  };
}

async function fetchRemotiveJobs(query) {
  const url = new URL("https://remotive.com/api/remote-jobs");
  if (query) {
    url.searchParams.set("search", query);
  }

  const response = await fetch(url, {
    headers: {
      "user-agent": "job-agent-local/0.1"
    }
  });
  if (!response.ok) {
    throw new Error(`Remotive request failed: ${response.status}`);
  }

  const payload = await response.json();
  const jobs = Array.isArray(payload.jobs) ? payload.jobs : [];
  return jobs.map((job) => normalizeRemotiveJob(job));
}

async function fetchArbeitnowJobs(query) {
  const jobs = [];
  let nextUrl = "https://www.arbeitnow.com/api/job-board-api";
  let pageCount = 0;

  while (nextUrl && pageCount < 3) {
    const response = await fetch(nextUrl, {
      headers: {
        "user-agent": "job-agent-local/0.1"
      }
    });
    if (!response.ok) {
      throw new Error(`Arbeitnow request failed: ${response.status}`);
    }

    const payload = await response.json();
    const pageJobs = Array.isArray(payload.data) ? payload.data : [];
    jobs.push(...pageJobs.map((job) => normalizeArbeitnowJob(job)));

    nextUrl = payload?.links?.next ? new URL(payload.links.next, nextUrl).toString() : "";
    pageCount += 1;
  }

  if (query) {
    const queryTokens = String(query).toLowerCase().split(/\s+/).filter(Boolean);
    return jobs.filter((job) => {
      const haystack = `${job.title} ${job.company} ${job.description} ${job.location}`.toLowerCase();
      return queryTokens.every((token) => haystack.includes(token));
    });
  }

  return jobs;
}

function normalizeRemotiveJob(job) {
  return {
    source: "remotive",
    company: job.company_name ?? job.company ?? "Unknown company",
    title: job.title ?? "Untitled role",
    location: job.candidate_required_location ?? job.location ?? "Remote",
    remote: true,
    jobUrl: job.url ?? "",
    applicationUrl: job.url ?? "",
    createdAt: job.publication_date ?? job.created_at ?? "",
    jobId: String(job.id ?? job.job_id ?? job.url ?? `${job.company_name}-${job.title}`),
    description: stripHtml(job.description ?? ""),
    tags: uniqueStrings([...(job.tags ?? []), job.category ?? "", job.job_type ?? ""])
  };
}

function normalizeArbeitnowJob(job) {
  return {
    source: "arbeitnow",
    company: job.company_name ?? "Unknown company",
    title: job.title ?? "Untitled role",
    location: job.location ?? "Remote",
    remote: Boolean(job.remote),
    jobUrl: job.url ?? job.application_url ?? "",
    applicationUrl: job.url ?? job.application_url ?? "",
    createdAt: job.created_at ?? "",
    jobId: String(job.slug ?? job.id ?? job.url ?? `${job.company_name}-${job.title}`),
    description: stripHtml(job.description ?? ""),
    tags: uniqueStrings([...(job.tags ?? []), ...(job.job_types ?? [])])
  };
}

function dedupeJobs(jobs) {
  const seen = new Set();
  const unique = [];

  for (const job of jobs) {
    const fingerprint = `${normalize(job.company)}|${normalize(job.title)}|${normalize(job.jobUrl || job.applicationUrl)}|${normalize(job.jobId)}`;
    if (seen.has(fingerprint)) {
      continue;
    }
    seen.add(fingerprint);
    unique.push(job);
  }

  return unique;
}

function normalize(value) {
  return String(value ?? "").trim().toLowerCase();
}

function stripHtml(html) {
  return String(html)
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeErrorMessage(error) {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return String(error ?? "Unknown source error");
}
