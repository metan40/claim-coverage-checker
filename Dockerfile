# Image du Space Hugging Face « claim-coverage-checker ».
# Un seul conteneur exécute Ollama (modèle de langage local) et l'API FastAPI.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860 \
    OLLAMA_HOST=127.0.0.1:11434 \
    OLLAMA_MODEL=llama3.2:3b

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl libgomp1 zstd \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://ollama.com/install.sh | sh

COPY requirements.txt requirements-app.txt ./
RUN python -m pip install --upgrade pip && pip install -r requirements-app.txt

# Hugging Face exécute les Spaces Docker avec l'utilisateur 1000.
RUN useradd -m -u 1000 user && mkdir -p /data && chown user /data

COPY --chown=user VERSION docker-entrypoint.sh ./
COPY --chown=user src ./src
COPY --chown=user static ./static
COPY --chown=user db ./db
COPY --chown=user models ./models
RUN chmod +x /app/docker-entrypoint.sh

ENV HOME=/home/user \
    PATH="/home/user/.local/bin:$PATH" \
    OLLAMA_MODELS=/data/ollama/models

USER user
EXPOSE 7860
CMD ["/app/docker-entrypoint.sh"]
