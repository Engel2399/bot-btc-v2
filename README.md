# Bot V2 – BTCUSDT perpetuo (Binance Futures)

Largos y cortos con la **SMA 200 de 4h**, filtrados por la **tendencia diaria (SMA 100)**. Apalancamiento 1x, margen aislado y stop de emergencia del 8%.
Corre gratis en un servidor **Oracle Cloud Always Free**, cada 4 horas y sin que tu PC esté encendida.

> Es un bot experimental, basado en un backtest de 2018–2026. No garantiza resultados. Pruébalo primero en modo simulación y en testnet.

> **¿Por qué no GitHub Actions?** Sus servidores están en EE. UU. y Binance responde `451 restricted location` a cualquier conexión desde allí. El servidor tiene que estar fuera de EE. UU.

---

## 1. Telegram (avisos)

1. En Telegram abre **@BotFather** → `/newbot` → copia el **token**. Si alguna vez lo pegaste en un chat, usa `/revoke` y usa el token nuevo.
2. Escríbele "hola" a tu bot.
3. Para saber tu **chat id**, escríbele a **@userinfobot** o abre `https://api.telegram.org/bot<TU_TOKEN>/getUpdates` y busca `"chat":{"id":...`.

## 2. Cuenta de Oracle Cloud

1. Entra a **https://signup.oracle.com** y crea la cuenta (plan *Free Tier*).
2. **Home region:** elige **Brazil East (São Paulo)** o **Mexico Central (Querétaro)**.
   ⚠️ No se puede cambiar después, y los recursos gratis solo existen en esa región. **No elijas regiones de EE. UU.**
3. Te piden una tarjeta solo para verificar (hacen una retención temporal; no cobran).
4. **Recomendado:** *Billing → Upgrade to Pay As You Go*. Sigues pagando $0 si solo usas recursos *Always Free*, y evitas que Oracle borre la máquina por "inactiva" (en cuentas gratis reclaman las máquinas con menos del 20% de uso durante 7 días, y este bot usa casi nada).
   Si lo haces, crea una alerta en *Billing → Budgets* de $1 para enterarte si algo empieza a costar.

## 3. Crear la clave SSH (desde el navegador)

1. En la consola de Oracle, arriba a la derecha, abre **Cloud Shell** (icono `>_`).
2. Pega:
   ```
   ssh-keygen -t ed25519 -N "" -f ~/.ssh/oracle_bot && cat ~/.ssh/oracle_bot.pub
   ```
3. Copia la línea que empieza por `ssh-ed25519 ...` (es la clave **pública**; se puede compartir sin problema).

## 4. Crear la máquina

*Menú ☰ → Compute → Instances → Create instance*
- **Name:** `bot-v2`
- **Image:** *Change image* → **Canonical Ubuntu 24.04** (o 22.04)
- **Shape:** *Change shape* → **AMD → VM.Standard.E2.1.Micro** (debe decir *Always Free-eligible*).
  Si no hay capacidad, usa **Ampere → VM.Standard.A1.Flex** con 1 OCPU y 6 GB.
- **Networking:** deja lo que viene (crear VCN nueva, *Assign a public IPv4 address* = sí).
- **Add SSH keys:** *Paste public keys* → pega la línea `ssh-ed25519 ...`.
- **Create**. Espera a que diga *Running* y copia la **Public IP address**.

## 5. Entrar a la máquina

En Cloud Shell:
```
ssh -i ~/.ssh/oracle_bot ubuntu@TU_IP_PUBLICA
```
Escribe `yes` la primera vez. Sabes que estás dentro cuando la línea empieza con `ubuntu@bot-v2`.

## 6. Instalar el bot

Para que el servidor pueda descargar el código, el repositorio tiene que ser **público** (*Settings → General → Danger Zone → Change visibility*). En el código no hay ninguna clave; las claves solo quedan en el servidor.

Dentro de la máquina:
```
git clone https://github.com/Engel2399/bot-btc-v2.git
cd bot-btc-v2
bash instalar.sh
```
El instalador:
1. Instala Python.
2. Pone el reloj del servidor en UTC.
3. Te pide el token y el chat id de Telegram, el modo (`simulacion`), las claves de Binance (puedes dejarlas vacías por ahora) y el capital.
4. Guarda todo en `.env`, que solo tu usuario puede leer.
5. Programa el horario.
6. Hace una ejecución de prueba, que debería mandarte un mensaje por Telegram.

Después ya puedes cerrar Cloud Shell; el servidor sigue funcionando solo.

Corre a las **8:05 p. m., 12:05 a. m., 4:05 a. m., 8:05 a. m., 12:05 p. m. y 4:05 p. m.** (hora RD).

## 7. Comandos útiles (dentro de la máquina)

| Para | Comando |
|---|---|
| Ver el registro | `tail -n 50 ~/bot-btc-v2/logs/bot.log` |
| Ejecutar ahora | `bash ~/bot-btc-v2/ejecutar.sh` |
| Cambiar la configuración (modo, claves, capital) | `bash ~/bot-btc-v2/instalar.sh` o `nano ~/bot-btc-v2/.env` |
| Actualizar el código tras subir cambios a GitHub | `cd ~/bot-btc-v2 && git pull` |
| Ver el horario | `crontab -l` |
| Apagar el bot | `crontab -r` |

## 8. Claves de prueba (testnet / Demo Trading de futuros)

1. Entra a **https://testnet.binancefuture.com** (o a *Demo Trading* desde Binance) y crea una API key.
2. Ejecuta `bash ~/bot-btc-v2/instalar.sh`, responde `s` para reemplazar, pon `MODO=testnet` y las claves.
3. Si las claves fallan, edita `.env` (`nano ~/bot-btc-v2/.env`) y quita el `#` de la línea `BASE_URL=https://testnet.binancefuture.com`.

## 9. Plan de pruebas (3–4 semanas)

| Semana | `MODO` | Qué revisar |
|---|---|---|
| 1 | `simulacion` | Que cada "Objetivo" coincida con lo que ves en el gráfico (BINANCE:BTCUSDT.P: 4h con SMA 200 y 1D con SMA 100) |
| 2–4 | `testnet` | Que abra y cierre bien, que ponga el stop y que los avisos lleguen |

Pruebas a propósito en testnet:
- [ ] Abre a mano una posición contraria a la señal → en la siguiente ejecución el bot debe corregirla.
- [ ] Cancela a mano el stop de emergencia → el bot debe volver a ponerlo ("Faltaba el stop").
- [ ] Ejecuta `bash ejecutar.sh` dos veces seguidas → no debe duplicar la posición.
- [ ] Pon `CAPITAL_INICIAL` muy alto (por ejemplo, 1000000) → debe activar la PAUSA. Después vuelve a poner el valor real.

**Señal de vida:** cada día a las **8:05 p. m.** (hora RD) llega un resumen. Si no llega, revisa la máquina en la consola de Oracle.

## 10. Pasar a dinero real

1. En Binance: **Perfil → Gestión de API → Crear API** (*System generated*).
   - Permisos: **solo "Habilitar futuros"**. **Nunca** actives retiros. Tampoco hace falta spot.
   - Opcional y recomendable: restringe el acceso a la **IP pública** de tu máquina de Oracle.
2. Transfiere a la billetera **Futuros USDⓈ-M** solo el capital del plan (recomendado: $150–200).
3. Ejecuta `bash ~/bot-btc-v2/instalar.sh` con `MODO=real`, las claves reales y `CAPITAL_INICIAL` igual al monto depositado.
4. Verifica en la app de Binance la posición y el stop (en Órdenes → Condicionales / Algo).

## 11. Apagar el bot

- **Servidor:** `crontab -r`. Si quieres borrarlo todo: consola de Oracle → la instancia → *Terminate*.
- **Binance:** borra la API key.
- Si quedó una posición abierta, ciérrala a mano en la app (y cancela el stop).

## Qué hace en cada ejecución

1. Configura margen **aislado**, **1x** y modo **one-way**.
2. Toma velas **cerradas** del perpetuo: 4h → SMA 200, diario → SMA 100.
3. Objetivo: tendencia diaria alcista + 4h encima → **LARGO**; tendencia diaria bajista + 4h debajo → **CORTO**; si no, **SIN POSICIÓN**.
4. Lee la posición **real**. Si coincide, solo verifica el stop. Si no coincide: cancela órdenes → cierra (reduce-only) → abre la nueva (98% del saldo disponible, en pasos de 0.001 BTC) → pone el stop de emergencia (−8% / +8%, precio de marca, *closePosition*).
5. Si el capital cae por debajo del 60% de `CAPITAL_INICIAL`: cierra todo y deja de operar.
6. Avisa por Telegram de cambios, errores y un resumen diario.
