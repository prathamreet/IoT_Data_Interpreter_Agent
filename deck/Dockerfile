# ── Pitch-deck generator (python-pptx) ───────────────────────────────
# Builds the .pptx into /out. Mount a host folder at /out to collect it.
FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir python-pptx && mkdir -p /out
COPY build_deck.py .

CMD ["python", "build_deck.py", "/out/IoT_Data_Interpreter_Pitch.pptx"]
