import requests
import json
import re
import os
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
            "num_predict": 512,
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
    # 1. Select the first error to fix
    target_error = error_lines[0]
    
    # 2. Extract the REAL filename from the error message immediately
    # Pattern looks for "path/to/file.c:10:..."
    file_match = re.search(r"([^:\s]+):(\d+):", target_error)
    real_filename = file_match.group(1) if file_match else ""
    
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
    json_output = call_ollama(json_input, temp=0.1)
    
    result = extract_json(json_output)
    
    fixes = []
    if "fixes" in result:
        fixes = result["fixes"]
        
        # --- CRITICAL FIX: OVERWRITE FILENAME ---
        # The AI often hallucinates "filename.c". We force the real filename here.
        if real_filename:
            for fix in fixes:
                # Use absolute path from error log, or relative if needed.
                # Since fixer.py uses os.path.join, passing the full path usually works fine on Windows.
                fix["file"] = real_filename
                
                # Cleanup: Ensure we don't accidentally escape backslashes twice
                if "\\" in fix["original_code"]:
                    fix["original_code"] = fix["original_code"].replace("\\", "")

    return {"fixes": fixes, "reasoning": reasoning_output}