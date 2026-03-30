# csgo-market-bot

Automated trading bot for [market.csgo.com](https://market.csgo.com).  
Monitors active listings, reprices items to top-1, and notifies you via Telegram when a sale requires confirmation.

tg_bot : @market_csgo_1bot
---

## Features

- **Auto-repricing** — fetches top-1 prices via `search-list-items-by-hash-name-all` and updates listings using `mass-set-price-mhn`
- **Ping loop** — keeps accounts online by calling `ping-new` on a configurable interval (default: 120s)
- **Sale notifications** — polls `items` endpoint for `status=2` (sold, pending transfer) and sends a Telegram message
- **Multi-account** — all active accounts from the database are processed in every cycle
- **Per-item settings** — each item can be toggled on/off or given a minimum price floor via `item_settings` table

---

## Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| HTTP client | httpx (async) |
| Telegram bot | aiogram 3.x |
| Database | PostgreSQL |
| ORM / queries | SQLAlchemy (sync core, raw SQL) |
| Config | pydantic-settings + .env |

---

## Project Structure
```
csgo-market-bot/
├── app/
│   ├── engine.py          # Main loops: price updates, ping, trade notifications
│   ├── market_api.py      # All HTTP requests to market.csgo.com API v2
│   └── rate_limiter.py    # Global asyncio.Semaphore
├── bot/
│   ├── main.py            # Bot startup, asyncio.gather() entry point
│   ├── handlers/          # Telegram command handlers
│   ├── keyboards/         # Inline keyboards
│   └── middlewares/       # DB engine injection via middleware
├── config/
│   └── settings.py        # Pydantic settings, reads from .env
├── db/
│   ├── session.py         # SQLAlchemy engine
│   └── repositories/      # Raw SQL CRUD: accounts, history, item_settings
├── infra/
│   └── logger.py          # Logging setup (console + file)
├── schema.sql             # Database schema (run manually)
├── .env.example
└── requirements.txt
```

---

## Setup

### 1. Clone & install dependencies
```bash
git clone https://github.com/yourname/csgo-market-bot.git
cd csgo-market-bot
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
```

Edit `.env`:
```env
BOT_TOKEN=your_telegram_bot_token
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/csgo_bot
CURRENCY=USD
INTERVAL=60
PING_INTERVAL=120
TRADES_INTERVAL=30
```

### 3. Create database schema
```bash
psql -U user -d csgo_bot -f schema.sql
```

### 4. Run
```bash
python bot/main.py
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | — | Telegram bot token from @BotFather |
| `DATABASE_URL` | — | PostgreSQL connection string |
| `CURRENCY` | `USD` | Trading currency: `USD`, `RUB`, `EUR` |
| `INTERVAL` | `60` | Repricing cycle interval in seconds |
| `PING_INTERVAL` | `120` | Ping-new interval in seconds (max 180) |
| `TRADES_INTERVAL` | `30` | Sale notification polling interval in seconds |

---

## API Rate Limits

market.csgo.com enforces a hard limit of **5 requests/second** — exceeding it results in API key deletion.  
The bot uses `asyncio.Semaphore` in `rate_limiter.py` and `asyncio.sleep(1)` between `set_price` calls to stay within limits.

---

## Database Schema
```sql
accounts        — API keys, Telegram owner, active flag, optional label
price_history   — Record of every successful reprice (old → new price)
item_settings   — Per-item overrides: is_active, min_price floor
```

Full schema: [`schema.sql`](./schema.sql)

---

## Telegram Commands

| Command | Description |
|---|---|
| `/start` | Main menu |
| `/accounts` | List all accounts |
| `/addaccount` | Add a new market.csgo.com API key |
| `/items` | View and configure items for an account |
| `/autosell` | Toggle auto-repricing on/off for an account |
| `/cancel` | Cancel current FSM dialog |
