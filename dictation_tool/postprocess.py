import re
from typing import List


def clean_transcript(text: str, filler_words: List[str]) -> str:
    if not text:
        return ""

    cleaned = text
    for filler in filler_words:
        pattern = re.compile(r'(?<!\w)' + re.escape(filler) + r'(?!\w)', re.IGNORECASE)
        cleaned = pattern.sub("", cleaned)

    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = re.sub(r'\s+([,.!?])', r'\1', cleaned)
    return cleaned
