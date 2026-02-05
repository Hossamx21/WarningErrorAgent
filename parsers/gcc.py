import re

ERROR_PATTERNS = [
    r"error:",
    r"fatal error:",
    r"undefined reference",
    r"ld: error",
    r"collect2:"
]

WARNING_PATTERNS = [
    r"warning:",
    r"-W[A-Za-z-]+",
    r"deprecated",
    r"may be used uninitialized",
    r"unused (variable|parameter|function)",
]

def extract_gcc_errors(log_text: str, max_lines=200):
    lines = log_text.splitlines()
    matched = []

    for line in lines:
        if any(re.search(p, line, re.IGNORECASE) for p in ERROR_PATTERNS):
            matched.append(line)

    return matched[:max_lines]


def extract_gcc_issues(log_text: str, max_lines=200):
    """
    Returns:
        errors, warnings
    """
    errors = []
    warnings = []

    for line in log_text.splitlines():
        if any(re.search(p, line, re.IGNORECASE) for p in ERROR_PATTERNS):
            errors.append(line)

        elif any(re.search(p, line, re.IGNORECASE) for p in WARNING_PATTERNS):
            warnings.append(line)

        if len(errors) + len(warnings) >= max_lines:
            break

    return errors, warnings
