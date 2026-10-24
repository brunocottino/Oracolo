# Immagine per Hugging Face Space (SDK Docker, gratuito). Vedi AVVIO_HF.md.
FROM python:3.12-slim

RUN useradd -m -u 1000 user
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .
USER user

# Disco temporaneo: archivio e cache in /tmp; al primo avvio parte il Laboratorio (--fast)
ENV PORT=7860 \
    ORACOLO_DB=/tmp/oracolo/oracolo.sqlite \
    ORACOLO_AUTO_SCAN=1 \
    ORACOLO_SCAN_HOUR=22 \
    ORACOLO_LAB_ON_START=1 \
    PYTHONUNBUFFERED=1

EXPOSE 7860
CMD ["gunicorn", "app:app", "--workers", "1", "--threads", "8", "--timeout", "300", "--bind", "0.0.0.0:7860"]
