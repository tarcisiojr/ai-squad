# Servico Whisper dedicado para transcricao de audio
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    openai-whisper>=20231117 \
    fastapi>=0.100 \
    uvicorn>=0.23 \
    python-multipart>=0.0.6

WORKDIR /app
COPY server.py .

# Modelo sera baixado no primeiro startup ou montado via volume em /root/.cache/whisper
ENV WHISPER_MODEL=small

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
