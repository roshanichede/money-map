"""Teaching MoneyMap in the chat: "garba is entertainment", "Preeti's payments up to £50 are groceries".

The message is turned into a rule *proposal*, never saved directly: the reply shows what the rule would be and
which payments it would move, and the user confirms (or picks a wider or narrower version).
Names and words are only accepted if they really appear in the user's statements.
"""
from __future__ import annotations

import difflib
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .categories import CATEGORIES
from .learning import STOPWORDS, Payees, Spec, nice, payees_for, preview, words_of
from .models import Transaction

# Plain words people use -> category. Longest phrases are tried first.
SYNONYMS: dict[str, str] = {c.lower(): c for c in CATEGORIES}
SYNONYMS.update({
    "grocery": "Groceries", "food shopping": "Groceries", "supermarket": "Groceries",
    "utilities": "Bills & utilities", "utility": "Bills & utilities", "bills": "Bills & utilities",
    "bill": "Bills & utilities", "electricity": "Bills & utilities", "wifi": "Bills & utilities",
    "rent": "Rent & housing", "housing": "Rent & housing",
    "restaurant": "Eating out", "dinner": "Eating out", "lunch": "Eating out", "eating out": "Eating out",
    "takeaway": "Takeaways", "cab": "Transport", "taxi": "Transport", "uber": "Transport", "train": "Transport",
    "bus": "Transport", "travel": "Travel", "holiday": "Travel", "trip": "Travel", "flight": "Travel",
    "flights": "Travel", "fun": "Entertainment", "movie": "Entertainment", "movies": "Entertainment",
    "party": "Entertainment", "event": "Entertainment", "events": "Entertainment", "clothes": "Shopping",
    "gift": "Gifts & charity", "gifts": "Gifts & charity", "charity": "Gifts & charity",
    "donation": "Gifts & charity", "gym": "Health & fitness", "fitness": "Health & fitness",
    "health": "Health & fitness", "tuition": "Education", "course": "Education", "fees": "Education",
    "salary": "Salary", "wages": "Salary", "my pay": "Salary", "income": "Other income",
    "freelance": "Other income", "my own account": "Transfers", "my own money": "Transfers",
    "savings": "Transfers", "transfer": "Transfers", "subscription": "Subscriptions",
    "haircut": "Personal care", "cash": "Cash",
})
_CAT_RE = re.compile(r"(?<![a-z])(" + "|".join(sorted(map(re.escape, SYNONYMS), key=len, reverse=True)) + r")(?![a-z])")
_QUESTION = re.compile(r"\?\s*$|^\s*(how|what|why|when|where|which|who|show|list|did|do|does|can|could|tell)\b|how much")
_TEACHING = re.compile(r"\b(is|are|was|were|means?|=|should be|count(s)? as|goes? (to|in|under)|put|mark|"
                       r"categori[sz]e|remember|always|basically|it's|its|for|sends?|pays?|paid|gives?)\b")
_LINKER = re.compile(r"\b(?:is|are|=|means?|should be|counts? as|goes? (?:to|in|under)|as)\b\s+"
                     r"(?:(?:for|basically|mostly|always|just|actually|really|my|the|a|an)\s+)*$")
_AMOUNT = re.compile(r"(?:up ?to|upto|under|below|less than|max(?:imum)?|within|at most|<=?|till|until)\s*"
                     r"£?\s*(\d+(?:\.\d{1,2})?)\s*(?:pounds?|quid|gbp|£)?|£\s*(\d+(?:\.\d{1,2})?)\s*or less", re.I)
ENGLISH = STOPWORDS | {"I", "ME", "IT", "THIS", "THAT", "THESE", "IS", "ARE", "WAS", "WHEN", "WITH", "BASICALLY",
                       "ALWAYS", "MEANS", "MEAN", "PAYMENTS", "RANGES", "RANGE", "UPTO", "UP", "POUNDS", "ITS",
                       "PARTICULAR", "ACCOUNT", "REPEATED", "SOMETHING", "ALL", "EVERY", "ONE", "SOME", "HER",
                       "HIS", "THEIR", "THEM", "SHE", "HE", "WE", "OUR", "AS", "BE", "JUST", "REALLY", "OR",
                       "SO", "IF", "BUT", "NOT", "NO", "ACTUALLY", "MOSTLY", "LIKE", "SAME", "ALSO"}


def _category(message: str) -> str | None:
    hits = list(_CAT_RE.finditer(message.lower()))
    return SYNONYMS[hits[-1].group(1)] if hits else None


def _amount(message: str) -> int | None:
    m = _AMOUNT.search(message)
    if not m:
        return None
    return round(float(m.group(1) or m.group(2)) * 100)


def _grams(text: str) -> list[str]:
    words = [w for w in re.sub(r"[^A-Z0-9 ]", " ", text.upper()).split()]
    out = []
    for n in (4, 3, 2, 1):
        for i in range(len(words) - n + 1):
            g = words[i:i + n]
            if all(w in ENGLISH for w in g) or g[0] in ENGLISH or g[-1] in ENGLISH:
                continue
            out.append(" ".join(g))
    return out


class _Index:
    def __init__(self, session: Session, user_id: int):
        rows = session.execute(select(Transaction.description, Transaction.txn_type).where(
            Transaction.user_id == user_id)).all()
        self.payees: Payees = payees_for(session, user_id)
        self.payee_names: set[str] = set()
        self.notes: dict[str, set[str]] = {}
        for d, typ in rows:
            p, note = self.payees.split(d, typ)
            if p:
                self.payee_names.add(p)
            for w in note:
                self.notes.setdefault(w, set()).add(p)
        self.all_words = {w for d, typ in rows for w in words_of(d, typ)}

    def payee_in(self, grams: list[str]) -> str | None:
        found = [g for g in grams if g in self.payee_names]
        # also accept the start of exactly one name ("preeti" -> PREETI MISAL, "first property" -> FIRST PROPERTY CON...)
        if not found:
            for g in grams:
                if len(g) >= 4:
                    n = len(g.split())
                    starts = {p for p in self.payee_names if p.split()[:n] == g.split() and p != g}
                    if len(starts) == 1:
                        found.append(starts.pop())
        return max(found, key=len) if found else None

    def word_in(self, grams: list[str], payee: str | None) -> str | None:
        found = [g for g in grams if g in self.notes and (not payee or g not in payee.split())]
        if payee:
            mine = [g for g in found if payee in self.notes[g]]
            found = mine or found
        return max(found, key=len) if found else None


def proposal(message: str, session: Session, user_id: int) -> dict | None:
    """A rule proposal if the message teaches something; None if it's an ordinary question."""
    text = message.strip()
    if _QUESTION.search(text.lower()) or not _TEACHING.search(text.lower()):
        return None
    category = _category(text)
    if not category:
        return None
    idx = _Index(session, user_id)
    cat_spans = [m.span() for m in _CAT_RE.finditer(text.lower())]
    # "garba is entertainment": the words right before the linker are the subject
    subject_grams: list[str] = []
    last = cat_spans[-1]
    left = text[:last[0]]
    if _LINKER.search(left.lower()):
        tail = " ".join(left[:_LINKER.search(left.lower()).start()].split()[-4:])
        subject_grams = _grams(tail)
    # the category word itself ("rent" in "... are rent") isn't the subject
    everything = _grams(text[:last[0]] + " " + text[last[1]:])
    max_pence = _amount(text)

    sp, sw = idx.payee_in(subject_grams), idx.word_in(subject_grams, None)
    payee, word = idx.payee_in(everything), None
    if sp or sw:
        main = Spec(payee=sp or "", word=sw if not sp else "", max_pence=max_pence)
    elif payee:
        word = idx.word_in(everything, payee)
        main = Spec(payee=payee, max_pence=max_pence) if max_pence else Spec(payee=payee, word=word or "")
    else:
        word = idx.word_in(everything, None)
        if not word:
            return _not_found(text, idx, category)
        main = Spec(word=word, max_pence=max_pence)
    word = word or idx.word_in(everything, main.payee or None)

    alternatives: list[Spec] = []
    if main.payee and word and main.word != word:
        alternatives.append(Spec(payee=main.payee, word=word))
    if main.payee and (main.word or main.max_pence):
        alternatives.append(Spec(payee=main.payee))
    if word and (main.payee or main.max_pence):
        alternatives.append(Spec(word=word))
    if main.word and not main.payee and payee:
        alternatives.append(Spec(payee=payee))

    p = preview(session, user_id, main, category)
    alts = []
    for a in alternatives:
        ap = preview(session, user_id, a, category)
        if ap["matches"] and ap["rule"] != p["rule"]:
            alts.append({"spec": a.__dict__, "rule": ap["rule"], "matches": ap["matches"], "would_move": ap["would_move"]})
    moving = (f"It would move {p['would_move']} of the {p['matches']} payments it matches."
              if p["matches"] else "Nothing else matches it yet; it will apply to future statements.")
    if p.get("set_by_hand"):
        moving += f" ({p['set_by_hand']} you already sorted by hand stay as you set them.)"
    if p["matches"] and p["would_move"] == 0:
        moving = f"All {p['matches']} payments it matches are already sorted that way, so it just keeps them there."
    return {
        "answer": f"Got it. Here's the rule I'd save: {p['rule']}. {moving} Save it, or pick another version below.",
        "proposal": {"spec": main.__dict__, "category": category, **p, "alternatives": alts[:3]},
    }


def _not_found(text: str, idx: _Index, category: str) -> dict:
    words = [g for g in _grams(text) if " " not in g and len(g) >= 3]
    close = []
    for w in words:
        close += difflib.get_close_matches(w, [p for p in idx.payee_names if len(p) < 40], n=2, cutoff=0.6)
        close += [p for p in idx.payee_names if w in p.split()][:2]
    close = list(dict.fromkeys(close))[:4]
    hint = (" Did you mean " + ", ".join(f"“{nice(c)}”" for c in close) + "?") if close else ""
    return {"answer": f"I'd put it in {category}, but I couldn't find who or what you mean on your statements. "
                      f"Write the name or the note the way your statement shows it, e.g. “Preeti Misal is groceries”."
                      + hint, "proposal": None}
