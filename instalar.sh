#!/usr/bin/env bash
# Instalador del Bot V2 para un servidor Ubuntu (Oracle Cloud Always Free).
# Uso:  bash instalar.sh
# Puedes ejecutarlo de nuevo cuando quieras para cambiar la configuración.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo
echo "=== Bot V2 BTC · instalación en $DIR ==="

echo
echo "[1/6] Instalando paquetes del sistema (puede tardar 1-3 minutos)..."
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv python3-pip cron util-linux >/dev/null

echo "[2/6] Poniendo el reloj del servidor en UTC (las velas de Binance cierran en UTC)..."
sudo timedatectl set-timezone Etc/UTC || true
sudo timedatectl set-ntp true 2>/dev/null || true
sudo systemctl enable --now cron >/dev/null 2>&1 || true
sudo systemctl restart cron || true

echo "[3/6] Preparando Python..."
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

echo "[4/6] Configuración"
CONFIGURAR=s
if [ -f .env ]; then
  read -rp "  Ya existe una configuración. ¿Quieres reemplazarla? (s/N): " r
  [[ "${r,,}" == s* ]] || CONFIGURAR=n
fi

if [ "$CONFIGURAR" = s ]; then
  echo "  (Lo que escribas en los campos secretos no se verá en pantalla; es normal.)"
  read -rsp "  TELEGRAM_TOKEN: " TG_TOKEN; echo
  read -rp  "  TELEGRAM_CHAT_ID: " TG_CHAT
  read -rp  "  MODO [simulacion/testnet/real] (Enter = simulacion): " MODO
  MODO="${MODO:-simulacion}"
  read -rsp "  BINANCE_API_KEY (Enter para dejarla vacía por ahora): " BKEY; echo
  read -rsp "  BINANCE_API_SECRET (Enter para dejarla vacía por ahora): " BSEC; echo
  read -rp  "  CAPITAL_INICIAL en USDT (Enter = 100): " CAP
  CAP="${CAP:-100}"

  umask 077
  {
    printf 'TELEGRAM_TOKEN=%q\n' "$TG_TOKEN"
    printf 'TELEGRAM_CHAT_ID=%q\n' "$TG_CHAT"
    printf 'MODO=%q\n' "$MODO"
    printf 'BINANCE_API_KEY=%q\n' "$BKEY"
    printf 'BINANCE_API_SECRET=%q\n' "$BSEC"
    printf 'CAPITAL_INICIAL=%q\n' "$CAP"
    printf 'SMA_4H=200\nSMA_DIARIA=100\n'
    printf '# Si las claves de testnet fallan con demo-fapi, descomenta la línea siguiente:\n'
    printf '# BASE_URL=https://testnet.binancefuture.com\n'
  } > .env
  chmod 600 .env
  echo "  Guardado en $DIR/.env (solo tu usuario puede leerlo)."
fi

echo "[5/6] Programando el horario (5 min después de cada cierre de 4h)..."
LINEA="5 0,4,8,12,16,20 * * * /bin/bash $DIR/ejecutar.sh"
( crontab -l 2>/dev/null | grep -v "bot-btc-v2/ejecutar.sh" || true; echo "$LINEA" ) | crontab -
echo "  $LINEA"

echo "[6/6] Ejecución de prueba..."
/bin/bash "$DIR/ejecutar.sh" || true
echo "------------------- últimas líneas del registro -------------------"
tail -n 25 "$DIR/logs/bot.log" || true
echo "-------------------------------------------------------------------"
echo
echo "Listo. Debió llegarte un mensaje por Telegram."
echo "Comandos útiles:"
echo "  Ver registro:        tail -n 50 $DIR/logs/bot.log"
echo "  Ejecutar ahora:      bash $DIR/ejecutar.sh"
echo "  Cambiar config:      bash $DIR/instalar.sh   (o: nano $DIR/.env)"
echo "  Ver horario:         crontab -l"
echo "  Apagar el bot:       crontab -r"
