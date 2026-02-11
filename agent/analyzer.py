import requests
import json
import re
import os
import ast
from agent.prompts import REASONING_PROMPT, JSON_CONVERSION_PROMPT
from agent.context import get_code_snippet 

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5-coder:7b"

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
    def escape_newlines(m):
        return m.group(0).replace('\n', '\\n').replace('\r', '')

    text = re.sub(r'("original_code"\s*:\s*".*?")', escape_newlines, text, flags=re.DOTALL)
    text = re.sub(r'("replacement_code"\s*:\s*".*?")', escape_newlines, text, flags=re.DOTALL)
    return text

def extract_json(text: str) -> dict:
    print("\n--- [DEBUG] RAW AI OUTPUT START ---")
    print(text)
    print("--- [DEBUG] RAW AI OUTPUT END ---\n")

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match: text = match.group(1)
    
    text = repair_json_string(text)
    
    try: return json.loads(text)
    except:
        try: return ast.literal_eval(text)
        except: pass
    return {}

def analyze_errors(error_lines: list[str], warning_lines: list[str] = None, root_dir: str = ".") -> dict:
    if not error_lines: return {"fixes": [], "reasoning": "No errors"}
        
    target_error = error_lines[0]
    file_match = re.search(r"([^:\s]+):(\d+):", target_error)
    real_filename = file_match.group(1) if file_match else ""
    snippet = get_code_snippet(target_error, root_dir)
    
    print(f"🕵️  Step 1: Reasoning about: {target_error}")
    
    # PHASE 1: REASONING
    reasoning_input = f"{REASONING_PROMPT}\n\nERROR: {target_error}\nCONTEXT:\n{snippet}"
    reasoning_output = call_ollama(reasoning_input, temp=0.3)
    if not reasoning_output: return {"fixes": [], "reasoning": "Model failed"}

    print("📝 Step 2: Converting to JSON...")
    
    # PHASE 2: JSON
    json_input = f"{JSON_CONVERSION_PROMPT}\n\nCONTEXT:\n{snippet}\n\nPROPOSED FIX:\n{reasoning_output}"
    json_output = call_ollama(json_input, temp=0.0)
    
    result = extract_json(json_output)
    
    valid_fixes = []
    if result and "fixes" in result:
        for fix in result["fixes"]:
            # --- FILTER: REJECT SKIPPED CODE HALLUCINATIONS ---
            if "[SKIPPED CODE]" in fix.get("original_code", ""):
                print("⚠️  Rejecting fix: contains '[SKIPPED CODE]' placeholder.")
                continue

            if real_filename:
                fix["file"] = os.path.normpath(real_filename)
                
            if "original_code" in fix:
                fix["original_code"] = clean_code_string(fix["original_code"])
            if "replacement_code" in fix:
                fix["replacement_code"] = clean_code_string(fix["replacement_code"])
                
            valid_fixes.append(fix)

    return {"fixes": valid_fixes, "reasoning": reasoning_output}