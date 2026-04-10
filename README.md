# CandidateMatch

A recruitment agency web app for scraping job listings from client career pages.

## Tech Stack

- **Backend**: Python FastAPI + SQLAlchemy + SQLite
- **Frontend**: React + Tailwind CSS (Vite)
- **Scraping**: Playwright (headless Chromium) with Claude API fallback
- **AI**: Claude API (`claude-sonnet-4-20250514`) for HTML job extraction

## Project Structure

```
backend/
  api/           # Route handlers (clients, jobs, scraper)
  models/        # SQLAlchemy models (Client, Job, ScrapeLog)
  services/      # Scraping logic, Claude integration
  database/      # SQLite async setup
  main.py        # FastAPI app entry point

frontend/
  src/
    components/  # Modal, ClientForm, Spinner, ConfirmDialog
    pages/       # ClientsPage, JobsPage
    services/    # API client (axios)
  index.html
```

## Setup

### 1. Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Set environment variable
export ANTHROPIC_API_KEY=your_key_here

# Start server
cd ..
uvicorn backend.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Usage

### Clients

- Add clients with company name, careers URL, ATS platform, city, notes
- Import multiple clients via CSV upload
- Toggle active/inactive status

**CSV Format:**
```csv
name,career_url,ats_platform,city,notes,is_active
Acme Corp,https://acme.com/careers,Greenhouse,New York,,true
```

### Scraping

- Click **Scrape Now** on a client card to scrape that client
- Click **Scrape All** to scrape all active clients sequentially (3s delay between each)
- Scraping uses Playwright to render JavaScript-heavy pages
- Falls back to Claude API if structural parsing finds no jobs

### Jobs Dashboard

- View all active jobs across all clients in a sortable table
- Filter by client, location keyword search, or free-text search
- **New** badge on jobs found in the last 48 hours
- Click job title to open the original posting

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for Claude fallback |
