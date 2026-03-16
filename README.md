# Wedding photo album selector

A simple tool to sort wedding photos into four albums (Us, My parents, Wife's father, Wife's mother), with optional discard. Photos can be in multiple albums.

## Preview

![UI preview](priview.png)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Run

**Default:** uses a `photos` folder next to the app. You can put all images in `photos/` or use **subfolders** (e.g. `photos/ceremony/`, `photos/reception/`). The app lists "Root" (images directly in `photos`) and each subfolder that contains images; use the **Folder** dropdown to switch between them.

```bash
python app.py
```

**Custom folder:**

```bash
python app.py /path/to/your/wedding/photos
```

Then open **http://127.0.0.1:8000** in your browser.

## Usage

- **Sort:** Use “Sort by date” (EXIF or file date) or “Sort by name”.
- **Preview:** Current photo is shown large; use **← / →** or **K / J** to move.
- **Assign to album:** Click an album button or press its configured shortcut key (set via **Settings**). A photo can be in more than one album.
- **Discard:** Click “Discard” or press **D** (or Delete). Discarded photos are listed in `selections/discarded.json`.

Selections are saved automatically **per folder**. For the root folder they live in `selections/_root/`; for a subfolder like `ceremony` they live in `selections/ceremony/`:

- `selections/_root/album_us.json` (or `selections/ceremony/album_us.json`, etc.)
- `selections/_root/album_my_parents.json`
- `selections/_root/album_wife_father.json`
- `selections/_root/album_wife_mother.json`
- `selections/_root/discarded.json`

Each file is a JSON array of image filenames (e.g. `["IMG_001.jpg", "IMG_002.jpg"]`).

**Copy to dirs** writes one set of album folders per source, e.g. `output/_root/album_us/` and `output/ceremony/album_us/`.



