# Pitch deck — standalone Docker build (no local Python)

Generates **`IoT_Data_Interpreter_Pitch.pptx`** (14 slides) from
[`build_deck.py`](build_deck.py) using `python-pptx`.

This is **completely separate from the app** — `docker compose up` never builds
it. You build and run this image on its own, only when you want the deck.

> Prerequisite: **Docker Desktop** installed and running.

---

## Build, then run (two commands, from the project root)

**PowerShell (Windows):**
```powershell
docker build -t iot-deck ./deck
docker run --rm -v "${PWD}/deck:/out" iot-deck
```

**bash (macOS / Linux):**
```bash
docker build -t iot-deck ./deck
docker run --rm -v "$(pwd)/deck:/out" iot-deck
```

The file appears at **`deck/IoT_Data_Interpreter_Pitch.pptx`**. Open it in PowerPoint.

> Rebuild the image (`docker build ...`) only when you change `build_deck.py`.
> After that, just re-run the `docker run ...` line.

---

## If the file doesn't appear (Windows volume mount)
Use the full path explicitly, or copy it out of the container:

```powershell
# Option 1: explicit path
docker run --rm -v "E:\development\cg\deck:/out" iot-deck

# Option 2: copy out (no volume needed)
docker run --name deckgen iot-deck
docker cp deckgen:/out/IoT_Data_Interpreter_Pitch.pptx ./deck/
docker rm deckgen
```
Also check Docker Desktop -> Settings -> Resources -> File sharing includes your `E:` drive.

---

## Editing the deck
All content and styling live in [`build_deck.py`](build_deck.py) — text is in the
`s_*()` functions, colors/fonts at the top. Change text, rebuild, re-run.

> Authored carefully but **not render-tested here** (no local Python/LibreOffice).
> Open it once in PowerPoint and skim for any wrapping you'd like tightened.
