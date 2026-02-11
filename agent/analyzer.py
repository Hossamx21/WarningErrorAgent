import requests
import json
import re
import os
import ast
from agent.prompts import REASONING_PROMPT, JSON_CONVERSION_PROMPT
from agent.context import get_code_snippet 

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5-coder:7b" # Ensuring we use the good model

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

def clean_code_string(code_str: str) -> str:
    """Removes hallucinated line numbers."""
    cleaned = re.sub(r'^\s*\d+\s*[:|]\s*', '', code_str, flags=re.MULTILINE)
    return cleaned

def repair_json_string(text: str) -> str:
    """
    Fixes common JSON errors from LLMs:
    1. Escapes newlines inside string values.
    2. Fixes trailing commas.
    """
    # Helper to escape newlines inside a specific matched group
    def escape_newlines(m):
        return m.group(0).replace('\n', '\\n').replace('\r', '')

    # Regex: Find "key": "value" patterns where value might span lines
    # We target specific keys to avoid breaking the structure
    text = re.sub(
        r'("original_code"\s*:\s*".*?")', 
        escape_newlines, 
        text, 
        flags=re.DOTALL
    )
    text = re.sub(
        r'("replacement_code"\s*:\s*".*?")', 
        escape_newlines, 
        text, 
        flags=re.DOTALL
    )
    return text

def extract_json(text: str) -> dict:
    print("\n--- [DEBUG] RAW AI OUTPUT START ---")
    print(text)
    print("--- [DEBUG] RAW AI OUTPUT END ---\n")

    # 1. Clean up Markdown
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    
    # 2. PRE-PROCESS: Repair Newlines
    text = repair_json_string(text)
    
    # 3. Try Parsing
    try:
        return json.loads(text)
    except:
        try:
            return ast.literal_eval(text)
        except:
            pass
    return {}

def analyze_errors(error_lines: list[str], warning_lines: list[str] = None, root_dir: str = ".") -> dict:
    if not error_lines:
        return {"fixes": [], "reasoning": "No errors"}
        
    target_error = error_lines[0]
    
    # Extract filename
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
    json_output = call_ollama(json_input, temp=0.0)
    
    result = extract_json(json_output)
    
    fixes = []
    if result and "fixes" in result:
        fixes = result["fixes"]
        
        # --- CRITICAL FIXES ---
        if real_filename:
            for fix in fixes:
                fix["file"] = os.path.normpath(real_filename)
                
                # Run the cleaners
                if "original_code" in fix:
                    fix["original_code"] = clean_code_string(fix["original_code"])
                if "replacement_code" in fix:
                    fix["replacement_code"] = clean_code_string(fix["replacement_code"])

    return {"fixes": fixes, "reasoning": reasoning_output}