"""Generate the IoT Data Interpreter Agent pitch deck (python-pptx).

Run locally:   python build_deck.py [output.pptx]
Run in Docker: see deck/README.md

Design notes:
- Committed light, premium theme matching the Wise design language (DESIGN.md).
- Sage-tinted canvas, white rounded cards, Ink text, and Primary Lime Green CTA.
- Clean typography and spacing (no artificial "AI" engineering kickers).
- Factual stat callouts only.
"""

from __future__ import annotations

import sys

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

# ── palette (Wise Design Tokens) ──────────────────────────────────────
PRIMARY = RGBColor(0x9F, 0xE8, 0x70)       # lime-green
ON_PRIMARY = RGBColor(0x0E, 0x0F, 0x0C)
PRIMARY_PALE = RGBColor(0xE2, 0xF6, 0xD5)  # soft surface tint
CANVAS_SOFT = RGBColor(0xE8, 0xEB, 0xE6)   # sage-tinted background
CANVAS = RGBColor(0xFF, 0xFF, 0xFF)        # pure white card surface
INK = RGBColor(0x0E, 0x0F, 0x0C)           # near-black
BODY_C = RGBColor(0x45, 0x47, 0x45)        # body text
MUTE = RGBColor(0x86, 0x86, 0x85)          # captions
POSITIVE = RGBColor(0x2E, 0xAD, 0x4B)
WARNING = RGBColor(0xFF, 0xD1, 0x1A)
NEGATIVE = RGBColor(0xD0, 0x32, 0x38)
LINE = RGBColor(0xD0, 0xD0, 0xD0)          # subtle borders if needed

HEAD = "Inter"
BODY = "Inter"

W, H = 13.333, 7.5      # 16:9 in inches
MARGIN = 0.75

prs = Presentation()
prs.slide_width = Inches(W)
prs.slide_height = Inches(H)


# ── primitives ────────────────────────────────────────────────────────
def slide(bg_color=CANVAS_SOFT):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    r = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    r.fill.solid()
    r.fill.fore_color.rgb = bg_color
    r.line.fill.background()
    r.shadow.inherit = False
    return s


def rect(s, x, y, w, h, fill, line=None, rounded=False, radius=0.06, line_w=1.0):
    shp = s.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h),
    )
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(line_w)
    shp.shadow.inherit = False
    if rounded:
        try:
            shp.adjustments[0] = radius
        except Exception:
            pass
    return shp


def text(s, x, y, w, h, lines, size=15, color=INK, bold=False, italic=False,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, font=BODY, gap=5,
         leading=1.1, margin=0.04):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, m, Inches(margin))
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(gap)
        p.space_before = Pt(0)
        p.line_spacing = leading
        txt, o = (ln if isinstance(ln, tuple) else (ln, {}))
        run = p.add_run()
        run.text = txt
        f = run.font
        f.size = Pt(o.get("size", size))
        f.bold = o.get("bold", bold)
        f.italic = o.get("italic", italic)
        f.name = o.get("font", font)
        f.color.rgb = o.get("color", color)
    return tb


def bullets(s, x, y, w, h, items, size=14.5, gap=10, marker_color=PRIMARY,
            head_color=INK, body_color=BODY_C, leading=1.1):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, m, Inches(0.04))
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap)
        p.line_spacing = leading
        mk = p.add_run()
        mk.text = "•  "
        mk.font.name = HEAD
        mk.font.size = Pt(size)
        mk.font.bold = True
        mk.font.color.rgb = marker_color
        if isinstance(it, tuple):
            head, body = it
            r1 = p.add_run()
            r1.text = head + " "
            r1.font.name = BODY
            r1.font.size = Pt(size)
            r1.font.bold = True
            r1.font.color.rgb = head_color
            r2 = p.add_run()
            r2.text = body
            r2.font.name = BODY
            r2.font.size = Pt(size)
            r2.font.color.rgb = body_color
        else:
            r = p.add_run()
            r.text = it
            r.font.name = BODY
            r.font.size = Pt(size)
            r.font.color.rgb = head_color
    return tb


def card(s, x, y, w, h, head, body, accent=None):
    rect(s, x, y, w, h, CANVAS, rounded=True, radius=0.06)
    if accent:
        bar = rect(s, x + 0.25, y + 0.35, 0.1, h - 0.7, accent, rounded=True, radius=0.5)
        bar.line.fill.background()
    pad = 0.55 if accent else 0.35
    text(s, x + pad, y + 0.25, w - pad - 0.25, h - 0.5,
         [(head, {"size": 16, "bold": True, "color": INK, "font": HEAD}),
          (body, {"size": 13.5, "color": BODY_C, "font": BODY})],
         anchor=MSO_ANCHOR.MIDDLE, gap=6)


def numdot(s, x, y, d, label, color=PRIMARY, text_color=ON_PRIMARY):
    o = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    o.fill.solid()
    o.fill.fore_color.rgb = color
    o.line.fill.background()
    o.shadow.inherit = False
    tf = o.text_frame
    tf.word_wrap = False
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, m, 0)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.name = HEAD
    r.font.size = Pt(13)
    r.font.bold = True
    r.font.color.rgb = text_color
    return o


def sparkline(s, x, y, w, h, pts, color=PRIMARY, width=2.5):
    n = len(pts)
    for i in range(n - 1):
        x1 = x + w * i / (n - 1)
        x2 = x + w * (i + 1) / (n - 1)
        y1 = y + h * (1 - pts[i])
        y2 = y + h * (1 - pts[i + 1])
        c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
        c.line.color.rgb = color
        c.line.width = Pt(width)
        c.shadow.inherit = False


def chip(s, x, y, w, h, label, bg=PRIMARY_PALE, fg=INK, font=BODY, size=12, bold=True):
    rect(s, x, y, w, h, bg, rounded=True, radius=0.5)
    text(s, x + 0.1, y, w - 0.2, h, [(label, {"size": size, "color": fg, "font": font, "bold": bold})],
         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


def base(s, idx, title, subtitle=None):
    # Header / Kicker
    text(s, MARGIN, 0.6, 0.8, 0.4,
         [(f"{idx:02d}", {"size": 22, "color": MUTE, "bold": True, "font": HEAD})])
    text(s, MARGIN + 0.7, 0.58, 11.0, 0.5,
         [(title, {"size": 32, "color": INK, "bold": True, "font": HEAD})])
    if subtitle:
        text(s, MARGIN + 0.7, 1.15, 11.0, 0.4,
             [(subtitle, {"size": 17, "color": BODY_C, "font": BODY})])
    
    # Footer
    text(s, MARGIN, H - 0.46, 8, 0.32,
         [("IoT Data Interpreter", {"size": 11, "color": MUTE, "font": BODY})])


# ── slides ────────────────────────────────────────────────────────────
def s_title():
    s = slide(bg_color=INK)
    text(s, MARGIN, 2.0, 11.8, 1.4,
         [("IoT Data Interpreter", {"size": 64, "color": PRIMARY, "bold": True, "font": HEAD})])
    text(s, MARGIN, 3.2, 9.7, 1.0,
         [("An AI reasoning layer that sits on top of any sensor stream and turns raw telemetry into explanations, anomaly flags, and maintenance actions.", 
           {"size": 20, "color": CANVAS, "font": BODY})],
         leading=1.2)
    
    chip(s, MARGIN, 5.2, 2.8, 0.45, "Builathon  ·  Use Case #43", bg=PRIMARY, fg=ON_PRIMARY, size=12)
    chip(s, MARGIN + 3.0, 5.2, 4.0, 0.45, "Working prototype ready", bg=CANVAS_SOFT, fg=INK, size=12)


def s_problem():
    s = slide()
    base(s, 1, "Dashboards show data, not meaning", "Why staring at red charts doesn't scale.")
    
    text(s, MARGIN, 2.0, 5.55, 2.6,
         [("A red value tells an operator a threshold was crossed. It does not say "
           "why it happened, whether it matters, or what to do next.",
           {"size": 18, "color": INK, "font": BODY, "bold": True}),
          ("Interpreting every spike still requires a domain expert — and there are "
           "never enough experts to watch every sensor.",
           {"size": 17, "color": BODY_C, "font": BODY})],
         leading=1.3, gap=16)
    
    rows = [
        ("Undetected anomalies", "Unplanned downtime and safety incidents", NEGATIVE),
        ("Alert fatigue", "Real warnings ignored, response delayed", WARNING),
        ("Reactive maintenance", "Higher repair cost, shorter asset life", WARNING),
        ("Noisy or missing data", "Decisions made on corrupted signals", MUTE),
    ]
    cx, cw, ch, gap = 6.85, 5.75, 1.0, 0.2
    for i, (h, b, a) in enumerate(rows):
        card(s, cx, 2.0 + i * (ch + gap), cw, ch, h, b, accent=a)


def s_whynow():
    s = slide()
    base(s, 2, "Three shifts make this possible")
    cols = [
        ("1", "LLM reasoning", "Models read structured sensor data and explain it in clear "
         "language, moving beyond fixed alert templates."),
        ("2", "Mature IoT pipelines", "MQTT and managed IoT hubs make ingesting real sensor streams "
         "standard, cheap, and reliable."),
        ("3", "Agentic tooling", "Tool-use loops allow a model to investigate across many signals, "
         "not just answer a single fixed prompt."),
    ]
    cw, gap = 3.78, 0.28
    x0 = MARGIN
    for i, (n, h, b) in enumerate(cols):
        x = x0 + i * (cw + gap)
        rect(s, x, 2.2, cw, 3.8, CANVAS, rounded=True, radius=0.06)
        numdot(s, x + 0.4, 2.6, 0.66, n, color=PRIMARY_PALE, text_color=INK)
        text(s, x + 0.4, 3.5, cw - 0.8, 0.5,
             [(h, {"size": 22, "color": INK, "bold": True, "font": HEAD})])
        text(s, x + 0.4, 4.1, cw - 0.8, 1.4,
             [(b, {"size": 15, "color": BODY_C, "font": BODY})], leading=1.3)


def s_solution():
    s = slide()
    base(s, 3, "A reasoning layer between sensors and people")
    text(s, MARGIN, 1.8, 11.9, 0.4,
         [("It's not a smarter chart. It's a layer that detects, explains, and recommends.",
           {"size": 18, "color": MUTE, "font": BODY, "italic": True})])
    
    labels = ["Sensor stream", "Clean & Score", "Detect Anomalies",
              "Narrate (LLM)", "Recommend Action"]
    cw, gap, ch, y = 2.0, 0.42, 1.2, 2.8
    x = MARGIN
    for i, lab in enumerate(labels):
        bg = PRIMARY if i in (2, 3) else CANVAS
        tc = ON_PRIMARY if i in (2, 3) else INK
        rect(s, x, y, cw, ch, bg, rounded=True, radius=0.1)
        text(s, x + 0.12, y, cw - 0.24, ch,
             [(lab, {"size": 15, "color": tc, "bold": True, "font": HEAD})],
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, leading=1.1)
        if i < len(labels) - 1:
            text(s, x + cw, y, gap, ch, [(">", {"size": 24, "color": MUTE, "bold": True, "font": HEAD})],
                 align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        x += cw + gap
        
    stats = [("6", "sensors simulated"), ("3", "detection methods"),
             ("5", "fault scenarios"), ("0", "API keys to run")]
    sw = 11.9 / 4
    for i, (n, lab) in enumerate(stats):
        sx = MARGIN + i * sw
        text(s, sx, 4.8, sw - 0.2, 0.8, [(n, {"size": 56, "color": INK, "bold": True, "font": HEAD})])
        text(s, sx, 5.8, sw - 0.2, 0.5, [(lab, {"size": 15, "color": BODY_C, "font": BODY})])


def s_built():
    s = slide()
    base(s, 4, "A working prototype, end to end")
    left = [
        "Realistic multi-sensor simulator with switchable fault scenarios",
        "Multi-method anomaly detection (statistical + ML)",
        "Data-quality scoring: separates broken sensors from real faults",
        "LLM narration with a deterministic fallback",
    ]
    right = [
        "Agentic investigator: a real Claude tool-use loop",
        "Live dashboard — no front-end build, no CDN required",
        "Auto-generated incident reports (HTML export)",
        "Reproducible evaluation harness; fully Dockerized",
    ]
    bullets(s, MARGIN, 2.2, 5.7, 2.7, left, size=15, gap=14)
    bullets(s, MARGIN + 6.05, 2.2, 5.7, 2.7, right, size=15, gap=14)
    
    rect(s, MARGIN, 5.5, 11.85, 1.2, CANVAS, rounded=True, radius=0.06)
    text(s, MARGIN + 0.4, 5.5, 11.1, 1.2,
         [("Honest scope:", {"size": 16, "color": INK, "bold": True, "font": HEAD}),
          (" There is no physical hardware. Sensors are simulated. Real devices integrate "
           "behind a single interface.",
           {"size": 15, "color": BODY_C, "font": BODY})],
         anchor=MSO_ANCHOR.MIDDLE)


def s_demo():
    s = slide()
    base(s, 5, "Sixty seconds, four moments")
    steps = [
        ("1", "Trigger an HVAC failure", "Temperature climbs; a narrated anomaly appears, "
         "with a correlated humidity sensor."),
        ("2", "Trigger a sensor malfunction", "The system flags a sensor fault — avoiding a "
         "false equipment alarm."),
        ("3", "Run Deep Investigation", "The agent inspects the fleet and writes a "
         "prioritized incident report."),
        ("4", "Export the report", "One click to a clean HTML report, ready to save as PDF."),
    ]
    cw, ch, gx, gy = 5.78, 1.7, 0.28, 0.24
    for i, (n, h, b) in enumerate(steps):
        x = MARGIN + (i % 2) * (cw + gx)
        y = 2.0 + (i // 2) * (ch + gy)
        rect(s, x, y, cw, ch, CANVAS, rounded=True, radius=0.06)
        numdot(s, x + 0.4, y + 0.4, 0.6, n, color=PRIMARY_PALE, text_color=INK)
        text(s, x + 1.3, y + 0.35, cw - 1.6, 0.5,
             [(h, {"size": 18, "color": INK, "bold": True, "font": HEAD})])
        text(s, x + 1.3, y + 0.85, cw - 1.6, 0.8,
             [(b, {"size": 14, "color": BODY_C, "font": BODY})], leading=1.2)
             
    text(s, MARGIN, 6.2, 11.9, 0.4,
         [("Runs fully offline by default. With an API key, the same flow uses live Claude.",
           {"size": 15, "color": MUTE, "font": BODY, "italic": True})])


def s_architecture():
    s = slide()
    base(s, 6, "How it works")
    boxes = [
        ("Data source", "simulator  |  MQTT (real hardware)"),
        ("Processing", "buffer  →  impute  →  quality  →  anomaly"),
        ("Engine", "orchestration  ·  edge-triggered alerts  ·  live WebSocket"),
        ("Reasoning", "narrator (1 call)  +  investigator (agent loop)  +  fallback"),
        ("Delivery", "live dashboard  +  incident report"),
    ]
    bw, bh, gap, y = 9.5, 0.8, 0.25, 2.0
    bx = (W - bw) / 2
    for i, (h, b) in enumerate(boxes):
        bg = PRIMARY_PALE if i in (1, 3) else CANVAS
        rect(s, bx, y, bw, bh, bg, rounded=True, radius=0.1)
        text(s, bx + 0.4, y, 2.5, bh,
             [(h, {"size": 16, "color": INK, "bold": True, "font": HEAD})],
             anchor=MSO_ANCHOR.MIDDLE)
        text(s, bx + 2.8, y, bw - 3.0, bh,
             [(b, {"size": 14, "color": BODY_C, "font": BODY})],
             anchor=MSO_ANCHOR.MIDDLE)
        y += bh + gap


def s_detection():
    s = slide()
    base(s, 7, "Detection you can defend")
    items = [
        ("Z-score vs. a reference window —", "catches gradual ramps, not just spikes."),
        ("IQR fence —", "robust outlier bounds, resistant to skew."),
        ("Isolation Forest —", "unsupervised ML over value and local slope."),
        ("Voting + 2-tick persistence —", "sensitive to real faults, quiet on noise."),
        ("Confidence scoring —", "flags low-quality data instead of trusting it."),
    ]
    bullets(s, MARGIN, 2.0, 7.0, 4.0, items, size=16, gap=16)
    
    px, pw = 8.35, 4.25
    rect(s, px, 2.0, pw, 2.8, CANVAS, rounded=True, radius=0.06)
    text(s, px + 0.4, 2.2, pw - 0.8, 0.4,
         [("Live Signal", {"size": 14, "color": INK, "bold": True, "font": HEAD})])
    sparkline(s, px + 0.4, 2.8, pw - 0.8, 1.6,
              [0.25, 0.27, 0.24, 0.30, 0.45, 0.6, 0.78, 0.9, 0.84, 0.88], color=PRIMARY, width=3.5)
              
    legend = [("Low", POSITIVE), ("Moderate", WARNING), ("Critical", NEGATIVE)]
    lx = px
    for lab, col in legend:
        sq = rect(s, lx, 5.1, 0.25, 0.25, col, rounded=True, radius=0.2)
        text(s, lx + 0.35, 5.05, 1.0, 0.35, [(lab, {"size": 13, "color": MUTE, "font": BODY})])
        lx += 1.3


def s_agentic():
    s = slide()
    base(s, 8, "From narration to investigation")
    panels = [
        ("Narrator", "One grounded, structured call per anomaly:",
         ["Plain-English summary", "Severity classification",
          "Root-cause hypothesis", "Recommended action"], PRIMARY_PALE),
        ("Investigator", "A real tool-use loop across the fleet:",
         ["List sensors", "Pull recent history", "Find correlations",
          "Write a prioritized incident report"], CANVAS),
    ]
    pw, gap = 5.78, 0.29
    for i, (h, sub, pts, bg) in enumerate(panels):
        x = MARGIN + i * (pw + gap)
        rect(s, x, 2.0, pw, 3.8, bg, rounded=True, radius=0.06)
        text(s, x + 0.4, 2.3, pw - 0.8, 0.5, [(h, {"size": 24, "color": INK, "bold": True, "font": HEAD})])
        text(s, x + 0.4, 2.9, pw - 0.8, 0.5, [(sub, {"size": 15, "color": BODY_C, "font": BODY})])
        bullets(s, x + 0.4, 3.5, pw - 0.8, 2.0, pts, size=15, gap=10, marker_color=INK)
        
    rect(s, MARGIN, 6.1, 11.85, 0.8, CANVAS, rounded=True, radius=0.08)
    text(s, MARGIN + 0.4, 6.1, 11.1, 0.8,
         [("Grounded strictly in the data. The system says “undetermined” rather than guessing.",
           {"size": 15, "color": MUTE, "font": BODY, "italic": True})], anchor=MSO_ANCHOR.MIDDLE)


def s_trust():
    s = slide()
    base(s, 9, "Built to be trusted")
    rows = [
        ("Sensor fault vs. real anomaly", "Confidence scoring separates a malfunctioning sensor "
         "from a genuine process change."),
        ("Communicates uncertainty", "Every sensor carries a confidence score; low-quality data "
         "is flagged, not trusted blindly."),
        ("Grounded by design", "Prompts forbid speculation beyond the data, preventing "
         "hallucinated causes."),
        ("Works without the cloud", "A deterministic fallback keeps the product running with no "
         "API key and no network connection."),
    ]
    y = 2.0
    for i, (h, b) in enumerate(rows):
        rect(s, MARGIN, y, 11.85, 1.0, CANVAS, rounded=True, radius=0.07)
        numdot(s, MARGIN + 0.3, y + 0.25, 0.5, f"{i+1}", color=PRIMARY_PALE, text_color=INK)
        text(s, MARGIN + 1.1, y, 3.6, 1.0,
             [(h, {"size": 16, "color": INK, "bold": True, "font": HEAD})], anchor=MSO_ANCHOR.MIDDLE)
        text(s, MARGIN + 4.95, y, 6.7, 1.0,
             [(b, {"size": 15, "color": BODY_C, "font": BODY})], anchor=MSO_ANCHOR.MIDDLE, leading=1.2)
        y += 1.0 + 0.16


def s_hardware():
    s = slide()
    base(s, 10, "Hardware is a drop-in, not a rebuild")
    text(s, MARGIN, 1.8, 6.0, 2.0,
         [("Everything consumes one DataSource interface. The simulator is one "
           "implementation; MQTT is another.", {"size": 18, "color": INK, "font": BODY})],
         leading=1.3)
    steps = ["Point sensors at an MQTT broker", "Set one variable: DATA_SOURCE=mqtt",
             "Adapt one parser to your schema"]
    y = 3.6
    for i, st in enumerate(steps):
        numdot(s, MARGIN, y, 0.5, f"{i+1}", color=PRIMARY_PALE, text_color=INK)
        text(s, MARGIN + 0.7, y - 0.05, 5.3, 0.6, [(st, {"size": 16, "color": BODY_C, "font": BODY})],
             anchor=MSO_ANCHOR.MIDDLE)
        y += 0.72
        
    px, pw = 7.1, 5.45
    rect(s, px, 2.0, pw, 2.6, INK, rounded=True, radius=0.06)
    text(s, px + 0.4, 2.3, pw - 0.8, 0.4,
         [(".env", {"size": 14, "color": MUTE, "bold": True, "font": HEAD})])
    text(s, px + 0.4, 2.9, pw - 0.8, 1.4,
         [("DATA_SOURCE=mqtt", {"size": 18, "color": PRIMARY, "font": HEAD}),
          ("MQTT_TOPIC=sensors/#", {"size": 18, "color": CANVAS, "font": HEAD})], gap=12)
          
    text(s, px, 4.9, pw, 1.0,
         [("No other code changes.", {"size": 16, "color": POSITIVE, "bold": True, "font": HEAD}),
          ("Same pipeline — real telemetry instead of simulated.", {"size": 15, "color": BODY_C, "font": BODY})],
         gap=6)


def s_eval():
    s = slide()
    base(s, 11, "Measured, not claimed")
    text(s, MARGIN, 2.0, 11.6, 2.0,
         [("A labeled golden dataset and an evaluation harness report precision, recall, "
           "and F1 for the detector — reproducible with a single command.",
           {"size": 19, "color": INK, "font": BODY}),
          ("The dataset deliberately includes a stuck-sensor case, to confirm the system "
           "does not raise a process anomaly for a malfunction.",
           {"size": 17, "color": BODY_C, "font": BODY})], leading=1.3, gap=16)
           
    rect(s, MARGIN, 4.2, 6.2, 0.9, INK, rounded=True, radius=0.1)
    text(s, MARGIN + 0.4, 4.2, 5.8, 0.9,
         [("python -m evaluation.evaluate", {"size": 18, "color": PRIMARY, "font": HEAD})],
         anchor=MSO_ANCHOR.MIDDLE)
         
    rect(s, MARGIN, 5.5, 11.85, 1.0, CANVAS, rounded=True, radius=0.07)
    text(s, MARGIN + 0.4, 5.5, 11.1, 1.0,
         [("We present the method and let the numbers come from your machine — "
           "not metrics we invented for a slide.",
           {"size": 15, "color": MUTE, "font": BODY, "italic": True})], anchor=MSO_ANCHOR.MIDDLE)


def s_roadmap():
    s = slide()
    base(s, 12, "What's built, what's next")
    built = ["Sensor simulation & scenarios", "Multi-method detection", "Narration & fallback",
             "Agentic investigator", "Dashboard & report", "Evaluation harness", "Docker & hardware interface"]
    nxt = ["Validate against real hardware streams", "Historical store & trend baselining",
           "Human feedback to tune recommendations", "Alert routing (Slack / SMS / email)",
           "Auth & multi-tenant", "Scale-out ingestion"]
    pw, gap = 5.78, 0.29
    
    rect(s, MARGIN, 2.0, pw, 4.5, CANVAS, rounded=True, radius=0.05)
    text(s, MARGIN + 0.5, 2.3, pw - 1.0, 0.5, [("BUILT", {"size": 18, "color": INK, "bold": True, "font": HEAD})])
    bullets(s, MARGIN + 0.5, 2.9, pw - 1.0, 3.4, built, size=15, gap=12, marker_color=PRIMARY)
    
    x2 = MARGIN + pw + gap
    rect(s, x2, 2.0, pw, 4.5, CANVAS, rounded=True, radius=0.05)
    text(s, x2 + 0.5, 2.3, pw - 1.0, 0.5, [("NEXT", {"size": 18, "color": MUTE, "bold": True, "font": HEAD})])
    bullets(s, x2 + 0.5, 2.9, pw - 1.0, 3.4, nxt, size=15, gap=12, marker_color=MUTE)


def s_close():
    s = slide(bg_color=INK)
    text(s, MARGIN, 2.2, 11.8, 1.2,
         [("Machines that explain themselves", {"size": 48, "color": CANVAS, "bold": True, "font": HEAD})])
    text(s, MARGIN, 3.5, 10.8, 1.0,
         [("A reasoning layer that makes industrial intelligence accessible to every "
           "operator — not just data scientists.", {"size": 20, "color": PRIMARY_PALE, "font": BODY})],
         leading=1.3)
         
    rect(s, MARGIN, 5.0, 11.85, 1.6, CANVAS_SOFT, rounded=True, radius=0.06)
    text(s, MARGIN + 0.5, 5.15, 4.0, 1.3,
         [("What we're looking for", {"size": 18, "color": INK, "bold": True, "font": HEAD})],
         anchor=MSO_ANCHOR.MIDDLE)
    bullets(s, MARGIN + 4.5, 5.15, 7.0, 1.3,
            ["A pilot sensor feed or dataset to validate against",
             "Mentorship to harden it for production"], size=16, gap=12)


def build(path: str):
    s_title()
    s_problem()
    s_whynow()
    s_solution()
    s_built()
    s_demo()
    s_architecture()
    s_detection()
    s_agentic()
    s_trust()
    s_hardware()
    s_eval()
    s_roadmap()
    s_close()
    cp = prs.core_properties
    cp.title = "IoT Data Interpreter Agent"
    cp.author = "Builathon Use Case #43"
    cp.subject = "AI reasoning layer for IoT sensor streams"
    prs.save(path)
    print(f"Saved deck -> {path}  ({len(prs.slides)} slides)")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "IoT_Data_Interpreter_Pitch.pptx"
    build(out)
