#!/bin/sh
set -eu

export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
export OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434/api/generate}"
# Espaces et points finaux retirés : « llama3.2:3b. » saisi par erreur reste valide.
export OLLAMA_MODEL="$(printf '%s' "${OLLAMA_MODEL:-llama3.2:3b}" | tr -d '[:space:]' | sed 's/\.*$//')"
export OLLAMA_TIMEOUT_SECONDS="${OLLAMA_TIMEOUT_SECONDS:-180}"
export OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:-30m}"

# Poids du modèle dans /data (volume ou stockage persistant) s'il est accessible.
export OLLAMA_MODELS="${OLLAMA_MODELS:-/data/ollama/models}"
if ! mkdir -p "$OLLAMA_MODELS" 2>/dev/null; then
    export OLLAMA_MODELS="${HOME:-/tmp}/.ollama/models"
    mkdir -p "$OLLAMA_MODELS"
fi

echo "Démarrage d'Ollama (${OLLAMA_HOST}), modèle ${OLLAMA_MODEL}, dossier ${OLLAMA_MODELS}"
ollama serve &
OLLAMA_PID=$!
for attempt in $(seq 1 60); do
    curl --silent --fail http://127.0.0.1:11434/api/tags >/dev/null && break
    kill -0 "$OLLAMA_PID" 2>/dev/null || { echo "ERREUR : Ollama s'est arrêté." >&2; exit 1; }
    sleep 2
done

# Téléchargement en arrière-plan : /health et /ready répondent pendant ce temps.
(
    ollama pull "$OLLAMA_MODEL" && \
    curl --silent --fail http://127.0.0.1:11434/api/generate \
         -d "{\"model\":\"${OLLAMA_MODEL}\",\"prompt\":\"ok\",\"stream\":false,\"keep_alive\":\"${OLLAMA_KEEP_ALIVE}\"}" >/dev/null \
    && echo "Modèle ${OLLAMA_MODEL} prêt."
) &

exec uvicorn src.app:app --host 0.0.0.0 --port "${PORT:-7860}"
