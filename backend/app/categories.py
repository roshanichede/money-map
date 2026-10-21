"""Rule-based categoriser for UK transactions. User-taught rules (MerchantRule) always win.

Money coming in is the hard part, so it's split four ways:
  Salary        - your pay: says SALARY/PAYROLL/WAGES, or a company paying you a similar amount most months
  Other income  - interest, HMRC, invoices, one-off payments from companies
  Paid back     - a person sending their share of something you paid for, with a note saying what ("cab",
                  "rent", "dinner"). NOT income: it's taken off that spending category (Transport, Rent...).
  From people   - a person sending money with no note we understand. Neither earnings nor spending.
Pay usually arrives as BGC (Bank Giro Credit), the code employers' payroll uses, so BGC money is income.
  Transfers     - moving money between your own accounts. Neither income nor spending.
Refunds from a shop keep the shop's category, so they reduce that category's spending.
"""
import re

CATEGORIES = [
    "Groceries", "Eating out", "Takeaways", "Transport", "Bills & utilities", "Rent & housing",
    "Subscriptions", "Shopping", "Entertainment", "Health & fitness", "Personal care", "Travel",
    "Education", "Gifts & charity", "Cash", "Fees & charges", "Card repayments",
    "Salary", "Other income", "From people", "Transfers", "Other",
]
INCOME_CATEGORIES = {"Salary", "Other income"}
# Excluded from both spending and income: your own money moving, and money from people with no clear reason.
NEUTRAL = {"Transfers", "From people"}

# Codes Lloyds and others print at the start of a description when there's no separate type column.
STATEMENT_CODE_RE = re.compile(
    r"^(DD|SO|DEB|FPI|FPO|BGC|TFR|CPT|BP|CHQ|PAY|DEP|COR|FEE|INT|CSH|BACS|DR|CR)\s+(?=\S)")


def split_code(description: str, txn_type: str = "") -> tuple[str, str]:
    """"DD THE GYM LTD" -> ("DD", "THE GYM LTD") when the file has no type column."""
    text = " ".join(description.split())
    m = STATEMENT_CODE_RE.match(text.upper())
    if m and not txn_type:
        return m.group(1), text[m.end():]
    if m and txn_type and m.group(1) == txn_type.upper():
        return txn_type, text[m.end():]
    return (txn_type or "").upper(), text


PAY_CODES = {"BGC", "BACS"}  # how employers' payroll arrives in UK statements
SALARY_RE = re.compile(r"\bSALARY\b|\bSAL\b|PAYROLL|PAY ROLL|\bWAGES?\b|\bPAYE\b|NET PAY")
OTHER_INCOME_RE = re.compile(
    r"INTEREST|DIVIDEND|\bHMRC\b|TAX REFUND|CASHBACK|CASH BACK|\bINVOICE\b|\bINV\b|BONUS|\bDWP\b|"
    r"STUDENT FINANCE|\bSLC\b|BURSARY|SCHOLARSHIP|STIPEND|PENSION|CHILD BENEFIT|UNIVERSAL CREDIT|COMMISSION")
COMPANY_RE = re.compile(
    r"\bLTD\b|LIMITED|\bLIM\b|\bLIMI|\bLTD\.|\bPLC\b|\bLLP\b|\bINC\b|\bCORP|\bGROUP\b|HOLDINGS|SERVICES|SOLUTIONS|"
    r"TECHNOLOG|\bTECH\b|CONSULT|AGENCY|UNIVERSITY|COUNCIL|\bTRUST\b|\bBANK\b|PAYPAL|STRIPE|\bWISE\b|"
    r"AMAZON|\bHMRC\b|\bDWP\b|\bNHS\b|COLLEGE|SCHOOL|ACADEMY|CLINIC|STUDIO|MEDIA|DIGITAL|SYSTEMS|PARTNERS|"
    r"\bUK\b|\bCO\b|\bCIC\b|FOUNDATION|ASSOCIATION|INTERNATIONAL|GLOBAL|VENTURES|CAPITAL|PAYMENTS")

# What a friend's note says they're paying you back for -> the spending it offsets.
PAID_BACK_NOTES: dict[str, str] = {
    "Transport": r"CAB|TAXI|UBER|BOLT|TRAINS?|TUBE|BUS|PETROL|FUEL|PARKING|LIFT|RIDE",
    "Takeaways": r"TAKEAWAY|DELIVEROO|JUST ?EAT",
    "Eating out": r"FOOD|DINNER|LUNCH|BRUNCH|BREAKFAST|DRINKS?|PIZZA|COFFEE|MEAL|RESTAURANT|PUB|NANDOS|CURRY",
    "Groceries": r"GROCER(?:Y|IES)?|TESCO|ALDI|LIDL|SAINSBURY|ASDA",
    "Rent & housing": r"RENT|DEPOSIT",
    "Bills & utilities": r"BILLS?|WIFI|WI-FI|INTERNET|BROADBAND|ELECTRIC(?:ITY)?|GAS|COUNCIL TAX|UTILIT(?:Y|IES)",
    "Entertainment": r"TICKETS?|CINEMA|CONCERT|GIG|MOVIE|FESTIVAL|BOWLING",
    "Travel": r"HOLIDAY|TRIP|HOTEL|FLIGHTS?|AIRBNB|HOSTEL",
    "Gifts & charity": r"GIFT|PRESENT|BIRTHDAY",
}
# Long note words also count when glued to other text ("1STDAYGROCERY"); short ones need a word boundary.
_GLUED_OK = {"Groceries": r"GROCER", "Bills & utilities": r"UTILIT|ELECTRIC|BROADBAND",
             "Eating out": r"DINNER|RESTAURANT", "Takeaways": r"TAKEAWAY|DELIVEROO", "Travel": r"HOLIDAY|AIRBNB"}
_PAID_BACK_RE = {cat: re.compile(r"(?<![A-Z])(?:" + rx + r")(?![A-Z])"
                                 + (("|" + _GLUED_OK[cat]) if cat in _GLUED_OK else ""))
                 for cat, rx in PAID_BACK_NOTES.items()}


def is_company(text: str) -> bool:
    return bool(COMPANY_RE.search(text.upper()))

KEYWORDS: dict[str, list[str]] = {
    "Groceries": ["TESCO", "SAINSBURY", "ASDA", "ALDI", "LIDL", "MORRISONS", "WAITROSE", "CO-OP", "M&S",
                  "OCADO", "ICELAND", "SPAR", "BUDGENS", "FARMFOODS", "WHOLE FOODS", "COSTCO"],
    "Takeaways": ["DELIVEROO", "UBER EATS", "JUST EAT", "DOMINOS", "PAPA JOHNS", "PIZZA HUT DEL"],
    "Eating out": ["PRET", "GREGGS", "COSTA", "STARBUCKS", "CAFFE NERO", "MCDONALD", "NANDO", "KFC",
                   "BURGER KING", "WAGAMAMA", "LEON", "SUBWAY", "PIZZA EXPRESS", "WETHERSPOON",
                   "RESTAURANT", "CAFE", "COFFEE", "BAR ", " PUB", "KITCHEN", "GRILL", "TACO", "SUSHI"],
    "Transport": ["TFL", "TRAINLINE", "UBER", "BOLT", "NATIONAL RAIL", "AVANTI", "LNER", "EAST MIDLANDS",
                  "STAGECOACH", "ARRIVA", "NATIONAL EXPRESS", "MEGABUS", "SHELL", "BP", "ESSO", "PARKING",
                  "RINGGO", "PAYBYPHONE", "DVLA", "LIME", "TRAINS"],
    "Subscriptions": ["NETFLIX", "SPOTIFY", "DISNEY+", "AMAZON PRIME", "PRIME VIDEO", "APPLE", "YOUTUBE",
                      "AUDIBLE", "OPENAI", "ANTHROPIC", "ADOBE", "MICROSOFT", "GOOGLE", "NOW TV", "PATREON",
                      "ICLOUD", "DROPBOX", "NOTION", "CANVA", "LINKEDIN", "DUOLINGO"],
    "Bills & utilities": ["VODAFONE", "EE", "O2", "THREE", "GIFFGAFF", "BT", "VIRGIN MEDIA", "SKY",
                          "BRITISH GAS", "OCTOPUS", "EDF", "E.ON", "OVO", "THAMES WATER", "SEVERN TRENT",
                          "COUNCIL TAX", "TV LICENCE", "WATER", "ENERGY", "INSURANCE", "BROADBAND"],
    "Rent & housing": ["RENT", "LETTING", "LETTINGS", "ESTATE AGENT", "MORTGAGE", "LANDLORD", "OPENRENT"],
    "Shopping": ["AMAZON", "ARGOS", "PRIMARK", "ZARA", "H&M", "ASOS", "IKEA", "EBAY", "VINTED", "JOHN LEWIS",
                 "NEXT", "UNIQLO", "TK MAXX", "CURRYS", "SHEIN", "TEMU", "ETSY", "WHSMITH", "WILKO", "B&M"],
    "Entertainment": ["CINEMA", "ODEON", "VUE", "CINEWORLD", "TICKETMASTER", "STEAM", "PLAYSTATION",
                      "XBOX", "NINTENDO", "EVENTBRITE", "BOWLING", "THEATRE"],
    "Health & fitness": ["PUREGYM", "THE GYM GROUP", "GYM", "BOOTS", "SUPERDRUG", "PHARMACY", "DENTAL",
                         "OPTICIAN", "SPECSAVERS", "NHS", "FITNESS", "YOGA"],
    "Personal care": ["SALON", "BARBER", "HAIR", "BEAUTY", "NAILS", "SPA"],
    "Travel": ["RYANAIR", "EASYJET", "BRITISH AIRWAYS", "AIRBNB", "BOOKING.COM", "HOTEL", "EXPEDIA",
               "JET2", "WIZZ", "TRAVELODGE", "PREMIER INN", "HOSTEL", "AIRLINE", "AIRPORT"],
    "Education": ["UNIVERSITY", "UNI OF", "COURSERA", "UDEMY", "TUITION", "STUDENT"],
    "Gifts & charity": ["DONATION", "CHARITY", "JUSTGIVING", "OXFAM", "RED CROSS", "MOONPIG", "FUNKY PIGEON"],
    "Fees & charges": ["FEE", "CHARGE", "INTEREST", "OVERDRAFT", "PENALTY", "NON-STERLING"],
}
_KEYWORD_RE = {
    cat: re.compile("|".join(r"(?<![A-Z])" + re.escape(k.strip()) + r"(?![A-Z])" for k in words))
    for cat, words in KEYWORDS.items()
}
_ORDER = ["Takeaways", "Subscriptions", "Groceries", "Eating out", "Transport", "Rent & housing",
          "Bills & utilities", "Travel", "Health & fitness", "Personal care", "Entertainment", "Education",
          "Gifts & charity", "Shopping", "Fees & charges"]

# Lloyds transaction type codes
TYPE_TRANSFER = {"TFR"}
TYPE_CASH = {"CPT", "CSH"}
TYPE_FEE = {"FEE", "INT"}
TYPE_DIRECT = {"DD", "SO"}
TYPE_INCOMING = {"BGC", "FPI", "CR", "DEP"}


CARD_REPAYMENT_RE = re.compile(
    r"CREDIT CARD|\bCC PAYMENT|BARCLAYCARD|AMERICAN EXPRESS|\bAMEX\b|CAPITAL ONE|MBNA|VANQUIS|AQUA CARD|"
    r"LLOYDS BANK PLC CARD|JOHN LEWIS FIN")
CARD_PAYMENT_RECEIVED_RE = re.compile(r"PAYMENT RECEIVED|PAYMENT - THANK|PAYMENT THANK YOU|DIRECT DEBIT PAYMENT")


def categorise(description: str, merchant_key: str, txn_type: str, amount_pence: int) -> str:
    code, description = split_code(description, txn_type)
    text = f"{description.upper()} {merchant_key}"
    if amount_pence > 0 and CARD_PAYMENT_RECEIVED_RE.search(text):
        return "Transfers"  # a repayment arriving on a credit card
    if amount_pence < 0 and CARD_REPAYMENT_RE.search(text):
        return "Card repayments"  # counted as spending until the card itself is uploaded
    if code in TYPE_TRANSFER or re.search(r"\bTRANSFER\b|\bSAVINGS\b|\bTO A/C\b|\bFROM A/C\b|\bPOT\b", text):
        return "Transfers"
    if code in TYPE_CASH or re.search(r"\bCASH\b|\bATM\b|\bLINK\b", text):
        return "Cash" if amount_pence < 0 else "Other income"
    if code in TYPE_FEE and amount_pence < 0:
        return "Fees & charges"
    if amount_pence > 0:
        return categorise_money_in(description, merchant_key, code)
    for cat in _ORDER:
        if _KEYWORD_RE[cat].search(text):
            return cat
    if code in ("FPO", "BP", "SO") and not is_company(text):
        for cat, rx in _PAID_BACK_RE.items():  # paying a person: your note says what for ("UTILITIES", "CAB")
            if rx.search(description.upper()):
                return cat
    if code in TYPE_DIRECT:
        return "Bills & utilities"
    return "Other"


def categorise_money_in(description: str, merchant_key: str, code: str = "") -> str:
    text = f"{description.upper()} {merchant_key}"
    if SALARY_RE.search(text):
        return "Salary"
    if OTHER_INCOME_RE.search(text):
        return "Other income"
    if code in PAY_CODES:  # payroll; upgraded to Salary when the same payer pays you in two or more months
        return "Other income"
    company = is_company(text)
    if company:
        for cat in _ORDER:  # a refund from a shop keeps the shop's category
            if _KEYWORD_RE[cat].search(text):
                return cat
        return "Other income"  # upgraded to Salary if the same company pays you most months
    if code in ("CHQ", "DEP"):
        return "Other income"
    if code in CARD_CODES:  # money back onto your card is a shop refund, never a person
        for cat in _ORDER:
            if _KEYWORD_RE[cat].search(text):
                return cat
        return "Other"
    # A person. Their share of something you paid for: take it off that spending.
    for cat, rx in _PAID_BACK_RE.items():
        if rx.search(text):
            return cat
    for cat in _ORDER:
        if _KEYWORD_RE[cat].search(text):
            return cat
    return "From people"


CARD_CODES = {"DEB", "POS", "CD"}
_CARD_REF_RE = re.compile(r"\bCD \d{4}\b")


def is_card_refund(description: str, txn_type: str = "") -> bool:
    code, _ = split_code(description, txn_type)
    return code in CARD_CODES or bool(_CARD_REF_RE.search(description.upper()))


def money_in_kind(category: str, amount_pence: int, description: str, is_transfer: bool,
                  txn_type: str = "") -> str | None:
    """How a positive amount is described in the app."""
    if amount_pence <= 0:
        return None
    if is_transfer or category == "Transfers":
        return "transfer"
    if category == "Salary":
        return "salary"
    if category == "Other income":
        return "income"
    if category == "From people":
        return "from_person"
    return "refund" if is_company(description) or is_card_refund(description, txn_type) else "paid_back"
