"""
RedNotebook API — FastAPI backend
Reads and writes RedNotebook yyyy-mm.txt files (YAML format).
"""

from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
import yaml
import re
import uuid
import shutil
from datetime import date, datetime
from typing import Optional
import os

# ── Config ────────────────────────────────────────────────────────────────────
# Set REDNOTEBOOK_DIR env var, or edit this default path
JOURNAL_DIR = Path(os.getenv("REDNOTEBOOK_DIR", Path.home() / ".rednotebook" / "data"))
ATTACHMENTS_DIR = JOURNAL_DIR / "attachments"

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20 MB

app = FastAPI(
    title="RedNotebook API",
    description="REST interface for your RedNotebook journal files",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # it needs tightening if auth is added later
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


# ── Models ────────────────────────────────────────────────────────────────────

class EntryIn(BaseModel):
    text: str


class DayEntry(BaseModel):
    date: str          # "2025-04-16"
    day: int
    month: int
    year: int
    text: str
    has_content: bool


class MonthSummary(BaseModel):
    year: int
    month: int
    label: str         # "2025-04"
    days_with_entries: list[int]


# ── File helpers ──────────────────────────────────────────────────────────────

def month_file(year: int, month: int) -> Path:
    return JOURNAL_DIR / f"{year}-{month:02d}.txt"


def load_month(year: int, month: int) -> dict:
    """Parse a RedNotebook month file. Returns {day: {text: ...}} or {}."""
    path = month_file(year, month)
    if not path.exists():
        return {}
    content = path.read_text(encoding="utf-8")
    # RedNotebook files are YAML with integer day keys
    try:
        data = yaml.safe_load(content) or {}
    except yaml.YAMLError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse {path.name}: {e}")
    return data


def save_month(year: int, month: int, data: dict):
    """Write a month dict back to the RedNotebook YAML file."""
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    path = month_file(year, month)
    # Preserve RedNotebook's format: integer keys, 'text' sub-key
    path.write_text(yaml.dump(data, allow_unicode=True, default_flow_style=False), encoding="utf-8")


def entry_text(day_data) -> str:
    """Extract the text field from a day's data (handles dict or plain string)."""
    if day_data is None:
        return ""
    if isinstance(day_data, dict):
        return day_data.get("text", "") or ""
    return str(day_data)


def build_day_entry(year: int, month: int, day: int, day_data) -> DayEntry:
    text = entry_text(day_data)
    return DayEntry(
        date=f"{year}-{month:02d}-{day:02d}",
        day=day,
        month=month,
        year=year,
        text=text.strip(),
        has_content=bool(text.strip()),
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", tags=["meta"])
def root():
    return {"status": "ok", "journal_dir": str(JOURNAL_DIR)}


@app.get("/months", response_model=list[MonthSummary], tags=["months"])
def list_months():
    """Return all months that have a journal file, newest first."""
    if not JOURNAL_DIR.exists():
        return []
    pattern = re.compile(r"^(\d{4})-(\d{2})\.txt$")
    summaries = []
    for f in sorted(JOURNAL_DIR.glob("*.txt"), reverse=True):
        m = pattern.match(f.name)
        if not m:
            continue
        year, month = int(m.group(1)), int(m.group(2))
        data = load_month(year, month)
        days_with_entries = sorted(
            [d for d, v in data.items() if entry_text(v).strip()]
        )
        summaries.append(MonthSummary(
            year=year,
            month=month,
            label=f"{year}-{month:02d}",
            days_with_entries=days_with_entries,
        ))
    return summaries


@app.get("/entries/{year}/{month}", response_model=list[DayEntry], tags=["entries"])
def get_month_entries(year: int, month: int):
    """Return all entries for a given month (including empty days if any)."""
    if not (1 <= month <= 12):
        raise HTTPException(status_code=422, detail="Month must be 1-12")
    data = load_month(year, month)
    entries = []
    for day, day_data in sorted(data.items()):
        if isinstance(day, int):
            entries.append(build_day_entry(year, month, day, day_data))
    return entries


@app.get("/entries/{year}/{month}/{day}", response_model=DayEntry, tags=["entries"])
def get_day_entry(year: int, month: int, day: int):
    """Return a single day's entry."""
    data = load_month(year, month)
    day_data = data.get(day)
    return build_day_entry(year, month, day, day_data)


@app.put("/entries/{year}/{month}/{day}", response_model=DayEntry, tags=["entries"])
def upsert_day_entry(year: int, month: int, day: int, entry: EntryIn):
    """Create or overwrite a day's entry."""
    if not (1 <= month <= 12) or not (1 <= day <= 31):
        raise HTTPException(status_code=422, detail="Invalid date")
    data = load_month(year, month)
    data[day] = {"text": entry.text}
    save_month(year, month, data)
    return build_day_entry(year, month, day, data[day])


@app.delete("/entries/{year}/{month}/{day}", tags=["entries"])
def delete_day_entry(year: int, month: int, day: int):
    """Remove a day's entry."""
    data = load_month(year, month)
    if day not in data:
        raise HTTPException(status_code=404, detail="Entry not found")
    del data[day]
    save_month(year, month, data)
    return {"deleted": True, "date": f"{year}-{month:02d}-{day:02d}"}


@app.get("/search", response_model=list[DayEntry], tags=["search"])
def search_entries(q: str = Query(..., min_length=1)):
    """Full-text search across all journal entries."""
    if not JOURNAL_DIR.exists():
        return []
    q_lower = q.lower()
    results = []
    pattern = re.compile(r"^(\d{4})-(\d{2})\.txt$")
    for f in sorted(JOURNAL_DIR.glob("*.txt"), reverse=True):
        m = pattern.match(f.name)
        if not m:
            continue
        year, month = int(m.group(1)), int(m.group(2))
        data = load_month(year, month)
        for day, day_data in sorted(data.items(), reverse=True):
            if not isinstance(day, int):
                continue
            text = entry_text(day_data)
            if q_lower in text.lower():
                results.append(build_day_entry(year, month, day, day_data))
    return results


# ── Attachment helpers ────────────────────────────────────────────────────────

def attachment_dir(date: str) -> Path:
    """Returns the attachments folder for a given date string YYYY-MM-DD."""
    return ATTACHMENTS_DIR / date


def attachment_token(filename: str) -> str:
    """Returns the portable token stored in entry text: [attachment:filename]"""
    return f"[attachment:{filename}]"


# ── Attachment routes ─────────────────────────────────────────────────────────

@app.get("/attachments/{date}", tags=["attachments"])
def list_attachments(date: str):
    """List all attachments for a given date (YYYY-MM-DD)."""
    folder = attachment_dir(date)
    if not folder.exists():
        return []
    files = [
        {"filename": f.name, "url": f"/attachments/{date}/{f.name}"}
        for f in sorted(folder.iterdir())
        if f.is_file()
    ]
    return files


@app.post("/attachments/{date}", tags=["attachments"])
async def upload_attachment(date: str, file: UploadFile = File(...)):
    """Upload an image attachment for a given date (YYYY-MM-DD)."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {file.content_type}. Allowed: jpeg, png, gif, webp"
        )

    # Read and check size
    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Max 20 MB.")

    # Generate a unique filename preserving the extension
    ext = Path(file.filename).suffix.lower() if file.filename else ".jpg"
    filename = f"{uuid.uuid4().hex[:12]}{ext}"

    folder = attachment_dir(date)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / filename).write_bytes(data)

    return {
        "filename": filename,
        "url": f"/attachments/{date}/{filename}",
        "token": attachment_token(filename),
        "size": len(data),
    }


@app.get("/attachments/{date}/{filename}", tags=["attachments"])
def get_attachment(date: str, filename: str):
    """Serve an attachment file."""
    # Security: prevent path traversal
    if ".." in date or ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid path")
    path = attachment_dir(date) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Attachment not found")
    return FileResponse(path)


@app.delete("/attachments/{date}/{filename}", tags=["attachments"])
def delete_attachment(date: str, filename: str):
    """Delete an attachment file."""
    if ".." in date or ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid path")
    path = attachment_dir(date) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Attachment not found")
    path.unlink()
    # Remove folder if empty
    folder = attachment_dir(date)
    if folder.exists() and not any(folder.iterdir()):
        folder.rmdir()
    return {"deleted": True, "filename": filename}
