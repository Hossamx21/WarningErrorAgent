def is_confident(result: dict) -> bool:
    return result.get("confidence", 0) >= 0.75
