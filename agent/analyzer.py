import requests
import json
import re
from agent.prompts import REASONING_PROMPT, JSON_CONVERSION_PROMPT
from agent.context import get_code_snippet 

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "phi3"

def call_ollama(prompt: str, temp: float = 0.2) -> str:
    """Helper to send requests to Ollama."""
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {
            "temperature": temp, 
            "num_predict": 512, # Keep it short
            "stop": ["```\n\n", "User:", "System:"]
        }
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=300)
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except Exception as e:
        print(f"💥 Ollama Error: {e}")
        return ""

def extract_json(text: str) -> dict:
    """Extract JSON safely."""
    try:
        match = re.search(r"\{", text)
        if not match: return {}
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(text[match.start():])
        return obj
    except:
        return {}

def analyze_errors(error_lines: list[str], warning_lines: list[str] = None, root_dir: str = ".") -> dict:
    fixes = []
    
    # Process only the FIRST error to ensure success (One-at-a-time strategy)
    # Once this works, we can loop through more.
    target_error = error_lines[0]
    snippet = get_code_snippet(target_error, root_dir)
    
    print(f"🕵️  Step 1: Reasoning about: {target_error}")
    
    # --- PHASE 1: REASONING ---
    reasoning_input = f"{REASONING_PROMPT}\n\nERROR: {target_error}\nCONTEXT:\n{snippet}"
    reasoning_output = call_ollama(reasoning_input, temp=0.3)
    
    if not reasoning_output:
        return {"fixes": [], "reasoning": "Model failed to reason"}

    print("📝 Step 2: Converting to JSON...")
    
    # --- PHASE 2: JSON CONVERSION ---
    json_input = f"{JSON_CONVERSION_PROMPT}\n\nCONTEXT:\n{snippet}\n\nPROPOSED FIX:\n{reasoning_output}"
    json_output = call_ollama(json_input, temp=0.1) # Low temp for strict format
    
    # Save debug logs
    with open("logs/debug_reasoning.txt", "w", encoding="utf-8") as f:
        f.write(reasoning_output)
    with open("logs/debug_json.txt", "w", encoding="utf-8") as f:
        f.write(json_output)

    result = extract_json(json_output)
    
    # If the model returned a list of fixes wrapped in a dict
    if "fixes" in result:
        fixes = result["fixes"]
    
    return {"fixes": fixes, "reasoning": reasoning_output}