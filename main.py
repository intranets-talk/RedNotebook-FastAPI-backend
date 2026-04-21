"""
RedNotebook API — FastAPI backend
Reads and writes RedNotebook yyyy-mm.txt files (YAML format).
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import yaml
import re
from datetime import date, datetime
from typing import Optional
import os
import httpx
from fastapi.responses import FileResponse, Response
from PIL import Image
import io

# ── Config ────────────────────────────────────────────────────────────────────
# Set REDNOTEBOOK_DIR env var, or edit this default path
JOURNAL_DIR = Path(os.getenv("REDNOTEBOOK_DIR", Path.home() / ".rednotebook" / "data"))

app = FastAPI(
    title="RedNotebook API",
    description="REST interface for your RedNotebook journal files",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # need to tighten this for auth later
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

# ── Immich proxy ──────────────────────────────────────────────────────────────

IMMICH_URL = os.getenv("IMMICH_URL", "https://your-immich-instance-url-or-ip")
IMMICH_API_KEY = os.getenv("IMMICH_API_KEY", "your-immich-api-key")

@app.get("/immich/{asset_id}.{ext}", tags=["immich"])
async def proxy_immich_image(asset_id: str, ext: str, size: int = 280):
    """
    Proxy an Immich asset, resized to `size` px wide (proportional height).
    Usage in RedNotebook: [""http://fastapi-ip-address:8000/immich/ASSET_ID"".jpg]
    """
    if not IMMICH_API_KEY:
        raise HTTPException(status_code=503, detail="IMMICH_API_KEY not configured")

    headers = {"x-api-key": IMMICH_API_KEY}

    async with httpx.AsyncClient(verify=False) as client:
        r = await client.get(
            f"{IMMICH_URL}/api/assets/{asset_id}/original",
            headers=headers,
            timeout=15,
        )

    if r.status_code == 401:
        raise HTTPException(status_code=401, detail="Invalid Immich API key")
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail="Asset not found in Immich")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Immich returned {r.status_code}")

    # Resize with Pillow
    from PIL import Image
    import io

    img = Image.open(io.BytesIO(r.content))

    # Preserve orientation from EXIF
    try:
        from PIL.ExifTags import TAGS
        exif = img._getexif()
        if exif:
            for tag, value in exif.items():
                if TAGS.get(tag) == "Orientation":
                    if value == 3:
                        img = img.rotate(180, expand=True)
                    elif value == 6:
                        img = img.rotate(270, expand=True)
                    elif value == 8:
                        img = img.rotate(90, expand=True)
                    break
    except Exception:
        pass

    # Resize proportionally
    orig_w, orig_h = img.size
    if orig_w > size:
        new_h = int(orig_h * size / orig_w)
        img = img.resize((size, new_h), Image.LANCZOS)

    # Output
    fmt = ext.upper()
    if fmt == "JPG":
        fmt = "JPEG"
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=95)
    buf.seek(0)

    return Response(
        content=buf.read(),
        media_type=f"image/{ext.lower().replace('jpg', 'jpeg')}",
    )
