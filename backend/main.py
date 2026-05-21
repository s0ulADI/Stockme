from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from nsetools import Nse
import pandas as pd
import os
from datetime import datetime, time as dtime, date
from zoneinfo import ZoneInfo
from sklearn.ensemble import RandomForestRegressor
import yfinance as yf
import requests
from functools import lru_cache

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolve the frontend index.html path (one level above backend/)
_FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

@app.get("/")
def serve_frontend():
    """Serve the Stock ME frontend from the root URL."""
    html_path = os.path.join(_FRONTEND_DIR, "index.html")
    if not os.path.exists(html_path):
        raise HTTPException(status_code=404, detail="Frontend index.html not found")
    return FileResponse(html_path, media_type="text/html")

nse = Nse()

MARKET_TZ = ZoneInfo("Asia/Kolkata")

#bot id

BOT_TOKEN = "8295527440:AAFcOQqhcP9Wu1MRMI5k3X9LZGtWUUiThhQ"
CHAT_ID = "1365833531"



alerts = []

#market time

MARKET_START = dtime(9, 15)
MARKET_END = dtime(15, 30)

last_price = {}
session_high = {}
session_low = {}
current_day = date.today()

#bot integration

def send_telegram_alert(symbol, price):
    message = f" {symbol} reached ₹{price}"

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    params = {
        "chat_id": CHAT_ID,
        "text": message
    }

    try:
        requests.get(url, params=params)
        print(" Telegram alert sent!")
    except Exception as e:
        print("Telegram error:", e)

#telgram alertssssssssssssss

class Alert(BaseModel):
    symbol: str
    target_price: float

@app.post("/alert")
def set_alert(alert: Alert):
    alerts.append({
        "symbol": alert.symbol.upper(),
        "target_price": alert.target_price,
        "triggered": False
    })
    return {"message": "Alert set successfully"}

@app.get("/alerts")
def get_alerts():
    return alerts

def check_alerts(symbol, price):
    for alert in alerts:
        if alert["symbol"] == symbol and not alert["triggered"]:
            if price >= alert["target_price"]:
                alert["triggered"] = True
                send_telegram_alert(symbol, price)



def is_market_open():
    now = datetime.now(MARKET_TZ)
    if now.weekday() >= 5:
        return False
    return MARKET_START <= now.time() <= MARKET_END

@app.get("/market-status")
def market_status():
    now = datetime.now(MARKET_TZ)
    return {
        "status": "Market Open" if is_market_open() else "Market Closed",
        "time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": "Asia/Kolkata"
    }

# Cache resolved symbols so we don't hit yfinance on every request
_symbol_cache = {}

def get_yf_symbol(symbol: str) -> str:
    symbol = symbol.upper()

    # Return cached result if available
    if symbol in _symbol_cache:
        return _symbol_cache[symbol]

    if symbol in {"BTC", "ETH", "XRP", "LTC", "DOGE"}:
        result = f"{symbol}-USD"
        _symbol_cache[symbol] = result
        return result

    if symbol in ("^NSEI", "NIFTY"):  return "^NSEI"
    if symbol in ("^BSESN", "SENSEX"): return "^BSESN"
    if symbol == "^GSPC":  return "^GSPC"
    if symbol == "^IXIC":  return "^IXIC"

    # For NSE stocks, try SYMBOL.NS first (most common), then plain symbol
    for candidate in [f"{symbol}.NS", symbol]:
        try:
            ticker = yf.Ticker(candidate)
            # Use fast_info instead of downloading history
            price = ticker.fast_info.get("lastPrice") or ticker.fast_info.get("regularMarketPrice")
            if price:
                _symbol_cache[symbol] = candidate
                return candidate
        except Exception:
            continue

    _symbol_cache[symbol] = symbol
    return symbol

HISTORY_RANGES = {
    "1H": ("1d", "5m"),
    "1D": ("1d", "5m"),
    "1W": ("7d", "1h"),
    "1M": ("1mo", "1d"),
    "6M": ("6mo", "1wk"),
    "1Y": ("1y", "1wk"),
    "3Y": ("3y", "1mo"),
    "5Y": ("5y", "1mo"),
}

def history_range_to_yfinance(range_key: str):
    return HISTORY_RANGES.get(range_key.upper(), ("1mo", "1d"))


def get_yf_info(symbol: str):
    yf_symbol = get_yf_symbol(symbol)
    try:
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info if hasattr(ticker, "info") else {}
        news_items = []
        try:
            for item in getattr(ticker, "news", [])[:3]:
                news_items.append({
                    "title": item.get("title"),
                    "publisher": item.get("publisher") or item.get("source"),
                    "link": item.get("link")
                })
        except Exception:
            news_items = []
        return {
            "summary": info.get("longBusinessSummary") or info.get("shortBusinessSummary"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "recommendation_key": info.get("recommendationKey"),
            "average_analyst_rating": info.get("averageAnalystRating"),
            "logo_url": info.get("logo_url"),
            "news": news_items
        }
    except Exception:
        return {
            "summary": None,
            "sector": None,
            "industry": None,
            "recommendation_key": None,
            "average_analyst_rating": None,
            "logo_url": None,
            "news": []
        }


def fetch_stock(symbol):
    symbol = symbol.upper()
    yf_info = get_yf_info(symbol)
    try:
        quote = nse.get_quote(symbol)
        price = float(quote.get("lastPrice") or quote.get("close") or 0)
        change = float(quote.get("change") or 0)
        p_change = float(quote.get("pChange") or 0)
        name = quote.get("companyName") or symbol
        exchange = "NSE"
        previous_close = float(quote.get("previousClose") or quote.get("open") or 0)
        fifty_two_week_range = f"{quote.get('low52')} - {quote.get('high52')}" if quote.get('low52') and quote.get('high52') else None
        stock = {
            "price": price,
            "change": change,
            "change_percent": p_change,
            "name": name,
            "exchange": exchange,
            "previous_close": previous_close,
            "open": float(quote.get("open") or 0),
            "fifty_two_week_range": fifty_two_week_range,
            "market_cap": quote.get("marketCap") or None,
            "volume": quote.get("totalTradedVolume") or None,
            "currency": "INR",
            "pe_ratio": None,
            "sector": yf_info.get("sector"),
            "industry": yf_info.get("industry"),
            "summary": yf_info.get("summary"),
            "recommendation_key": yf_info.get("recommendation_key"),
            "average_analyst_rating": yf_info.get("average_analyst_rating"),
            "logo_url": yf_info.get("logo_url"),
            "news": yf_info.get("news")
        }
        return stock
    except Exception:
        try:
            yf_symbol = get_yf_symbol(symbol)
            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(period="2d", interval="1d")
            if hist.empty or len(hist) < 2:
                raise Exception("No data returned from yfinance")

            last = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2])
            change = last - prev
            p_change = 100 * change / prev if prev else 0
            info = ticker.info if hasattr(ticker, "info") else {}
            name = info.get("longName") or info.get("shortName") or symbol
            exchange = info.get("exchange") or "YFinance"
            market_cap = info.get("marketCap")
            volume = info.get("volume")
            pe_ratio = info.get("trailingPE") or info.get("forwardPE")
            low_52 = info.get("fiftyTwoWeekLow")
            high_52 = info.get("fiftyTwoWeekHigh")
            fifty_two_week_range = f"{low_52} - {high_52}" if low_52 and high_52 else None
            return {
                "price": last,
                "change": change,
                "change_percent": p_change,
                "name": name,
                "exchange": exchange,
                "previous_close": float(info.get("previousClose") or prev),
                "open": float(info.get("open") or 0),
                "fifty_two_week_range": fifty_two_week_range,
                "market_cap": market_cap,
                "volume": volume,
                "currency": info.get("currency") or "USD",
                "pe_ratio": pe_ratio,
                "sector": yf_info.get("sector"),
                "industry": yf_info.get("industry"),
                "summary": yf_info.get("summary"),
                "recommendation_key": yf_info.get("recommendation_key"),
                "average_analyst_rating": yf_info.get("average_analyst_rating"),
                "logo_url": yf_info.get("logo_url"),
                "news": yf_info.get("news")
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Stock fetch error: {exc}")

def save_to_csv(symbol, data):
    file = f"{symbol}_live.csv"
    df = pd.DataFrame([data])

    if os.path.exists(file):
        df.to_csv(file, mode="a", header=False, index=False)
    else:
        df.to_csv(file, mode="w", header=True, index=False)

#apiiiiiiiiiii

@app.get("/stock")
def get_stock(symbol: str, force: bool = False):

    symbol = symbol.upper()

    if not is_market_open() and not force:
        return {"status": "Market Closed"}

    stock = fetch_stock(symbol)

    now = datetime.now(MARKET_TZ).strftime("%H:%M:%S")

    data = {
        "time": now,
        "symbol": symbol,
        "price": stock["price"],
        "company": stock.get("name", symbol),
        "exchange": stock.get("exchange", "N/A"),
        "change": stock.get("change", 0),
        "change_percent": stock.get("change_percent", 0),
        "previous_close": stock.get("previous_close"),
        "open": stock.get("open"),
        "fifty_two_week_range": stock.get("fifty_two_week_range"),
        "market_cap": stock.get("market_cap"),
        "volume": stock.get("volume"),
        "pe_ratio": stock.get("pe_ratio"),
        "currency": stock.get("currency", "INR"),
        "sector": stock.get("sector"),
        "industry": stock.get("industry"),
        "summary": stock.get("summary"),
        "recommendation_key": stock.get("recommendation_key"),
        "average_analyst_rating": stock.get("average_analyst_rating"),
        "news": stock.get("news", [])
    }

    save_to_csv(symbol, {"time": now, "symbol": symbol, "price": stock["price"]})

    check_alerts(symbol, stock["price"])

    return {"status": "Live", "data": data}

#past data of stocks

def fetch_historical_data(symbol, range_key="1D"):
    yf_symbol = get_yf_symbol(symbol)
    period, interval = history_range_to_yfinance(range_key)
    data = yf.download(yf_symbol, period=period, interval=interval, progress=False)

    if data.empty:
        return False

    df = data.reset_index()

    # yfinance uses 'Datetime' for intraday intervals, 'Date' for daily/weekly/monthly
    time_col = "Datetime" if "Datetime" in df.columns else "Date"
    df = df[[time_col, "Close"]].copy()
    df.rename(columns={time_col: "time", "Close": "price"}, inplace=True)

    # Flatten MultiIndex columns if present (yfinance sometimes returns them)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] if col[1] == '' else col[0] for col in df.columns]

    df["time"] = df["time"].astype(str)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df.dropna(inplace=True)

    df.to_csv(f"{symbol}_{range_key}_live.csv", index=False)
    return True

@app.get("/history")
def get_history(symbol: str, range: str = "1D"):

    symbol = symbol.upper()
    file = f"{symbol}_{range}_live.csv"

    if not os.path.exists(file):
        fetch_historical_data(symbol, range)

    df = pd.read_csv(file)

    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df.dropna(inplace=True)

    if len(df) < 20:
        print("[WARN] Not enough history, fetching data...")
        fetch_historical_data(symbol, range)
        df = pd.read_csv(file)

        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df.dropna(inplace=True)

    if "time" in df.columns:
        df["time"] = df["time"].astype(str)

    return {
        "symbol": symbol,
        "range": range,
        "count": len(df),
        "history": df.tail(100).to_dict(orient="records")
    }

#prediction systummm

def prepare_data(symbol):
    live_file = f"{symbol}_live.csv"
    hist_file = f"{symbol}_1D_live.csv"

    # Try live file first; fall back to 1D historical CSV
    file = live_file if os.path.exists(live_file) else hist_file

    if not os.path.exists(file):
        # Neither file exists — download 1D history
        fetch_historical_data(symbol, "1D")
        file = hist_file

    df = pd.read_csv(file)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df.dropna(inplace=True)

    if len(df) < 20:
        print("[WARN] Not enough data in live file, fetching 1D historical...")
        fetch_historical_data(symbol, "1D")
        df = pd.read_csv(hist_file)
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df.dropna(inplace=True)

    if len(df) < 10:
        return None, None, None

    # Features
    df["lag1"] = df["price"].shift(1)
    df["lag2"] = df["price"].shift(2)
    df["ma3"] = df["price"].rolling(3).mean()
    df["ma5"] = df["price"].rolling(5).mean()

    df.dropna(inplace=True)

    X = df[["lag1", "lag2", "ma3", "ma5"]]
    y = df["price"]

    return X, y, df

@app.get("/predict")
def predict(symbol: str):

    X, y, df = prepare_data(symbol.upper())

    if X is None:
        return {"error": "Not enough data"}

    model = RandomForestRegressor(random_state=42)
    model.fit(X, y)

    last = df.iloc[-1]

    pred = model.predict([[last["lag1"], last["lag2"], last["ma3"], last["ma5"]]])

    return {
        "symbol": symbol,
        "predicted_price": round(float(pred[0]), 2)
    }

#Auto alerts
import asyncio
@app.on_event("startup")
async def start_background_task():
    asyncio.create_task(auto_check_alerts())
async def auto_check_alerts():
    while True:
        print("[CHECK] Checking alerts...")

        for alert in list(alerts):  # iterate a copy to avoid mutation issues
            if not alert["triggered"]:
                symbol = alert["symbol"]
                try:
                    # fetch_stock returns a dict; extract numeric price
                    stock_data = fetch_stock(symbol)
                    price = float(stock_data["price"])

                    if price >= alert["target_price"]:
                        alert["triggered"] = True
                        print(f"[ALERT] AUTO ALERT: {symbol} reached {price}")
                        send_telegram_alert(symbol, price)

                except Exception as e:
                    print(f"Error checking alert for {symbol}:", e)

        await asyncio.sleep(10)
        