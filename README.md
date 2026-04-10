# Chainguard Coverage Dashboard

A tool for analysing Chainguard library coverage against PyPI publish dates. It consists of two parts:

1. **`add_pypi_dates.py`** — enriches a Chainguard Python build report CSV with PyPI publish dates
2. **`index.html`** — an interactive dashboard for loading the enriched CSV and visualising coverage by publish year

## Background

Chainguard's internal dashboard can export a CSV report of customer library coverage status — whether each package was successfully built, failed, errored, or was excluded. This tooling adds PyPI publish date context to each package, then visualises the distribution across build statuses and publish years to help identify patterns (e.g. whether older or newer packages have lower coverage rates).

## Usage

### Step 1 — Export the CSV from Chainguard

Download the Python build report CSV from the Chainguard internal dashboard. The file should contain at minimum a `Requirement` column with entries in `package==version` format.

### Step 2 — Enrich with PyPI publish dates

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Then run the script:

```bash
python add_pypi_dates.py <input.csv> [output.csv]
```

The output path is optional — it defaults to `<input>-with-pypi-dates.csv`.

This fetches publish dates from the PyPI JSON API concurrently and writes a new CSV with an added `PyPI Published` column. A summary is printed on completion showing counts of dated, not found, unknown, and errored entries.

**Output values in the `PyPI Published` column:**

| Value | Meaning |
|---|---|
| `YYYY-MM-DD` | Publish date from PyPI |
| `not_found` | Package/version returned 404 from PyPI |
| `unknown` | PyPI responded but no upload date was found |
| `invalid_requirement` | Could not parse the `Requirement` field |
| `timeout` | Request timed out |
| `error_<status>` | HTTP error with status code |

### Step 3 — Load into the dashboard

Open `index.html` in a browser and load the enriched CSV via the file picker or drag-and-drop. No server required — everything runs locally in the browser.

The dashboard requires the CSV to have `PyPI Published`, `Status`, and `Requirement` columns.

## Dashboard Features

### Version histogram

Stacked bar chart of every package version grouped by PyPI publish year, coloured by Chainguard build status.

- **Count / 100% stacked** radio buttons to switch between absolute and relative views
- **Status filters** to show/hide individual statuses
- **Hover tooltips** with per-year breakdowns and percentages

### Library coverage donut

Deduplicates by library name (ignoring version) and shows how many distinct libraries have at least one built version vs none.

- A library is marked **Built** if any version of it has status `found`
- Labels show count and percentage for each slice

**Status categories:**

| Status | Description |
|---|---|
| Found | Successfully built by Chainguard |
| Build Failed | Build attempted but failed |
| Error | Internal Chainguard build error |
| Excluded | Cannot be built (licence or source issues) |
| Not in PyPI | Version pulled or never published |

## Configuration

The script has a few constants at the top of `add_pypi_dates.py` that can be adjusted:

```python
CONCURRENCY = 30      # concurrent HTTP requests to PyPI
RETRY_ATTEMPTS = 3    # retries on failure
RETRY_DELAY = 2.0     # base delay (seconds) for exponential backoff
```

## Dependencies

**Python:** see `requirements.txt`

**Dashboard:** No installation needed — PapaParse and ECharts are loaded from CDN.
