"""Teaching MoneyMap: rules by payee, note word and amount; scope choices after an edit; questions; chat."""
from app.learning import NO_NOTE, Payees, words_of

CSV = b"""Date,Description,Amount
2026-03-05,FPO JANE ROY 05MAR26 00:53,-25.60
2026-03-18,FPO JANE ROY UTILITIES 18MAR26 23:17,-50.00
2026-04-17,FPO JANE ROY UTILITIES 17APR26 18:10,-44.64
2026-05-07,FPO JANE ROY RENT 07MAY26 12:20,-390.00
2026-06-04,FPO JANE ROY 04JUN26 08:47,-390.00
2026-06-22,FPO JANE ROY UTILITIES 21JUN26 17:11,-94.50
2026-07-02,FPO JANE ROY UTILITIES 02JUL26 23:40,-50.00
2026-10-14,FPO AMIT SEN GARBA 14OCT26 22:26,-11.55
2026-10-19,FPO LEO DIAS GARBA 18OCT26 12:30,-25.00
2026-03-18,FPO AMIT SEN MANCHESTER 18MAR26 23:13,-23.40
2026-06-01,FPO NORTHGATE PROP CON 11 MILL LANE 01JUN26 16:25,-950.00
2026-07-01,FPO NORTHGATE PROP CON 11 MILL LANE 01JUL26 16:25,-950.00
2026-07-03,FPI AMIT SEN 03JUL26,40.00
"""


def _load(client):
    r = client.post("/api/upload", files=[("files", ("bank.csv", CSV))])
    assert r.json()["results"][0]["ok"], r.text
    return {t["description"]: t for t in client.get("/api/transactions").json()}


def test_names_and_notes_are_learned_from_your_own_statements():
    p = Payees([(d, "") for d in ["FPO JANE ROY UTILITIES 18MAR26 23:17", "FPO JANE ROY 05MAR26 00:53",
                                  "FPO JANE ROY RENT 07MAY26", "FPO AMIT SEN GARBA 14OCT26 22:26"]])
    assert p.split("FPO JANE ROY UTILITIES 18MAR26 23:17") == ("JANE ROY", ["UTILITIES"])
    assert p.split("FPO AMIT SEN GARBA 14OCT26 22:26") == ("AMIT SEN", ["GARBA"])  # fallback: first two words
    assert words_of("FPI P KUMAR RAKHI 29AUG••6041") == ["P", "KUMAR", "RAKHI"]


def test_date_and_time_dont_make_every_payment_a_new_merchant(client):
    txns = _load(client)
    keys = {t["merchant"].upper() for d, t in txns.items() if "UTILITIES" in d}
    assert keys == {"JANE ROY UTILITIES"}


def test_note_word_rule_applies_to_everyone(client):
    _load(client)
    r = client.post("/api/rules", json={"spec": {"word": "garba"}, "category": "Entertainment", "taught_via": "chat"})
    assert r.json()["moved"] == 2
    txns = client.get("/api/transactions", params={"q": "garba"}).json()
    assert {t["category"] for t in txns} == {"Entertainment"}


def test_payee_with_amount_limit(client):
    txns = _load(client)
    r = client.post("/api/rules", json={"spec": {"payee": "Jane Roy", "max_pence": 5000}, "category": "Groceries"})
    assert r.status_code == 200
    after = {t["description"]: t["category"] for t in client.get("/api/transactions").json()}
    assert after["FPO JANE ROY UTILITIES 18MAR26 23:17"] == "Groceries"      # £50: within the limit
    assert after["FPO JANE ROY UTILITIES 21JUN26 17:11"] != "Groceries"      # £94.50: over it
    assert after["FPO JANE ROY RENT 07MAY26 12:20"] == txns["FPO JANE ROY RENT 07MAY26 12:20"]["category"]


def test_most_specific_rule_wins_and_deleting_reverts(client):
    _load(client)
    client.post("/api/rules", json={"spec": {"payee": "JANE ROY"}, "category": "Gifts & charity"})
    client.post("/api/rules", json={"spec": {"payee": "JANE ROY", "word": "UTILITIES"}, "category": "Groceries"})
    cats = {t["description"]: t["category"] for t in client.get("/api/transactions", params={"q": "jane"}).json()}
    assert cats["FPO JANE ROY UTILITIES 02JUL26 23:40"] == "Groceries"
    assert cats["FPO JANE ROY 04JUN26 08:47"] == "Gifts & charity"
    rules = client.get("/api/rules").json()
    assert len(rules) == 2 and rules[0]["text"].endswith("→ Groceries")
    for r in rules:
        client.delete(f"/api/rules/{r['id']}")
    cats = {t["description"]: t["category"] for t in client.get("/api/transactions", params={"q": "jane"}).json()}
    assert cats["FPO JANE ROY UTILITIES 02JUL26 23:40"] == "Bills & utilities"  # back to the built-in rule


def test_rules_never_touch_payments_set_by_hand(client):
    txns = _load(client)
    t = txns["FPO JANE ROY 05MAR26 00:53"]
    client.patch(f"/api/transactions/{t['id']}", json={"category": "Travel", "apply_to_merchant": False})
    client.post("/api/rules", json={"spec": {"payee": "JANE ROY"}, "category": "Groceries"})
    assert client.get("/api/transactions", params={"q": "05MAR26"}).json()[0]["category"] == "Travel"


def test_editing_offers_ways_to_apply_it(client):
    txns = _load(client)
    t = txns["FPO JANE ROY UTILITIES 18MAR26 23:17"]
    r = client.patch(f"/api/transactions/{t['id']}", json={"category": "Groceries", "apply_to_merchant": False}).json()
    labels = [o["label"] for o in r["options"]]
    assert labels[0] == "Jane Roy, when the note says “Utilities”"
    assert "Everything to or from Jane Roy" in labels
    first = r["options"][0]
    assert first["matches"] == 3  # the other three UTILITIES payments
    saved = client.post("/api/rules", json={"spec": first["spec"], "category": "Groceries"}).json()
    assert saved["moved"] == 3


def test_questions_ask_about_unsure_payments_biggest_first(client):
    _load(client)
    q = client.get("/api/questions").json()
    first = q["items"][0]
    assert first["question"] == "What are your payments to Northgate Prop Con Mill Lane for?"
    assert first["count"] == 2 and first["total_pence"] == 190000
    jane = next(g for g in q["items"] if g["name"] == "Jane Roy")
    assert jane["spec"]["word"] == NO_NOTE  # the unnoted ones only: her RENT payments are already sorted
    r = client.post("/api/rules", json={"spec": jane["spec"], "category": "Rent & housing", "taught_via": "question"})
    assert r.json()["moved"] == 2
    client.post("/api/questions/dismiss", json={"key": first["key"]})
    keys = [g["key"] for g in client.get("/api/questions").json()["items"]]
    assert first["key"] not in keys and jane["key"] not in keys


def test_income_rule_never_applies_to_money_going_out(client):
    _load(client)
    client.post("/api/rules", json={"spec": {"payee": "AMIT SEN"}, "category": "Other income"})
    cats = {t["amount_pence"] > 0: t["category"] for t in client.get("/api/transactions", params={"q": "amit"}).json()}
    assert cats[True] == "Other income" and cats[False] != "Other income"


def test_rules_apply_to_statements_uploaded_later(client):
    client.post("/api/rules", json={"spec": {"word": "GARBA"}, "category": "Entertainment"})
    _load(client)
    assert {t["category"] for t in client.get("/api/transactions", params={"q": "garba"}).json()} == {"Entertainment"}


# ---------- teaching in the chat ----------

def _ask(client, q):
    return client.post("/api/chat", json={"question": q}).json()


def test_chat_note_word(client):
    _load(client)
    r = _ask(client, "Amit Sen Garba : means i paid amit for garba and garba is entertainment")
    assert r["intent"] == "teach"
    assert r["proposal"]["spec"]["word"] == "GARBA" and r["proposal"]["category"] == "Entertainment"
    assert r["proposal"]["would_move"] == 2
    saved = client.post("/api/rules", json={"spec": r["proposal"]["spec"], "category": "Entertainment",
                                            "taught_via": "chat"}).json()
    assert saved["moved"] == 2


def test_chat_person_with_amount_limit(client):
    _load(client)
    r = _ask(client, "Jane Roy Utilities : this payment is repeated to jane ranges upto 50 pounds its basically for groceries")
    p = r["proposal"]
    assert p["spec"]["payee"] == "JANE ROY" and p["spec"]["max_pence"] == 5000 and p["category"] == "Groceries"
    assert any("Utilities" in a["rule"] for a in p["alternatives"])


def test_chat_first_name_and_partial_names(client):
    _load(client)
    assert _ask(client, "jane is groceries")["proposal"]["spec"]["payee"] == "JANE ROY"
    assert _ask(client, "payments to northgate are rent")["proposal"]["spec"]["payee"].startswith("NORTHGATE")


def test_chat_questions_are_still_questions(client):
    _load(client)
    for q in ("How much did I spend on groceries?", "where did my money go", "what is rent"):
        assert _ask(client, q)["intent"] != "teach"


def test_chat_unknown_name_gets_suggestions(client):
    _load(client)
    r = _ask(client, "Jayne Roy is groceries")
    assert r["proposal"] is None and "Jane Roy" in r["answer"]
