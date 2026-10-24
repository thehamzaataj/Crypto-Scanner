# Document (Roman Urdu)

## Ye kaam kaise karta hai
1. Backend CoinGecko se top coins (default 150, `TOP_N` se 250 tak) leta hai.
2. Har coin ke liye pehle Binance, phir OKX, Bybit, KuCoin check hota hai. Jis exchange par SYMBOL/USDT mile, us ka data use hota hai. Is liye wo coin bhi aate hain jo Binance par nahi hain. TradingView link bhi usi exchange ka banta hai.
3. 6 timeframes ka data: 15m, 1h, 4h, 12h, 1d, 1w. Sirf CLOSED candles par signal banta hai (repaint nahi hota).
4. Har 5 minute (`SCAN_SECONDS`) baad full scan. Har 15 second (`LIVE_SECONDS`) baad live price + live RSI update, aur browser ko SSE (`/api/stream`) se turant push hota hai. Reload ki zaroorat nahi.

## Signal kyun diya jata hai (Trend Following)
- 1D trend: price > EMA200, EMA50 > EMA200, EMA200 upar ja rahi ho. 4H entry ke liye 4H par bhi yehi.
- ADX >= 20: trend maujood hai, market sideways nahi.
- Pullback: price EMA50 ke 1 ATR ke andar wapas aaya ho.
- RSI 40-55 me ho aur upar mud raha ho.
- Bullish candle band hui ho aur volume 20-candle average se 1.2x zyada ho.
- Stop Loss = (entry - 1.5 ATR) aur 10-candle swing low me se jo neeche ho. TP1/TP2/TP3 = 1.5R/2.5R/4R. R:R 1.5 se kam ho to signal chhupa diya jata hai.
- Har signal ke saath `reason` field hoti hai jo batati hai kaun si shart poori hui. No-signal coin ke liye batata hai kya kam hai.
- Score 0-100: Trend 30, Pullback 20, RSI 15, Volume 15, ADX 10, BTC regime 10. Strong Buy 85+, Buy 70-84, Watch 55-69.

## Accuracy kaise napi jati hai
Har scan ka signal SQLite (`scanner.db`) me save hota hai. Agle scans me us signal ki aane wali candles dekhi jati hain:
- TP1 pehle hit hua => **TP hit** (win). Stop Loss pehle hit hua => **Stopped** (loss). Dono ek hi candle me hon to loss gina jata hai (conservative).
- 12 candles (`EXPIRE_CANDLES`) tak kuch na hua => **Expired**.
- Win rate = TP hit / (TP hit + Stopped). Direction accuracy = kitne signals ke baad price entry se upar tha. Grade, timeframe aur exchange ke hisab se alag alag.
Ye sirf live-tracked data hai (backtest nahi). Jab tak 30 se kam signals resolve na hon, percent par bharosa na karein.

## RSI Heatmap
Tab "RSI Heatmap": timeframe chunein, RSI range (jaise 50-100) lagayein. RSI live (forming candle ke saath) nikalti hai. Rang: 30 se neeche green (oversold), 70 se upar red (overbought).

## Run
`pip install -r requirements.txt` phir `uvicorn main:app --port 8000`. Scan button: frontend ke "Strategy & Scan" page par ya `POST /api/scan`.

## Zaroori note
Ye tool financial advice nahi hai. Accuracy numbers past results hain, future ki guarantee nahi.
