# Build from the REPOSITORY ROOT:  docker build -f backend/Dockerfile -t aegisone-api .
FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/app backend/app
COPY data/processed data/processed
COPY data/models data/models

# Bake the deterministic demo database into the image so cold starts are fast and identical on every host.
WORKDIR /srv/backend
RUN python -m app.datagen

ENV AEGIS_CORS_ORIGINS=""
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
