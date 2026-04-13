import asyncio
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

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


def _detect_url_pagination(url: str) -> Optional[dict]:
    """
    Detect if the URL uses parameter-based pagination (e.g., Phenom People ATS).
    Returns pagination config dict or None.
    
    Supports patterns like:
      ?from=10&s=1  (Phenom/HelloFresh)
      ?page=2       (generic)
      ?offset=20    (generic)
      ?start=10     (generic)
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    # Phenom People pattern: ?from=N
    if "from" in params:
        return {"param": "from", "current": int(params["from"][0]), "step": 10}

    # Generic patterns
    for param_name, step in [("page", 1), ("offset", 10), ("start", 10), ("p", 1)]:
        if param_name in params:
            return {"param": param_name, "current": int(params[param_name][0]), "step": step}

    return None


def _build_paginated_url(url: str, param: str, value: int) -> str:
    """Build a new URL with the pagination parameter set to the given value."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params[param] = [str(value)]
    # Rebuild query string with single values
    flat_params = {k: v[0] for k, v in params.items()}
    new_query = urlencode(flat_params)
    return urlunparse(parsed._replace(query=new_query))


def _get_first_page_url(url: str, param: str) -> str:
    """Build the URL for the first page (param=0 or param=1 depending on type)."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    # For 'page' param, first page is usually 1; for offset-style, it's 0
    first_value = "1" if param == "page" or param == "p" else "0"
    params[param] = [first_value]
    flat_params = {k: v[0] for k, v in params.items()}
    new_query = urlencode(flat_params)
    return urlunparse(parsed._replace(query=new_query))


async def _load_single_page(page: Page, url: str) -> str:
    """Navigate to a URL and return the rendered HTML after waiting for content."""
    await page.goto(url, wait_until="networkidle", timeout=30_000)
    await page.wait_for_timeout(2000)
    return await page.content()


async def _scrape_page(browser: Browser, url: str) -> str:
    """
    Load a page in Playwright, handle all pagination types, and return combined HTML.
    
    Handles:
    1. URL parameter pagination (Phenom, generic ?page=, ?offset=, ?from=)
    2. Infinite scroll
    3. "Load More" / "Show More" buttons
    4. Click-based Next/Previous pagination
    """
    page: Page = await browser.new_page()
    try:
        # First, check if the URL already has pagination parameters
        pagination = _detect_url_pagination(url)

        if pagination:
            # === URL-BASED PAGINATION ===
            # Start from page 1 / offset 0 and collect all pages
            param = pagination["param"]
            step = pagination["step"]

            all_html = ""
            current_offset = 0 if param not in ("page", "p") else 1
            max_pages = 30
            pages_scraped = 0

            while pages_scraped < max_pages:
                page_url = _build_paginated_url(url, param, current_offset)
                html = await _load_single_page(page, page_url)
                
                # Check if this page has job listings
                soup = BeautifulSoup(html, "lxml")
                job_indicators = soup.select(
                    "[class*='job'], [class*='position'], [class*='opening'], "
                    "[class*='posting'], [class*='career'], [class*='vacancy']"
                )
                
                current_job_count = len(job_indicators)
                
                # Stop if: no job indicators found on this page
                if pages_scraped > 0 and current_job_count == 0:
                    break

                all_html += "\n" + html
                pages_scraped += 1

                # Move to next page
                if param in ("page", "p"):
                    current_offset += 1
                else:
                    current_offset += step

                # Small delay between page loads
                await asyncio.sleep(1)

            return all_html

        # === NON-URL PAGINATION — load the page normally first ===
        await page.goto(url, wait_until="networkidle", timeout=30_000)
        await page.wait_for_timeout(2000)

        # Strategy 1: Infinite scroll — scroll to bottom repeatedly
        previous_height = 0
        scroll_attempts = 0
        max_scrolls = 20

        while scroll_attempts < max_scrolls:
            current_height = await page.evaluate("document.body.scrollHeight")
            if current_height == previous_height:
                break
            previous_height = current_height
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)
            scroll_attempts += 1

        # Strategy 2: Click "Load More" / "Show More" buttons repeatedly
        load_more_selectors = [
            "button:has-text('Load More')",
            "button:has-text('Show More')",
            "button:has-text('Mehr anzeigen')",
            "button:has-text('Weitere')",
            "button:has-text('Mehr laden')",
            "button:has-text('Alle anzeigen')",
            "button:has-text('View All')",
            "a:has-text('Load More')",
            "a:has-text('Show More')",
            "a:has-text('Mehr anzeigen')",
            "a:has-text('View All')",
            "[class*='load-more']",
            "[class*='show-more']",
        ]

        for _ in range(20):  # max clicks
            clicked = False
            for selector in load_more_selectors:
                try:
                    btn = page.locator(selector).first
                    if await btn.is_visible(timeout=1000):
                        await btn.click()
                        await page.wait_for_timeout(2000)
                        clicked = True
                        break
                except Exception:
                    continue
            if not clicked:
                break

        # Strategy 3: Click-based pagination (Next page buttons)
        all_html = await page.content()

        next_selectors = [
            "a:has-text('Next')",
            "a:has-text('Weiter')",
            "a:has-text('Nächste')",
            "button:has-text('Next')",
            "button:has-text('Weiter')",
            "[class*='next-page']",
            "[class*='pagination-next']",
            "[aria-label='Next']",
            "[aria-label='Next page']",
            "a[rel='next']",
            "li.next a",
            ".pagination a:last-child",
        ]

        pages_visited = 0
        max_pages = 15

        while pages_visited < max_pages:
            clicked = False
            for selector in next_selectors:
                try:
                    btn = page.locator(selector).first
                    if await btn.is_visible(timeout=1000):
                        await btn.click()
                        await page.wait_for_load_state("networkidle", timeout=15000)
                        await page.wait_for_timeout(2000)
                        all_html += "\n" + await page.content()
                        clicked = True
                        pages_visited += 1
                        break
                except Exception:
                    continue
            if not clicked:
                break

        return all_html

    finally:
        await page.close()


async def _upsert_jobs(
    db: AsyncSession,
    client_id: int,
    raw_jobs: list[dict],
) -> tuple[int, int]:
    """Insert or update jobs. Returns (total_found, new_jobs)."""
    now = datetime.utcnow()
    new_count = 0

    # Deduplicate raw jobs by (title, location) before processing
    seen = set()
    unique_jobs = []
    for raw in raw_jobs:
        title = (_clean_text(raw.get("title")) or "").strip()
        if not title:
            continue
        location = _clean_text(raw.get("location"))
        key = (title.lower(), (location or "").lower())
        if key not in seen:
            seen.add(key)
            unique_jobs.append(raw)

    total = len(unique_jobs)

    # Load existing jobs for this client keyed by (title, location)
    result = await db.execute(select(Job).where(Job.client_id == client_id))
    existing = {(j.title.lower(), (j.location or "").lower()): j for j in result.scalars().all()}

    seen_keys = set()

    for raw in unique_jobs:
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