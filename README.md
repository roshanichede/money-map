# MoneyMap

**See where your money went, without linking your bank.** Upload the CSV exports or PDF statements you already have, from one account or several. MoneyMap sorts every payment, keeps transfers between your own accounts out of your spending, finds your regular bills and answers questions in plain English.

Built because Lloyds doesn't email transaction alerts, has no personal API, and caps its CSV export at 150 rows, and because UK budgeting apps that need bank linking keep shutting down (Yolt 2021, Money Dashboard 2023, Moneyhub's consumer app 2026).

## What it does

| | |
|---|---|
| **Statement import** | Lloyds / Halifax / Bank of Scotland CSV natively; most other UK bank and card CSVs by header detection; text-based PDF statements by column position. |
| **Several accounts** | Each file is matched to an account by its account number, by overlap with payments already imported, or by your choice. Current accounts, savings and credit cards. |
| **Transfers don't count twice** | Money moved between your own accounts (savings top-ups, card repayments) is matched and left out of spending and income. Card purchases count as spending, not the repayment. |
| **Duplicate-safe** | Upload overlapping exports, or a PDF and a CSV of the same month: each payment is counted once. |
| **Reconciled to the penny** | Every file is checked: opening balance + transactions = closing balance. A missing row is flagged. |
| **Categories that learn** | 200+ UK merchant keywords and 70+ brand names. Fix one Pret payment and every Pret payment follows, now and in future uploads. |
| **Regular payments** | Weekly / monthly / quarterly / yearly charges with stable amounts, and when the next one is due. |
| **Plain-English summary** | Each month opens with a sentence: what you spent, how it compares, and what drove it. |
| **Ask your money** | Chat answers are calculated from your transactions first. With an API key, Claude words them, and any £ figure or % it writes that isn't in the calculated facts gets the reply thrown out. |
| **Google login** | Optional. Each person sees only their own data. Without it, the app runs in local mode for one person. |

## How data is stored

- **Statement files are never kept.** A PDF or CSV is read in memory, its transactions are extracted, and the file is discarded. Only its name and the import result are saved.
- **Account and card numbers are never stored in full**, not even inside descriptions: only the last four digits, plus a salted one-way hash to recognise the same account later.
- Transactions live in `backend/moneymap.db` (SQLite) by default, or Postgres via `DATABASE_URL`. Every row belongs to a user.
- The chat sends Claude only the calculated facts for that answer (totals, merchant names, dates), and only if `ANTHROPIC_API_KEY` is set.
- "Your data" in the app exports everything as CSV or deletes it all.

## Run it

Needs Python 3.10+ and Node 20+ (on a Mac: `brew install python@3.12 node`).

```bash
./start.sh            # installs what's needed, then open http://localhost:3000
```

Click **Try it with sample data** to explore with three synthetic accounts (current, savings, credit card), or add your own Lloyds exports (online banking on a computer → the account → *Statement options* → *Export transactions*).

Settings live in `.env` at the project root: `cp .env.example .env`.

### Turn on Google login

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → create a project → **APIs & Services → OAuth consent screen**: choose *External*, fill in the app name and your email, and add yourself as a test user.
2. **APIs & Services → Credentials → Create credentials → OAuth client ID**, type *Web application*.
   Authorised redirect URI: `http://localhost:3000/api/auth/callback/google`
3. Paste the client ID and secret into `.env` as `AUTH_GOOGLE_ID` and `AUTH_GOOGLE_SECRET`, then run `./start.sh`. It generates `AUTH_SECRET` and `INTERNAL_API_SECRET` for you.

The first person to sign in keeps anything already imported in local mode. Everyone after starts empty.

**How login protects the data:** the browser only talks to Next.js. Next.js signs you in with Google (Auth.js) and forwards each API call to FastAPI with your email plus a shared secret. FastAPI rejects any request without that secret, so identity can't be forged from the browser.

### Claude-worded chat answers

Add `ANTHROPIC_API_KEY` to `.env`.

### Tests

`cd backend && .venv/bin/pytest`: 42 tests covering parsers, duplicates, reconciliation, accounts, transfer matching, credit cards, number masking, user isolation, the v1 database upgrade, categorisation, recurring payments and the chat guardrail.

## How it fits together

```
frontend/  Next.js 16 + Auth.js. app/api/[...path] forwards calls to the backend with the signed-in user.
backend/   FastAPI + SQLAlchemy (SQLite by default; DATABASE_URL for Postgres)
  app/auth.py       who is asking: local mode, or signed-in user + shared secret
  app/parsers/      CSV (Lloyds + generic) and PDF statement parsers
  app/accounts.py   which account a file belongs to
  app/importer.py   mask numbers → pick account → reconcile → dedupe → categorise → store → match transfers
  app/transfers.py  pairs money moving between your own accounts
  app/merchants.py  raw description → merchant ("PAYPAL *NETFLIX.COM 402…" → Netflix)
  app/categories.py UK merchant rules + Lloyds transaction-type codes
  app/recurring.py  regular-payment detection
  app/insights.py   every number shown anywhere (the model never calculates)
  app/chat.py       question → facts → answer → figure check
  app/migrate.py    upgrades a v1 database in place (backup first)
  sample_data/      generator for three synthetic Lloyds accounts
```

**Key decision: numbers come from SQL, words from the model.** The model only explains figures that were already calculated, and its reply is checked before it's shown. A wrong total is worse than no answer.

## Not yet

Open-banking sync, budgets and alerts, a mobile app, shared households, investments, financial advice, hosting (the code is ready for it: Postgres via `DATABASE_URL`, login via Google).
