import requests
import json
import re
from agent.prompts import ANALYSIS_PROMPT
# We will create this context module next to make the "get_code_snippet" function work
# LIMITATION: Small local models (like phi3) struggle with large contexts.
# We restrict analysis to the first 5 errors and 5 warnings.
# TODO: Remove or increase this limit if using a larger model (e.g., Llama 3 70b, GPT-4).
from agent.context import get_code_snippet 

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "phi3"

def extract_json(text: str) -> dict:
    """Extract first JSON object from text safely."""
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
        "stream": False,
        # SAFETY FIX 1: Limit the "thinking" capacity
        "options": {
            "num_predict": 1024,   # Stop after ~750 words
            "temperature": 0.2,    # Be more precise/deterministic
            "stop": ["```\n\n", "User:", "System:"] # Stop if it tries to roleplay
        }
    }

    print(f"⏳ Sending request to {MODEL} (timeout set to 120s)...")
    
    try:
        # SAFETY FIX 2: specific timeout so it doesn't hang forever
        resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
        resp.raise_for_status()

        raw_output = resp.json()["message"]["content"]
        
        # Debug: Save what the model actually said
        with open("raw_model_last_run.txt", "w", encoding="utf-8") as debug_f:
            debug_f.write(raw_output)

        return extract_json(raw_output)
        
    except requests.exceptions.Timeout:
        print("⏰ Error: Model took too long to respond.")
        return {"fixes": [], "confidence": 0}
    except Exception as e:
        print(f"💥 Error communicating with Ollama: {e}")
        return {"fixes": [], "confidence": 0}