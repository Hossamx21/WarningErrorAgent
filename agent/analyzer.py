import requests
import json
import re
from agent.prompts import ANALYSIS_PROMPT
# We will create this context module next to make the "get_code_snippet" function work
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

def analyze_errors(error_lines: list[str], warning_lines: list[str] = None, root_dir: str = ".") -> dict:
    # ---------------------------------------------------------
    # LIMITATION: Small local models (like phi3) struggle with large contexts.
    # We restrict analysis to the first 5 errors and 5 warnings.
    # TODO: Remove or increase this limit if using a larger model (e.g., Llama 3 70b, GPT-4).
    # ---------------------------------------------------------
    MAX_ISSUES = 5
    
    prompt = ANALYSIS_PROMPT + "\n\n### Build Issues with Context:\n"
    
    # 1. Process Errors (High Priority)
    for err in error_lines[:MAX_ISSUES]:
        snippet = get_code_snippet(err, root_dir)
        prompt += f"ERROR: {err}\nCONTEXT:\n{snippet}\n---\n"

    # 2. Process Warnings (Lower Priority)
    if warning_lines:
        for warn in warning_lines[:MAX_ISSUES]:
            snippet = get_code_snippet(warn, root_dir)
            prompt += f"WARNING: {warn}\nCONTEXT:\n{snippet}\n---\n"

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "options": {
            "temperature": 0.2,  # Low temperature for more deterministic code fixes
            "num_ctx": 4096      # Ensure context window is large enough
        },
        "stream": False
    }

    print(f"🧠 Analyzing {min(len(error_lines), MAX_ISSUES)} errors and {min(len(warning_lines or []), MAX_ISSUES)} warnings...")
    
    try:
        resp = requests.post(OLLAMA_URL, json=payload)
        resp.raise_for_status()
        
        raw_output = resp.json()["message"]["content"]
        
        # Debug: Save raw thought process
        with open("logs/model_thought.md", "w", encoding="utf-8") as f:
            f.write(raw_output)

        return extract_json(raw_output)
        
    except Exception as e:
        print(f"❌ AI Analysis Failed: {e}")
        return {"fixes": [], "reasoning": "Model failure"}