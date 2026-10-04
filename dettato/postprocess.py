import re
from typing import Dict, List, Optional


def apply_replacements(text: str, replacements: Optional[Dict[str, str]]) -> str:
    """User's fixed corrections ("meta ed" -> "Meta Ads"), whole words,
    case-insensitive. Longest first, so "meta ed" wins over "meta"."""
    for wrong in sorted(replacements or {}, key=len, reverse=True):
        if not wrong.strip():
            continue
        right = replacements[wrong]
        pattern = re.compile(r'(?<!\w)' + re.escape(wrong.strip()) + r'(?!\w)', re.IGNORECASE)
        text = pattern.sub(lambda m: right, text)
    return text


def clean_transcript(text: str, filler_words: List[str], replacements: Optional[Dict[str, str]] = None) -> str:
    if not text:
        return ""

    cleaned = text
    for filler in filler_words:
        pattern = re.compile(r'(?<!\w)' + re.escape(filler) + r'(?!\w)', re.IGNORECASE)
        cleaned = pattern.sub("", cleaned)

    cleaned = apply_replacements(cleaned, replacements)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = re.sub(r'\s+([,.!?])', r'\1', cleaned)
    return cleaned
