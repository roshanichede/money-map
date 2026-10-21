# MoneyMap

**See where your money went, without linking your bank.** Upload the CSV exports or PDF statements you already have; MoneyMap sorts every payment, finds your regular bills and answers questions about your spending in plain English.

Built because Lloyds doesn't email transaction alerts, has no personal API, and caps its CSV export at 150 rows, and because UK budgeting apps that need bank linking keep shutting down (Yolt 2021, Money Dashboard 2023, Moneyhub's consumer app 2026).

## What v1 does

| | |
|---|---|
| **Statement import** | Lloyds / Halifax / Bank of Scotland CSV natively; most other UK bank CSVs by header detection; text-based PDF statements by column position. |
| **Duplicate-safe** | Upload overlapping exports, or a PDF and a CSV of the same month: each payment is counted once. |
| **Reconciled to the penny** | Every file is checked: opening balance + transactions = closing balance. A missing row is flagged. |
| **Categories that learn** | 200+ UK merchant keywords and 70+ brand names. Fix one Pret payment and every Pret payment follows, now and in future uploads. |
| **Regular payments** | Detects weekly / monthly / quarterly / yearly charges with stable amounts, and when the next one is due. |
| **Plain-English headline** | Each month opens with a sentence: what you spent, how it compares, and what drove the change. |
| **Ask your money** | Chat answers are calculated from your transactions first. With an API key, Claude words them, and any £ figure or % it writes that isn't in the calculated facts gets the reply thrown out. |
| **Your data stays yours** | Stored locally in SQLite. One click exports everything as CSV or deletes it all. |

## Run it

Needs Python 3.10+ and Node 20+ (on a Mac: `brew install python@3.12 node`).

```bash
./start.sh            # first run installs everything; then open http://localhost:3000
```

Click **Try it with sample data** to explore with synthetic statements, or drop in your own Lloyds exports (online banking on a computer → the account → *Statement options* → *Export transactions*).

To have Claude word the chat answers: `cp backend/.env.example backend/.env` and add your `ANTHROPIC_API_KEY`.

Run the pieces separately:

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
cd frontend && npm install && npm run dev
```

Tests: `cd backend && .venv/bin/pytest`. These are 23 tests covering the parsers, duplicate removal, reconciliation, categorisation rate, recurring detection, recategorisation and the chat guardrail.

## How it fits together

```
frontend/  Next.js 16 (App Router). One page; /api/* is proxied to the backend.
backend/   FastAPI + SQLAlchemy (SQLite by default; set DATABASE_URL for Postgres)
  app/parsers/     CSV (Lloyds + generic) and PDF statement parsers
  app/importer.py  reconcile → dedupe → categorise → store
  app/merchants.py raw description → merchant ("PAYPAL *NETFLIX.COM 402…" → Netflix)
  app/categories.py UK merchant rules + Lloyds transaction-type codes
  app/recurring.py regular-payment detection
  app/insights.py  every number shown anywhere (the model never calculates)
  app/chat.py      question → facts → answer → figure check
  sample_data/     generator for synthetic Lloyds CSVs and a PDF statement
```

**Key decision: numbers come from SQL, words from the model.** The model only explains figures that were already calculated, and its reply is checked before it's shown. A wrong total is worse than no answer.

## Not in v1 (on purpose)

Open-banking sync, budgets and alerts, mobile app, shared households, investments, financial advice. See the case study for why and what's next.
