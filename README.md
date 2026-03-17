# 🎬 Telegram Sticker-to-GIF Converter Bot

A Telegram bot that converts stickers to GIF, MP4, WebM, and PNG — with custom watermarks, font & color pickers, admin panel, and payment support.

## ✨ Features

- 🎬 Convert stickers → **GIF / MP4 / WebM / PNG**
- 💧 Custom **watermark** with font, color & position
- 🔤 Google Fonts picker (Telegram Mini App)
- 🎨 Color picker (Telegram Mini App)
- 💰 Balance system with CryptoBot payment integration
- 📊 Admin panel with user stats & broadcast
- 🚀 Ready to deploy on **Railway**

## 🛠 Tech Stack

- **Python 3.11+** with **aiogram 3.6**
- **SQLite** (dev) / **PostgreSQL** (prod via Railway)
- **Pillow** for image processing, **ffmpeg** for video
- **SQLAlchemy** async ORM

---

## 🚀 Deploy to Railway

### 1. Clone & configure

```bash
git clone <your-repo>
cd converter_bot
cp .env.example .env
# Edit .env with your BOT_TOKEN and ADMIN_ID
```

### 2. Deploy

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app)

1. Push this folder to a GitHub repo
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
3. Select your repo
4. Go to **Variables** tab and add:
   - `BOT_TOKEN` — from [@BotFather](https://t.me/BotFather)
   - `ADMIN_ID` — your Telegram user ID (from [@userinfobot](https://t.me/userinfobot))
   - *(optional)* `CRYPTOBOT_TOKEN` — from [@CryptoBot](https://t.me/CryptoBot)
   - *(optional)* `WEBAPP_URL` — your Railway public URL (for mini-apps)
5. Railway auto-deploys. Check **Logs** to confirm the bot is running.

### 3. PostgreSQL (recommended for production)

In Railway: **New** → **Database** → **PostgreSQL** → copy `DATABASE_URL` and set:
```
DATABASE_URL=postgresql+asyncpg://...
```
Also add `asyncpg` to `requirements.txt`.

---

## 💻 Local Development

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Fill in BOT_TOKEN and ADMIN_ID

python -m bot.main
```

> **Note**: ffmpeg must be installed locally for MP4/WebM conversion.
> - macOS: `brew install ffmpeg`
> - Ubuntu: `apt install ffmpeg`
> - Windows: [ffmpeg.org](https://ffmpeg.org/download.html)

---

## 📁 Project Structure

```
converter_bot/
├── bot/
│   ├── main.py          # Entry point & dispatcher setup
│   └── config.py        # Pydantic settings from .env
├── handlers/
│   ├── start.py         # /start, /help, /balance
│   ├── converter.py     # Sticker receiving & conversion flow
│   ├── watermark.py     # Watermark settings & Mini App data
│   ├── payment.py       # Balance display & top-up
│   └── admin.py         # Admin panel, stats, broadcast
├── keyboards/
│   ├── inline.py        # Inline keyboards
│   └── reply.py         # Reply keyboard (main menu)
├── services/
│   ├── converter.py     # Image/video conversion logic (Pillow + ffmpeg)
│   ├── database.py      # SQLAlchemy async ORM & helpers
│   └── payment.py       # CryptoBot API client
├── static/
│   ├── fonts.html       # Font picker Mini App
│   └── color.html       # Color picker Mini App
├── .env.example         # Environment variable template
├── railway.toml         # Railway deployment config
├── Procfile             # Process definition
└── requirements.txt     # Python dependencies
```

---

## ⚙️ Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome screen & main menu |
| `/help` | Usage instructions |
| `/balance` | Check your balance |
| `/pay` | Top up balance |
| `/settings` | Watermark settings |
| `/admin` | Admin panel (admin only) |

---

## 💰 Monetization

- **Pay-per-use**: configurable `PAYMENT_RATE` (default 10₽/conversion)
- **CryptoBot**: crypto payment integration via USDT
- **Admin grants**: manually add balance via admin panel

---

## ⚠️ Legal

- Only convert stickers you have rights to use
- Add terms of service to your bot description
