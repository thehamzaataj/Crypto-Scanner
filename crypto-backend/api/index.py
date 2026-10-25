"""Crypto Trend Scanner backend, Vercel (serverless) version.
Data: CoinGecko + Binance/OKX/Bybit/KuCoin public candles. State lives in Upstash Redis (falls back to memory if not configured).
Scans run when /api/cron?key=SECRET is called (GitHub Actions does it every 10 min) or from the Scan button."""
import asyncio, json, os, time
from datetime import datetime, timezone
import httpx, pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

BINANCE = os.getenv("BINANCE_URL", "https://data-api.binance.vision")
CFG = {"topN": int(os.getenv("TOP_N", "60")), "adxMin": 20.0, "minRR": 1.5, "minScore": 55, "expire": int(os.getenv("EXPIRE_CANDLES", "12"))}
CRON_SECRET = os.getenv("CRON_SECRET", "")
RURL = os.getenv("UPSTASH_REDIS_REST_URL") or os.getenv("KV_REST_API_URL"); RTOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN") or os.getenv("KV_REST_API_TOKEN")
MIN_VOL, MIN_MCAP = 1e6, 1e7
TFS = ["15m", "1h", "4h", "12h", "1d", "1w"]
MS = {"15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "12h": 43_200_000, "1d": 86_400_000, "1w": 604_800_000}
MAP = {"Bybit": {"15m": "15", "1h": "60", "4h": "240", "12h": "720", "1d": "D", "1w": "W"}, "OKX": {"15m": "15m", "1h": "1H", "4h": "4H", "12h": "12H", "1d": "1D", "1w": "1W"},
       "KuCoin": {"15m": "15min", "1h": "1hour", "4h": "4hour", "12h": "12hour", "1d": "1day", "1w": "1week"}}
TV = {"Binance": "BINANCE", "OKX": "OKX", "Bybit": "BYBIT", "KuCoin": "KUCOIN"}; EXS = list(TV)
STABLE = {"USDT", "USDC", "FDUSD", "DAI", "TUSD", "USDE", "USDS", "PYUSD", "USDD", "BUSD", "WBTC", "STETH", "WSTETH", "WETH", "WEETH", "USDG", "USD1"}
SEM, EXMAP, MEM, SNAP = {}, {}, {}, {"t": 0, "d": None}
f = lambda v: float(v) if pd.notna(v) else 0.0
grade = lambda n: "Strong Buy" if n >= 85 else "Buy" if n >= 70 else "Watch" if n >= 55 else "Neutral"
def init_sem(): SEM.clear(); SEM.update({"Binance": asyncio.Semaphore(6), "OKX": asyncio.Semaphore(3), "Bybit": asyncio.Semaphore(6), "KuCoin": asyncio.Semaphore(4)})


# ---------- storage (Upstash Redis REST, or memory) ----------
async def rcmd(*cmd):
    async with httpx.AsyncClient(timeout=20) as c:
        x = await c.post(RURL, json=list(cmd), headers={"Authorization": f"Bearer {RTOKEN}"}); x.raise_for_status(); return x.json()["result"]
async def kv_get(k): return await rcmd("GET", k) if RURL else MEM.get(k)
async def kv_set(k, v):
    if RURL: await rcmd("SET", k, v)
    else: MEM[k] = v
async def h_all(k):
    if not RURL: return dict(MEM.get(k, {}))
    a = await rcmd("HGETALL", k) or []; return dict(zip(a[::2], a[1::2]))
async def h_set(k, m):
    if not m: return
    if RURL: await rcmd("HSET", k, *[x for kv in m.items() for x in kv])
    else: MEM.setdefault(k, {}).update(m)
async def l_push(k, v):
    if RURL: await rcmd("LPUSH", k, v); await rcmd("LTRIM", k, 0, 29)
    else: MEM[k] = ([v] + MEM.get(k, []))[:30]
async def l_all(k): return ((await rcmd("LRANGE", k, 0, 29)) if RURL else MEM.get(k, [])) or []

# ---------- data + indicators ----------
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
    for ex in dict.fromkeys(([EXMAP[sym]] if sym in EXMAP else []) + EXS):
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

# ---------- scan ----------
async def scan(params=None):
    if params: CFG.update({k: type(CFG[k])(v) for k, v in params.items() if k in CFG and v is not None})
    init_sem(); EXMAP.clear(); EXMAP.update(json.loads(await kv_get("exmap") or "{}"))
    async with httpx.AsyncClient(timeout=25) as c:
        r = await c.get("https://api.coingecko.com/api/v3/coins/markets", params={"vs_currency": "usd", "order": "market_cap_desc", "per_page": min(CFG["topN"], 250), "page": 1}); r.raise_for_status()
        seen, mk = set(), []
        for m in r.json():
            s = m["symbol"].upper()
            if s not in STABLE and s not in seen: seen.add(s); mk.append(m)
        async def load(m):
            sym = m["symbol"].upper(); ex, d1 = await pick(c, sym)
            if d1 is None: return None
            tfs = ("15m", "1h", "4h", "12h", "1w"); res = await asyncio.gather(*(fetch(c, ex, sym, tf, 300 if tf == "4h" else 120) for tf in tfs))
            D = dict(zip(tfs, res)); D["1d"] = d1; return m, ex, D
        data = [x for x in await asyncio.gather(*(load(m) for m in mk)) if x]
    btc = next((x for x in data if x[0]["symbol"].upper() == "BTC"), None)
    if not btc: raise RuntimeError("BTC data missing (exchanges unreachable from this server region?)")
    regime = regime_of(btc[2]["1d"]); rows, frames, heat = [], {}, {}
    for m, ex, D in data:
        sym = m["symbol"].upper(); rsi, ud = {}, {}
        for tf in TFS:
            d = D.get(tf); rsi[tf] = f(d.rsi.iloc[-1]) if d is not None else None
            if d is not None: frames[(sym, tf)] = d; ud[tf] = [f(d.up.iloc[-1]), f(d.dn.iloc[-1]), f(d.close.iloc[-1])]
        heat[sym] = {"symbol": sym, "name": m["name"], "logo": m["image"], "exchange": ex, "tradingViewSymbol": f"{TV[ex]}:{sym}USDT", "price": float(m["current_price"] or 0), "change24h": f(m.get("price_change_percentage_24h")),
                     "marketCap": f(m["market_cap"]), "volume24h": f(m["total_volume"]), "rank": int(m.get("market_cap_rank") or 0), "rsi": rsi, "ud": ud}
        if all(D.get(t) is not None and len(D[t]) >= 210 for t in ("4h", "1d")):
            for tf in ("4H", "1D"):
                try: rows.append(analyze(m, ex, D, tf, regime, rsi))
                except Exception as e: print("analyze failed", sym, e)
    sigs = {k: json.loads(v) for k, v in (await h_all("sigs")).items()}; ch = {}
    for s in rows:
        k = f'{s["symbol"]}:{s["timeframe"]}:{s["closeMs"]}'
        if s["isSignal"] and k not in sigs: sigs[k] = ch[k] = {"symbol": s["symbol"], "tf": s["timeframe"], "exchange": s["exchange"], "grade": s["grade"], "score": s["score"], "entry": s["entryHigh"], "sl": s["stopLoss"], "tp1": s["tp1"], "closeMs": s["closeMs"], "reason": s["reason"], "status": "New", "fwd": 0.0}
    for k, rec in sigs.items():  # judge earlier signals against the candles that closed since
        if rec["status"] in ("New", "Active"):
            d = frames.get((rec["symbol"], rec["tf"].lower()))
            if d is not None:
                st, fw = resolve(d, rec["closeMs"], rec["entry"], rec["sl"], rec["tp1"])
                if st != rec["status"] or abs(fw - rec["fwd"]) > 1e-9: rec["status"], rec["fwd"] = st, fw; ch[k] = rec
    await h_set("sigs", {k: json.dumps(v) for k, v in ch.items()})
    for s in rows:
        g = sigs.get(f'{s["symbol"]}:{s["timeframe"]}:{s["closeMs"]}')
        if s["isSignal"] and g: s["status"] = g["status"]
    by_ex = {e: sum(h["exchange"] == e for h in heat.values()) for e in EXS}; now = datetime.now(timezone.utc).isoformat(); n_sig = sum(s["isSignal"] for s in rows)
    top = sorted([s for s in rows if s["isSignal"]], key=lambda s: -s["score"])[:10]
    last = {"id": int(time.time()), "ts": now, "coins": len(heat), "signals": n_sig, "byExchange": by_ex, "regime": regime, "params": dict(CFG), "top": [{k: s[k] for k in ("symbol", "exchange", "timeframe", "grade", "score", "reason")} for s in top]}
    market = {"btcRegime": regime, "totalScanned": len(heat), "activeSignals": n_sig, "strongTrendCount": sum(s["trend"] == "Bullish" for s in rows if s["timeframe"] == "4H"), "lastScanTime": now, "byExchange": by_ex}
    await kv_set("snap", json.dumps({"ts": time.time(), "rows": rows, "heat": heat, "market": market, "last": last}))
    await kv_set("exmap", json.dumps(EXMAP)); await l_push("scans", json.dumps({k: last[k] for k in ("id", "ts", "regime", "coins", "signals", "byExchange")}))
    SNAP["d"] = None
    return last

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

async def live(d):  # live price + live (forming-candle) RSI, applied on top of the last scan
    async with httpx.AsyncClient(timeout=8) as c: T = await tickers(c)
    for h in d["heat"].values():
        t = T.get((h["exchange"], h["symbol"]))
        if not t: continue
        h["price"], h["change24h"] = t
        for tf, u in h.get("ud", {}).items():
            ch = t[0] - u[2]; ag, al = (u[0] * 13 + max(ch, 0)) / 14, (u[1] * 13 + max(-ch, 0)) / 14; h["rsi"][tf] = 100 - 100 / (1 + ag / al) if al > 0 else 100.0
    for s in d["rows"]:
        h = d["heat"].get(s["symbol"])
        if h: s["price"], s["change24h"], s["rsiByTf"] = h["price"], h["change24h"], h["rsi"]

async def get_snap():
    if SNAP["d"] and time.time() - SNAP["t"] < 10: return SNAP["d"]
    raw = await kv_get("snap")
    if not raw: raise HTTPException(503, "No scan data yet. Open /api/cron?key=YOUR_CRON_SECRET once and wait 1-2 minutes.")
    d = json.loads(raw)
    try: await live(d)
    except Exception as e: print("live failed:", e)
    SNAP.update(t=time.time(), d=d); return d

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

async def run_scan(params=None, gap=60):
    raw = await kv_get("snap")
    if raw and time.time() - json.loads(raw)["ts"] < gap: return json.loads(raw)["last"]   # scanned a moment ago
    try: return await scan(params)
    except Exception as e: raise HTTPException(500, f"Scan failed: {e!r}")
@app.get("/api/cron")
async def cron(key: str = ""):
    if not CRON_SECRET or key != CRON_SECRET: raise HTTPException(403, "Bad or missing key (set CRON_SECRET in Vercel env vars)")
    return await run_scan(gap=120)
@app.post("/api/scan")
async def scan_now(body: dict | None = None): return await run_scan(body or {})
@app.get("/api/scan/status")
async def scan_status():
    raw = await kv_get("snap"); return {"running": False, "done": 0, "total": 0, "last": json.loads(raw)["last"] if raw else None}
@app.get("/api/scans")
async def scans(): return [json.loads(x) for x in await l_all("scans")]

def rsi_ok(rsi, tf, lo, hi): v = (rsi or {}).get(tf); return v is not None and (lo is None or v >= lo) and (hi is None or v <= hi)
def listing(rows, a):
    mc = MIN_MCAP if a["minMarketCap"] is None else a["minMarketCap"]; vol = MIN_VOL if a["minVolume"] is None else a["minVolume"]; q = a["search"].lower()
    r = [s for s in rows if s["marketCap"] >= mc and s["volume24h"] >= vol and (not q or q in (s["symbol"] + s["name"]).lower()) and (not a["signal"] or s["grade"] == a["signal"]) and (not a["exchange"] or s["exchange"] == a["exchange"])
         and (not a["timeframe"] or s["timeframe"] == a["timeframe"]) and (not a["rsiTf"] or (a["rsiMin"] is None and a["rsiMax"] is None) or rsi_ok(s["rsiByTf"], a["rsiTf"], a["rsiMin"], a["rsiMax"]))]
    if not a["timeframe"]:
        best = {}
        for s in r:
            if s["symbol"] not in best or s["score"] > best[s["symbol"]]["score"]: best[s["symbol"]] = s
        r = list(best.values())
    r.sort(key=lambda s: -s["marketCap"] if a["sort"] == "marketCap" else -s["volume24h"] if a["sort"] == "volume" else -s["score"])
    return {"items": r[(a["page"] - 1) * a["limit"]: a["page"] * a["limit"]], "total": len(r), "page": a["page"], "limit": a["limit"]}
@app.get("/")
def home():
    return {
        "message": "Crypto Scanner API Running"
    }
@app.get("/api/coins")
async def coins(page: int = 1, limit: int = 50, search: str = "", signal: str = "", minMarketCap: float | None = None, minVolume: float | None = None, exchange: str = "", sort: str = "score", timeframe: str = "", confirmedOnly: bool = False, rsiTf: str = "", rsiMin: float | None = None, rsiMax: float | None = None):
    return listing((await get_snap())["rows"], locals())
@app.get("/api/signals")
async def signals(page: int = 1, limit: int = 50, search: str = "", signal: str = "", minMarketCap: float | None = None, minVolume: float | None = None, exchange: str = "", sort: str = "score", timeframe: str = "", confirmedOnly: bool = False, rsiTf: str = "", rsiMin: float | None = None, rsiMax: float | None = None):
    return listing([s for s in (await get_snap())["rows"] if s["isSignal"]], locals())

@app.get("/api/rsi-heatmap")
async def heatmap(tf: str = "4h", rsiMin: float | None = None, rsiMax: float | None = None, exchange: str = "", search: str = "", minMarketCap: float = 0, minVolume: float = 0):
    d = await get_snap(); q = search.lower()
    r = [{k: v for k, v in h.items() if k != "ud"} for h in d["heat"].values() if h["marketCap"] >= minMarketCap and h["volume24h"] >= minVolume and (not exchange or h["exchange"] == exchange) and (not q or q in (h["symbol"] + h["name"]).lower()) and (rsiMin is None and rsiMax is None or rsi_ok(h["rsi"], tf, rsiMin, rsiMax))]
    r.sort(key=lambda h: h["rank"] or 9999)
    return {"items": r, "total": len(r), "tf": tf, "byExchange": {e: sum(h["exchange"] == e for h in r) for e in EXS}}

@app.get("/api/coin/{symbol}")
async def coin(symbol: str):
    d = await get_snap(); sym = symbol.upper(); s = next((x for x in d["rows"] if x["symbol"] == sym and x["timeframe"] == "4H"), None)
    if not s: raise HTTPException(404, "Coin not scanned")
    init_sem()
    async with httpx.AsyncClient(timeout=20) as c: d4 = await fetch(c, s["exchange"], sym, "4h", 300)
    if d4 is None: raise HTTPException(502, "Could not load candles")
    cs = [{"t": datetime.fromtimestamp(r.open_time / 1000, tz=timezone.utc).isoformat(), "o": r.open, "h": r.high, "l": r.low, "c": r.close, "v": r.volume, "ema50": f(r.ema50), "ema200": f(r.ema200), "rsi": f(r.rsi)} for r in d4.tail(80).itertuples()]
    return {**s, "candles": cs}

@app.get("/api/market-status")
async def market(): return {**(await get_snap())["market"], "lastLiveTime": datetime.now(timezone.utc).isoformat()}
@app.get("/api/test-redis")
async def test_redis():
    await kv_set("test_key", "redis_working")
    value = await kv_get("test_key")

    return {
        "value": value,
        "redis_enabled": bool(RURL)
    }
@app.get("/api/strategy")
def strategy():
    return {"name": "Trend Following (1D trend, 4H/1D entry)", "params": CFG, "weights": {"Trend": 30, "Pullback quality": 20, "RSI": 15, "Volume": 15, "Momentum/ADX": 10, "Market regime": 10},
            "grades": {"Strong Buy": "85+", "Buy": "70-84", "Watch": "55-69", "Neutral": "below 55"}, "exchanges": EXS, "timeframes": TFS,
            "rules": ["Only CLOSED candles are used (no repainting).", "1D: price > EMA200, EMA50 > EMA200, EMA200 rising.", "4H entry also needs price > EMA200 and EMA50 > EMA200.", "ADX(14) must be above the minimum (trend present, not ranging).",
                      "Pullback: price within 1 ATR of EMA50; RSI 40-55 and turning up (recovery from below 40 gives a bonus).", "Confirmation: bullish candle with volume above 1.2x the 20-candle average; pullback volume lower than impulse volume.",
                      "Stop loss = lower of entry - 1.5 ATR and the 10-candle swing low. TP1/TP2/TP3 = 1.5R / 2.5R / 4R.", "R:R is measured to the nearest 60-candle swing high; signals below the minimum R:R are hidden.", "If BTC is below its 1D EMA200, altcoin scores are capped at 69."]}

@app.get("/api/signals/performance")
async def perf():
    R = sorted([json.loads(v) for v in (await h_all("sigs")).values()], key=lambda r: -r["closeMs"])
    done = [r for r in R if r["status"] in ("TP hit", "Stopped", "Expired")]
    def agg(label, rs):
        w, l, n = sum(r["status"] == "TP hit" for r in rs), sum(r["status"] == "Stopped" for r in rs), len(rs)
        return {"label": label, "winRate": round(100 * w / (w + l), 1) if w + l else 0, "avgR": round((1.5 * w - l) / (w + l), 2) if w + l else 0, "total": n, "wins": w, "losses": l, "expired": n - w - l, "directionAccuracy": round(100 * sum(r["fwd"] > 0 for r in rs) / n, 1) if n else 0}
    t = agg("All", done)
    return {"winRate": t["winRate"], "avgR": t["avgR"], "directionAccuracy": t["directionAccuracy"], "totalSignals": len(R), "open": len(R) - len(done),
            "source": f"Live-tracked: {len(done)} resolved of {len(R)} signals. Win rate = TP1 hit before stop loss (expired excluded). Direction accuracy = price higher at resolution.{' Sample is small, treat with caution.' if len(done) < 30 else ''}{'' if RURL else ' WARNING: Upstash Redis not connected, history resets.'}",
            "byGrade": [agg(g, [r for r in done if r["grade"] == g]) for g in ("Strong Buy", "Buy", "Watch")], "byTimeframe": [agg(x, [r for r in done if r["tf"] == x]) for x in ("4H", "1D")],
            "byExchange": [agg(e, [r for r in done if r["exchange"] == e]) for e in EXS], "recent": [{"symbol": r["symbol"], "exchange": r["exchange"], "timeframe": r["tf"], "grade": r["grade"], "status": r["status"], "fwdReturn": round(r["fwd"] * 100, 2), "reason": r["reason"]} for r in done[:15]]}

@app.get("/api/watchlist")
async def wl():
    d = await get_snap(); w = json.loads(await kv_get("watch") or "[]")
    return [x for sym in w for x in d["rows"] if x["symbol"] == sym and x["timeframe"] == "4H"]
@app.post("/api/watchlist")
async def wl_add(body: dict):
    w = json.loads(await kv_get("watch") or "[]"); sym = str(body.get("symbol", "")).upper()
    if sym and sym not in w: w.append(sym); await kv_set("watch", json.dumps(w))
    return {"ok": True}
@app.delete("/api/watchlist/{symbol}")
async def wl_del(symbol: str):
    w = [x for x in json.loads(await kv_get("watch") or "[]") if x != symbol.upper()]; await kv_set("watch", json.dumps(w)); return {"ok": True}
