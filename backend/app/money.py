def fmt_gbp(pence: int | None, signed: bool = False) -> str:
    """123456 -> '£1,234.56'. With signed=True, prefixes + or −."""
    if pence is None:
        return "—"
    sign = ""
    if pence < 0:
        sign = "-"
    elif signed and pence > 0:
        sign = "+"
    return f"{sign}£{abs(pence) / 100:,.2f}"
