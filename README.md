# Parcel Label Extractor

A lightweight local web app for uploading parcel images, extracting label details, and classifying the scanner situation into simple status categories such as OK, NO_PARCEL, LABEL_BLOCKED, or LABEL_UNREADABLE.

## What this project does
- Lets a user upload a parcel image through a simple browser UI.
- Runs OCR-based extraction on the backend to identify fields such as tracking number, carrier, weight, and dimensions.
- Returns a structured result plus a status label for the image.
- Supports downloading completed job results as a CSV file.

## Why I built it
I wanted to create a practical demo that combines a polished frontend, a Python backend, and local OCR processing without needing a heavy cloud setup. The priority was to make the project easy to run on a laptop and easy to understand, rather than to build the most advanced parcel-processing system possible.

## Approach and why
- I chose a simple FastAPI backend so the app could be launched locally with minimal setup.
- I used local OCR instead of depending on a remote AI service so it is easier to run without internet or extra infrastructure.
- The extraction logic is rule-based and explainable, which makes it easier to debug than a black-box model.
- This approach is strong for a prototype, demo, or learning project, but it is not yet a fully production-grade parcel vision pipeline.

## Tech stack
- Python 3.10+ — the main programming language for the backend and processing logic.
- FastAPI — powers the API for uploading files, tracking jobs, and serving results.
- Uvicorn — the ASGI server used to run the FastAPI app locally.
- RapidOCR ONNX Runtime — the local OCR engine used to read text from parcel labels.
- Pillow — used for basic image handling and a rotation-based retry when an image looks upside down.
- HTML, CSS, and JavaScript — provide the simple browser-based UI.
- Python Multipart — enables file uploads from the browser to the backend.

## Run it locally in under 15 minutes

### Option 1: Windows one-click startup (fastest)
1. Install Python 3.10+ and make sure Python is available in your terminal.
2. Open the project folder in PowerShell.
3. Run one of these:
   - start_app.bat
   - .\start_app.ps1
4. Wait for the setup to finish. The first run may take 5–10 minutes because dependencies are being installed.
5. Open your browser at http://localhost:3000

This launcher creates a local virtual environment, installs the required packages, and starts the app for you.

### Option 2: Manual startup
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 3000
```

Then open http://localhost:3000 in your browser.

> If this is your first run, expect the OCR dependencies to install before the app becomes fully responsive.

## Project structure
```text
Parcel/
├── main.py                  # FastAPI backend and API routes
├── processor.py             # OCR extraction and status classification logic
├── generate_test_data.py    # Creates sample parcel images for testing
├── requirements.txt         # Python dependencies
├── start_app.bat            # One-click Windows launcher
├── start_app.ps1            # One-click PowerShell launcher
├── static/                  # Frontend files
│   ├── index.html
│   ├── style.css
│   └── app.js
└── uploads/                 # Temporary upload folder created at runtime
```

## Quick test data
You can generate a small set of sample images to test the app:
```powershell
python generate_test_data.py
```

This creates a test_images folder with synthetic parcel scenarios that help validate the UI and OCR flow.

## UI images
Space for screenshots that will be added later.

### Screenshot 1
- Add your first UI image here.

### Screenshot 2
- Add your second UI image here.

### Screenshot 3
- Add your third UI image here.

## What I would improve with more time
- Add a stronger OCR pipeline with better layout understanding and confidence scoring.
- Improve handling for blurry, rotated, partially visible, or damaged labels.
- Add automated tests and a small CI pipeline.
- Add better job history, user feedback, and a more refined UI.
- Containerize the app with Docker for easier deployment.

## Known limitations
- OCR accuracy depends heavily on image quality, lighting, label angle, and sharpness.
- The current version is a strong prototype, but it is not yet a production-grade parcel scanning system.
- Some labels may be misread or partially classified when the label is cropped, blocked, or heavily distorted.
- The app currently runs locally and does not include advanced cloud-based inference or GPU acceleration.
- The status logic is heuristic-based, so results should be treated as helpful suggestions rather than guaranteed correctness.

## API overview
- POST /api/upload — upload one or more parcel images.
- GET /api/job/{job_id} — check job progress and results.
- GET /api/job/{job_id}/download — download the completed result as CSV.
- GET /api/health — simple health check endpoint.
