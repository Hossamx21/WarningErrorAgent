import requests
import json
import re
from agent.promptsqnx import ANALYSIS_PROMPT

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "phi3"

def extract_json(text: str) -> dict:
    """
    Extract first JSON object from text safely.
    """
    match = re.search(r"\{", text)
    if not match:
        raise ValueError("No JSON found in model output")
    start = match.start()
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(text[start:])
    return obj

def analyze_errors(error_lines: list[str], warning_lines: list[str] | None = None) -> dict:
    prompt = ANALYSIS_PROMPT + "\n\nBuild Errors:\n"
    prompt += "\n".join(error_lines)

    if warning_lines:
        prompt += "\n\nBuild Warnings:\n"
        prompt += "\n".join(warning_lines)

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }

    resp = requests.post(OLLAMA_URL, json=payload)
    resp.raise_for_status()

    raw_output = resp.json()["message"]["content"]
    with open("raw_model_output.txt", "w", encoding="utf-8") as debug_f:
        debug_f.write(raw_output)

    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        # Fallback for local models
        return extract_json(raw_output)
