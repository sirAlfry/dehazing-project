FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# Nel container non serve la GUI: si installa la variante "headless" di OpenCV,
# che non richiede librerie grafiche di sistema (libGL, GTK) ed e' piu' leggera.
# requirements.txt resta quello per lo sviluppo in locale (con GUI).
COPY requirements.txt .
RUN sed 's/^opencv-contrib-python>=/opencv-contrib-python-headless>=/' requirements.txt > requirements-docker.txt \
    && grep -q '^opencv-contrib-python-headless' requirements-docker.txt \
    && pip install --no-cache-dir -r requirements-docker.txt \
    && rm requirements-docker.txt

COPY src/ src/
COPY scripts/ scripts/
COPY tests/ tests/
COPY pytest.ini .

ENTRYPOINT ["python"]
CMD ["scripts/evaluate.py", "--help"]
