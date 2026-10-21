"""Formatting money in the currency of the accounts being looked at (£ or ₹, never mixed).

The current currency is set once per request (see main._scope) and read by every formatter, so insights,
highlights and chat answers all speak the same currency as the numbers they describe."""
from contextvars import ContextVar

CURRENCIES = {"GBP": "£", "INR": "₹", "EUR": "€", "USD": "$"}
_current: ContextVar[str] = ContextVar("currency", default="GBP")


def set_currency(code: str | None) -> None:
    _current.set(code if code in CURRENCIES else "GBP")


def currency() -> str:
    return _current.get()


def symbol() -> str:
    return CURRENCIES[_current.get()]


def group(units: int) -> str:
    """Thousands separators: 1,234,567 for £; Indian lakh/crore grouping 12,34,567 for ₹."""
    s = str(abs(units))
    if _current.get() == "INR" and len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        return ",".join(parts) + "," + tail
    return f"{abs(units):,}"


def fmt_money(minor: int | None, signed: bool = False) -> str:
    """123456 -> '£1,234.56' (or '₹1,234.56'). With signed=True, prefixes + or −."""
    if minor is None:
        return "—"
    sign = "-" if minor < 0 else ("+" if signed and minor > 0 else "")
    whole, frac = divmod(abs(minor), 100)
    return f"{sign}{symbol()}{group(whole)}.{frac:02d}"


def fmt_round(minor: int) -> str:
    """Whole units: '£1,235', '₹1,23,457'."""
    return f"{symbol()}{group(round(abs(minor) / 100))}"


fmt_gbp = fmt_money  # older name, kept so existing imports work
