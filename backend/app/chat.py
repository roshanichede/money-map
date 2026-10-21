"""Ask-your-money chat.

1. Work out what the question is about (months, categories, merchants, intent) with plain rules.
2. Compute the facts with the same deterministic functions the dashboard uses.
3. Write a rule-based answer from those facts (always available, no API key needed).
4. If ANTHROPIC_API_KEY is set, ask Claude to explain the facts in plain English, then check every £ figure
   and % in its reply against the facts. Any figure not in the facts -> discard the reply, use step 3.
"""
import json
import os
import re
from datetime import date

from .categories import CATEGORIES
from .insights import (by_category, by_merchant, compare_months, in_month, is_spend, month_key, months_overview,
                       totals, txn_dict)
from .models import Transaction
from .money import fmt_gbp
from .recurring import detect_recurring

MODEL = os.environ.get("MONEYMAP_MODEL", "claude-haiku-5-5")

MONTHS = {name: i for i, name in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
     "november", "december"], start=1)}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
MONTHS["sept"] = 9

CATEGORY_WORDS: dict[str, list[str]] = {
    "food": ["Groceries", "Eating out", "Takeaways"],
    "groceries": ["Groceries"], "grocery": ["Groceries"], "supermarket": ["Groceries"],
    "eating out": ["Eating out"], "restaurants": ["Eating out"], "coffee": ["Eating out"],
    "takeaway": ["Takeaways"], "takeaways": ["Takeaways"], "delivery": ["Takeaways"],
    "transport": ["Transport"], "travel": ["Travel"], "flights": ["Travel"],
    "bills": ["Bills & utilities"], "utilities": ["Bills & utilities"], "rent": ["Rent & housing"],
    "housing": ["Rent & housing"], "subscriptions": ["Subscriptions"], "shopping": ["Shopping"],
    "entertainment": ["Entertainment"], "gym": ["Health & fitness"], "health": ["Health & fitness"],
    "cash": ["Cash"], "fees": ["Fees & charges"],
}
for cat in CATEGORIES:
    CATEGORY_WORDS.setdefault(cat.lower(), [cat])

MONEY_RE = re.compile(r"£\s?\d[\d,]*(?:\.\d{1,2})?")
PCT_RE = re.compile(r"\d+(?:\.\d+)?\s?%")


# ---------- understanding the question ----------

def _months_in(question: str, data_months: list[str]) -> list[str]:
    q = question.lower()
    found: list[tuple[int, str]] = []
    if not data_months:
        return []
    latest = data_months[-1]
    if "this month" in q:
        found.append((q.index("this month"), latest))
    if "last month" in q or "previous month" in q:
        idx = q.find("last month") if "last month" in q else q.find("previous month")
        found.append((idx, data_months[-2] if len(data_months) > 1 else latest))
    for m in re.finditer(r"\b([a-z]{3,9})\b(?:\s+(\d{4}))?", q):
        word, year = m.group(1), m.group(2)
        if word not in MONTHS:
            continue
        if word == "may" and not (year or re.search(r"\b(in|for|since|during|of|and|vs|to|from)\s+may\b", q)):
            continue  # "may" the verb, not the month
        num = MONTHS[word]
        candidates = [dm for dm in data_months if int(dm[5:]) == num and (not year or dm[:4] == year)]
        if candidates:
            found.append((m.start(), candidates[-1]))
    found.sort()
    out: list[str] = []
    for _, mk in found:
        if mk not in out:
            out.append(mk)
    return out


def _categories_in(question: str) -> list[str]:
    q = question.lower()
    cats: list[str] = []
    for word in sorted(CATEGORY_WORDS, key=len, reverse=True):
        if re.search(r"\b" + re.escape(word) + r"\b", q):
            for c in CATEGORY_WORDS[word]:
                if c not in cats:
                    cats.append(c)
            q = q.replace(word, " ")
    return cats


def _merchants_in(question: str, txns: list[Transaction]) -> list[str]:
    q = f" {question.lower()} "
    names = {t.merchant for t in txns}
    hits = [n for n in names if len(n) >= 3 and re.search(r"(?<![a-z])" + re.escape(n.lower()) + r"(?![a-z])", q)]
    return sorted(hits, key=len, reverse=True)[:3]


def _intent(question: str, months: list[str], cats: list[str], merchants: list[str]) -> str:
    q = question.lower()
    if re.search(r"subscription|recurring|regular payment|direct debit|standing order|renew", q) and not cats[1:]:
        if "subscriptions" in q and re.search(r"how much|spend|spent", q) and months:
            return "spend"
        return "recurring"
    if re.search(r"\bwhy\b|compare|comparison|\bvs\b|versus|differ|change|more expensive|cheaper|"
                 r"higher|lower|went up|go up|increase|decrease", q):
        return "compare"
    if re.search(r"biggest|largest|top|most expensive|where did|where does|where is", q):
        return "top"
    if re.search(r"income|earn|salary|paid in", q):
        return "income"
    if merchants or cats or re.search(r"how much|spend|spent|cost", q):
        return "spend"
    return "overview"


# ---------- facts + rule-based answers ----------

def _label(month: str) -> str:
    return date(int(month[:4]), int(month[5:]), 1).strftime("%B %Y")


def _coverage_note(month: str, overview: dict[str, dict]) -> str:
    o = overview.get(month)
    if not o:
        return ""
    last = date.fromisoformat(o["last_date"])
    y, m = int(month[:4]), int(month[5:])
    import calendar
    if last.day < calendar.monthrange(y, m)[1] - 1:
        return f" (data up to {last:%-d %b} only)"
    return ""


def build_answer(question: str, txns: list[Transaction]) -> dict:
    overview_list = months_overview(txns)
    overview = {o["month"]: o for o in overview_list}
    data_months = [o["month"] for o in overview_list]
    if not txns:
        return {"intent": "empty", "facts": {}, "answer": "Upload a statement first, then ask me anything about it.",
                "evidence": []}
    months = _months_in(question, data_months)
    cats = _categories_in(question)
    merchants = _merchants_in(question, txns)
    intent = _intent(question, months, cats, merchants)
    latest = data_months[-1]
    facts: dict = {"question_scope": {"months": months, "categories": cats, "merchants": merchants,
                                      "data_covers": f"{overview_list[0]['first_date']} to {overview_list[-1]['last_date']}"}}
    evidence: list[Transaction] = []

    if intent == "compare":
        if len(months) >= 2:
            a, b = months[0], months[1]
            this, prev = (a, b) if a > b else (b, a)
        else:
            this = months[0] if months else latest
            idx = data_months.index(this)
            if idx == 0:
                return {"intent": intent, "facts": facts, "evidence": [],
                        "answer": f"I only have data from {_label(this)}, so there's no earlier month to compare with."}
            prev = data_months[idx - 1]
        comp = compare_months(txns, this, prev)
        changes = [c for c in comp["changes"] if not cats or c["category"] in cats]
        diff = comp["this"]["spend_pence"] - comp["prev"]["spend_pence"]
        facts["comparison"] = {
            "this_month": _label(this) + _coverage_note(this, overview), "previous_month": _label(prev),
            "this_spend": fmt_gbp(comp["this"]["spend_pence"]), "previous_spend": fmt_gbp(comp["prev"]["spend_pence"]),
            "difference": fmt_gbp(abs(diff)), "direction": "more" if diff > 0 else "less",
            "biggest_changes": [{
                "category": c["category"], "this": fmt_gbp(c["this_pence"]), "previous": fmt_gbp(c["prev_pence"]),
                "change": fmt_gbp(c["delta_pence"], signed=True),
                "drivers": [{"merchant": d["merchant"], "change": fmt_gbp(d["delta_pence"], signed=True),
                             "this_count": d["this_count"], "previous_count": d["prev_count"]} for d in c["drivers"]],
            } for c in changes[:4]],
        }
        f = facts["comparison"]
        lines = [f"You spent {f['this_spend']} in {f['this_month']} vs {f['previous_spend']} in "
                 f"{f['previous_month']}: {f['difference']} {f['direction']}."]
        for c in f["biggest_changes"][:3]:
            line = f"{c['category']}: {c['previous']} → {c['this']} ({c['change']})"
            if c["drivers"]:
                d = c["drivers"][0]
                line += f", mostly {d['merchant']} ({d['previous_count']} → {d['this_count']} payments, {d['change']})"
            lines.append(line + ".")
        answer = "\n".join(lines)
        top_cats = {c["category"] for c in changes[:3]}
        evidence = sorted([t for t in in_month(txns, this) if t.category in top_cats and is_spend(t)],
                          key=lambda t: t.amount_pence)[:8]

    elif intent == "recurring":
        rec = [r for r in detect_recurring(txns) if r["active"]]
        subs_only = "subscription" in question.lower()
        subs = [r for r in rec if r["category"] in ("Subscriptions", "Health & fitness", "Entertainment")]
        other = [r for r in rec if r not in subs]
        shown = subs if subs_only else rec
        shown_total = sum(r["monthly_cost_pence"] for r in shown)
        other_total = sum(r["monthly_cost_pence"] for r in other)
        facts["recurring"] = {
            "showing": "subscriptions" if subs_only else "all regular payments",
            "count": len(shown), "monthly_total": fmt_gbp(shown_total),
            "items": [{"merchant": r["merchant"], "amount": fmt_gbp(r["typical_amount_pence"]),
                       "frequency": r["frequency"], "next_expected": r["next_expected"],
                       "category": r["category"]} for r in shown],
            "other_regular_bills": {"count": len(other), "monthly_total": fmt_gbp(other_total)} if subs_only else None,
        }
        if not shown:
            answer = "I didn't find any regular payments yet. I need at least three payments to spot a pattern."
        else:
            items = "; ".join(f"{i['merchant']} {i['amount']} {i['frequency']} (next {date.fromisoformat(i['next_expected']):%-d %b})"
                              for i in facts["recurring"]["items"][:8])
            noun = "subscriptions" if subs_only else "regular payments"
            answer = f"You have {len(shown)} active {noun}, about {fmt_gbp(shown_total)} a month: {items}."
            if subs_only and other:
                answer += (f" On top of that, {len(other)} regular bills (rent, energy and so on) "
                           f"come to about {fmt_gbp(other_total)} a month.")

    elif intent == "top":
        month = months[0] if months else latest
        mt = in_month(txns, month)
        cats_rows = by_category(mt)[:5]
        merch_rows = by_merchant(mt, 5)
        biggest = sorted([t for t in mt if is_spend(t)], key=lambda t: t.amount_pence)[:5]
        facts["top"] = {
            "month": _label(month) + _coverage_note(month, overview),
            "total_spend": fmt_gbp(totals(mt)["spend_pence"]),
            "top_categories": [{"category": r["category"], "spend": fmt_gbp(r["spend_pence"])} for r in cats_rows],
            "top_merchants": [{"merchant": r["merchant"], "spend": fmt_gbp(r["spend_pence"]), "payments": r["count"]}
                              for r in merch_rows],
            "biggest_single_payments": [{"merchant": t.merchant, "amount": fmt_gbp(-t.amount_pence),
                                         "date": t.date.isoformat()} for t in biggest],
        }
        f = facts["top"]
        answer = (f"In {f['month']} you spent {f['total_spend']}. Biggest categories: "
                  + ", ".join(f"{c['category']} {c['spend']}" for c in f["top_categories"][:3])
                  + ". Top merchants: "
                  + ", ".join(f"{m['merchant']} {m['spend']}" for m in f["top_merchants"][:3]) + ".")
        evidence = biggest

    elif intent == "income":
        rows = [{"month": _label(o["month"]) + _coverage_note(o["month"], overview),
                 "income": fmt_gbp(o["income_pence"]), "spend": fmt_gbp(o["spend_pence"]),
                 "net": fmt_gbp(o["net_pence"], signed=True)} for o in overview_list
                if not months or o["month"] in months]
        facts["income"] = rows
        answer = " ".join(f"{r['month']}: income {r['income']}, spending {r['spend']}, net {r['net']}." for r in rows[-3:])
        evidence = [t for t in txns if t.category == "Income" and (not months or month_key(t.date) in months)][-6:]

    elif intent == "spend":
        scope_months = months or [latest]
        sel = [t for t in txns if month_key(t.date) in scope_months and is_spend(t)]
        if merchants:
            sel = [t for t in sel if t.merchant in merchants]
        elif cats:
            sel = [t for t in sel if t.category in cats]
        total = -sum(t.amount_pence for t in sel)
        what = ", ".join(merchants) if merchants else (", ".join(cats) if cats else "everything")
        period = " and ".join(_label(m) + _coverage_note(m, overview) for m in scope_months)
        per_month = [{"month": _label(m), "spend": fmt_gbp(-sum(t.amount_pence for t in sel if month_key(t.date) == m))}
                     for m in scope_months]
        facts["spend"] = {"what": what, "period": period, "total": fmt_gbp(total), "payments": len(sel),
                          "per_month": per_month,
                          "average_payment": fmt_gbp(total // len(sel)) if sel else fmt_gbp(0)}
        f = facts["spend"]
        if not sel:
            answer = f"I found no spending on {what} in {period}."
        else:
            answer = (f"You spent {f['total']} on {what} in {period}, across {f['payments']} payments "
                      f"(average {f['average_payment']}).")
        evidence = sorted(sel, key=lambda t: t.date, reverse=True)[:8]

    else:  # overview
        month = months[0] if months else latest
        mt = in_month(txns, month)
        tt = totals(mt)
        facts["overview"] = {"month": _label(month) + _coverage_note(month, overview),
                             "income": fmt_gbp(tt["income_pence"]), "spend": fmt_gbp(tt["spend_pence"]),
                             "net": fmt_gbp(tt["net_pence"], signed=True),
                             "top_categories": [{"category": r["category"], "spend": fmt_gbp(r["spend_pence"])}
                                                for r in by_category(mt)[:3]]}
        f = facts["overview"]
        answer = (f"In {f['month']}: income {f['income']}, spending {f['spend']}, net {f['net']}. Most went on "
                  + ", ".join(f"{c['category']} ({c['spend']})" for c in f["top_categories"]) + ".")

    return {"intent": intent, "facts": facts, "answer": answer, "evidence": evidence}


# ---------- the guardrail ----------

def _allowed_figures(facts: dict) -> tuple[set[str], set[str]]:
    money, pct = set(), set()
    text = json.dumps(facts, ensure_ascii=False)
    for m in MONEY_RE.findall(text):
        v = m.replace(" ", "").replace(",", "")
        money.add(v)
        if v.endswith(".00"):
            money.add(v[:-3])
        whole = v.split(".")[0]
        money.add(whole)  # "£84" for "£84.20" (rounding down) is allowed
        try:
            money.add(f"£{round(float(v[1:]))}")
        except ValueError:
            pass
    for p in PCT_RE.findall(text):
        pct.add(p.replace(" ", ""))
    return money, pct


def check_figures(reply: str, facts: dict) -> list[str]:
    """Return every £ figure or % in the reply that isn't backed by the facts."""
    money_ok, pct_ok = _allowed_figures(facts)
    bad = []
    for m in MONEY_RE.findall(reply):
        v = m.replace(" ", "").replace(",", "")
        if v not in money_ok:
            bad.append(m)
    for p in PCT_RE.findall(reply):
        if p.replace(" ", "") not in pct_ok:
            bad.append(p)
    return bad


SYSTEM_PROMPT = """You explain a person's own bank transactions back to them in plain British English.
Rules:
- Use ONLY the figures in FACTS. Copy amounts exactly as written there (e.g. £84.20). Never add, subtract,
  estimate or invent any number, amount or percentage.
- If FACTS say the data only covers part of a month, say so.
- 2 to 4 short sentences. Friendly, specific, no lists unless there are more than 3 items.
- Explain what drove the numbers using the merchants and counts in FACTS.
- Don't give investment, credit or legal advice. You may point out a pattern (e.g. more takeaway orders).
- If FACTS don't answer the question, say what you can see instead."""


def ask(question: str, txns: list[Transaction]) -> dict:
    result = build_answer(question, txns)
    response = {
        "answer": result["answer"], "source": "rules", "guardrail": "not_used", "intent": result["intent"],
        "facts": result["facts"], "evidence": [txn_dict(t) for t in result["evidence"]],
    }
    if not os.environ.get("ANTHROPIC_API_KEY") or result["intent"] == "empty":
        response["guardrail"] = "no_api_key" if result["intent"] != "empty" else "not_used"
        return response
    try:
        import anthropic

        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=MODEL, max_tokens=400, system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content":
                       f"QUESTION: {question}\n\nFACTS (computed from the transactions):\n"
                       f"{json.dumps(result['facts'], ensure_ascii=False, indent=1)}"}],
        )
        reply = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    except Exception as exc:  # network, auth, model errors: keep the rule-based answer
        response["guardrail"] = f"model_error: {type(exc).__name__}"
        return response
    bad = check_figures(reply, result["facts"])
    if bad or not reply:
        response["guardrail"] = "blocked: " + ", ".join(bad[:5]) if bad else "blocked: empty reply"
        return response
    response.update(answer=reply, source="claude", guardrail="passed")
    return response
