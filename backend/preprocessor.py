import re
from typing import List

STOP_WORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
    "is", "are", "was", "were", "be", "by", "at", "from", "as", "this", "that",
    "it", "its", "into", "than", "then", "over", "under", "after", "before",
}


def preprocess_message(message: str) -> str:
    lowered = message.lower()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", lowered)
    tokens = [tok for tok in cleaned.split() if tok and tok not in STOP_WORDS]
    return " ".join(tokens)


def preprocess_records(messages: List[str]) -> List[str]:
    return [preprocess_message(m) for m in messages]