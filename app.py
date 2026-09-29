from flask import Flask, render_template_string
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

app = Flask(__name__)

KALSHI_URL='https://external-api.kalshi.com/trade-api/v2/markets'
SERIES='KXBTC15M'
locked_ticker=None
locked_direction=None
locked_probability=None

def parse_time(v):
    try:
        if isinstance(v,(int,float)): return datetime.fromtimestamp(v,tz=timezone.utc)
        d=datetime.fromisoformat(str(v).replace('Z','+00:00'))
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    except: return None

def btc_price():
    try:
        r=requests.get('https://api.kraken.com/0/public/Ticker',params={'pair':'XBTUSD'},timeout=8).json()
        x=next(iter(r.get('result',{}).values())); return float(x['c'][0])
    except: return None

def btc_change():
    try:
        r=requests.get('https://api.kraken.com/0/public/OHLC',params={'pair':'XBTUSD','interval':1},timeout=8).json()['result']
        k=next(k for k in r if k!='last'); a=r[k]
        return (float(a[-1][4])-float(a[-6][4]))/float(a[-6][4])*100 if len(a)>=6 else 0
    except: return 0

def markets():
    try:
        r=requests.get(KALSHI_URL,params={'series_ticker':SERIES,'status':'open','limit':50},timeout=8)
        return r.json().get('markets',[]) if r.ok else []
    except: return []

def current_market():
    now=datetime.now(timezone.utc)
    for m in markets():
        o,c=parse_time(m.get('open_time')),parse_time(m.get('close_time'))
        if o and c and o<=now<c:return m
    return None

def next_market():
    now=datetime.now(timezone.utc); a=[]
    for m in markets():
        o=parse_time(m.get('open_time'))
        if o and o>now:a.append((o,m))
    return sorted(a,key=lambda x:x[0])[0][1] if a else None

def target(m):
    if not m:return None
    for k in ('custom_strike','floor_strike','cap_strike'):
        try:
            if m.get(k) is not None:return float(m[k])
        except:pass
    return None

def kalshi_prob(m):
    if not m:return None
    try:
        b,a,last=m.get('yes_bid_dollars'),m.get('yes_ask_dollars'),m.get('last_price_dollars')
        if b is not None and a is not None:return (float(b)+float(a))/2
        if last is not None:return float(last)
    except:pass
    return None

def model(b,t):
    if b is None or t in (None,0):return 'SUBE',.55
    d=(b-t)/t
    return ('SUBE' if d>=0 else 'BAJA'),.55+min(.29,abs(d)*300)

def fixed(m,b,t):
    global locked_ticker,locked_direction,locked_probability
    if not m:return 'SUBE',.55
    tick=m.get('ticker')
    if tick!=locked_ticker:
        locked_direction,locked_probability=model(b,t)
        locked_ticker=tick
    return locked_direction,locked_probability

def money(v):
    return '—' if v is None else f'${v:,.2f}'

def clamp(v,a,b):
    return max(a,min(b,v))

def countdown(sec):
    sec=max(0,int(sec))
    return f'{sec//60:02d}:{sec%60:02d}'

def close_info(m):
    if not m:return 0,900
    o,c=parse_time(m.get('open_time')),parse_time(m.get('close_time'))
    if not o or not c:return 0,900
    now=datetime.now(timezone.utc)
    return max(0,int((c-now).total_seconds())),max(1,int((c-o).total_seconds()))

def confirm(b,t,d,k):
    if b is None or t is None:return 0
    a=(b>=t if d=='SUBE' else b<t)
    q=(k>=.5 if d=='SUBE' else k<.5) if k is not None else False
    r=abs(b-t)/t>=.0005
    return int(a)+int(q)+int(r)

HTML='''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="10">
<title>BTC 15M • Neon</title>
<style>
:root{
--bg:#05030d;
--card:#0b0820;
--card2:#100b2c;
--line:#38256d;
--txt:#f8f7ff;
--muted:#a8a1c5;
--g:#22ff9a;
--r:#ff3f78;
--p:#9d5cff;
--b:#36cfff
}
*{box-sizing:border-box}
body{
margin:0;
background:radial-gradient(circle at 50% 0,#21104b 0,#080512 35%,#030209 100%);
color:var(--txt);
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif
}
.wrap{
width:min(700px,calc(100% - 16px));
margin:auto;
padding:12px 0 28px
}
.head{
display:flex;
justify-content:space-between;
align-items:center;
border:1px solid #3b207e;
border-radius:18px;
padding:13px 15px;
background:#090718;
box-shadow:0 0 22px #5715a833
}
.brand{font-weight:900;font-size:17px}
.sub,.small{color:var(--muted);font-size:11px}
.live{color:var(--g);font-weight:900;font-size:12px;text-align:right}
.card{
background:linear-gradient(145deg,#0d0921,#080615);
border:1px solid var(--line);
border-radius:17px;
padding:14px;
margin-top:10px;
box-shadow:0 0 20px #6d2cff12
}
.label{
color:#bfb6df;
font-size:11px;
font-weight:900;
letter-spacing:.7px
}
.main{
margin-top:10px;
border:1px solid #4a2b91;
border-radius:17px;
padding:17px;
background:linear-gradient(135deg,#10082c,#080714)
}
.signal{
display:flex;
justify-content:space-between;
align-items:center;
gap:10px
}
.dir{font-size:35px;font-weight:950}
.up{color:var(--g)}
.down{color:var(--r)}
.prob{font-size:35px;font-weight:950}
.lock{color:#c2bbd6;font-size:12px;margin-top:7px}
.grid2{
display:grid;
grid-template-columns:1fr 1fr;
gap:9px
}
.metric{
margin-top:9px;
padding:12px;
border:1px solid #2c2250;
border-radius:13px;
background:#090718
}
.value{
font-size:21px;
font-weight:900;
margin-top:3px
}
.bars{
display:grid;
grid-template-columns:repeat(3,1fr);
gap:6px;
margin:9px 0 6px
}
.bar{
height:7px;
border-radius:9px;
background:#29233c
}
.on{
background:linear-gradient(90deg,var(--g),#52e7ff);
box-shadow:0 0 10px #22ff9a66
}
.alert{
margin-top:9px;
padding:11px;
border-radius:12px;
font-size:12px;
background:#0b1820;
border:1px solid #1d9d7a
}
.alert.bad{
background:#210a18;
border-color:#a52d55
}
.guide{
border:1px solid #5331a0;
border-radius:15px;
padding:13px;
margin-top:8px;
box-shadow:0 0 18px #8c3dff14
}
.ghead{
display:flex;
justify-content:space-between;
gap:8px;
font-weight:900;
font-size:13px
}
.gprob{font-size:21px}
.explain{
color:#aaa2c0;
font-size:11px;
line-height:1.4;
margin:8px 0
}
.grid3{
display:grid;
grid-template-columns:repeat(3,1fr);
gap:7px
}
.mini{
background:#0c0920;
border:1px solid #2b2150;
border-radius:10px;
padding:9px
}
.mini span{
display:block;
color:var(--muted);
font-size:9px;
margin-bottom:4px
}
.mini b{font-size:12px}
.kbar{
height:10px;
background:#2b2539;
border-radius:9px;
overflow:hidden;
display:flex;
margin:10px 0
}
.kg{background:var(--g)}
.kr{background:var(--r)}
.kl{
display:flex;
justify-content:space-between;
font-size:12px;
font-weight:900
}
.radar{
display:grid;
grid-template-columns:1fr 1fr;
gap:8px;
margin-top:9px
}
.r{
border:1px solid #2b2150;
background:#090718;
border-radius:11px;
padding:10px
}
.r b{
display:block;
margin-top:3px;
font-size:15px
}
.footer{
text-align:center;
color:#70698b;
font-size:10px;
margin-top:12px
}
@media(max-width:500px){
.wrap{width:calc(100% - 12px)}
.dir,.prob{font-size:29px}
.grid3{grid-template-columns:1fr}
.signal{align-items:flex-end}
}
</style>
</head>
<body>
<div class="wrap">

<div class="head">
<div>
<div class="brand">₿ BTC • 15 MIN</div>
<div class="sub">Bot 4 • Predictor • Kalshi</div>
</div>
<div class="live">🟢 EN VIVO<br>{{ny}}</div>
</div>

<div class="card">
<div class="label">LECTURA ACTUAL</div>

<div class="main">
<div class="signal">
<div>
<div class="dir {{'up' if d=='SUBE' else 'down'}}">{{d}}</div>
<div class="lock">🔒 Dirección fija durante esta vela</div>
</div>
<div class="prob {{'up' if d=='SUBE' else 'down'}}">{{p}}%</div>
</div>

<div class="grid2">
<div class="metric">
<div class="small">BTC ACTUAL</div>
<div class="value">{{btc}}</div>
<div class="small">{{chg}} en ~5 min</div>
</div>

<div class="metric">
<div class="small">ENTRADA MÁXIMA</div>
<div class="value">{{entry}}%</div>
<div class="small">Guía de entrada</div>
</div>
</div>

<div class="metric">
<div class="small">CONFIRMACIÓN PROGRESIVA • {{conf}}/3</div>
<div class="bars">
<i class="bar {{'on' if conf>=1 else ''}}"></i>
<i class="bar {{'on' if conf>=2 else ''}}"></i>
<i class="bar {{'on' if conf>=3 else ''}}"></i>
</div>
<div class="small">Posición sugerida: <b>25%</b></div>
</div>

<div class="alert {{'bad' if div else ''}}">
<b>{{'⚠️ DIVERGENCIA KALSHI' if div else '🎯 '+d+' activa'}}</b><br>
{{msg}}
</div>

</div>
</div>

<div class="grid2">

<div class="card">
<div class="label">OBJETIVO KALSHI</div>
<div class="value">{{target}}</div>
<div class="small">Strike de la vela</div>
</div>

<div class="card">
<div class="label">CIERRE</div>
<div class="value">{{close}}</div>
<div class="small">Cuenta regresiva</div>
</div>

</div>

<div class="card">
<div class="label">GUÍA PARA EL CIERRE</div>

<div class="guide">
<div class="ghead">
<span class="{{'up' if d=='SUBE' else 'down'}}">PROBABLE CIERRE {{d}}</span>
<span class="{{'up' if d=='SUBE' else 'down'}} gprob">{{p}}%</span>
</div>

<div class="explain">
Estimación basada en el precio, el objetivo y el ritmo observado. No cambia la señal fija.
</div>

<div class="grid3">

<div class="mini">
<span>CIERRE PROYECTADO</span>
<b>{{proj}}</b>
</div>

<div class="mini">
<span>RITMO ACTUAL</span>
<b>{{rate}}%</b>
</div>

<div class="mini">
<span>RITMO NECESARIO</span>
<b>{{need}}%</b>
</div>

</div>
</div>
</div>

<div class="card">
<div class="label">KALSHI EN VIVO</div>

<div class="kl">
<span class="up">SUBE {{ku}}%</span>
<span class="down">BAJA {{kd}}%</span>
</div>

<div class="kbar">
<div class="kg" style="width:{{ku}}%"></div>
<div class="kr" style="width:{{kd}}%"></div>
</div>

<div class="small">
Dirección en vivo: <b>{{kdirection}}</b>
</div>
</div>

<div class="card">
<div class="label">RADAR TEMPRANO</div>

<div class="radar">

<div class="r">
<span class="small">SEÑAL PRINCIPAL</span>
<b class="{{'up' if d=='SUBE' else 'down'}}">{{d}}</b>
</div>

<div class="r">
<span class="small">KALSHI</span>
<b>{{kdirection}}</b>
</div>

<div class="r">
<span class="small">DIVERGENCIA</span>
<b class="{{'down' if div else 'up'}}">
{{'ACTIVA' if div else 'NO'}}
</b>
</div>

<div class="r">
<span class="small">CALIDAD</span>
<b>{{quality}}</b>
</div>

</div>
</div>

{% if nd %}
<div class="card">
<div class="label">PRÓXIMA VELA</div>

<div class="grid2">

<div class="metric">
<div class="small">PREVISIÓN</div>
<div class="value {{'up' if nd=='SUBE' else 'down'}}">{{nd}}</div>
</div>

<div class="metric">
<div class="small">PROBABILIDAD</div>
<div class="value">{{np}}%</div>
</div>

</div>

<div class="small" style="margin-top:8px">
Vista previa. No cambia la señal actual.
</div>
</div>
{% endif %}

<div class="footer">
Señales únicamente • No realiza compras automáticas • Hora Nueva York<br>
Probabilidades y proyecciones son estimaciones.
</div>

</div>
</body>
</html>'''

@app.route('/')
def home():
    b=btc_price()
    ch=btc_change()
    m=current_market()
    nm=next_market()
    t=target(m)
    d,p=fixed(m,b,t)
    k=kalshi_prob(m)

    ku=50 if k is None else clamp(k*100,0,100)
    kd=100-ku
    kdri='SUBE' if ku>=50 else 'BAJA'
    div=k is not None and kdri!=d

    rem,total=close_info(m)
    elapsed=max(1,total-rem)

    rate=((b-t)/t*100) if b is not None and t else 0

    proj=(t*(1+((b-t)/t)*(total/elapsed))) if b is not None and t else None
    proj=clamp(proj,t*.97,t*1.03) if proj else None

    need=0 if (b>=t if d=='SUBE' else b<=t) else abs(b-t)/t*100

    conf=confirm(b,t,d,k)

    quality='VIGILAR' if div else (
        'FUERTE' if conf==3 else
        'MEDIA' if conf==2 else
        'BASE'
    )

    nd,np=model(b,target(nm)) if nm and target(nm) else (None,None)

    ny=datetime.now(
        ZoneInfo('America/New_York')
    ).strftime('%I:%M:%S %p').lstrip('0')

    return render_template_string(
        HTML,
        ny=ny,
        d=d,
        p=round(p*100),
        btc=money(b),
        chg=f'{ch:+.2f}%',
        entry=f'{clamp(p/1.10*100,0,100):.0f}',
        conf=conf,
        div=div,
        msg=(
            'Kalshi marca la dirección contraria. '
            'La señal principal permanece fija.'
            if div else
            'Kalshi acompaña la dirección. '
            'La señal permanece fija.'
        ),
        target=money(t),
        close=countdown(rem),
        proj=money(proj),
        rate=f'{rate:+.2f}',
        need=f'{need:.2f}',
        ku=f'{ku:.0f}',
        kd=f'{kd:.0f}',
        kdirection=kdri,
        quality=quality,
        nd=nd,
        np=round(np*100) if np else None
    )

@app.route('/health')
def health():
    return {'status':'ok','service':'btc15m-bot-4'}

if __name__=='__main__':
    app.run(host='0.0.0.0',port=10000)
