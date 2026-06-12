# 🛰 Startup Guide — IoT Data Interpreter

**A friendly, no-experience-needed guide to running this app on your computer.**

You do **not** need to know any coding. You'll install one free program, type
**one** command, and open a web page. That's the whole thing. ☕ Takes about
10–15 minutes the first time (mostly waiting for downloads).

> 💡 The app works **without internet or any account** once it's running. An AI
> key is optional (see the very end) — skip it for now.

---

## ✅ What you need (just one thing)

**Docker Desktop** — a free app that runs this project for you in a tidy box so
nothing clutters your computer.

- **Windows:** https://www.docker.com/products/docker-desktop/ → click
  *Download for Windows*.
- **Mac:** same link → *Download for Mac* (pick **Apple chip** or **Intel chip** —
  if unsure, click the Apple menu  → *About This Mac*; "Apple M1/M2/M3" = Apple chip).

---

## Part 1 — Install Docker Desktop

1. Open the file you just downloaded and follow the installer (keep clicking
   **Next / Install / OK**, accept the defaults).
2. When it finishes, **open Docker Desktop** (search for it in your Start menu /
   Applications).
3. Wait until it says **"Docker Desktop is running"** (on Windows you'll see a
   little **whale 🐳 icon** near the clock; it stops animating when ready).
   - First launch may ask you to accept terms or restart — that's normal.

> ⏳ **Don't skip this:** the app only works while Docker Desktop is open and
> running. Think of it as the engine — it has to be on.

---

## Part 2 — Open a terminal in the project folder

A "terminal" is just a box where you type one command. Here's the easy way:

### On Windows
1. Open **File Explorer** and go to the project folder (the one containing
   `docker-compose.yml` — it's this folder: `E:\development\cg`).
2. Click once in the **address bar** at the top (where the folder path is shown).
3. Type **`powershell`** and press **Enter**.
4. A dark blue window opens — that's your terminal, already pointed at the folder. ✅

### On Mac
1. Open **Terminal** (press `Cmd + Space`, type *Terminal*, press Enter).
2. Type `cd ` (the letters c, d, then a space) — **do not press Enter yet**.
3. **Drag the project folder** from Finder onto the Terminal window, then press **Enter**. ✅

---

## Part 3 — Start the app (one command)

In that terminal window, type this exactly and press **Enter**:

```
docker compose up --build
```

- **The first time, this downloads things and takes several minutes.** Lots of
  text will scroll by — that's good, leave it alone. ☕
- You'll know it's ready when you see a line like:

  ```
  Uvicorn running on http://0.0.0.0:8000
  Application startup complete.
  ```

➡️ **Leave this window open.** Closing it stops the app.

---

## Part 4 — Open the dashboard 🎉

Open your web browser (Chrome, Edge, Safari…) and go to:

### **http://localhost:8000**

You'll see a live dashboard with six sensors streaming. Try this 60-second demo:

1. Up top, click **"HVAC failure — data center."** Watch a sensor climb and an
   **anomaly card** appear on the right, explained in plain English.
2. Click **"Sensor malfunction."** Notice it's labeled a *SENSOR FAULT* — the app
   knows a broken sensor from a real problem.
3. Click the **⚙ Deep Investigation** button — it writes a full incident report.
4. Click **⤓ Report** to open a clean printable report (Print → Save as PDF).
5. Click **"Nominal operation"** to return everything to calm green.

That's it — you're running an AI IoT monitoring system. 🙌

---

## ⏹ How to stop it

- In the terminal window, press **`Ctrl` + `C`** (hold Ctrl, tap C).
- To fully shut down and free things up, type:
  ```
  docker compose down
  ```

**To start it again later** (Docker Desktop running), open the terminal in the
folder again and type:
```
docker compose up
```
*(You can drop `--build` after the first time — it starts much faster.)*

---

## 🆘 If something goes wrong

| What you see | What to do |
|---|---|
| `Cannot connect to the Docker daemon` / `docker: command not found` | Docker Desktop isn't running. Open it, wait for the whale 🐳 / "running", try again. |
| `port is already allocated` / `8000 ... in use` | Something else uses port 8000. Open `docker-compose.yml`, change `"8000:8000"` to `"8080:8000"`, save, run again, and use **http://localhost:8080**. |
| The browser page won't load | Wait for *"Application startup complete"* in the terminal first. Then refresh the page. Make sure you typed `localhost`, not `localhost:8000:8000`. |
| Lots of red text during `--build` the first time | Often just download noise. Wait for it to finish. If it stops with `ERROR`, copy the last ~15 lines and send them over. |
| Want to start completely fresh | `docker compose down` then `docker compose up --build`. |
| It's slow the very first time | Normal — it's downloading. Later runs are quick. |

---

## 🤖 Optional: turn on the live AI (Claude)

The app is fully functional without this — it uses a smart built-in engine. To
upgrade to **live Claude AI** narration:

1. In the project folder, open the file named **`.env`** with Notepad (Windows)
   or TextEdit (Mac).
2. Find the line:
   ```
   ANTHROPIC_API_KEY=
   ```
3. Paste your key right after the `=` (no spaces), so it looks like:
   ```
   ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
   ```
4. **Save** the file, then stop (`Ctrl+C`) and start again (`docker compose up`).
5. The badge at the top of the dashboard flips from **"Offline mode"** to
   **"Claude live."** ✨

---

*Questions? Send a screenshot of the terminal window — that usually tells the
whole story.* 💚
