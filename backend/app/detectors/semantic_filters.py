import re


FALSE_PERSON_PHRASES = {
    "red herring prospectus",
    "risk factors",
    "board of directors",
    "book running lead managers",
    "general information",
    "offer price",
    "equity shares",
    "qualified institutional buyers",
    "retail individual investors",
    "companies act",
    "corporate governance",
    "financial statements",
    "risk management committee",
    "reference rate",
    "selling shareholders",
    "promoter selling shareholders",
    "statutory disclosures",
    "our management",
    "foreign trade",
    "absolute responsibility",
    "average cost of acquisition",
    "mutual funds",
    "promoter trusts",
    "share transfer agents",
    "qib bidders",
    "taluka khed",
    "executive directors",
}

FALSE_COMPANY_PHRASES = {
    "board of directors",
    "audit committee",
    "risk management committee",
    "government of india",
    "government of maharashtra",
    "registrar of companies",
    "companies act",
    "sebi icdr regulations",
    "sebi",
    "securities and exchange board of india",
    "reserve bank of india",
    "stock exchanges",
    "qualified institutional buyers",
    "securities contracts regulation rules",
    "securities transaction tax",
    "key management personnel",
    "education management information system",
    "refund bank",
    "public offer account bank",
    "sponsor banks",
    "bank balances",
    "private final consumption expenditure",
    "short term bank facilities",
}

GENERIC_DOMAIN_TERMS = {
    "offer",
    "board",
    "committee",
    "regulations",
    "prospectus",
    "equity shares",
    "risk factors",
    "financial statements",
    "shareholders",
    "disclosures",
    "facility",
    "funds",
    "trusts",
    "branch",
    "rate",
    "responsibility",
    "acquisition",
    "foreign trade",
    "management",
    "agents",
    "bidders",
    "taluka",
    "website",
}

ROLE_STOP_PATTERN = re.compile(
    r"\b(?:Company Secretary|Compliance Officer|Chief Financial Officer|Chief Executive Officer|"
    r"Managing Director|Director|Auditor|Chairman|CFO|CEO)\b",
    re.IGNORECASE,
)


def normalize_phrase(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.strip(" \t\r\n,;:.()[]{}")).lower()
    return re.sub(r"^(?:the|a|an|our)\s+", "", normalized)


def trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start] in " \t\r\n,;:()[]{}":
        start += 1
    while end > start and text[end - 1] in " \t\r\n,;:()[]{}.":
        end -= 1
    return start, end


def is_false_person(value: str) -> bool:
    normalized = normalize_phrase(value)
    if normalized in FALSE_PERSON_PHRASES:
        return True
    if re.search(r"\b(?:number|id|code|reference|registration|certificate|application|account)s?$", normalized):
        return True
    return any(term == normalized or term in normalized for term in GENERIC_DOMAIN_TERMS)


def is_false_company(value: str) -> bool:
    normalized = normalize_phrase(value)
    if normalized in FALSE_COMPANY_PHRASES:
        return True
    return (
        normalized.endswith(" committee")
        or normalized.startswith("committee ")
        or normalized.endswith(" rules")
        or normalized.endswith(" tax")
        or normalized.endswith(" branch")
        or normalized.endswith(" balances")
        or normalized.endswith(" facilities")
        or normalized.endswith(" expenditure")
        or " vendor" in normalized
        or "securities and exchange board" in normalized
        or "foreign exchange management" in normalized
        or "finance department" in normalized
        or "management personnel" in normalized
        or normalized.endswith("information system")
    )


def is_name_like(value: str) -> bool:
    cleaned = value.strip()
    if is_false_person(cleaned):
        return False
    parts = cleaned.replace("-", " ").split()
    if not 2 <= len(parts) <= 5:
        return False
    for part in parts:
        if re.fullmatch(r"[A-Z]\.", part):
            continue
        if not re.fullmatch(r"[A-Z][A-Za-z']{1,}", part):
            return False
    return True
