"""
Wedding photo album selector — Flask backend.
Serves photos, supports sort by date/name, saves per-album JSON.
"""
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from PIL import Image
from PIL.ExifTags import TAGS

app = Flask(__name__, static_folder="static")

# Config: set PHOTOS_DIR via env or use ./photos
BASE_DIR = Path(__file__).resolve().parent
PHOTOS_DIR = Path(os.environ.get("PHOTOS_DIR", BASE_DIR / "photos"))
SELECTIONS_DIR = BASE_DIR / "selections"
OUTPUT_DIR = BASE_DIR / "output"

# Album IDs and their JSON filenames
ALBUMS = [
    {"id": "us", "label": "Us"},
    {"id": "my_parents", "label": "My parents"},
    {"id": "wife_father", "label": "Wife's father"},
    {"id": "wife_mother", "label": "Wife's mother"},
]
ALBUM_IDS = [a["id"] for a in ALBUMS]
DISCARDED_FILE = "discarded.json"

# Source "" (root) is stored as this in selections dir
ROOT_SOURCE_KEY = "_root"


def get_photos_dir(source: str) -> Path:
    """Resolve the directory for a given source ('' = root, else subdir name)."""
    if not source or source == ROOT_SOURCE_KEY:
        return PHOTOS_DIR
    return PHOTOS_DIR / source


def get_selections_dir(source: str) -> Path:
    """Selections are stored per source: selections/_root/ or selections/engagement/ etc."""
    key = source if source else ROOT_SOURCE_KEY
    return SELECTIONS_DIR / key


def list_sources() -> list[dict]:
    """List root (if it has images) and all subdirs that contain images."""
    sources = []
    if not PHOTOS_DIR.exists():
        return sources
    allowed = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"}
    # Root: include if it has any image files
    root_has_images = any(
        f.is_file() and f.suffix.lower() in allowed for f in PHOTOS_DIR.iterdir()
    )
    if root_has_images:
        sources.append({"id": "", "label": "Root"})
    # Subdirs: only directories
    for f in sorted(PHOTOS_DIR.iterdir()):
        if f.is_dir() and not f.name.startswith("."):
            subdir = f
            if any(
                x.is_file() and x.suffix.lower() in allowed for x in subdir.iterdir()
            ):
                sources.append({"id": f.name, "label": f.name})
    return sources


def get_photo_date(filepath: Path) -> datetime:
    """Get photo date from EXIF DateTimeOriginal, else file mtime."""
    try:
        img = Image.open(filepath)
        exif = img.getexif()
        if exif:
            for tag_id, value in exif.items():
                if TAGS.get(tag_id) == "DateTimeOriginal" and value:
                    # Value is like "2024:06:15 14:30:00"
                    return datetime.strptime(str(value), "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return datetime.fromtimestamp(os.path.getmtime(filepath))


def _natural_sort_key(s: str):
    """Key for natural/human sort: pic-1, pic-2, pic-10 not pic-1, pic-10, pic-2."""
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", s)
    ]


def list_photos(sort_by: str, source: str = "") -> list[dict]:
    """List image files from the given source dir. sort_by: 'date' | 'name'."""
    allowed = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"}
    photos = []
    base = get_photos_dir(source)
    if not base.exists():
        return photos
    for f in base.iterdir():
        if f.is_file() and f.suffix.lower() in allowed:
            # path is relative to PHOTOS_DIR for serving (e.g. "engagement/IMG_001.jpg")
            rel = f.relative_to(PHOTOS_DIR)
            path_str = str(rel).replace("\\", "/")
            photos.append({
                "filename": f.name,
                "path": path_str,
                "mtime": os.path.getmtime(f),
            })
    if sort_by == "date":
        with_dates = []
        for p in photos:
            fp = base / p["filename"]
            with_dates.append((get_photo_date(fp), p))
        with_dates.sort(key=lambda x: x[0])
        photos = [p for _, p in with_dates]
    else:
        photos.sort(key=lambda p: _natural_sort_key(p["filename"]))
    return photos


def load_selections(source: str = "") -> dict:
    """Load all album selections and discarded for the given source."""
    sel_dir = get_selections_dir(source)
    sel_dir.mkdir(parents=True, exist_ok=True)
    out = {aid: [] for aid in ALBUM_IDS}
    out["discarded"] = []
    for aid in ALBUM_IDS:
        p = sel_dir / f"album_{aid}.json"
        if p.exists():
            try:
                out[aid] = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    discarded_path = sel_dir / DISCARDED_FILE
    if discarded_path.exists():
        try:
            out["discarded"] = json.loads(discarded_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return out


def save_album_selection(source: str, album_id: str, filenames: list[str]) -> None:
    sel_dir = get_selections_dir(source)
    sel_dir.mkdir(parents=True, exist_ok=True)
    path = sel_dir / f"album_{album_id}.json"
    path.write_text(json.dumps(filenames, indent=2), encoding="utf-8")


def save_discarded(source: str, filenames: list[str]) -> None:
    sel_dir = get_selections_dir(source)
    sel_dir.mkdir(parents=True, exist_ok=True)
    path = sel_dir / DISCARDED_FILE
    path.write_text(json.dumps(filenames, indent=2), encoding="utf-8")


def copy_to_dirs(source: str = "", output_base: Path | None = None) -> dict:
    """
    Copy each album's selected photos into a folder per album.
    source: which photo source ('' or subdir name). Output is under output_base/<source>/album_*.
    """
    out_base = (output_base or OUTPUT_DIR).resolve()
    photos_base = get_photos_dir(source)
    if not photos_base.exists():
        return {"error": "Photos directory does not exist", "copied": {}}
    sel = load_selections(source)
    # Output per source: output/_root/... or output/engagement/...
    source_slug = source if source else ROOT_SOURCE_KEY
    out_base = out_base / source_slug
    result = {"output_dir": str(out_base), "copied": {}}
    for aid in ALBUM_IDS:
        filenames = sel.get(aid) or []
        if not filenames:
            result["copied"][aid] = 0
            continue
        album_dir = out_base / f"album_{aid}"
        album_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for fn in filenames:
            src = photos_base / fn
            if not src.is_file():
                continue
            shutil.copy2(src, album_dir / fn)
            count += 1
        result["copied"][aid] = count
    return result


@app.route("/api/albums")
def albums():
    return jsonify(ALBUMS)


@app.route("/api/sources")
def api_sources():
    return jsonify(list_sources())


@app.route("/api/photos")
def photos():
    sort_by = request.args.get("sort", "date")
    source = request.args.get("source", "")
    if sort_by not in ("date", "name"):
        sort_by = "date"
    return jsonify(list_photos(sort_by, source))


@app.route("/api/photo/<path:path>")
def photo_file(path):
    """Serve image; path is relative to PHOTOS_DIR (e.g. 'IMG_001.jpg' or 'engagement/IMG_001.jpg')."""
    return send_from_directory(PHOTOS_DIR, path)


@app.route("/api/selections", methods=["GET"])
def get_selections():
    source = request.args.get("source", "")
    return jsonify(load_selections(source))


@app.route("/api/selections", methods=["POST"])
def update_selections():
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    source = data.pop("source", "")
    for aid in ALBUM_IDS:
        if aid in data and isinstance(data[aid], list):
            save_album_selection(source, aid, data[aid])
    if "discarded" in data and isinstance(data["discarded"], list):
        save_discarded(source, data["discarded"])
    return jsonify(load_selections(source))


@app.route("/api/copy-to-dirs", methods=["POST"])
def api_copy_to_dirs():
    """Copy selected images into separate folders per album for the current source."""
    data = request.get_json() or {}
    source = data.get("source", "")
    output_dir = data.get("output_dir")
    if output_dir:
        try:
            out_path = Path(output_dir).resolve()
        except Exception as e:
            return jsonify({"error": str(e)}), 400
    else:
        out_path = None
    try:
        result = copy_to_dirs(source, out_path)
        if "error" in result:
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        PHOTOS_DIR = Path(sys.argv[1]).resolve()
    print(f"Photos directory: {PHOTOS_DIR}")
    print("Open http://127.0.0.1:8000 in your browser.")
    app.run(host="127.0.0.1", port=8000, debug=True)