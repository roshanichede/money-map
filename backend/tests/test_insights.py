from app.categories import categorise
from app.chat import check_figures
from app.merchants import normalise


def test_merchant_normalisation():
    assert normalise("TESCO STORES 3021 CD 4821") == ("TESCO", "Tesco")
    assert normalise("PAYPAL *NETFLIX.COM 4029357733")[1] == "Netflix"
    assert normalise("DELIVEROO PLUS LONDON GB CD 4821")[1] == "Deliveroo"
    key, _ = normalise("JOE'S CORNER CAFE 0042 LEICESTER GB")
    assert "0042" not in key and "LEICESTER" not in key


def test_categoriser():
    assert categorise("DELIVEROO", "DELIVEROO", "DEB", -2000) == "Takeaways"
    assert categorise("ACME LTD SALARY", "ACME LTD", "BGC", 200000) == "Income"
    assert categorise("TO A/C 87654321 SAVINGS", "TO A", "TFR", -30000) == "Transfers"
    assert categorise("CITY LETTINGS RENT", "CITY LETTINGS RENT", "SO", -85000) == "Rent & housing"
    assert categorise("SOMETHING UNKNOWN", "SOMETHING UNKNOWN", "DD", -1000) == "Bills & utilities"


def test_categorisation_rate_meets_target(loaded):
    assert loaded.get("/api/overview").json()["categorised_rate"] >= 0.85


def test_summary_excludes_transfers_from_spending(loaded):
    s = loaded.get("/api/summary/2026-09").json()
    cats = {c["category"] for c in s["categories"]}
    assert "Transfers" not in cats and "Income" not in cats
    assert s["income_pence"] == 248500
    assert s["spend_pence"] == sum(c["spend_pence"] for c in s["categories"])


def test_recurring_finds_subscriptions_and_rent(loaded):
    items = loaded.get("/api/recurring").json()["items"]
    names = {i["merchant"]: i for i in items}
    for expected in ("Netflix", "Spotify", "PureGym", "Vodafone"):
        assert names[expected]["frequency"] == "monthly", expected
    assert names["Netflix"]["typical_amount_pence"] == 1099
    assert names["Netflix"]["next_expected"] == "2026-11-12"
    assert not any(i["merchant"] == "Pret" and i["frequency"] == "monthly" for i in items)


def test_learning_a_category_applies_to_the_merchant(loaded):
    txns = loaded.get("/api/transactions", params={"q": "pret"}).json()
    r = loaded.patch(f"/api/transactions/{txns[0]['id']}", json={"category": "Groceries"}).json()
    assert r["updated"] == len(txns)
    after = loaded.get("/api/transactions", params={"q": "pret"}).json()
    assert {t["category"] for t in after} == {"Groceries"}


def test_export_and_delete(loaded):
    csv = loaded.get("/api/export").text
    assert csv.startswith("date,account,description") and csv.count("\n") > 200
    loaded.delete("/api/data")
    assert loaded.get("/api/overview").json()["transaction_count"] == 0


def test_chat_compare_uses_real_figures(loaded):
    r = loaded.post("/api/chat", json={"question": "Why was October more expensive than September?"}).json()
    assert r["intent"] == "compare" and r["source"] == "rules"
    assert "October 2026" in r["answer"] and "September 2026" in r["answer"]
    assert "data up to 20 Oct" in r["answer"]
    assert not check_figures(r["answer"], r["facts"])  # rule answers always pass the guardrail


def test_chat_spend_on_merchant(loaded):
    r = loaded.post("/api/chat", json={"question": "How much did I spend on Deliveroo in September?"}).json()
    assert r["intent"] == "spend"
    assert r["facts"]["spend"]["what"] == "Deliveroo"
    assert all(e["merchant"] == "Deliveroo" for e in r["evidence"])


def test_chat_recurring(loaded):
    r = loaded.post("/api/chat", json={"question": "What subscriptions do I have?"}).json()
    assert r["intent"] == "recurring" and "Netflix" in r["answer"]


def test_guardrail_blocks_invented_numbers():
    facts = {"spend": {"total": "£84.20", "payments": 6}}
    assert check_figures("You spent £84.20 on takeaways.", facts) == []
    assert check_figures("About £84 in total.", facts) == []
    assert check_figures("You spent £90 on takeaways.", facts) == ["£90"]
    assert check_figures("That's 25% more.", facts) == ["25%"]


class _FakeClient:
    """Stands in for anthropic.Anthropic so the guardrail path is tested without a key."""

    reply = ""

    def __init__(self, *a, **k):
        self.messages = self

    def create(self, **kwargs):
        class Block:
            type = "text"
            text = _FakeClient.reply

        class Msg:
            content = [Block()]

        return Msg()


def _with_fake_claude(monkeypatch, reply):
    import anthropic

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(anthropic, "Anthropic", _FakeClient)
    _FakeClient.reply = reply


def test_claude_reply_used_when_figures_check_out(loaded, monkeypatch):
    rules = loaded.post("/api/chat", json={"question": "How much on Deliveroo in October?"}).json()
    total = rules["facts"]["spend"]["total"]
    _with_fake_claude(monkeypatch, f"You've spent {total} on Deliveroo so far this October.")
    r = loaded.post("/api/chat", json={"question": "How much on Deliveroo in October?"}).json()
    assert r["source"] == "claude" and r["guardrail"] == "passed"


def test_claude_reply_blocked_when_it_invents_a_number(loaded, monkeypatch):
    _with_fake_claude(monkeypatch, "You've spent £999.99 on Deliveroo, about 40% of your budget.")
    r = loaded.post("/api/chat", json={"question": "How much on Deliveroo in October?"}).json()
    assert r["source"] == "rules" and r["guardrail"].startswith("blocked")
    assert "£999.99" not in r["answer"]


def test_unchanged_categories_show_zero_change(loaded):
    comp = loaded.get("/api/summary/2026-09").json()["comparison"]
    rent = next(c for c in comp["changes"] if c["category"] == "Rent & housing")
    assert rent["delta_pence"] == 0 and rent["prev_pence"] == 85000
