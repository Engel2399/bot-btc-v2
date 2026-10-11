"""
Bot V2 – BTCUSDT perpetuo (Binance Futures USDⓈ-M)
Largos y cortos con SMA 200 de 4h + filtro de tendencia diaria (SMA 100 por defecto).

Se ejecuta una vez y termina (GitHub Actions lo llama cada 4 horas, 5 minutos después del cierre).
En cada ejecución:
  1. Verifica configuración: margen AISLADO, 1x, modo one-way.
  2. Descarga velas cerradas de 4h y diarias del propio perpetuo.
  3. Calcula la posición objetivo:
        tendencia diaria alcista y cierre 4h > SMA200  -> LARGO
        tendencia diaria bajista y cierre 4h < SMA200  -> CORTO
        cualquier otro caso                            -> SIN POSICIÓN
  4. Lee la posición REAL en Binance y ajusta solo si no coincide.
  5. Mantiene un stop de emergencia (-8% largo / +8% corto) con closePosition y precio de marca.
  6. Interruptor: si el capital cae por debajo del 60% de CAPITAL_INICIAL, cierra todo y deja de operar.
  7. Avisa por Telegram de cada operación, de errores y con un resumen diario (00:05 UTC = 8:05 p. m. RD).

Variables de entorno (secretos/variables de GitHub):
  BINANCE_API_KEY, BINANCE_API_SECRET   claves de la API (solo permiso de futuros, SIN retiros)
  TELEGRAM_TOKEN, TELEGRAM_CHAT_ID      avisos (opcionales, pero muy recomendados)
  MODO             simulacion | testnet | real          (por defecto: simulacion)
  CAPITAL_INICIAL  capital con el que empiezas, en USDT  (por defecto: 100)
  SMA_4H           por defecto 200
  SMA_DIARIA       por defecto 100
  STOP_EMERGENCIA  por defecto 0.08 (8%)
  LIMITE_PAUSA     por defecto 0.60 (pausa si el capital cae por debajo del 60% del inicial)
  BASE_URL         opcional, para forzar otra URL de la API
"""
import hashlib
import hmac
import math
import os
import sys
import time
import urllib.parse

import requests

SYMBOL = "BTCUSDT"
MODO = os.getenv("MODO", "simulacion").strip().lower()
API_KEY = os.getenv("BINANCE_API_KEY", "").strip()
API_SECRET = os.getenv("BINANCE_API_SECRET", "").strip()
TG_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "").strip()
CAPITAL_INICIAL = float(os.getenv("CAPITAL_INICIAL", "100") or 100)
SMA_4H = int(os.getenv("SMA_4H", "200") or 200)
SMA_DIARIA = int(os.getenv("SMA_DIARIA", "100") or 100)
STOP_PCT = float(os.getenv("STOP_EMERGENCIA", "0.08") or 0.08)
LIMITE_PAUSA = float(os.getenv("LIMITE_PAUSA", "0.60") or 0.60)
MARGEN_SEGURIDAD = 0.98   # usa el 98% del saldo disponible para dejar espacio a comisiones

URLS = {"real": "https://fapi.binance.com", "testnet": "https://demo-fapi.binance.com",
        "simulacion": "https://fapi.binance.com"}
BASE = os.getenv("BASE_URL", "").strip() or URLS.get(MODO, URLS["simulacion"])
# En simulación sin claves se usan datos públicos de producción y no se envía ninguna orden.

session = requests.Session()
session.headers.update({"X-MBX-APIKEY": API_KEY} if API_KEY else {})
_offset_ms = 0


# ----------------------------------------------------------------------------- utilidades
def telegram(texto):
    print(texto)
    if not (TG_TOKEN and TG_CHAT):
        return
    try:
        session.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                     data={"chat_id": TG_CHAT, "text": f"[V2 · {MODO}]\n{texto}"}, timeout=15)
    except Exception as e:  # un fallo de Telegram nunca debe detener el bot
        print("No se pudo enviar a Telegram:", e)


class BinanceError(Exception):
    def __init__(self, code, msg):
        super().__init__(f"Binance {code}: {msg}")
        self.code = code


def publico(path, params=None):
    r = session.get(BASE + path, params=params or {}, timeout=20)
    if r.status_code != 200:
        raise BinanceError(r.status_code, r.text)
    return r.json()


def sincronizar_reloj():
    global _offset_ms
    t = publico("/fapi/v1/time")["serverTime"]
    _offset_ms = t - int(time.time() * 1000)
    return t


def firmado(metodo, path, params=None):
    if not (API_KEY and API_SECRET):
        raise RuntimeError("Faltan BINANCE_API_KEY / BINANCE_API_SECRET")
    params = dict(params or {})
    params["timestamp"] = int(time.time() * 1000) + _offset_ms
    params["recvWindow"] = 10000
    qs = urllib.parse.urlencode(params, doseq=True)
    firma = hmac.new(API_SECRET.encode(), qs.encode(), hashlib.sha256).hexdigest()
    url = f"{BASE}{path}?{qs}&signature={firma}"
    r = session.request(metodo, url, timeout=20)
    try:
        data = r.json()
    except ValueError:
        data = {"code": r.status_code, "msg": r.text}
    if r.status_code != 200 or (isinstance(data, dict) and data.get("code", 0) not in (0, 200)):
        raise BinanceError(data.get("code", r.status_code) if isinstance(data, dict) else r.status_code,
                           data.get("msg", r.text) if isinstance(data, dict) else r.text)
    return data


def redondear_abajo(x, paso):
    return math.floor(x / paso + 1e-9) * paso


def fmt(x, paso):
    dec = max(0, -int(round(math.log10(paso)))) if paso < 1 else 0
    return f"{x:.{dec}f}"


# ----------------------------------------------------------------------------- mercado
def reglas_simbolo():
    info = publico("/fapi/v1/exchangeInfo")
    s = next(x for x in info["symbols"] if x["symbol"] == SYMBOL)
    f = {x["filterType"]: x for x in s["filters"]}
    return {
        "step": float(f["MARKET_LOT_SIZE"]["stepSize"] if "MARKET_LOT_SIZE" in f else f["LOT_SIZE"]["stepSize"]),
        "min_qty": float(f["MARKET_LOT_SIZE"]["minQty"] if "MARKET_LOT_SIZE" in f else f["LOT_SIZE"]["minQty"]),
        "tick": float(f["PRICE_FILTER"]["tickSize"]),
        "min_notional": float(f.get("MIN_NOTIONAL", {}).get("notional", 5)),
    }


def cierres_cerrados(intervalo, n, ahora_ms):
    velas = publico("/fapi/v1/klines", {"symbol": SYMBOL, "interval": intervalo, "limit": n + 5})
    cerradas = [v for v in velas if int(v[6]) < ahora_ms]          # v[6] = hora de cierre
    if len(cerradas) < n:
        raise RuntimeError(f"No hay suficientes velas {intervalo} cerradas ({len(cerradas)})")
    return [float(v[4]) for v in cerradas], int(cerradas[-1][6])


def senal(ahora_ms):
    c4, t4 = cierres_cerrados("4h", SMA_4H, ahora_ms)
    cd, td = cierres_cerrados("1d", SMA_DIARIA, ahora_ms)
    sma4 = sum(c4[-SMA_4H:]) / SMA_4H
    smad = sum(cd[-SMA_DIARIA:]) / SMA_DIARIA
    cierre4, cierred = c4[-1], cd[-1]
    tendencia = 1 if cierred > smad else (-1 if cierred < smad else 0)
    gatillo = 1 if cierre4 > sma4 else (-1 if cierre4 < sma4 else 0)
    objetivo = gatillo if (gatillo != 0 and gatillo == tendencia) else 0
    return dict(objetivo=objetivo, cierre4=cierre4, sma4=sma4, cierred=cierred, smad=smad,
                tendencia=tendencia, gatillo=gatillo, t4=t4, td=td)


# ----------------------------------------------------------------------------- cuenta
def configurar_cuenta():
    try:
        firmado("POST", "/fapi/v1/positionSide/dual", {"dualSidePosition": "false"})
    except BinanceError as e:
        if e.code != -4059:          # -4059: ya está en one-way
            raise
    try:
        firmado("POST", "/fapi/v1/marginType", {"symbol": SYMBOL, "marginType": "ISOLATED"})
    except BinanceError as e:
        if e.code == -4046:          # ya es aislado
            pass
        elif e.code in (-4047, -4048):
            telegram("⚠️ No pude cambiar a margen AISLADO porque hay posición u órdenes abiertas. Revísalo a mano.")
        else:
            raise
    firmado("POST", "/fapi/v1/leverage", {"symbol": SYMBOL, "leverage": 1})


def posicion():
    datos = firmado("GET", "/fapi/v3/positionRisk", {"symbol": SYMBOL})
    for p in datos:
        if p["symbol"] == SYMBOL and p.get("positionSide", "BOTH") == "BOTH":
            amt = float(p["positionAmt"])
            return amt, float(p.get("entryPrice", 0) or 0), float(p.get("unRealizedProfit", 0) or 0)
    return 0.0, 0.0, 0.0


def saldos():
    a = firmado("GET", "/fapi/v3/account")
    return dict(billetera=float(a["totalWalletBalance"]), no_realizado=float(a["totalUnrealizedProfit"]),
                disponible=float(a["availableBalance"]))


def ordenes_algo_abiertas():
    r = firmado("GET", "/fapi/v1/openAlgoOrders", {"symbol": SYMBOL})
    if isinstance(r, dict):
        r = r.get("orders", r.get("rows", []))
    return [o for o in r if o.get("symbol") == SYMBOL]


def cancelar_todo():
    for path in ("/fapi/v1/algoOpenOrders", "/fapi/v1/allOpenOrders"):
        try:
            firmado("DELETE", path, {"symbol": SYMBOL})
        except BinanceError as e:
            print("Aviso al cancelar:", e)


def orden_mercado(lado, qty, reglas, reduce_only=False):
    p = {"symbol": SYMBOL, "side": lado, "type": "MARKET", "quantity": fmt(qty, reglas["step"]),
         "newOrderRespType": "RESULT"}
    if reduce_only:
        p["reduceOnly"] = "true"
    r = firmado("POST", "/fapi/v1/order", p)
    return float(r.get("avgPrice") or 0) or None


def poner_stop(lado_pos, precio_ref, reglas):
    if lado_pos > 0:
        disparo, lado = precio_ref * (1 - STOP_PCT), "SELL"
    else:
        disparo, lado = precio_ref * (1 + STOP_PCT), "BUY"
    disparo = redondear_abajo(disparo, reglas["tick"])
    firmado("POST", "/fapi/v1/algoOrder", {
        "algoType": "CONDITIONAL", "symbol": SYMBOL, "side": lado, "type": "STOP_MARKET",
        "triggerPrice": fmt(disparo, reglas["tick"]), "closePosition": "true",
        "workingType": "MARK_PRICE", "clientAlgoId": f"v2stop{int(time.time())}"})
    return disparo


def stop_correcto(lado_pos):
    lado_esperado = "SELL" if lado_pos > 0 else "BUY"
    for o in ordenes_algo_abiertas():
        tipo = o.get("orderType") or o.get("type")
        if tipo == "STOP_MARKET" and o.get("side") == lado_esperado:
            return True
    return False


# ----------------------------------------------------------------------------- principal
NOMBRE = {1: "LARGO", -1: "CORTO", 0: "SIN POSICIÓN"}


def main():
    ahora = sincronizar_reloj()
    hora_utc = time.gmtime(ahora / 1000).tm_hour
    s = senal(ahora)
    resumen = (f"BTC 4h: cierre {s['cierre4']:,.1f} vs SMA{SMA_4H} {s['sma4']:,.1f} "
               f"({'encima' if s['gatillo'] > 0 else 'debajo'})\n"
               f"Diario: cierre {s['cierred']:,.1f} vs SMA{SMA_DIARIA} {s['smad']:,.1f} "
               f"(tendencia {'alcista' if s['tendencia'] > 0 else 'bajista'})\n"
               f"Objetivo: {NOMBRE[s['objetivo']]}")
    print(resumen)

    if MODO == "simulacion" and not (API_KEY and API_SECRET):
        telegram("🧪 Simulación (sin claves): no se consulta la cuenta ni se envían órdenes.\n" + resumen)
        return

    reglas = reglas_simbolo()
    amt, entrada, pnl = posicion()
    actual = 1 if amt > 0 else (-1 if amt < 0 else 0)
    sal = saldos()
    capital = sal["billetera"] + sal["no_realizado"]

    # Interruptor de pausa
    if capital < LIMITE_PAUSA * CAPITAL_INICIAL:
        if actual != 0 and MODO != "simulacion":
            cancelar_todo()
            orden_mercado("SELL" if actual > 0 else "BUY", abs(amt), reglas, reduce_only=True)
            telegram(f"🛑 PAUSA: capital {capital:,.2f} < {LIMITE_PAUSA:.0%} de {CAPITAL_INICIAL:,.2f}. "
                     "Cerré la posición y el bot ya no operará. Revisa el plan antes de reactivarlo.")
        elif hora_utc == 0:
            telegram(f"🛑 Bot en PAUSA (capital {capital:,.2f}). No opera hasta que lo revises.")
        return

    if MODO != "simulacion":
        configurar_cuenta()

    if actual == s["objetivo"]:
        if actual != 0 and MODO != "simulacion" and not stop_correcto(actual):
            cancelar_todo()
            d = poner_stop(actual, entrada, reglas)
            telegram(f"🔧 Faltaba el stop de emergencia. Lo puse en {d:,.1f}.")
        if hora_utc == 0:
            telegram(f"📋 Resumen diario\nPosición: {NOMBRE[actual]} {abs(amt)} BTC\n"
                     f"Capital: {capital:,.2f} USDT (PnL abierto {pnl:+,.2f})\n" + resumen)
        print("Sin cambios.")
        return

    # Hay que ajustar la posición
    plan = f"Cambio: {NOMBRE[actual]} → {NOMBRE[s['objetivo']]}"
    if MODO == "simulacion":
        telegram(f"🧪 (simulación, sin órdenes) {plan}\n" + resumen)
        return

    cancelar_todo()
    mensaje = [plan]
    if actual != 0:
        px = orden_mercado("SELL" if actual > 0 else "BUY", abs(amt), reglas, reduce_only=True)
        mensaje.append(f"Cerré {NOMBRE[actual]} de {abs(amt)} BTC (entrada {entrada:,.1f}, salida ~{px or 0:,.1f}, "
                       f"PnL aprox. {pnl:+,.2f} USDT)")
        time.sleep(1)
        amt2, _, _ = posicion()
        if abs(amt2) > 0:
            raise RuntimeError(f"La posición no quedó cerrada (queda {amt2} BTC). Revisa a mano.")

    if s["objetivo"] != 0:
        sal = saldos()
        precio = s["cierre4"]
        qty = redondear_abajo(sal["disponible"] * MARGEN_SEGURIDAD / precio, reglas["step"])
        if qty < reglas["min_qty"] or qty * precio < reglas["min_notional"]:
            mensaje.append(f"⚠️ No abrí {NOMBRE[s['objetivo']]}: saldo {sal['disponible']:,.2f} USDT no alcanza "
                           f"para el mínimo ({reglas['min_qty']} BTC / {reglas['min_notional']} USDT).")
        else:
            px = orden_mercado("BUY" if s["objetivo"] > 0 else "SELL", qty, reglas)
            time.sleep(1)
            amt3, entrada3, _ = posicion()
            if abs(amt3) <= 0:
                raise RuntimeError("Envié la orden de apertura pero no veo la posición. Revisa a mano.")
            d = poner_stop(s["objetivo"], entrada3 or px or precio, reglas)
            mensaje.append(f"Abrí {NOMBRE[s['objetivo']]} de {abs(amt3)} BTC a ~{entrada3 or px:,.1f}. "
                           f"Stop de emergencia: {d:,.1f}")
    sal = saldos()
    mensaje.append(f"Capital: {sal['billetera'] + sal['no_realizado']:,.2f} USDT")
    telegram("✅ " + "\n".join(mensaje) + "\n" + resumen)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        telegram(f"❌ ERROR: {e}\nEl bot no completó esta ejecución. Revisa Binance y el registro de GitHub.")
        sys.exit(1)
