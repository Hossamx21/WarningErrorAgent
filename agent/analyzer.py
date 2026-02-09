import requests
import json
import re
import os
import ast  #Using Python's own parser as a backup
from agent.prompts import REASONING_PROMPT, JSON_CONVERSION_PROMPT
from agent.context import get_code_snippet 

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "phi3"

def call_ollama(prompt: str, temp: float = 0.2) -> str:
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {
            "temperature": temp, 
            "num_predict": 512,
            "stop": ["User:", "System:"] 
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
    """
    Robust extraction that handles messy AI output.
    """
    # 1. Strip Markdown
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        text = match.group(1)
    
    # 2. Attempt 1: Standard Strict JSON
    try:
        return json.loads(text)
    except:
        pass
        
    # 3. Attempt 2: Python Eval (Forgives single quotes, trailing commas)
    try:
        # This understands {'key': 'val',} which JSON hates
        return ast.literal_eval(text)
    except:
        pass

    # 4. Attempt 3: Aggressive Comma Repair (The most common error)
    try:
        # Regex: Find "string" followed by newline and "string", insert comma
        text_fixed = re.sub(r'\"\s*\n\s*\"', '",\n"', text)
        return json.loads(text_fixed)
    except:
        pass
        
    return {}

def analyze_errors(error_lines: list[str], warning_lines: list[str] = None, root_dir: str = ".") -> dict:
    target_error = error_lines[0]
    
    # Extract filename from error log
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
    # Use 0.0 temperature for maximum strictness
    json_output = call_ollama(json_input, temp=0.0)
    
    result = extract_json(json_output)
    
    fixes = []
    if result and "fixes" in result:
        fixes = result["fixes"]
        
        # Override filename to be safe
        if real_filename:
            for fix in fixes:
                fix["file"] = os.path.normpath(real_filename)
                if "\\" in fix["original_code"]:
                    fix["original_code"] = fix["original_code"].replace("\\", "")

    return {"fixes": fixes, "reasoning": reasoning_output}