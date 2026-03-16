"""Servico HTTP para transcricao de audio via Whisper."""

import logging
import tempfile
import os

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("whisper-service")

app = FastAPI(title="Whisper Transcription Service")

# Carrega modelo na inicializacao (evita recarregar a cada request)
_model = None
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "medium")


def _get_model():
    global _model
    if _model is None:
        import whisper
        logger.info("Carregando modelo Whisper '%s'...", WHISPER_MODEL)
        _model = whisper.load_model(WHISPER_MODEL)
        logger.info("Modelo carregado.")
    return _model


@app.on_event("startup")
async def startup():
    """Pre-carrega modelo no startup."""
    _get_model()


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """Transcreve arquivo de audio e retorna texto."""
    try:
        audio_bytes = await file.read()

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            model = _get_model()
            result = model.transcribe(tmp_path, language="pt")
            text = result.get("text", "").strip()
            logger.info("Transcricao: %d chars", len(text))
            return JSONResponse({"text": text})
        finally:
            os.unlink(tmp_path)

    except Exception as e:
        logger.error("Erro na transcricao: %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/health")
async def health():
    return {"status": "ok", "model": WHISPER_MODEL}
