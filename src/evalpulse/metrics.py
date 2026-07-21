import re


def normalize(value: str) -> str:
    return " ".join(re.findall(r"\w+", value.casefold(), flags=re.UNICODE))


def exact_match(actual: str, expected: str) -> float:
    return float(normalize(actual) == normalize(expected))


def token_overlap(actual: str, expected: str) -> float:
    actual_tokens = set(normalize(actual).split())
    expected_tokens = set(normalize(expected).split())
    if not expected_tokens:
        return float(not actual_tokens)
    return len(actual_tokens & expected_tokens) / len(expected_tokens)
