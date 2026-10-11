# Bot V2 – BTCUSDT perpetuo (Binance Futures)

Largos y cortos con la **SMA 200 de 4h**, filtrados por la **tendencia diaria (SMA 100)**. Apalancamiento 1x, margen aislado y stop de emergencia del 8%.
Corre gratis en **GitHub Actions** cada 4 horas, sin que tu PC esté encendida.

> Es un bot experimental, basado en un backtest de 2018–2026. No garantiza resultados. Pruébalo primero en modo simulación y en testnet.

---

## 1. Telegram (avisos)

1. En Telegram abre **@BotFather** → `/newbot` → elige nombre y usuario → copia el **token**.
2. Abre tu bot nuevo y envíale cualquier mensaje (por ejemplo, "hola").
3. En el navegador, abre `https://api.telegram.org/bot<TU_TOKEN>/getUpdates`.
4. Busca `"chat":{"id":123456789` → ese número es tu **TELEGRAM_CHAT_ID**.

## 2. Claves de prueba (testnet / Demo Trading de futuros)

1. Entra a **https://testnet.binancefuture.com** (o a *Demo Trading* desde Binance) e inicia sesión.
2. En la pestaña **API Key**, crea una clave y copia la **API Key** y la **Secret Key**.
3. Te dan USDT ficticio en la billetera de futuros.
   El bot usa `https://demo-fapi.binance.com` cuando `MODO=testnet`. Si tu clave de prueba no funciona con esa URL, crea la variable `BASE_URL` con `https://testnet.binancefuture.com`.

## 3. Repositorio en GitHub

1. Crea un repositorio **privado** (por ejemplo, `bot-btc-v2`).
2. Sube estos archivos, respetando las carpetas:
   ```
   bot.py
   requirements.txt
   README.md
   .github/workflows/bot.yml
   ```
3. Ve a **Settings → Secrets and variables → Actions**.
   - Pestaña **Secrets** → *New repository secret*:
     | Nombre | Valor |
     |---|---|
     | `BINANCE_API_KEY` | tu API key (primero la de testnet) |
     | `BINANCE_API_SECRET` | tu secret key |
     | `TELEGRAM_TOKEN` | token de @BotFather |
     | `TELEGRAM_CHAT_ID` | tu chat id |
   - Pestaña **Variables** → *New repository variable*:
     | Nombre | Valor inicial |
     |---|---|
     | `MODO` | `simulacion` |
     | `CAPITAL_INICIAL` | `100` (o lo que deposites) |
     | `SMA_4H` | `200` |
     | `SMA_DIARIA` | `100` |

## 4. Primera ejecución

1. Pestaña **Actions** → *Bot V2 BTC* → **Run workflow**.
2. Abre la ejecución y revisa el registro: debe mostrar el cierre de 4h, la SMA 200, el cierre diario, la SMA 100 y el **objetivo**.
3. Debe llegarte el mensaje por Telegram.
4. Compáralo con tu gráfico (BINANCE:BTCUSDT.P en TradingView): 4h con SMA 200 y 1D con SMA 100.

A partir de ahí corre solo a las **8:05 p. m., 12:05 a. m., 4:05 a. m., 8:05 a. m., 12:05 p. m. y 4:05 p. m.** (hora RD). GitHub a veces se retrasa unos minutos; es normal.

## 5. Plan de pruebas (3–4 semanas)

| Semana | `MODO` | Qué revisar |
|---|---|---|
| 1 | `simulacion` | Que cada "Objetivo" coincida con lo que ves en el gráfico |
| 2–4 | `testnet` | Que abra y cierre bien, que ponga el stop y que los avisos lleguen |

Pruebas a propósito en testnet:
- [ ] Abre a mano una posición contraria a la señal → en la siguiente ejecución el bot debe corregirla.
- [ ] Cancela a mano el stop de emergencia → el bot debe volver a ponerlo ("Faltaba el stop").
- [ ] Ejecuta *Run workflow* dos veces seguidas → no debe duplicar la posición.
- [ ] Pon `CAPITAL_INICIAL` muy alto (por ejemplo, 1000000) → debe activar la PAUSA. Después vuelve a poner el valor real.

## 6. Pasar a dinero real

1. En Binance: **Perfil → Gestión de API → Crear API**.
   - Permisos: **solo "Habilitar futuros"**. **Nunca** actives retiros. Tampoco hace falta spot.
2. Transfiere a la billetera **Futuros USDⓈ-M** solo el capital del plan (recomendado: $150–200).
3. Cambia los secretos `BINANCE_API_KEY` y `BINANCE_API_SECRET` por los reales.
4. Cambia `CAPITAL_INICIAL` al monto depositado y `MODO` a `real`.
5. Haz un *Run workflow* manual y verifica en la app de Binance la posición y el stop (en Órdenes → Condicionales / Algo).

## 7. Apagar el bot

- **GitHub:** Actions → *Bot V2 BTC* → `···` → **Disable workflow**.
- **Binance:** borra la API key.
- Si quedó una posición abierta, ciérrala a mano en la app (y cancela el stop).

## Qué hace en cada ejecución

1. Configura margen **aislado**, **1x** y modo **one-way**.
2. Toma velas **cerradas** del perpetuo: 4h → SMA 200, diario → SMA 100.
3. Objetivo: tendencia diaria alcista + 4h encima → **LARGO**; tendencia diaria bajista + 4h debajo → **CORTO**; si no, **SIN POSICIÓN**.
4. Lee la posición **real**. Si coincide, solo verifica el stop. Si no coincide: cancela órdenes → cierra (reduce-only) → abre la nueva (98% del saldo disponible, en pasos de 0.001 BTC) → pone el stop de emergencia (−8% / +8%, precio de marca, *closePosition*).
5. Si el capital cae por debajo del 60% de `CAPITAL_INICIAL`: cierra todo y deja de operar.
6. Avisa por Telegram de cambios, errores y un resumen diario (8:05 p. m. RD).
