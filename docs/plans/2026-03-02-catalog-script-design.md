# Flipper Zero App Catalog Script — Design

## Goal

Python script that generates a comprehensive README.md catalog of Flipper Zero apps, organized by categories, with 123fzero's own apps featured first in each category. Runs manually or via a daily GitHub Actions cron, then publishes the site via GitHub Pages.

## Data Sources

1. **Official Catalog API** (`catalog.flipperzero.one/api/v0/`) — primary source. 11 categories, ~322 verified apps with structured JSON data including descriptions, authors, and source code links.
2. **awesome-flipperzero** (`djsime1/awesome-flipperzero`) — secondary source. Parsed from README.md for apps/resources not in the official catalog (Databases, Firmwares, Graphics, Modules, etc.).

## 123fzero Prioritization

- Fetch 123fzero repos via GitHub API
- Match apps by author name or source URL containing `github.com/123fzero/`
- Featured apps appear first in their category with a star marker

## Generated README Structure

```
# 123 Games
> Flipper Zero app catalog ...

## Table of Contents
(auto-generated links to all categories)

## Category Name

### Featured
| App | Description | Author | Source |
| 123fzero app... | ... | 123fzero | link |

### All Apps
| App | Description | Author | Source |
| Other apps... | ... | author | link |
```

## Files

| File | Purpose |
|------|---------|
| `scripts/update_catalog.py` | Main script |
| `scripts/requirements.txt` | Python dependencies |
| `.github/workflows/update-catalog.yml` | Daily cron GitHub Action for catalog refresh |
| `.github/workflows/deploy-pages.yml` | GitHub Pages deploy workflow triggered after catalog refreshes and manual site changes |
| `README.md` | Generated output |

## Script Modules

1. `fetch_categories()` — GET /api/v0/category, returns category list
2. `fetch_apps_for_category(cat_id)` — paginated GET /api/v0/application, returns all apps in category with details
3. `fetch_awesome_list()` — downloads and parses awesome-flipperzero README.md into structured sections
4. `fetch_123fzero_repos()` — GitHub API to get 123fzero's public repos
5. `merge_and_prioritize()` — combines sources, deduplicates, marks featured apps
6. `generate_readme()` — builds final README.md string

## Tech Stack

- Python 3.10+
- `requests` for HTTP
- No template engine needed (string formatting sufficient)
- GitHub Actions for automation
