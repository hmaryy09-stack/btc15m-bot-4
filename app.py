from flask import Flask, render_template_string
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

app = Flask(__name__)

KALSHI_URL = "https://external-api.kalshi.com/trade-api/v2/markets"
SERIES = "KXBTC15M"

# Guarda la señal de la vela actual
locked_ticker = None
locked_direction = None
locked_probability = None


def get_btc_price():
    try:
        r = requests.get(
            "https://api.kraken.com/0/public/Ticker",
            params={"pair": "XBTUSD"},
            timeout=8
        )
        data = r.json()
        result = data.get("result", {})

        if result:
            item = next(iter(result.values()))
            return float(item["c"][0])

    except Exception:
        pass

    return None


def get_markets():
    try:
        r = requests.get(
            KALSHI_URL,
            params={
                "series_ticker": SERIES,
                "status": "open",
                "limit": 50
            },
            timeout=8
        )

        if r.ok:
            return r.json().get("markets", [])

    except Exception:
        pass

    return []


def parse_time(value):
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(
                value,
                tz=timezone.utc
            )

        value = str(value).replace(
            "Z",
            "+00:00"
        )

        dt = datetime.fromisoformat(value)

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.astimezone(timezone.utc)

    except Exception:
        return None


def get_current_market():
    now = datetime.now(timezone.utc)

    for market in get_markets():

        opened = parse_time(
            market.get("open_time")
        )

        closed = parse_time(
            market.get("close_time")
        )

        if opened and closed:

            if opened <= now < closed:
                return market

    return None


def get_target(market):
    if not market:
        return None

    for key in [
        "custom_strike",
        "floor_strike",
        "cap_strike"
    ]:

        value = market.get(key)

        if value is not None:

            try:
                return float(value)

            except Exception:
                pass

    return None


def get_kalshi_probability(market):
    if not market:
        return None

    try:

        bid = market.get(
            "yes_bid_dollars"
        )

        ask = market.get(
            "yes_ask_dollars"
        )

        last = market.get(
            "last_price_dollars"
        )

        if bid is not None and ask is not None:

            return (
                float(bid)
                + float(ask)
            ) / 2

        if last is not None:
            return float(last)

    except Exception:
        pass

    return None


def calculate_signal(btc, target):
    if btc is None or target is None:
        return "SUBE", 0.55

    difference = (
        btc - target
    ) / target

    if difference >= 0:
        direction = "SUBE"
    else:
        direction = "BAJA"

    probability = 0.55 + min(
        0.29,
        abs(difference) * 300
    )

    return direction, probability


def update_locked_signal(market, btc, target):

    global locked_ticker
    global locked_direction
    global locked_probability

    if not market:
        return "SUBE", 0.55

    ticker = market.get("ticker")

    if ticker != locked_ticker:

        direction, probability = calculate_signal(
            btc,
            target
        )

        locked_ticker = ticker
        locked_direction = direction
        locked_probability = probability

    return (
        locked_direction,
        locked_probability
    )


@app.route("/")
def home():

    btc = get_btc_price()

    market = get_current_market()

    target = get_target(market)

    kalshi = get_kalshi_probability(
        market
    )

    direction, probability = update_locked_signal(
        market,
        btc,
        target
    )

    now = datetime.now(
        ZoneInfo("America/New_York")
    )

    close_time = None

    if market:
        close_time = parse_time(
            market.get("close_time")
        )

    remaining = "--:--"

    if close_time:

        seconds = max(
            0,
            int(
                (
                    close_time
                    - datetime.now(timezone.utc)
                ).total_seconds()
            )
        )

        minutes = seconds // 60
        secs = seconds % 60

        remaining = f"{minutes:02d}:{secs:02d}"

    if direction == "SUBE":
        signal_class = "up"
        arrow = "▲"
    else:
        signal_class = "down"
        arrow = "▼"

    if kalshi is not None:

        kalshi_up = kalshi * 100
        kalshi_down = (
            1 - kalshi
        ) * 100

    else:

        kalshi_up = None
        kalshi_down = None

    max_entry = (
        probability / 1.10
    ) * 100

    return render_template_string(
        HTML,
        now=now.strftime(
            "%-I:%M:%S %p"
        ),
        btc=(
            f"${btc:,.2f}"
            if btc is not None
            else "—"
        ),
        direction=direction,
        probability=f"{probability * 100:.0f}%",
        signal_class=signal_class,
        arrow=arrow,
        target=(
            f"${target:,.2f}"
            if target is not None
            else "—"
        ),
        remaining=remaining,
        kalshi_up=(
            f"{kalshi_up:.0f}%"
            if kalshi_up is not None
            else "—"
        ),
        kalshi_down=(
            f"{kalshi_down:.0f}%"
            if kalshi_down is not None
            else "—"
        ),
        max_entry=f"{max_entry:.1f}%"
    )


HTML = """
<!DOCTYPE html>
<html lang="es">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<meta http-equiv="refresh" content="10">

<title>BTC 15 MIN</title>

<style>

body {
    margin: 0;
    background: #070b14;
    color: white;
    font-family: Arial, sans-serif;
}

.container {
    max-width: 700px;
    margin: auto;
    padding: 25px 18px 50px;
}

.header {
    text-align: center;
    margin-bottom: 25px;
}

.title {
    font-size: 32px;
    font-weight: 900;
}

.subtitle {
    color: #9da7b8;
    margin-top: 8px;
}

.card {
    background: #101722;
    border-radius: 18px;
    padding: 22px;
    margin-top: 18px;
}

.label {
    color: #9da7b8;
    font-size: 14px;
    text-transform: uppercase;
}

.value {
    font-size: 38px;
    font-weight: 900;
    margin-top: 8px;
}

.signal {
    border-radius: 16px;
    padding: 22px;
    margin-top: 12px;
}

.up {
    background: #123d2c;
    color: #42ef9a;
}

.down {
    background: #421f27;
    color: #ff6269;
}

.signal-main {
    font-size: 32px;
    font-weight: 900;
}

.probability {
    font-size: 24px;
    margin-top: 8px;
}

.grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
}

.box {
    background: #151e2b;
    border-radius: 14px;
    padding: 18px;
}

.green {
    color: #42ef9a;
}

.red {
    color: #ff6269;
}

.lock {
    color: #c4ccd8;
    margin-top: 14px;
}

.footer {
    text-align: center;
    color: #707b8c;
    margin-top: 30px;
    font-size: 13px;
}

</style>

</head>

<body>

<div class="container">

<div class="header">

<div class="title">
₿ BTC • 15 MIN
</div>

<div class="subtitle">
Predictor • Kalshi
<br>
🟢 EN VIVO • {{ now }} NY
</div>

</div>


<div class="card">

<div class="label">
LECTURA ACTUAL
</div>

<div class="signal {{ signal_class }}">

<div class="signal-main">
{{ arrow }} {{ direction }}
</div>

<div class="probability">
{{ probability }}
</div>

</div>

<div class="lock">
🔒 Dirección fija durante esta vela
</div>

</div>


<div class="card">

<div class="label">
BTC ACTUAL
</div>

<div class="value">
{{ btc }}
</div>

</div>


<div class="card">

<div class="label">
🎯 OBJETIVO KALSHI
</div>

<div class="value">
{{ target }}
</div>

</div>


<div class="card">

<div class="label">
⏱️ CIERRE
</div>

<div class="value">
{{ remaining }}
</div>

</div>


<div class="card">

<div class="label">
📊 KALSHI EN VIVO
</div>

<div class="grid">

<div class="box green">
SUBE<br>
<strong>{{ kalshi_up }}</strong>
</div>

<div class="box red">
BAJA<br>
<strong>{{ kalshi_down }}</strong>
</div>

</div>

</div>


<div class="card">

<div class="label">
💰 GUÍA DE ENTRADA
</div>

<div class="value">
{{ max_entry }}
</div>

<p>
Entrada máxima sugerida
</p>

<p>
Posición sugerida: <strong>25%</strong>
</p>

<p style="color:#8d98a8;">
Solo señales. Sin compras automáticas.
</p>

</div>


<div class="card">

<div class="label">
🚨 RADAR
</div>

<p>
Señal principal:
<strong>{{ direction }}</strong>
</p>

<p>
Modelo:
<strong>{{ probability }}</strong>
</p>

</div>


<div class="footer">

BTC 15 MIN • Hora de Nueva York<br>
Señales solamente

</div>

</div>

</body>
</html>
"""

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=10000
    )
