# MoneyMap

**See where your money went, without linking your bank.** Upload the CSV exports or PDF statements you already have, from one account or several. MoneyMap sorts every payment, keeps transfers between your own accounts out of your spending, finds your regular bills and answers questions in plain English.

Built because Lloyds doesn't email transaction alerts, has no personal API, and caps its CSV export at 150 rows, and because UK budgeting apps that need bank linking keep shutting down (Yolt 2021, Money Dashboard 2023, Moneyhub's consumer app 2026).

## What it does

| | |
|---|---|
| **Statement import** | CSV, Excel (.xlsx/.xls, including the HTML "xls" some banks send) and text-based PDF. UK banks (Lloyds/Halifax/BoS natively, others by header detection) and Indian banks (HDFC, ICICI, SBI, Axis, Kotak layouts, with account details above the table). |
| **UK and India, kept apart** | Each account has a currency (detected from the file, editable). Totals, transfers and salary detection never mix £ and ₹; ₹ shows Indian grouping (₹1,23,456). UPI / NEFT / IMPS / ATM / POS lines are rewritten as payee + note ("UPI/DR/4123…/PREETI M/SBIN/…/rent" → "UPI PREETI M RENT"), and Swiggy, Zomato, Blinkit, Ola, Jio and 100+ Indian merchants are known. |
| **Several accounts** | Each file is matched to an account by its account number, by overlap with payments already imported, or by your choice. Current accounts, savings and credit cards. |
| **Transfers don't count twice** | Money moved between your own accounts (savings top-ups, card repayments) is matched and left out of spending and income. Card purchases count as spending, not the repayment. |
| **Duplicate-safe** | Upload overlapping exports, or a PDF and a CSV of the same month: each payment is counted once. |
| **Reconciled to the penny** | Every file is checked: opening balance + transactions = closing balance. A missing row is flagged. |
| **Learns your patterns** | 200+ UK merchant keywords and 70+ brands sort most payments. The rest is personal, so MoneyMap learns rules from you: by person ("Preeti Misal"), by a word in the note ("GARBA"), and/or up to an amount ("up to £50"). Teach it by changing a category (it asks how widely to apply it), by answering its questions about unsure payments (biggest amounts first), or in the chat: "garba is entertainment". Every rule is previewed before saving, listed, and can be forgotten. It works out where a person's name ends and the note begins from your own statements. |
| **Earnings, read honestly** | Salary is pay that arrives by payroll (BGC) or from the same company most months, even when shift pay varies. Money from people is never earnings: a flatmate's RENT share or a friend's CAB share is taken off that spending, and money with no note stays out of both. Self-transfers and card refunds are recognised too. |
| **What stands out** | Each month gets a few plain sentences: the biggest cost, what went up and why, what isn't sorted yet, when your pay arrived. |
| **Regular payments** | Weekly / monthly / quarterly / yearly charges with stable amounts, and when the next one is due. |
| **Plain-English summary** | Each month opens with a sentence: what you spent, how it compares, and what drove it. |
| **Ask your money** | Chat answers are calculated from your transactions first. With an API key, Claude words them, and any £ figure or % it writes that isn't in the calculated facts gets the reply thrown out. |
| **Accounts** | Create an account with email and password (stored only as a salted scrypt hash, with repeated wrong guesses slowed down), or add "Continue with Google". Each person sees only their own data. |

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

### Add Google sign-in (optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → create a project → **APIs & Services → OAuth consent screen**: choose *External*, fill in the app name and your email, and add yourself as a test user.
2. **APIs & Services → Credentials → Create credentials → OAuth client ID**, type *Web application*.
   Authorised redirect URI: `http://localhost:3000/api/auth/callback/google`
3. Paste the client ID and secret into `.env` as `AUTH_GOOGLE_ID` and `AUTH_GOOGLE_SECRET`, then run `./start.sh`. It generates `AUTH_SECRET` and `INTERNAL_API_SECRET` for you.

The first account created keeps anything imported before sign-in existed. Everyone after starts empty.

**How sign-in protects the data:** the browser only talks to Next.js. Next.js signs you in (Auth.js: email + password checked by the backend, or Google) and forwards each API call to FastAPI with your email plus a shared secret. FastAPI rejects any request without that secret, so identity can't be forged from the browser.

### Claude-worded chat answers

Add `ANTHROPIC_API_KEY` to `.env`.

### Tests

`cd backend && .venv/bin/pytest`: 90 tests covering parsers (UK and Indian formats), currencies, learned rules and teaching by chat, money-in classification (salary, paid back, refunds, self-transfers), duplicates, reconciliation, accounts, transfer matching, credit cards, number masking, user isolation, the v1 database upgrade, categorisation, recurring payments and the chat guardrail.

## Deploy (free): Vercel + Render + Neon

The public demo runs on three free services. Real statements are best kept on your own computer.

| Part | Service | Settings |
|---|---|---|
| Database | [Neon](https://neon.tech) Postgres | Create a project (region: Frankfurt). Copy the connection string. |
| API | [Render](https://render.com) web service | New → Blueprint → this repo (uses `render.yaml`). Paste the Neon string as `DATABASE_URL`; Render generates `INTERNAL_API_SECRET`. |
| Website | [Vercel](https://vercel.com) | Import this repo, Root Directory `frontend`. Environment: `API_URL` (the Render URL), `INTERNAL_API_SECRET` (copied from Render), `DEMO_SITE=1`. The sign-in key is derived from that secret unless `AUTH_SECRET` is set. |

Notes: Render's free API sleeps after 15 minutes without visits, so the first request can take up to a minute. Uploads through Vercel are limited to about 4.5 MB per request. Tables are created on first start; `TEST_DATABASE_URL=postgresql+psycopg://... pytest` runs the test suite against Postgres.

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
  app/learning.py   rules you teach: payee / note word / amount, questions, scope choices
  app/teach.py      turns chat messages like "garba is entertainment" into rule proposals
  app/income.py     salary detection, and re-sorting existing data when the rules improve
  app/insights.py   every number shown anywhere, earnings and highlights (the model never calculates)
  app/chat.py       question → facts → answer → figure check
  app/migrate.py    upgrades a v1 database in place (backup first)
  sample_data/      generator for three synthetic Lloyds accounts
```

**Key decision: numbers come from SQL, words from the model.** The model only explains figures that were already calculated, and its reply is checked before it's shown. A wrong total is worse than no answer.

## Not yet

Open-banking sync, budgets and alerts, a mobile app, shared households, investments, financial advice, hosting (the code is ready for it: Postgres via `DATABASE_URL`, login via Google).
