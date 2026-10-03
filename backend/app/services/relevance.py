"""Does a post or article actually name the company? Search engines return namesakes and loosely related items."""
import re

MIN_ALIAS_CHARS = 3  # shorter aliases ("GS") match too many unrelated posts to prove relevance


def mentions_company(text: str, company: dict) -> bool:
    names = [company["name"], *(a for a in company.get("aliases") or [] if len(a.strip()) >= MIN_ALIAS_CHARS)]
    return any(re.search(rf"(?<!\w){re.escape(n.strip())}(?!\w)", text, re.I) for n in names if n.strip())


def title_key(title: str) -> str:
    """Normalised headline for spotting the same article from different sources."""
    return re.sub(r"\W+", " ", title.lower()).strip()
