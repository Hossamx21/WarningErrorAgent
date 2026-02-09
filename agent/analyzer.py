import requests
import json
import re
from agent.prompts import ANALYSIS_PROMPT
from agent.context import get_code_snippet 

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "phi3"

# We will create this context module next to make the "get_code_snippet" function work
# LIMITATION: Small local models (like phi3) struggle with large contexts.
# We restrict analysis to the first 5 errors and 5 warnings.
# TODO: Remove or increase this limit if using a larger model (e.g., Llama 3 70b, GPT-4).

def extract_json(text: str) -> dict:
    """Extract first JSON object from text safely."""
    try:
        match = re.search(r"\{", text)
        if not match:
            return {"fixes": [], "reasoning": "No JSON found in output"}
        start = match.start()
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(text[start:])
        return obj
    except Exception:
        return {"fixes": [], "reasoning": "JSON parsing failed"}

def analyze_errors(error_lines: list[str], warning_lines: list[str] = None, root_dir: str = ".") -> dict:
    # 1. LIMIT CONTEXT (Prevent freezing on large logs)
    MAX_ISSUES = 5
    
    prompt = ANALYSIS_PROMPT + "\n\n### Build Issues with Context:\n"
    
    # 2. ADD SOURCE CODE CONTEXT
    # We loop through errors and fetch the actual code lines so the AI sees the bug.
    for err in error_lines[:MAX_ISSUES]:
        snippet = get_code_snippet(err, root_dir)
        prompt += f"ERROR: {err}\nCONTEXT:\n{snippet}\n---\n"

    if warning_lines:
        for warn in warning_lines[:MAX_ISSUES]:
            snippet = get_code_snippet(warn, root_dir)
            prompt += f"WARNING: {warn}\nCONTEXT:\n{snippet}\n---\n"

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        # 3. SAFETY SETTINGS
        "options": {
            "num_predict": 1024,   # Stop generating after ~750 words
            "temperature": 0.2,    # Low creativity (better for code)
            "stop": ["```\n\n", "User:", "System:"] 
        }
    }

    print(f"⏳ Sending request to {MODEL} (timeout 120s)...")
    
    try:
        # 4. TIMEOUT (Prevents hanging forever)
        resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
        resp.raise_for_status()
        
        raw_output = resp.json()["message"]["content"]
        
        # Debug logging
        with open("logs/model_last_run.txt", "w", encoding="utf-8") as f:
            f.write(raw_output)

        return extract_json(raw_output)
        
    except requests.exceptions.Timeout:
        print("⏰ Error: Model took too long. Skipping this attempt.")
        return {"fixes": [], "reasoning": "Timeout"}
    except Exception as e:
        print(f"💥 Error: {e}")
        return {"fixes": [], "reasoning": str(e)}