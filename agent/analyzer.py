import requests
import json
import re
import os
import ast
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
    print("\n--- [DEBUG] RAW AI OUTPUT START ---")
    print(text)
    print("--- [DEBUG] RAW AI OUTPUT END ---\n")

    # 1. Clean up Markdown (```json ... ```)
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    
    # 2. Attempt 1: Standard JSON
    try:
        return json.loads(text)
    except:
        pass
        
    # 3. Attempt 2: Python Literal Eval (Handles single quotes)
    try:
        return ast.literal_eval(text)
    except:
        pass

    # 4. Attempt 3: "Dirty" Extraction (Find the fixes list manually)
    # Sometimes the model just outputs: "fixes": [ ... ] without the curly braces
    try:
        match = re.search(r'"fixes"\s*:\s*(\[.*\])', text, re.DOTALL)
        if match:
            list_text = match.group(1)
            # Try to parse just the list
            fixes_list = json.loads(list_text)
            return {"fixes": fixes_list}
    except:
        pass
        
    return {}

def analyze_errors(error_lines: list[str], warning_lines: list[str] = None, root_dir: str = ".") -> dict:
    # 1. Select the first error to fix
    if not error_lines:
        return {"fixes": [], "reasoning": "No errors found"}
        
    target_error = error_lines[0]
    
    # 2. Extract the REAL filename from the error message immediately
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
    if result and "fixes" in result:
        fixes = result["fixes"]
        
        # --- CRITICAL FIX: OVERWRITE FILENAME ---
        if real_filename:
            for fix in fixes:
                # Use os.path.normpath to fix mix of / and \
                fix["file"] = os.path.normpath(real_filename)
                
                # Cleanup: Ensure we don't accidentally escape backslashes twice
                if "\\" in fix["original_code"]:
                    fix["original_code"] = fix["original_code"].replace("\\", "")

    return {"fixes": fixes, "reasoning": reasoning_output}