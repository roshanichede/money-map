"""Rule-based categoriser for UK transactions. User-taught rules (MerchantRule) always win."""
import re

CATEGORIES = [
    "Groceries", "Eating out", "Takeaways", "Transport", "Bills & utilities", "Rent & housing",
    "Subscriptions", "Shopping", "Entertainment", "Health & fitness", "Personal care", "Travel",
    "Education", "Gifts & charity", "Cash", "Fees & charges", "Income", "Transfers", "Other",
]
# Categories excluded from "spending" and "income" totals (money moving between your own pots).
NEUTRAL = {"Transfers"}

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
    "Income": ["SALARY", "PAYROLL", "WAGES", "HMRC", "REFUND", "DIVIDEND", "INVOICE"],
}
_KEYWORD_RE = {
    cat: re.compile("|".join(r"(?<![A-Z])" + re.escape(k.strip()) + r"(?![A-Z])" for k in words))
    for cat, words in KEYWORDS.items()
}
_ORDER = ["Income", "Takeaways", "Subscriptions", "Groceries", "Eating out", "Transport", "Rent & housing",
          "Bills & utilities", "Travel", "Health & fitness", "Personal care", "Entertainment", "Education",
          "Gifts & charity", "Shopping", "Fees & charges"]

# Lloyds transaction type codes
TYPE_TRANSFER = {"TFR"}
TYPE_CASH = {"CPT", "CSH"}
TYPE_FEE = {"FEE", "INT"}
TYPE_DIRECT = {"DD", "SO"}
TYPE_INCOMING = {"BGC", "FPI", "CR", "DEP"}


def categorise(description: str, merchant_key: str, txn_type: str, amount_pence: int) -> str:
    text = f"{description.upper()} {merchant_key}"
    code = (txn_type or "").upper()
    if code in TYPE_TRANSFER or re.search(r"\bTRANSFER\b|\bSAVINGS\b|\bTO A/C\b|\bFROM A/C\b|\bPOT\b", text):
        return "Transfers"
    if code in TYPE_CASH or re.search(r"\bCASH\b|\bATM\b|\bLINK\b", text):
        return "Cash"
    if code in TYPE_FEE:
        return "Fees & charges"
    if amount_pence > 0:
        if _KEYWORD_RE["Income"].search(text) or code in TYPE_INCOMING:
            return "Income"
        for cat in _ORDER:
            if cat != "Income" and _KEYWORD_RE[cat].search(text):
                return cat  # refund from a merchant keeps the merchant's category
        return "Income"
    for cat in _ORDER:
        if cat == "Income":
            continue
        if _KEYWORD_RE[cat].search(text):
            return cat
    if code in TYPE_DIRECT:
        return "Bills & utilities"
    return "Other"
