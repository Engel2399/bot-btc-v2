#!/usr/bin/env bash
# Ejecuta el bot una vez con la configuración de .env y guarda el registro.
# Lo llama cron cada 4 horas; también puedes ejecutarlo a mano: bash ejecutar.sh
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1
mkdir -p logs
LOG="logs/bot.log"

# Evita que el registro crezca sin límite (~1 MB).
if [ -f "$LOG" ] && [ "$(stat -c%s "$LOG")" -gt 1000000 ]; then
  tail -n 3000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi

if [ ! -f .env ]; then
  echo "$(date -u '+%F %T') Falta .env: ejecuta bash instalar.sh" >> "$LOG"
  exit 1
fi

set -a
. ./.env
set +a

{
  echo "===== $(date -u '+%Y-%m-%d %H:%M:%S UTC') ====="
  # flock: nunca dos ejecuciones a la vez. timeout: máximo 5 minutos.
  flock -n /tmp/bot-btc-v2.lock timeout 300 .venv/bin/python bot.py
  echo "salida: $?"
} >> "$LOG" 2>&1
