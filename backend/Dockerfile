# Alternative to Vercel: any Docker host. Build from the REPOSITORY ROOT:  docker build -f backend/Dockerfile -t aegisone-api backend
# (the build context is backend/ itself)
FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv/backend

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY app app
COPY data/processed data/processed
COPY data/models data/models

# Bake the deterministic demo database into the image so cold starts are fast and identical on every host.
RUN python -m app.datagen

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
