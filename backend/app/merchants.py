"""Turn raw bank descriptions into a stable merchant key and a readable name.

"TESCO STORES 3021 CD 1234"      -> key TESCO STORES   name Tesco Stores
"PAYPAL *NETFLIX.COM 4029357733" -> key NETFLIX        name Netflix
"DELIVEROO PLUS LONDON GB"       -> key DELIVEROO      name Deliveroo
"""
import re

_LONG_NUMBER = re.compile(r"(?<!\d)(\d[\d ]{6,22}\d)(?!\d)")


def mask_numbers(description: str) -> str:
    """Hide account and card numbers that banks print in descriptions: "FROM A/C 12345678" -> "FROM A/C ••5678".
    Runs of 8+ digits (spaces allowed, as in card numbers) keep only their last four."""
    def repl(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(1))
        return f"••{digits[-4:]}" if len(digits) >= 8 else m.group(1)
    return _LONG_NUMBER.sub(repl, description)


_TRANSFER = re.compile(r"^(TO|FROM)\s+A/?C\b\s*(?:••)?(\d{4})?", re.I)

# Known brands: if the cleaned description contains the pattern, use this key and name.
BRANDS: list[tuple[str, str]] = [
    (r"\bAMZN|\bAMAZON", "Amazon"), (r"\bNETFLIX", "Netflix"), (r"\bSPOTIFY", "Spotify"),
    (r"\bDISNEY", "Disney+"), (r"\bAPPLE\.COM|\bAPPLE COM|\bITUNES", "Apple"),
    (r"\bGOOGLE", "Google"), (r"\bDELIVEROO", "Deliveroo"), (r"\bUBER\s*\*?\s*EATS|\bUBEREATS", "Uber Eats"),
    (r"\bUBER\b", "Uber"), (r"\bJUST ?EAT", "Just Eat"), (r"\bTFL\b|TRANSPORT FOR LONDON", "TfL"),
    (r"\bTRAINLINE", "Trainline"), (r"\bTESCO", "Tesco"), (r"\bSAINSBURY", "Sainsbury's"),
    (r"\bASDA\b", "Asda"), (r"\bALDI\b", "Aldi"), (r"\bLIDL\b", "Lidl"), (r"\bMORRISONS", "Morrisons"),
    (r"\bWAITROSE", "Waitrose"), (r"\bCO-?OP\b", "Co-op"), (r"\bM ?& ?S\b|MARKS ?& ?SPENCER|MARKS AND SPENCER", "M&S"),
    (r"\bOCADO", "Ocado"), (r"\bICELAND\b", "Iceland"), (r"\bPRET\b", "Pret"), (r"\bGREGGS", "Greggs"),
    (r"\bCOSTA\b", "Costa"), (r"\bSTARBUCKS", "Starbucks"), (r"\bMCDONALD", "McDonald's"),
    (r"\bNANDO", "Nando's"), (r"\bBOOTS\b", "Boots"), (r"\bSUPERDRUG", "Superdrug"),
    (r"\bPRIMARK", "Primark"), (r"\bZARA\b", "Zara"), (r"\bH ?& ?M\b", "H&M"), (r"\bASOS", "ASOS"),
    (r"\bARGOS", "Argos"), (r"\bIKEA", "IKEA"), (r"\bEBAY", "eBay"), (r"\bVINTED", "Vinted"),
    (r"\bPUREGYM|PURE GYM", "PureGym"), (r"\bGYM ?GROUP", "The Gym Group"), (r"\bVODAFONE", "Vodafone"),
    (r"\bEE LIMITED|\bEE LTD|\bEE\b", "EE"), (r"\bO2\b|TELEFONICA", "O2"), (r"\bTHREE\b|HUTCHISON", "Three"),
    (r"\bGIFFGAFF", "giffgaff"), (r"\bBT GROUP|\bBT\b", "BT"), (r"\bVIRGIN MEDIA", "Virgin Media"),
    (r"\bSKY\b", "Sky"), (r"BRITISH GAS", "British Gas"), (r"\bOCTOPUS", "Octopus Energy"),
    (r"\bEDF\b", "EDF"), (r"\bE\.?ON\b", "E.ON"), (r"\bOVO\b", "OVO"), (r"THAMES WATER", "Thames Water"),
    (r"SEVERN TRENT", "Severn Trent"), (r"COUNCIL|CNCL|\bC TAX|COUNCIL TAX", "Council Tax"),
    (r"TV LICEN", "TV Licence"), (r"\bRYANAIR", "Ryanair"), (r"\bEASYJET", "easyJet"),
    (r"BRITISH AIRWAYS|\bBA\.COM", "British Airways"), (r"\bAIRBNB", "Airbnb"), (r"BOOKING\.COM", "Booking.com"),
    (r"\bSHELL\b", "Shell"), (r"\bBP\b", "BP"), (r"\bESSO\b", "Esso"), (r"\bCHATGPT|OPENAI", "OpenAI"),
    (r"\bANTHROPIC|CLAUDE\.AI", "Anthropic"), (r"\bMICROSOFT", "Microsoft"), (r"\bADOBE", "Adobe"),
    (r"\bAUDIBLE", "Audible"), (r"\bYOUTUBE", "YouTube"), (r"\bPAYPAL", "PayPal"),
]
_BRANDS = [(re.compile(p), name) for p, name in BRANDS]

_NOISE = [
    re.compile(r"\bCD \d{4}\b.*$"),                 # Lloyds card suffix: "CD 1234 ..."
    re.compile(r"\b\d{2}[A-Z]{3}\d{2}\b"),           # dates like 01OCT26
    re.compile(r"\b\d{2}/\d{2}(/\d{2,4})?\b"),
    re.compile(r"\bON \d{1,2} [A-Z]{3}\b"),
    re.compile(r"\b(GB|GBR|UK|IE|US|USA)\b$"),
    re.compile(r"\bCONTACTLESS\b|\bCLP\b|\bVIS\b|\bPOS\b|\bCARD PAYMENT TO\b|\bDEBIT CARD\b"),
    re.compile(r"\b[A-Z]*\d[A-Z\d]{5,}\b"),          # reference codes / long numbers
    re.compile(r"\b\d+\b"),
    re.compile(r"[*#]+"),
]
_LOCATIONS = {"LONDON", "LEICESTER", "MANCHESTER", "BIRMINGHAM", "LEEDS", "GLASGOW", "EDINBURGH",
              "BRISTOL", "LIVERPOOL", "NOTTINGHAM", "SHEFFIELD", "CARDIFF", "LUXEMBOURG", "DUBLIN",
              "INTERNET", "WWW", "COM", "GB", "UK"}


def normalise(description: str) -> tuple[str, str]:
    """Return (merchant_key, display_name)."""
    from .categories import split_code

    text = split_code(" ".join(description.upper().split()))[1]
    transfer = _TRANSFER.match(text)
    if transfer:
        direction = "to" if transfer.group(1) == "TO" else "from"
        last4 = transfer.group(2)
        name = f"Transfer {direction} ••{last4}" if last4 else f"Transfer {direction} another account"
        return name.upper(), name
    if text.startswith("PAYPAL *") or text.startswith("PAYPAL*"):
        rest = text.split("*", 1)[1].strip()
        text = rest or text
    for pattern, name in _BRANDS:
        if pattern.search(text):
            return name.upper(), name
    cleaned = text
    for pattern in _NOISE:
        cleaned = pattern.sub(" ", cleaned)
    cleaned = re.sub(r"\.(COM|CO\.UK|CO|UK)\b", " ", cleaned)
    words = [w for w in re.split(r"[\s,/]+", cleaned) if w and w.strip(".-'")]
    while len(words) > 1 and words[-1] in _LOCATIONS:
        words.pop()
    words = words[:4]
    key = " ".join(words).strip(" .-") or text[:40]
    display = " ".join(w.capitalize() if len(w) > 3 else w for w in key.split())
    return key[:120], display[:120]
