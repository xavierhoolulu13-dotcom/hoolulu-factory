#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Hoolulu Factory on Termux — the phone becomes the factory.
#
#   bash setup.sh              install everything and serve the model
#   bash setup.sh --no-model   install the stack, skip the model download
#   bash setup.sh --threads 4  pin fewer CPU threads (default 6)
#
# Run inside Termux on Android. Requires ~3 GB free for the default 3B model.
# Nothing here talks to the cloud.
# ---------------------------------------------------------------------------
set -euo pipefail

THREADS="${THREADS:-6}"
PORT="${PORT:-8080}"
MODEL_DIR="${MODEL_DIR:-$HOME/models}"
MODEL_URL="https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
MODEL_FILE="$MODEL_DIR/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
NO_MODEL=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-model) NO_MODEL=1; shift ;;
    --threads) THREADS="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

say() { printf '\n\033[1;36m%s\033[0m\n' "$*"; }

say "1/5 · updating Termux"
pkg update -y && pkg upgrade -y

say "2/5 · installing the stack"
pkg install -y python nodejs git termux-api wget

say "3/5 · cloning the factory"
REPO="$HOME/hoolulu-factory"
if [[ -d "$REPO/.git" ]]; then
  git -C "$REPO" pull --ff-only || echo "(left your local changes alone)"
else
  git clone https://github.com/xavierhoolulu13-dotcom/hoolulu-factory.git "$REPO"
fi
cd "$REPO"

say "4/5 · python environment"
python -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt

if [[ "$NO_MODEL" == "1" ]]; then
  say "5/5 · skipping the model (--no-model)"
  echo "Amanda will run deterministic until you serve one:"
  echo "  llama-server -m <model.gguf> --port $PORT -t $THREADS"
else
  say "5/5 · fetching the model (2.2 GB, Q4_K_M)"
  mkdir -p "$MODEL_DIR"
  if [[ -f "$MODEL_FILE" ]]; then
    echo "  already have $(basename "$MODEL_FILE")"
  else
    wget -O "$MODEL_FILE.part" "$MODEL_URL"
    mv "$MODEL_FILE.part" "$MODEL_FILE"
  fi

  say "serving $(basename "$MODEL_FILE") on :$PORT with $THREADS threads"
  export HOOLULU_OFFLINE_URL="http://localhost:$PORT/v1"
  nohup llama-server -m "$MODEL_FILE" --port "$PORT" -t "$THREADS" -c 4096 \
    >"$HOME/llama-server.log" 2>&1 &
  echo "  log: $HOME/llama-server.log"
  sleep 3
  curl -fsS "http://localhost:$PORT/v1/models" >/dev/null \
    && echo "  ✓ model answering" \
    || echo "  ! model not answering yet — check the log"
fi

say "done · start the factory"
cat <<EOF

  cd $REPO
  export HOOLULU_OFFLINE_URL=http://localhost:$PORT/v1
  hoolulu-ecosystem-hub/ops/start.sh        # console on :8010
  python -m amanda "build me a snake game and host it"

Optional, so the agents have hands (battery, location, notifications):
  pkg install -y termux-api
  Settings → Developer options → Wireless debugging → ON
  adb pair <phone-ip>:<pair-port> <code> && adb connect <phone-ip>:<connect-port>
EOF
