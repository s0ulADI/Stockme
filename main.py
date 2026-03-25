from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from nsetools import Nse
import pandas as pd
import os
from datetime import datetime, time as dtime, date
from sklearn.ensemble import RandomForestRegressor
import yfinance as yf
import requests

app = FastAPI()
nse = Nse()

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
    now = datetime.now().time()
    return MARKET_START <= now <= MARKET_END

def fetch_stock(symbol):
    try:
        quote = nse.get_quote(symbol)
        return quote["lastPrice"]
    except:
        raise HTTPException(status_code=500, detail="Stock fetch error")

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

    price = fetch_stock(symbol)

    now = datetime.now().strftime("%H:%M:%S")

    data = {
        "time": now,
        "symbol": symbol,
        "price": price
    }

    save_to_csv(symbol, data)


    check_alerts(symbol, price)

    return {"status": "Live", "data": data}

#past data of stocks

def fetch_historical_data(symbol):
    data = yf.download(symbol + ".NS", period="7d", interval="5m")

    if data.empty:
        return False

    df = data.reset_index()
    df = df[["Datetime", "Close"]]
    df.rename(columns={"Datetime": "time", "Close": "price"}, inplace=True)

    df.to_csv(f"{symbol}_live.csv", index=False)
    return True

@app.get("/history")
def get_history(symbol: str):

    symbol = symbol.upper()
    file = f"{symbol}_live.csv"

    
    if not os.path.exists(file):
        fetch_historical_data(symbol)

    df = pd.read_csv(file)

   
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df.dropna(inplace=True)

    
    if len(df) < 20:
        print("⚠️ Not enough history, fetching data...")
        fetch_historical_data(symbol)
        df = pd.read_csv(file)

        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df.dropna(inplace=True)

    
    if "time" in df.columns:
        df["time"] = df["time"].astype(str)

    return {
        "symbol": symbol,
        "count": len(df),
        "history": df.tail(100).to_dict(orient="records")
    }

#prediction systummm

def prepare_data(symbol):
    file = f"{symbol}_live.csv"

    
    if not os.path.exists(file):
        fetch_historical_data(symbol)

    df = pd.read_csv(file)

    
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df.dropna(inplace=True)

   
    if len(df) < 20:
        print("⚠️ Not enough data, fetching historical...")
        fetch_historical_data(symbol)
        df = pd.read_csv(file)

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

    model = RandomForestRegressor()
    model.fit(X, y)

    last = df.iloc[-1]

    pred = model.predict([[last["price"], last["lag1"], last["ma3"], last["ma5"]]])

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
        print("🔄 Checking alerts...")

        for alert in alerts:
            if not alert["triggered"]:

                symbol = alert["symbol"]

                try:
                    price = fetch_stock(symbol)

                    if price >= alert["target_price"]:
                        alert["triggered"] = True

                        print(f" AUTO ALERT: {symbol} reached {price}")

                        send_telegram_alert(symbol, price)

                except Exception as e:
                    print("Error checking:", e)

        await asyncio.sleep(10)
        