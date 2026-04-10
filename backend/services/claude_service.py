import json
import os
import anthropic

CLAUDE_MODEL = "claude-sonnet-4-20250514"

_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")
        _client = anthropic.AsyncAnthropic(api_key=api_key)
    return _client


EXTRACT_JOBS_PROMPT = """You are a web scraping assistant. I will provide you with HTML content from a company's careers/jobs page.

Extract all job listings from the HTML and return them as a JSON array. Each job should have these fields:
- title: string (required) - the job title
- location: string or null - city, region, or "Remote" if specified
- department: string or null - team or department name if listed
- job_url: string or null - the full or relative URL to the job posting

Return ONLY a valid JSON array, no explanation or markdown. Example:
[
  {"title": "Software Engineer", "location": "New York, NY", "department": "Engineering", "job_url": "/jobs/123"},
  {"title": "Product Manager", "location": "Remote", "department": "Product", "job_url": null}
]

If no jobs are found, return an empty array: []

HTML content:
{html}"""


async def extract_jobs_with_claude(html: str, base_url: str = "") -> list[dict]:
    """Send HTML to Claude and extract job listings as structured JSON."""
    # Truncate HTML to avoid excessive tokens (keep first 100k chars)
    html_truncated = html[:100_000]

    client = get_client()

    message = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": EXTRACT_JOBS_PROMPT.format(html=html_truncated),
            }
        ],
    )

    raw = message.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    jobs = json.loads(raw)

    # Resolve relative URLs
    if base_url and isinstance(jobs, list):
        for job in jobs:
            url = job.get("job_url")
            if url and url.startswith("/"):
                from urllib.parse import urlparse
                parsed = urlparse(base_url)
                job["job_url"] = f"{parsed.scheme}://{parsed.netloc}{url}"

    return jobs if isinstance(jobs, list) else []
