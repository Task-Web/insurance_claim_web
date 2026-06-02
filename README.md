# Insurance Claim Web

Online version of task 005's insurance claim system. It follows the same
frontend/backend layout as `formcraft_web`: a static frontend, a FastAPI backend,
cookie-scoped `/api/state`, and `/api/files` for uploaded documents.

All form edits, selections, file changes, signature confirmation, and submit
actions are mirrored to the backend state immediately. Local storage is kept only
as a browser-side fallback for refresh recovery.

## Local run

Backend:

```bash
cd backend
uvicorn app.main:app --reload --port 8005
```

Frontend:

```bash
cd frontend
python -m http.server 5173
```

Open http://localhost:5173.

## State Shape

Submissions are stored under:

```json
{
  "data": {
    "submitted_claims": [
      {
        "id": "claim-...",
        "formData": {},
        "uploadedFiles": []
      }
    ],
    "current_claim": {
      "formData": {},
      "uploadedFiles": [],
      "currentStep": 1
    }
  }
}
```
