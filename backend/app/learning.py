"""How MoneyMap learns from you.

Built-in rules sort most payments. What they can't know is personal: that GARBA is a dance night, or that
your £50 payments to a flatmate are for groceries. So MoneyMap learns *rules* from you, never silent guesses:

  - a payee      "PREETI MISAL"            every payment to or from that person or company
  - a note word  "GARBA"                   any payment with that word in its description
  - an amount    "up to £50"               only payments up to that size
  combined freely: "Preeti Misal, up to £50 -> Groceries".

You teach a rule three ways: when you change a category (it asks how widely to apply it), by answering the
questions MoneyMap asks about payments it isn't sure of, or in the chat ("garba is entertainment"). Every rule
is listed and can be deleted, and each one is previewed ("this moves 6 payments") before it's saved.

When several rules match, the most specific wins (payee + word + amount beats payee alone), then the newest.
Payments you set by hand are never touched by rules.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .categories import CATEGORIES, INCOME_CATEGORIES, categorise, is_company, split_code
from .models import Dismissed, MerchantRule, Rule, Transaction
from .money import fmt_round

# ---------- reading a description as payee + note ----------

_CLEAN = [
    re.compile(r"\bCD \d{4}\b.*$"),            # card suffix
    re.compile(r"••\S*"),                      # masked numbers and references
    re.compile(r"\b\d{1,2}[A-Z]{3}(\d{2})?\b"),  # 13MAY26, 18JAN
    re.compile(r"\b\d{1,2}:\d{2}\b"),          # 23:16
    re.compile(r"\b(?=[A-Z]*\d)[A-Z\d]{8,}\b"),  # long reference codes
    re.compile(r"\b\d+\b"),
    re.compile(r"[^A-Z\s&'-]"),
]
_TRAILING = {"OD"}
STOPWORDS = {"OF", "FOR", "THE", "MY", "AND", "TO", "A", "AN", "IN", "ON", "AT", "FROM", "SHARE", "PAYMENT",
             "PAY", "PAID", "SENT", "REF", "MONEY", "BACK", "DONE", "THANKS", "THANK", "YOU", "TY", "PLS", "N",
             "REVOLUT", "MONZO", "WISE", "PAYPAL", "STARLING", "TRANSFER", "VIA", "BANK"}
NO_NOTE = "(NO NOTE)"  # a rule word meaning "payments to this person with nothing written in the note"
PERSON_CODES = {"FPO", "FPI", "BP", "TFR", "SO", "", "UPI", "IMPS", "NEFT", "RTGS"}


def words_of(description: str, txn_type: str = "") -> list[str]:
    """'FPO PREETI MISAL UTILITIES 13MAY26 23:16' -> ['PREETI', 'MISAL', 'UTILITIES']"""
    text = split_code(description, txn_type)[1].upper()
    for rx in _CLEAN:
        text = rx.sub(" ", text)
    words = [w.strip("&'-") for w in text.split()]
    words = [w for w in words if w]
    while words and words[-1] in _TRAILING:
        words.pop()
    return words


def _fallback_payee(words: list[str]) -> tuple[str, ...]:
    """First two words, plus any initials that follow ('SHARMA A S')."""
    n = min(2, len(words))
    while n < len(words) and n < 4 and len(words[n]) == 1:
        n += 1
    return tuple(words[:n])


class Payees:
    """Works out where the name ends and the note begins, from your own statements: a name is the start of a
    description that comes back with *different* notes ('PREETI MISAL' + UTILITIES / RENT / HOLI / nothing)."""

    def __init__(self, descriptions: list[tuple[str, str]]):
        conts: dict[tuple[str, ...], set[str]] = defaultdict(set)
        seen: Counter = Counter()
        self.whole: Counter = Counter()
        for desc, typ in descriptions:
            w = words_of(desc, typ)
            self.whole[tuple(w)] += 1
            for k in range(2, min(4, len(w)) + 1):
                p = tuple(w[:k])
                seen[p] += 1
                conts[p].add(w[k] if k < len(w) else "")
        self.names = {p for p, c in conts.items() if len(c) >= 2 and seen[p] >= 2}

    def split(self, description: str, txn_type: str = "") -> tuple[str, list[str]]:
        w = words_of(description, txn_type)
        payee = next((tuple(w[:k]) for k in range(2, min(4, len(w)) + 1) if tuple(w[:k]) in self.names), None)
        if payee is None and self.whole[tuple(w)] >= 2 and len(w) > 2:
            # the same description again and again ("FIRST PROPERTY CON 11 MILLSTONE LANE") is one payee
            return " ".join(w[:6]), []
        if payee is None:
            payee = _fallback_payee(w)
        note = [x for x in w[len(payee):] if x not in STOPWORDS and len(x) > 1]
        return " ".join(payee), note


def _is_person(t: Transaction) -> bool:
    code = split_code(t.description, t.txn_type)[0]
    return code in PERSON_CODES and not is_company(t.description)


def nice(text: str) -> str:
    return " ".join(w if len(w) == 1 else w.capitalize() for w in text.split())


# ---------- rules ----------

@dataclass
class Spec:
    """A rule before it's saved."""
    payee: str = ""
    word: str = ""
    max_pence: int | None = None
    merchant_key: str = ""  # an exact merchant (the older kind of rule)

    def specificity(self) -> float:
        if self.merchant_key:
            return 2.5
        return 2 * bool(self.payee) + bool(self.word) + bool(self.max_pence)


def _spec(r: Rule | MerchantRule) -> Spec:
    if isinstance(r, MerchantRule):
        return Spec(merchant_key=r.merchant_key)
    return Spec(payee=r.payee, word=r.word, max_pence=r.max_pence)


def matches(spec: Spec, t: Transaction, words: list[str] | None = None, category: str | None = None) -> bool:
    if category in INCOME_CATEGORIES and t.amount_pence < 0:
        return False  # money going out is never salary
    if spec.merchant_key:
        return t.merchant_key == spec.merchant_key
    if not (spec.payee or spec.word):
        return False
    words = words if words is not None else words_of(t.description, t.txn_type)
    if spec.payee:
        p = spec.payee.split()
        if words[:len(p)] != p:
            return False
    if spec.word == NO_NOTE:
        if not spec.payee or [x for x in words[len(spec.payee.split()):] if x not in STOPWORDS and len(x) > 1]:
            return False
    elif spec.word:
        w = spec.word.split()
        if not any(words[i:i + len(w)] == w for i in range(len(words))):
            return False
    if spec.max_pence is not None and abs(t.amount_pence) > spec.max_pence:
        return False
    return True


def describe(spec: Spec, category: str) -> str:
    if spec.merchant_key:
        who = f"Every {nice(spec.merchant_key)} payment"
    else:
        who = f"Payments to or from {nice(spec.payee)}" if spec.payee else "Any payment"
        if spec.word == NO_NOTE:
            who += " with no note"
        elif spec.word:
            who += f" with “{nice(spec.word)}” in the note" if spec.payee else f" with “{nice(spec.word)}” in it"
        if spec.max_pence is not None:
            who += f", up to {fmt_round(spec.max_pence)}"
    return f"{who} → {category}"


def _rules(session: Session, user_id: int) -> list[tuple[Spec, str, object]]:
    out = [(_spec(r), r.category, r) for r in session.scalars(
        select(Rule).where(Rule.user_id == user_id).order_by(Rule.created_at, Rule.id))]
    out += [(_spec(r), r.category, r) for r in session.scalars(
        select(MerchantRule).where(MerchantRule.user_id == user_id).order_by(MerchantRule.created_at))]
    # most specific first; among equals, the newest
    out.sort(key=lambda x: (x[0].specificity(), getattr(x[2], "created_at")), reverse=True)
    return out


def _txns(session: Session, user_id: int) -> list[Transaction]:
    return list(session.scalars(select(Transaction).where(Transaction.user_id == user_id)
                                .order_by(Transaction.date, Transaction.id)))


def _taught(t: Transaction) -> bool:
    return t.category_source in ("manual", "transfer") or t.transfer_pair_id is not None


def apply_rules(session: Session, user_id: int) -> int:
    """Re-sort every payment you haven't set by hand with the rules you've taught. Returns how many moved."""
    rules = _rules(session, user_id)
    changed = 0
    for t in _txns(session, user_id):
        if _taught(t):
            continue
        words = words_of(t.description, t.txn_type)
        hit = next(((s, c) for s, c, _ in rules if matches(s, t, words, c)), None)
        if hit:
            changed += t.category != hit[1]
            t.category, t.category_source = hit[1], "learned"
        elif t.category_source == "learned":  # its rule was deleted: back to the built-in rules
            built_in = categorise(t.description, t.merchant_key, t.txn_type, t.amount_pence)
            changed += t.category != built_in
            t.category, t.category_source = built_in, "rule"
    session.flush()
    return changed


def preview(session: Session, user_id: int, spec: Spec, category: str, exclude_id: int | None = None) -> dict:
    hits = [t for t in _txns(session, user_id)
            if t.id != exclude_id and not _taught(t) and matches(spec, t, category=category)]
    moving = [t for t in hits if t.category != category]
    by_hand = sum(1 for t in _txns(session, user_id) if t.category_source == "manual" and t.id != exclude_id
                  and matches(spec, t, category=category))
    return {"rule": describe(spec, category), "matches": len(hits), "would_move": len(moving), "set_by_hand": by_hand,
            "total_pence": sum(abs(t.amount_pence) for t in hits),
            "examples": [{"date": t.date.isoformat(), "description": t.description, "amount_pence": t.amount_pence,
                          "category": t.category} for t in hits[-5:]]}


def save_rule(session: Session, user_id: int, spec: Spec, category: str, via: str) -> dict:
    """Save a rule (replacing one with exactly the same conditions) and re-sort."""
    from .income import detect_salary

    if category not in CATEGORIES:
        raise ValueError("Unknown category.")
    if spec.merchant_key:
        rule = session.scalar(select(MerchantRule).where(MerchantRule.user_id == user_id,
                                                         MerchantRule.merchant_key == spec.merchant_key))
        if rule:
            rule.category = category
        else:
            session.add(MerchantRule(user_id=user_id, merchant_key=spec.merchant_key, category=category))
    else:
        if not (spec.payee or spec.word):
            raise ValueError("A rule needs a name or a word.")
        for same in session.scalars(select(Rule).where(Rule.user_id == user_id, Rule.payee == spec.payee,
                                                       Rule.word == spec.word)):
            if same.max_pence == spec.max_pence:
                session.delete(same)
        session.flush()
        session.add(Rule(user_id=user_id, payee=spec.payee, word=spec.word, max_pence=spec.max_pence,
                         category=category, taught_via=via))
    session.flush()
    moved = apply_rules(session, user_id)
    detect_salary(session, user_id)
    session.commit()
    return {"rule": describe(spec, category), "moved": moved}


def list_rules(session: Session, user_id: int) -> list[dict]:
    out = []
    learned = [t for t in _txns(session, user_id) if t.category_source == "learned"]
    for spec, category, r in _rules(session, user_id):
        n = sum(1 for t in learned if t.category == category and matches(spec, t, category=category))
        out.append({"id": f"{'m' if isinstance(r, MerchantRule) else 'r'}{r.id}", "text": describe(spec, category),
                    "category": category, "payments": n, "taught_via": getattr(r, "taught_via", "edit"),
                    "created_at": r.created_at.isoformat()})
    return sorted(out, key=lambda x: x["created_at"], reverse=True)


def delete_rule(session: Session, user_id: int, rule_id: str) -> int:
    from .income import detect_salary

    model = MerchantRule if rule_id.startswith("m") else Rule
    try:
        r = session.get(model, int(rule_id[1:]))
    except ValueError:
        r = None
    if r is None or r.user_id != user_id:
        raise LookupError("Rule not found.")
    session.delete(r)
    session.flush()
    moved = apply_rules(session, user_id)
    detect_salary(session, user_id)
    session.commit()
    return moved


# ---------- after you change one payment: how widely should it apply? ----------

def payees_for(session: Session, user_id: int) -> Payees:
    return Payees([(d, typ) for d, typ in session.execute(
        select(Transaction.description, Transaction.txn_type).where(Transaction.user_id == user_id))])


def scope_options(session: Session, user_id: int, t: Transaction, category: str) -> list[dict]:
    options: list[dict] = []

    def add(spec: Spec, label: str):
        p = preview(session, user_id, spec, category, exclude_id=t.id)
        if p["matches"] and not any(o["label"] == label for o in options):
            options.append({"label": label, "spec": spec.__dict__, "matches": p["matches"],
                            "would_move": p["would_move"]})

    if _is_person(t):
        payee, note = payees_for(session, user_id).split(t.description, t.txn_type)
        if note:
            add(Spec(payee=payee, word=note[0]), f"{nice(payee)}, when the note says “{nice(note[0])}”")
        else:
            add(Spec(payee=payee, word=NO_NOTE), f"{nice(payee)}, when there's no note")
        add(Spec(payee=payee), f"Everything to or from {nice(payee)}")
        for w in note[:2]:
            add(Spec(word=w), f"Any payment that says “{nice(w)}”")
    else:
        add(Spec(merchant_key=t.merchant_key), f"Every {t.merchant} payment")
    return options[:4]


# ---------- questions about the payments MoneyMap is least sure of ----------

def questions(session: Session, user_id: int, limit: int = 6) -> dict:
    dismissed = set(session.scalars(select(Dismissed.key).where(Dismissed.user_id == user_id)))
    payees = payees_for(session, user_id)
    groups: dict[str, dict] = {}
    for t in _txns(session, user_id):
        if _taught(t) or t.category_source != "rule":
            continue
        unsure_out = t.amount_pence < 0 and t.category == "Other"
        unsure_in = t.amount_pence > 0 and t.category == "From people"
        if not (unsure_out or unsure_in):
            continue
        direction = "out" if t.amount_pence < 0 else "in"
        if _is_person(t):
            payee, note = payees.split(t.description, t.txn_type)
            word = note[0] if note else ""
            key = f"{direction}|p|{payee}|{word}"
            spec = Spec(payee=payee, word=word or NO_NOTE)
            name = nice(payee)
        else:
            key = f"{direction}|m|{t.merchant_key}"
            spec, word, name = Spec(merchant_key=t.merchant_key), "", t.merchant
        if key in dismissed:
            continue
        g = groups.setdefault(key, {"key": key, "direction": direction, "name": name, "word": nice(word),
                                    "spec": spec.__dict__, "count": 0, "total_pence": 0, "amounts": [],
                                    "examples": []})
        g["count"] += 1
        g["total_pence"] += abs(t.amount_pence)
        g["amounts"].append(abs(t.amount_pence))
        g["examples"].append({"date": t.date.isoformat(), "description": t.description,
                              "amount_pence": t.amount_pence})
    out = []
    for g in sorted(groups.values(), key=lambda g: -g["total_pence"]):
        amounts = sorted(g.pop("amounts"))
        g["examples"] = g["examples"][-3:]
        g["largest_pence"] = amounts[-1]
        if g["direction"] == "out":
            ask = f"What are your payments to {g['name']} for?"
            if g["word"]:
                ask = f"What are your payments to {g['name']} marked “{g['word']}” for?"
        else:
            ask = f"Why does {g['name']} send you money?"
            if g["word"]:
                ask = f"What does {g['name']} pay you for when the note says “{g['word']}”?"
        g["question"] = ask
        # Wider ways to apply the answer (the narrowest is the default).
        alts = []
        s = g["spec"]
        if s.get("payee") and s.get("word") == NO_NOTE:
            alts = [{"label": f"Everything to or from {g['name']}", "spec": Spec(payee=s["payee"]).__dict__}]
        elif s.get("payee") and s.get("word"):
            alts = [{"label": f"Everything to or from {g['name']}", "spec": Spec(payee=s["payee"]).__dict__},
                    {"label": f"Any payment that says “{g['word']}”", "spec": Spec(word=s["word"]).__dict__}]
        g["alternatives"] = alts
        out.append(g)
    return {"total": len(out), "items": out[:limit]}


def dismiss(session: Session, user_id: int, key: str) -> None:
    if not session.scalar(select(Dismissed).where(Dismissed.user_id == user_id, Dismissed.key == key)):
        session.add(Dismissed(user_id=user_id, key=key[:200]))
        session.commit()
