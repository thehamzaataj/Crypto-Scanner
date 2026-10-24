"""Crypto Trend Scanner backend v2. Run: uvicorn main:app --port 8000
Data: CoinGecko (market cap) + Binance/OKX/Bybit/KuCoin public candles. No API keys."""
import asyncio, json, os, sqlite3, time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import httpx, pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

BINANCE = os.getenv("BINANCE_URL", "https://data-api.binance.vision")
SCAN_SECONDS, LIVE_SECONDS = int(os.getenv("SCAN_SECONDS", "300")), int(os.getenv("LIVE_SECONDS", "15"))
CFG = {"topN": int(os.getenv("TOP_N", "150")), "adxMin": 20.0, "minRR": 1.5, "minScore": 55, "expire": int(os.getenv("EXPIRE_CANDLES", "12"))}
MIN_VOL, MIN_MCAP = 1e6, 1e7
TFS = ["15m", "1h", "4h", "12h", "1d", "1w"]
MS = {"15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "12h": 43_200_000, "1d": 86_400_000, "1w": 604_800_000}
MAP = {"Bybit": {"15m": "15", "1h": "60", "4h": "240", "12h": "720", "1d": "D", "1w": "W"}, "OKX": {"15m": "15m", "1h": "1H", "4h": "4H", "12h": "12H", "1d": "1D", "1w": "1W"},
       "KuCoin": {"15m": "15min", "1h": "1hour", "4h": "4hour", "12h": "12hour", "1d": "1day", "1w": "1week"}}
TV = {"Binance": "BINANCE", "OKX": "OKX", "Bybit": "BYBIT", "KuCoin": "KUCOIN"}; EXS = list(TV)
SEM = {"Binance": asyncio.Semaphore(6), "OKX": asyncio.Semaphore(3), "Bybit": asyncio.Semaphore(6), "KuCoin": asyncio.Semaphore(4)}
STABLE = {"USDT", "USDC", "FDUSD", "DAI", "TUSD", "USDE", "USDS", "PYUSD", "USDD", "BUSD", "WBTC", "STETH", "WSTETH", "WETH", "WEETH", "USDG", "USD1"}
EXMAP, UD, LOCK = {}, {}, asyncio.Lock()
S = {"rows": [], "heat": {}, "frames": {}, "market": None, "last": None, "error": None, "watch": [], "ver": 0}
P = {"running": False, "done": 0, "total": 0}
db = sqlite3.connect(os.getenv("DB_PATH", "scanner.db"), check_same_thread=False)
db.executescript("""create table if not exists scans(id integer primary key autoincrement, ts text, strategy text, params text, regime text, coins int, signals int, by_exchange text);
create table if not exists sigs(key text primary key, scan_id int, symbol text, exchange text, tf text, grade text, score int, entry real, sl real, tp1 real, rr real, close_ms int, reason text, status text default 'New', fwd_ret real default 0);""")
f = lambda v: float(v) if pd.notna(v) else 0.0
grade = lambda n: "Strong Buy" if n >= 85 else "Buy" if n >= 70 else "Watch" if n >= 55 else "Neutral"

def ind(df):
    c, h, l = df.close, df.high, df.low
    w = lambda s: s.ewm(alpha=1 / 14, adjust=False).mean()
    df["ema50"], df["ema200"] = c.ewm(span=50, adjust=False).mean(), c.ewm(span=200, adjust=False).mean()
    d = c.diff(); df["up"], df["dn"] = w(d.clip(lower=0)), w((-d).clip(lower=0))
    df["rsi"] = 100 - 100 / (1 + df.up / df.dn.replace(0, 1e-12))
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1); atr = w(tr); df["atr"] = atr
    u, dd = h.diff(), -l.diff()
    pdi = 100 * w(u.where((u > dd) & (u > 0), 0.0)) / atr; mdi = 100 * w(dd.where((dd > u) & (dd > 0), 0.0)) / atr
    df["adx"] = w(100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, 1e-12))
    df["vol_avg"] = df.volume.rolling(20).mean().shift(1)
    return df

async def fetch(c, ex, sym, tf, limit):
    try:
        async with SEM[ex]:
            if ex == "Binance":
                r = await c.get(f"{BINANCE}/api/v3/klines", params={"symbol": sym + "USDT", "interval": tf, "limit": limit}); rows = [x[:6] for x in r.json()] if r.status_code == 200 else []
            elif ex == "OKX":
                r = await c.get("https://www.okx.com/api/v5/market/candles", params={"instId": f"{sym}-USDT", "bar": MAP[ex][tf], "limit": min(limit, 300)}); rows = [x[:6] for x in r.json().get("data", [])][::-1]; await asyncio.sleep(0.1)
            elif ex == "Bybit":
                r = await c.get("https://api.bybit.com/v5/market/kline", params={"category": "spot", "symbol": sym + "USDT", "interval": MAP[ex][tf], "limit": limit}); rows = [x[:6] for x in r.json()["result"]["list"]][::-1]
            else:
                r = await c.get("https://api.kucoin.com/api/v1/market/candles", params={"symbol": f"{sym}-USDT", "type": MAP[ex][tf]}); rows = [[int(x[0]) * 1000, x[1], x[3], x[4], x[2], x[5]] for x in (r.json().get("data") or [])][::-1][-limit:]
        if len(rows) < 30: return None
        df = pd.DataFrame(rows, columns=["open_time", "open", "high", "low", "close", "volume"]).astype(float)
        df["close_time"] = df.open_time + MS[tf] - 1
        df = df[df.close_time < time.time() * 1000].reset_index(drop=True)  # closed candles only
        return ind(df) if len(df) >= 30 else None
    except Exception: return None

async def pick(c, sym):
    for ex in dict.fromkeys(([EXMAP[sym]] if sym in EXMAP else []) + EXS):  # first exchange that lists SYM/USDT
        d = await fetch(c, ex, sym, "1d", 300)
        if d is not None: EXMAP[sym] = ex; return ex, d
    return None, None

def regime_of(d1):
    x = d1.iloc[-1]; rising = d1.ema200.iloc[-1] > d1.ema200.iloc[-6]
    return "Bullish" if x.close > x.ema200 and x.ema50 > x.ema200 and rising else "Bearish" if x.close < x.ema200 else "Neutral"

def analyze(m, ex, D, tf, regime, rsi):
    d, d1 = D[tf.lower()], D["1d"]; x, p, X = d.iloc[-1], d.iloc[-2], d1.iloc[-1]; sym = m["symbol"].upper()
    pos, neg = [], []
    def chk(ok, a, b): (pos if ok else neg).append(a if ok else b); return bool(ok)
    slope = bool(d1.ema200.iloc[-1] > d1.ema200.iloc[-6])
    checks = [chk(X.close > X.ema200, "1D close above EMA200", "1D close below EMA200"), chk(X.ema50 > X.ema200, "1D EMA50 above EMA200", "1D EMA50 below EMA200"), chk(slope, "1D EMA200 rising", "1D EMA200 not rising")]
    if tf == "4H": checks.append(chk(x.close > x.ema200 and x.ema50 > x.ema200, "4H above EMA200 with EMA50 above EMA200", "4H trend structure broken"))
    adx_ok = chk(x.adx >= CFG["adxMin"], f"ADX {x.adx:.0f}, trend present", f"ADX {x.adx:.0f} below {CFG['adxMin']:.0f}, market ranging")
    trend_ok = all(checks) and adx_ok
    atr = f(x.atr); dist = abs(float(d.low.iloc[-3:].min()) - x.ema50) / atr if atr else 9
    bull, rising = bool(x.close > x.open), bool(x.rsi > p.rsi); vr = f(x.volume / x.vol_avg) if x.vol_avg else 0
    chk(dist <= 1, f"pulled back to EMA50 ({dist:.1f} ATR away)", f"price {dist:.1f} ATR from EMA50, no pullback entry")
    chk(40 <= x.rsi <= 55 and rising, f"RSI {x.rsi:.0f} in 40-55 and turning up", f"RSI {x.rsi:.0f} outside 40-55 or not turning up")
    chk(bull and vr >= 1.2, f"bullish candle closed on {vr:.1f}x average volume", f"no bullish volume confirmation ({vr:.1f}x)")
    recovered = bool((d.rsi.iloc[-6:-1] < 40).any()); pv_ok = bool(d.volume.iloc[-6:-1].mean() < d.volume.iloc[-30:-6].max())
    bd = {"Trend": round(30 * sum(checks) / len(checks)), "Pullback quality": round((20 if dist <= .5 else 14 if dist <= 1 else 8 if dist <= 1.5 else 0) * (1 if bull else .5)),
          "RSI": 15 if 40 <= x.rsi <= 55 and rising else 9 if 40 <= x.rsi <= 55 else 4 if rising and 30 <= x.rsi <= 65 else 0,
          "Volume": (8 if bull and vr >= 1.2 else 4 if vr >= 1 else 0) + (7 if pv_ok else 0), "Momentum/ADX": 10 if x.adx >= 25 else 7 if x.adx >= 20 else 0, "Market regime": {"Bullish": 10, "Neutral": 5, "Bearish": 0}[regime]}
    if recovered and rising: bd["RSI"] = min(15, bd["RSI"] + 3)
    score = sum(bd.values())
    if not trend_ok: score = min(score, 54)
    if regime == "Bearish" and sym != "BTC": score = min(score, 69); neg.append("BTC below 1D EMA200, altcoin signals downgraded")
    entry = f(x.close); sl = min(entry - 1.5 * atr, float(d.low.iloc[-10:].min()) - 0.1 * atr); risk = entry - sl
    rr = max(0.0, (float(d.high.iloc[-60:].max()) - entry) / risk) if risk > 0 else 0.0
    if rr < CFG["minRR"]: neg.append(f"R:R {rr:.1f} below {CFG['minRR']} (resistance too close)")
    sig = bool(score >= CFG["minScore"] and rr >= CFG["minRR"]); cm = int(x.close_time)
    return {"symbol": sym, "name": m["name"], "logo": m["image"], "exchange": ex, "pair": f"{sym}/USDT", "tradingViewSymbol": f"{TV[ex]}:{sym}USDT", "price": float(m["current_price"] or entry),
        "change24h": f(m.get("price_change_percentage_24h")), "marketCap": f(m["market_cap"]), "volume24h": f(m["total_volume"]), "rank": int(m.get("market_cap_rank") or 0), "timeframe": tf, "score": int(score), "grade": grade(score),
        "rsi": f(x.rsi), "ema50": f(x.ema50), "ema200": f(x.ema200), "adx": f(x.adx), "atr": atr, "volumeRatio": vr, "entryLow": entry - 0.25 * atr, "entryHigh": entry, "stopLoss": sl, "tp1": entry + 1.5 * risk, "tp2": entry + 2.5 * risk, "tp3": entry + 4 * risk,
        "riskReward": rr, "status": "No signal", "candleCloseTime": datetime.fromtimestamp(cm / 1000, tz=timezone.utc).isoformat(), "closeMs": cm, "trend": "Bullish" if trend_ok else "Bearish" if X.close < X.ema200 else "Neutral", "isSignal": sig,
        "reason": ("Signal: " + "; ".join(pos) + ".") if sig else ("No signal: " + "; ".join(neg[:3]) + "."), "explanation": pos + neg, "rsiByTf": rsi,
        "scoreBreakdown": bd, "invalidation": [f"A {tf} candle closes below the stop loss.", f"Price closes below the {tf} EMA200.", "BTC loses its 1D EMA200."]}

def resolve(d, close_ms, entry, sl, tp1):
    sub = d[d.close_time > close_ms]
    for i, r in enumerate(sub.itertuples()):
        if r.low <= sl: return "Stopped", sl / entry - 1      # stop checked first if both hit in one candle
        if r.high >= tp1: return "TP hit", tp1 / entry - 1
        if i + 1 >= CFG["expire"]: return "Expired", r.close / entry - 1
    return ("Active", float(sub.close.iloc[-1]) / entry - 1) if len(sub) else ("New", 0.0)

async def scan(params=None):
    async with LOCK:
        if params: CFG.update({k: type(CFG[k])(v) for k, v in params.items() if k in CFG and v is not None})
        P.update(running=True, done=0, total=0)
        try:
            async with httpx.AsyncClient(timeout=25) as c:
                r = await c.get("https://api.coingecko.com/api/v3/coins/markets", params={"vs_currency": "usd", "order": "market_cap_desc", "per_page": min(CFG["topN"], 250), "page": 1}); r.raise_for_status()
                seen, mk = set(), []
                for m in r.json():
                    s = m["symbol"].upper()
                    if s not in STABLE and s not in seen: seen.add(s); mk.append(m)
                P["total"] = len(mk)
                async def load(m):
                    try:
                        sym = m["symbol"].upper(); ex, d1 = await pick(c, sym)
                        if d1 is None: return None
                        tfs = ("15m", "1h", "4h", "12h", "1w"); res = await asyncio.gather(*(fetch(c, ex, sym, tf, 300 if tf == "4h" else 120) for tf in tfs))
                        D = dict(zip(tfs, res)); D["1d"] = d1; return m, ex, D
                    finally: P["done"] += 1
                data = [x for x in await asyncio.gather(*(load(m) for m in mk)) if x]
            btc = next((x for x in data if x[0]["symbol"].upper() == "BTC"), None)
            if not btc: raise RuntimeError("BTC data missing")
            regime = regime_of(btc[2]["1d"]); rows, frames, heat = [], {}, {}
            for m, ex, D in data:
                sym = m["symbol"].upper(); rsi = {}
                for tf in TFS:
                    d = D.get(tf)
                    rsi[tf] = f(d.rsi.iloc[-1]) if d is not None else None
                    if d is not None: frames[(sym, tf)] = d; UD[(sym, tf)] = (f(d.up.iloc[-1]), f(d.dn.iloc[-1]), f(d.close.iloc[-1]))
                heat[sym] = {"symbol": sym, "name": m["name"], "logo": m["image"], "exchange": ex, "tradingViewSymbol": f"{TV[ex]}:{sym}USDT", "price": float(m["current_price"] or 0), "change24h": f(m.get("price_change_percentage_24h")),
                             "marketCap": f(m["market_cap"]), "volume24h": f(m["total_volume"]), "rank": int(m.get("market_cap_rank") or 0), "rsi": rsi}
                if all(D.get(t) is not None and len(D[t]) >= 210 for t in ("4h", "1d")):
                    for tf in ("4H", "1D"):
                        try: rows.append(analyze(m, ex, D, tf, regime, rsi))
                        except Exception as e: print("analyze failed", sym, e)
            by_ex = {e: sum(h["exchange"] == e for h in heat.values()) for e in EXS}
            cur = db.execute("insert into scans(ts,strategy,params,regime,coins,signals,by_exchange) values(?,?,?,?,?,?,?)", (datetime.now(timezone.utc).isoformat(), "trend_following", json.dumps(CFG), regime, len(heat), sum(s["isSignal"] for s in rows), json.dumps(by_ex)))
            sid = cur.lastrowid
            for s in rows:
                if s["isSignal"]: db.execute("insert or ignore into sigs(key,scan_id,symbol,exchange,tf,grade,score,entry,sl,tp1,rr,close_ms,reason) values(?,?,?,?,?,?,?,?,?,?,?,?,?)", (f'{s["symbol"]}:{s["timeframe"]}:{s["closeMs"]}', sid, s["symbol"], s["exchange"], s["timeframe"], s["grade"], s["score"], s["entryHigh"], s["stopLoss"], s["tp1"], s["riskReward"], s["closeMs"], s["reason"]))
            for key, sym, tf, cm, en, sl, tp in db.execute("select key,symbol,tf,close_ms,entry,sl,tp1 from sigs where status in ('New','Active')").fetchall():  # judge old signals against new candles
                d = frames.get((sym, tf.lower()))
                if d is not None: st, fw = resolve(d, cm, en, sl, tp); db.execute("update sigs set status=?, fwd_ret=? where key=?", (st, fw, key))
            db.commit()
            for s in rows:
                g = db.execute("select status from sigs where key=?", (f'{s["symbol"]}:{s["timeframe"]}:{s["closeMs"]}',)).fetchone()
                if s["isSignal"] and g: s["status"] = g[0]
            now = datetime.now(timezone.utc).isoformat(); top = sorted([s for s in rows if s["isSignal"]], key=lambda s: -s["score"])[:10]
            S.update(rows=rows, heat=heat, frames=frames, error=None, ver=S["ver"] + 1,
                     market={"btcRegime": regime, "totalScanned": len(heat), "activeSignals": sum(s["isSignal"] for s in rows), "strongTrendCount": sum(s["trend"] == "Bullish" for s in rows if s["timeframe"] == "4H"), "lastScanTime": now, "byExchange": by_ex},
                     last={"id": sid, "ts": now, "coins": len(heat), "signals": len(top) and sum(s["isSignal"] for s in rows), "byExchange": by_ex, "regime": regime, "params": dict(CFG), "top": [{k: s[k] for k in ("symbol", "exchange", "timeframe", "grade", "score", "reason")} for s in top]})
        finally: P["running"] = False

async def tickers(c):
    T = {}
    async def b():
        for x in (await c.get(f"{BINANCE}/api/v3/ticker/24hr")).json():
            if x["symbol"].endswith("USDT"): T[("Binance", x["symbol"][:-4])] = (float(x["lastPrice"]), float(x["priceChangePercent"]))
    async def o():
        for x in (await c.get("https://www.okx.com/api/v5/market/tickers", params={"instType": "SPOT"})).json()["data"]:
            if x["instId"].endswith("-USDT"): l, o24 = float(x["last"]), float(x["open24h"] or 0); T[("OKX", x["instId"][:-5])] = (l, (l / o24 - 1) * 100 if o24 else 0)
    async def y():
        for x in (await c.get("https://api.bybit.com/v5/market/tickers", params={"category": "spot"})).json()["result"]["list"]:
            if x["symbol"].endswith("USDT"): T[("Bybit", x["symbol"][:-4])] = (float(x["lastPrice"]), float(x["price24hPcnt"] or 0) * 100)
    async def k():
        for x in (await c.get("https://api.kucoin.com/api/v1/market/allTickers")).json()["data"]["ticker"]:
            if x["symbol"].endswith("-USDT") and x["last"]: T[("KuCoin", x["symbol"][:-5])] = (float(x["last"]), float(x["changeRate"] or 0) * 100)
    await asyncio.gather(b(), o(), y(), k(), return_exceptions=True); return T

async def live():  # realtime: live price + live (forming-candle) RSI every LIVE_SECONDS
    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as c: T = await tickers(c)
            for h in S["heat"].values():
                t = T.get((h["exchange"], h["symbol"]))
                if not t: continue
                h["price"], h["change24h"] = t
                for tf in TFS:
                    u = UD.get((h["symbol"], tf))
                    if u: ch = t[0] - u[2]; ag, al = (u[0] * 13 + max(ch, 0)) / 14, (u[1] * 13 + max(-ch, 0)) / 14; h["rsi"][tf] = 100 - 100 / (1 + ag / al) if al > 0 else 100.0
            for s in S["rows"]:
                h = S["heat"].get(s["symbol"])
                if h: s["price"], s["change24h"] = h["price"], h["change24h"]
            S["ver"] += 1
        except Exception as e: print("live failed:", e)
        await asyncio.sleep(LIVE_SECONDS)

async def loop():
    while True:
        try: await scan()
        except Exception as e: S["error"] = repr(e); print("scan failed:", e)
        await asyncio.sleep(SCAN_SECONDS)

@asynccontextmanager
async def life(app):
    ts = [asyncio.create_task(loop()), asyncio.create_task(live())]; yield
    for t in ts: t.cancel()

app = FastAPI(lifespan=life)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
def ready():
    if not S["rows"] and not S["heat"]: raise HTTPException(503, S["error"] or "First scan in progress, retry in ~30-60 seconds")

def rsi_ok(rsi, tf, lo, hi): v = (rsi or {}).get(tf); return v is not None and (lo is None or v >= lo) and (hi is None or v <= hi)
def listing(rows, page, limit, search, signal, mc, vol, exchange, sort, timeframe, rsiTf, rsiMin, rsiMax):
    mc = MIN_MCAP if mc is None else mc; vol = MIN_VOL if vol is None else vol
    r = [s for s in rows if s["marketCap"] >= mc and s["volume24h"] >= vol and (not search or search.lower() in (s["symbol"] + s["name"]).lower()) and (not signal or s["grade"] == signal)
         and (not exchange or s["exchange"] == exchange) and (not timeframe or s["timeframe"] == timeframe) and (not rsiTf or (rsiMin is None and rsiMax is None) or rsi_ok(s["rsiByTf"], rsiTf, rsiMin, rsiMax))]
    if not timeframe:
        best = {}
        for s in r:
            if s["symbol"] not in best or s["score"] > best[s["symbol"]]["score"]: best[s["symbol"]] = s
        r = list(best.values())
    r.sort(key=lambda s: -s["marketCap"] if sort == "marketCap" else -s["volume24h"] if sort == "volume" else -s["score"])
    return {"items": r[(page - 1) * limit: page * limit], "total": len(r), "page": page, "limit": limit}
Q = dict(page=1, limit=50, search="", signal="", minMarketCap=None, minVolume=None, exchange="", sort="score", timeframe="", confirmedOnly=False, rsiTf="", rsiMin=None, rsiMax=None)
def _l(rows, a): return listing(rows, a["page"], a["limit"], a["search"], a["signal"], a["minMarketCap"], a["minVolume"], a["exchange"], a["sort"], a["timeframe"], a["rsiTf"], a["rsiMin"], a["rsiMax"])

@app.get("/api/coins")
def coins(page: int = 1, limit: int = 50, search: str = "", signal: str = "", minMarketCap: float | None = None, minVolume: float | None = None, exchange: str = "", sort: str = "score", timeframe: str = "", confirmedOnly: bool = False, rsiTf: str = "", rsiMin: float | None = None, rsiMax: float | None = None):
    ready(); return _l(S["rows"], locals())
@app.get("/api/signals")
def signals(page: int = 1, limit: int = 50, search: str = "", signal: str = "", minMarketCap: float | None = None, minVolume: float | None = None, exchange: str = "", sort: str = "score", timeframe: str = "", confirmedOnly: bool = False, rsiTf: str = "", rsiMin: float | None = None, rsiMax: float | None = None):
    ready(); return _l([s for s in S["rows"] if s["isSignal"]], locals())

@app.get("/api/rsi-heatmap")
def heatmap(tf: str = "4h", rsiMin: float | None = None, rsiMax: float | None = None, exchange: str = "", search: str = "", minMarketCap: float = 0, minVolume: float = 0):
    ready(); r = [h for h in S["heat"].values() if h["marketCap"] >= minMarketCap and h["volume24h"] >= minVolume and (not exchange or h["exchange"] == exchange) and (not search or search.lower() in (h["symbol"] + h["name"]).lower()) and (rsiMin is None and rsiMax is None or rsi_ok(h["rsi"], tf, rsiMin, rsiMax))]
    r.sort(key=lambda h: h["rank"] or 9999)
    return {"items": r, "total": len(r), "tf": tf, "byExchange": {e: sum(h["exchange"] == e for h in r) for e in EXS}, "updated": datetime.now(timezone.utc).isoformat()}

@app.get("/api/coin/{symbol}")
def coin(symbol: str):
    ready(); sym = symbol.upper(); s = next((x for x in S["rows"] if x["symbol"] == sym and x["timeframe"] == "4H"), None)
    if not s: raise HTTPException(404, "Coin not scanned")
    cs = [{"t": datetime.fromtimestamp(r.open_time / 1000, tz=timezone.utc).isoformat(), "o": r.open, "h": r.high, "l": r.low, "c": r.close, "v": r.volume, "ema50": r.ema50, "ema200": r.ema200, "rsi": r.rsi} for r in S["frames"][(sym, "4h")].tail(80).itertuples()]
    return {**s, "candles": json.loads(json.dumps(cs))}

@app.get("/api/market-status")
def market(): ready(); return {**S["market"], "lastLiveTime": datetime.now(timezone.utc).isoformat()}
@app.get("/api/stream")
async def stream():  # Server-Sent Events: the browser refreshes the moment data changes, no manual reload
    async def gen():
        last = -1
        while True:
            if S["ver"] != last: last = S["ver"]; yield f"data: {last}\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

@app.get("/api/strategy")
def strategy():
    return {"name": "Trend Following (1D trend, 4H/1D entry)", "params": CFG, "weights": {"Trend": 30, "Pullback quality": 20, "RSI": 15, "Volume": 15, "Momentum/ADX": 10, "Market regime": 10},
            "grades": {"Strong Buy": "85+", "Buy": "70-84", "Watch": "55-69", "Neutral": "below 55"}, "exchanges": EXS, "timeframes": TFS,
            "rules": ["Only CLOSED candles are used (no repainting).", "1D: price > EMA200, EMA50 > EMA200, EMA200 rising.", "4H entry also needs price > EMA200 and EMA50 > EMA200.", "ADX(14) must be above the minimum (trend present, not ranging).",
                      "Pullback: price within 1 ATR of EMA50; RSI 40-55 and turning up (recovery from below 40 gives a bonus).", "Confirmation: bullish candle with volume above 1.2x the 20-candle average; pullback volume lower than impulse volume.",
                      "Stop loss = lower of entry - 1.5 ATR and the 10-candle swing low. TP1/TP2/TP3 = 1.5R / 2.5R / 4R.", "R:R is measured to the nearest 60-candle swing high; signals below the minimum R:R are hidden.", "If BTC is below its 1D EMA200, altcoin scores are capped at 69."]}

@app.post("/api/scan")
async def scan_now(body: dict | None = None):
    if P["running"]: raise HTTPException(409, "A scan is already running")
    asyncio.create_task(scan(body or {})); return {"started": True}
@app.get("/api/scan/status")
def scan_status(): return {**P, "last": S["last"]}
@app.get("/api/scans")
def scans(): return [{"id": r[0], "ts": r[1], "regime": r[2], "coins": r[3], "signals": r[4], "byExchange": json.loads(r[5] or "{}")} for r in db.execute("select id,ts,regime,coins,signals,by_exchange from scans order by id desc limit 20")]

@app.get("/api/signals/performance")
def perf():
    R = db.execute("select grade,tf,exchange,status,fwd_ret,symbol,reason from sigs order by close_ms desc").fetchall()
    done = [r for r in R if r[3] in ("TP hit", "Stopped", "Expired")]
    def agg(label, rs):
        w, l, n = sum(r[3] == "TP hit" for r in rs), sum(r[3] == "Stopped" for r in rs), len(rs)
        return {"label": label, "winRate": round(100 * w / (w + l), 1) if w + l else 0, "avgR": round((1.5 * w - l) / (w + l), 2) if w + l else 0, "total": n, "wins": w, "losses": l, "expired": n - w - l, "directionAccuracy": round(100 * sum((r[4] or 0) > 0 for r in rs) / n, 1) if n else 0}
    t = agg("All", done)
    return {"winRate": t["winRate"], "avgR": t["avgR"], "directionAccuracy": t["directionAccuracy"], "totalSignals": len(R), "open": len(R) - len(done),
            "source": f"Live-tracked: {len(done)} resolved of {len(R)} signals. Win rate = TP1 hit before stop loss (expired excluded). Direction accuracy = price higher at resolution.{' Sample is small, treat with caution.' if len(done) < 30 else ''}",
            "byGrade": [agg(g, [r for r in done if r[0] == g]) for g in ("Strong Buy", "Buy", "Watch")], "byTimeframe": [agg(x, [r for r in done if r[1] == x]) for x in ("4H", "1D")],
            "byExchange": [agg(e, [r for r in done if r[2] == e]) for e in EXS], "recent": [{"symbol": r[5], "exchange": r[2], "timeframe": r[1], "grade": r[0], "status": r[3], "fwdReturn": round((r[4] or 0) * 100, 2), "reason": r[6]} for r in done[:15]]}

@app.get("/api/watchlist")
def wl(): return [x for sym in S["watch"] for x in S["rows"] if x["symbol"] == sym and x["timeframe"] == "4H"]
@app.post("/api/watchlist")
def wl_add(body: dict):
    sym = str(body.get("symbol", "")).upper()
    if sym and sym not in S["watch"]: S["watch"].append(sym)
    return {"ok": True}
@app.delete("/api/watchlist/{symbol}")
def wl_del(symbol: str): S["watch"] = [x for x in S["watch"] if x != symbol.upper()]; return {"ok": True}
