import asyncio
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Browser, Page
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.client import Client
from backend.models.job import Job
from backend.models.scrape_log import ScrapeLog
from backend.services.claude_service import extract_jobs_with_claude

# Simple heuristics for job listing containers
JOB_SELECTORS = [
    # Greenhouse
    "div.opening",
    # Lever
    "div.posting",
    # Workday
    "li[class*='job']",
    # Generic
    "article[class*='job']",
    "li[class*='position']",
    "div[class*='job-item']",
    "div[class*='job-listing']",
    "div[class*='career-item']",
    "tr[class*='job']",
]

TITLE_SELECTORS = ["h3", "h2", "h4", "a", ".title", ".job-title", "[class*='title']"]
LOCATION_SELECTORS = [".location", "[class*='location']", "[class*='city']", "span.sort-by-location"]
DEPT_SELECTORS = [".department", "[class*='department']", "[class*='team']", "span.sort-by-team"]


def _clean_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    return re.sub(r"\s+", " ", text).strip() or None


def _extract_jobs_structural(html: str, base_url: str) -> list[dict]:
    """Attempt to parse job listings using structural CSS selectors."""
    soup = BeautifulSoup(html, "lxml")
    jobs = []

    for selector in JOB_SELECTORS:
        items = soup.select(selector)
        if len(items) >= 2:  # Plausible — at least 2 listings found
            for item in items:
                title = None
                for ts in TITLE_SELECTORS:
                    el = item.select_one(ts)
                    if el and el.get_text(strip=True):
                        title = _clean_text(el.get_text())
                        break

                if not title:
                    continue

                location = None
                for ls in LOCATION_SELECTORS:
                    el = item.select_one(ls)
                    if el:
                        location = _clean_text(el.get_text())
                        break

                department = None
                for ds in DEPT_SELECTORS:
                    el = item.select_one(ds)
                    if el:
                        department = _clean_text(el.get_text())
                        break

                job_url = None
                link = item.select_one("a[href]")
                if link:
                    href = link.get("href", "")
                    job_url = urljoin(base_url, href) if href else None

                jobs.append({
                    "title": title,
                    "location": location,
                    "department": department,
                    "job_url": job_url,
                })

            if jobs:
                return jobs

    return []


async def _scrape_page(browser: Browser, url: str) -> str:
    """Load a page in Playwright and return the rendered HTML."""
    page: Page = await browser.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=30_000)
        await page.wait_for_timeout(2000)  # extra settle time for SPAs
        return await page.content()
    finally:
        await page.close()


async def _upsert_jobs(
    db: AsyncSession,
    client_id: int,
    raw_jobs: list[dict],
) -> tuple[int, int]:
    """Insert or update jobs. Returns (total_found, new_jobs)."""
    now = datetime.utcnow()
    total = len(raw_jobs)
    new_count = 0

    # Load existing jobs for this client keyed by (title, location)
    result = await db.execute(select(Job).where(Job.client_id == client_id))
    existing = {(j.title.lower(), (j.location or "").lower()): j for j in result.scalars().all()}

    seen_keys = set()

    for raw in raw_jobs:
        title = (_clean_text(raw.get("title")) or "").strip()
        if not title:
            continue

        location = _clean_text(raw.get("location"))
        key = (title.lower(), (location or "").lower())
        seen_keys.add(key)

        if key in existing:
            existing[key].last_seen_at = now
            existing[key].is_active = True
            if raw.get("job_url"):
                existing[key].job_url = raw["job_url"]
        else:
            job = Job(
                client_id=client_id,
                title=title,
                location=location,
                department=_clean_text(raw.get("department")),
                job_url=raw.get("job_url"),
                is_active=True,
                found_at=now,
                last_seen_at=now,
            )
            db.add(job)
            new_count += 1

    # Mark jobs not seen in this scrape as inactive
    for key, job in existing.items():
        if key not in seen_keys:
            job.is_active = False

    await db.commit()
    return total, new_count


async def scrape_client(
    db: AsyncSession,
    client: Client,
    browser: Browser,
) -> ScrapeLog:
    log = ScrapeLog(
        client_id=client.id,
        status="running",
        jobs_found=0,
        jobs_new=0,
        started_at=datetime.utcnow(),
    )
    db.add(log)
    await db.commit()

    used_claude = False
    try:
        html = await _scrape_page(browser, client.career_url)

        raw_jobs = _extract_jobs_structural(html, client.career_url)

        if not raw_jobs:
            # Fall back to Claude
            used_claude = True
            raw_jobs = await extract_jobs_with_claude(html, client.career_url)

        total, new_count = await _upsert_jobs(db, client.id, raw_jobs)

        log.status = "success"
        log.jobs_found = total
        log.jobs_new = new_count
        log.used_claude = used_claude
        log.finished_at = datetime.utcnow()

    except Exception as exc:
        log.status = "error"
        log.error_message = str(exc)
        log.used_claude = used_claude
        log.finished_at = datetime.utcnow()

    await db.commit()
    await db.refresh(log)
    return log


async def run_scrape_job(
    db: AsyncSession,
    client_ids: Optional[list[int]] = None,
) -> list[dict]:
    """
    Scrape one or more clients sequentially with a 3-second delay.
    If client_ids is None, scrape all active clients.
    """
    if client_ids:
        query = select(Client).where(Client.id.in_(client_ids), Client.is_active == True)  # noqa: E712
    else:
        query = select(Client).where(Client.is_active == True)  # noqa: E712

    result = await db.execute(query.order_by(Client.name))
    clients = result.scalars().all()

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            for i, client in enumerate(clients):
                if i > 0:
                    await asyncio.sleep(3)

                log = await scrape_client(db, client, browser)
                results.append({
                    "client_id": client.id,
                    "client_name": client.name,
                    "status": log.status,
                    "jobs_found": log.jobs_found,
                    "jobs_new": log.jobs_new,
                    "used_claude": log.used_claude,
                    "error": log.error_message,
                })
        finally:
            await browser.close()

    return results
