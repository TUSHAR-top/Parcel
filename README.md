# Parcel Label Extractor

Automatically extracts parcel label fields (tracking number, carrier, weight, dimensions) from uploaded parcel images and provides per-image verdicts and CSV exports for downstream QA or batch reporting.

## Table of Contents

1. [The Problem (What & Why)](#the-problem-what--why)
2. [Solution at a Glance](#solution-at-a-glance)
3. [Architecture (How)](#architecture-how)
4. [Tech Stack](#tech-stack)
5. [Getting Started (run locally in under 15 minutes)](#getting-started-run-locally-in-under-15-minutes)
6. [How to Use (for non-technical users)](#how-to-use-for-non-technical-users)
7. [Output Format](#output-format)
8. [Matching Rules & Edge Cases](#matching-rules--edge-cases)
9. [Assumptions & Design Trade-offs](#assumptions--design-trade-offs)
10. [Known Limitations](#known-limitations)
11. [What I'd Improve With More Time](#what-id-improve-with-more-time)
12. [Testing](#testing)
13. [Project Structure](#project-structure)
14. [Demo](#demo)

## The Problem (What & Why)

Warehouse and courier operations often rely on automated camera systems to capture parcel labels. Downstream systems (scanners, sorters, tracking reconciliation) need structured fields such as carrier, tracking number, weight and dimensions. Manual verification of label OCR output across thousands of frames is slow and brittle. This service automates field extraction and assigns a short, explainable status code per image so operators and QA teams can filter images that need human review.

Key pain points addressed:

- Camera frames with partial parcels, rotated/cropped labels, or multiple parcels confuse simple OCR flows.
- Different carriers use different tracking-number formats and logo styles; naive regex-only extraction misses many valid numbers.
- Teams need a compact CSV export summarising extraction success/failure for batch analysis.

This project turns an uploaded image (or batch of images) into a small JSON result describing extracted fields plus a CSV export of completed jobs. It reduces the manual verification surface to a small subset of images flagged `NOT_OK` or `LABEL_UNREADABLE`.

## Solution at a Glance

Upload one or many parcel images to the API. Each image is queued as a background job. The processing pipeline runs OCR (via RapidOCR), normalises the extracted text, and applies a set of deterministic extractors and heuristics to find:

- Carrier (by keyword/logo tokens)
- Tracking number (carrier-aware regex fallbacks)
- Weight (explicit `Weight:` labels or unit-aware regex)
- Dimensions (explicit Length/Width/Height fields or `LxWxH` patterns)

Each job returns a small JSON `status` code (e.g. `OK`, `TRACKING_NUMBER_MISSING`, `LABEL_UNREADABLE`, `MULTIPLE_PARCELS`) and the extracted fields. A CSV download endpoint returns completed jobs as a CSV suitable for spreadsheets or ingestion by downstream systems.

What this covers:

- Upload single/multi images via the web API; background processing keeps the upload request non-blocking.
- Per-image JSON results with deterministic, explainable status codes.
- CSV export of completed jobs (`/api/job/{job_id}/download` and `/api/batch/download`).
- A small static UI is served from the `static/` folder for manual uploads and progress polling.

## Architecture (How)
<img width="1024" height="559" alt="image" src="https://github.com/user-attachments/assets/f7b0c0c0-9706-4543-9546-75f10e508d74" />

<img width="1024" height="559" alt="image" src="https://github.com/user-attachments/assets/ac07f71e-adbb-4788-84a8-51fa318ad6cc" />

**Pipeline walkthrough:**

1. **Upload & validation** — `main.py` exposes `/api/upload` which accepts single or multiple `jpg|jpeg|png` files, enforces a 20 MB per-file limit, and writes each file to `uploads/` with a UUID filename.
2. **Background job** — each uploaded image schedules `process_job_task` (background task). Job metadata and progress live in an in-process `job_store` protected by a `threading.Lock`.
3. **OCR & extraction** — `processor.py` runs RapidOCR (`RapidOCR()`), collects raw OCR lines, normalises text, and performs field extraction (`extract_fields`) using carrier keywords, regex heuristics, and fallback candidate selection.
4. **Status derivation** — `processor.py` runs `evaluate_parcel_status` and `determine_parcel_status` to compute a compact status code combining visual-layout cues and missing-field checks.
5. **Result publishing** — when finished the background job writes a cleaned result into the `job_store`. The `/api/job/{job_id}` endpoint returns progress and the final JSON, and `/api/job/{job_id}/download` streams a single-row CSV for that job. `/api/batch/download` aggregates all completed jobs.

### Design decisions & why

1. **Deterministic heuristics, not ML classifiers for final verdicts.** RapidOCR is used for text extraction, but the subsequent decision logic is deterministic rule-based code so results are reproducible and explainable for QA.
2. **Carrier-aware tracking extraction.** A small set of carrier-specific regexes helps capture tracker formats (UPS 1Z, FedEx grouped digits, DHL, etc.) rather than relying on one monolithic pattern.
3. **Background tasks with in-process job store.** Simple and dependency-free for internal use. Jobs are kept in memory for quick access; this trades durability for simplicity.

## Tech Stack

| Layer | Technology | Why chosen |
|---|---|---|
| Web framework | FastAPI + Uvicorn | Lightweight, async-friendly API server and easy static file mounting. |
| OCR backend | RapidOCR (`rapidocr_onnxruntime`) | Fast local OCR model with ONNX runtime integration used for per-frame word/line extraction. |
| Image utils | Pillow | Image rotation and test-data generation. |
| Background jobs | FastAPI BackgroundTasks + `threading.Lock` | No external queue required for lightweight internal use. |
| Frontend | Vanilla HTML/CSS/JS in `static/` | Simple UI for manual uploads and status polling, zero build step. |

No external paid services or API keys are required — all processing runs locally once dependencies are installed.

## Getting Started (run locally in under 15 minutes)

**Prerequisites:** Python 3.9+, `pip`, and a machine able to run the RapidOCR runtime used in `requirements.txt`.

### Windows — one click

Double-click `start_app.bat`. It installs dependencies (if missing) and launches the Uvicorn server. The script prints the local URL to open.

### Manual — any OS

```bash
git clone <this-repo-url>
cd Parcel
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 in your browser. The static UI in `static/index.html` provides a simple upload form and progress UI.

### Environment variables

None required. The application reads no secrets or external service credentials.

### Verify it works

Use `generate_test_data.py` to create a small set of representative test images and a manifest. Run:

```bash
python generate_test_data.py
```

Then upload some of the images through the UI or call the `/api/upload` endpoint with `curl`/Postman to verify processing and downloads work.

## How to Use (for non-technical users)

1. Open the application in a browser (http://127.0.0.1:8000).
<img width="1516" height="837" alt="image" src="https://github.com/user-attachments/assets/0f95e020-d262-4fa6-a95e-ea67993f1e55" />
2. Use the upload control to attach one or more `.jpg/.jpeg/.png` images and click **Upload**.
<img width="1547" height="682" alt="image" src="https://github.com/user-attachments/assets/f1a99a84-ee4a-4a3b-b2bb-43c18849584a" />
3. The UI polls `/api/job/{job_id}` for progress. When complete you'll see extracted fields and a one-click CSV download for that job.
<img width="1291" height="921" alt="image" src="https://github.com/user-attachments/assets/9168f11a-cc9c-46a0-8663-18b5b1d62549" />
4. For batch reports, use **Download All Completed** which calls `/api/batch/download`.
<img width="1207" height="872" alt="image" src="https://github.com/user-attachments/assets/6cb981e2-73df-4bc5-961d-92c297643ae6" />

<img width="1542" height="337" alt="image" src="https://github.com/user-attachments/assets/8e1e9921-e4a3-4091-889a-aef13f7d7e58" />

## Output Format

There are two primary outputs:

- JSON job result (via `/api/job/{job_id}`) containing:
   - `tracking_number`, `carrier`, `weight`, `dimensions`, `status` (short code)
- CSV export (`/api/job/{job_id}/download` or `/api/batch/download`) with the columns:
   - `Original Filename, Status, Carrier, Tracking Number, Weight, Dimensions`

The CSV is intentionally minimal — designed for quick QA ingestion or spreadsheet review.

## Matching Rules & Edge Cases

### Extraction order

1. OCR lines are joined and normalised (whitespace collapsed, uppercased).
2. Carrier is detected by checking for a small keyword set (logo text or carrier-specific tokens).
3. Tracking number is attempted in this order:
    - Carrier-specific regexes (e.g. UPS `1Z...`, FedEx grouped digits)
    - Generic numeric/alphanumeric heuristics (8–22 chars with digits)
4. Weight/dimensions are pulled via labelled fields (`Weight:`, `Length:`/`Width:`/`Height:`) or regex patterns (e.g. `12.5 KG`, `12X8X6`).

### Verdict logic (status codes)

Status codes returned by `processor.py` include (but are not limited to):

- `OK` — all expected fields present and consistent.
- `TRACKING_NUMBER_MISSING` — no plausible tracking number found.
- `CARRIER_NOT_VISIBLE` — carrier keywords not present.
- `WEIGHT_NOT_FOUND` — weight not extracted.
- `DIMENSIONS_NOT_VISIBLE` — dimensions not extracted.
- `MULTIPLE_PARCELS` — OCR indicates more than one parcel/label in frame.
- `LABEL_UNREADABLE` — very low text yield or heavy distortion.
- `NO_PARCEL_IN_FRAME` — empty or background-only frame (useful for conveyor captures).

These codes help teams filter and prioritise which frames need human intervention.

### Edge cases handled

- Multiple parcel frames: flagged as `MULTIPLE_PARCELS` so they can be inspected separately.
- Rotated labels: the processor attempts a 180° rotation retry for certain visually abnormal statuses.
- Partial labels and blocked barcodes: heuristics try to extract what is visible; missing critical fields map to specific status codes instead of silent failure.

## Assumptions & Design Trade-offs

- **OCR-first, deterministic heuristics second.** We rely on RapidOCR for text extraction; downstream logic is rule-based for reproducibility.
- **In-memory job store.** Jobs are stored in-process for simplicity. This keeps the architecture dependency-free at the cost of durability across restarts.
- **Carrier list & patterns are hand-curated.** This is small and effective for common carriers but requires maintenance when new formats appear.
- **Single visual label per member row assumption for extraction.** Very complex multi-label layouts may require custom layout reassembly.

## Known Limitations

- Job state is ephemeral: restarting the server clears the `job_store`; completed CSVs must be downloaded immediately if needed.
- No authentication or rate-limiting — deployment is intended for internal or lab use only.
- RapidOCR runtime may require platform-specific wheels; installing `rapidocr_onnxruntime` may need additional OS-specific dependencies.
- The tracker extraction is heuristic; some obscure carrier formats or damaged numbers may still be missed.

## What I'd Improve With More Time

1. Persist job metadata to SQLite so results survive restarts and users can re-download past reports.
2. Add an administrative UI to replay or reprocess failed jobs and to tune carrier regexes without code changes.
3. Provide per-field confidence scores from the OCR backend and expose a `needs_review` filter for borderline cases.
4. Add a small CI test suite that runs `generate_test_data.py` and verifies the pipeline produces expected status codes for a labelled set.

## Testing

Run `generate_test_data.py` to produce a small set of 18 representative images in `test_images/` and a `manifest.json`. These images include clean labels, blurred labels, empty conveyor frames, blocked barcodes, partial parcels and multiple parcel frames.

A manual smoke test sequence:

1. `python generate_test_data.py` — creates `test_images/manifest.json` and images.
2. Upload a few images via the UI or call the `/api/upload` endpoint.
3. Inspect `/api/job/{job_id}` for the JSON result and use `/api/job/{job_id}/download` to fetch the CSV row.

## Project Structure

```
. 
├── main.py                    FastAPI entry point: routes, upload validation, background job orchestration
├── processor.py               OCR glue code, heuristics, status derivation
├── generate_test_data.py      Generates synthetic parcel label images for local testing
├── requirements.txt           Dependencies to install
├── start_app.bat              Windows one-click installer + launcher
├── start_app.ps1             PowerShell launcher
├── static/                    Static UI (index.html, app.js, style.css)
└── uploads/                   Runtime scratch dir for uploaded images and temporary artifacts (git-ignored)
```

## Demo

No deployed demo is provided with this repository. Use `generate_test_data.py` and the local server to verify the pipeline quickly.

---
