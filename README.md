# Stockme
# 📈 AI Stock Dashboard

🚀 **AI-powered real-time stock analysis system** with live price tracking, ML-based predictions, automated Telegram alerts, and dynamic chart visualization.

---

## 🔥 Features

* 📊 Real-time stock price tracking (NSE)
* 🤖 Machine Learning prediction (Random Forest)
* 📈 Live updating chart (5-min interval data)
* 🔔 Telegram alert system (instant notifications)
* ⚡ Background auto-check (no manual trigger)
* 📂 Automatic historical data fetching (yfinance)
* 🧠 Feature engineering (lag, moving averages)

---

## 🧱 Tech Stack

* **Backend:** FastAPI
* **ML Model:** Scikit-learn (Random Forest)
* **Data Source:** NSE + yfinance
* **Frontend:** (Add your tech — React / HTML / JS)
* **Alerts:** Telegram Bot API

---

## ⚙️ How It Works

1. User enters stock symbol
2. Backend fetches real-time + historical data
3. ML model predicts next price
4. Graph displays live updates
5. Alerts trigger automatically via Telegram

---

## 📊 APIs

| Endpoint   | Description                      |
| ---------- | -------------------------------- |
| `/stock`   | Get live stock price             |
| `/history` | Get historical data (for charts) |
| `/predict` | Predict next price               |
| `/alert`   | Set alert                        |
| `/alerts`  | View alerts                      |

---

## 🚀 Installation & Setup

### 1️⃣ Clone repo

```bash
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
```

---

### 2️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

---

### 3️⃣ Run server

```bash
python -m uvicorn main:app --reload
```

---

### 4️⃣ Open in browser

```
http://127.0.0.1:8000/docs
```

---

## 🔔 Telegram Setup

1. Create bot using BotFather
2. Get BOT_TOKEN
3. Get CHAT_ID using `/getUpdates`
4. Add in code:

```python
BOT_TOKEN = "your_token"
CHAT_ID = "your_chat_id"
```

---

## 📸 Screenshots (Add Later)

* Dashboard UI
 
* Live chart
  
* Telegram alert


---

## 🎯 Future Improvements

* 📊 Advanced ML models (LSTM)
* 👥 Multi-user support
* 🌐 Deployment (Render / AWS)
* 📉 Accuracy metrics (RMSE)
* 📲 Mobile-friendly UI

---


## ⭐ If you like this project

Give it a ⭐ on GitHub!

