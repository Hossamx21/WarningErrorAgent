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

def clean_code_string(code_str: str) -> str:
    """
    Removes hallucinated line numbers from AI output.
    Example: '11: int x = 50' -> 'int x = 50'
    """
    # Remove leading line numbers (e.g., "  11 : ")
    cleaned = re.sub(r'^\s*\d+\s*[:|]\s*', '', code_str, flags=re.MULTILINE)
    return cleaned

def extract_json(text: str) -> dict:
    print("\n--- [DEBUG] RAW AI OUTPUT START ---")
    print(text)
    print("--- [DEBUG] RAW AI OUTPUT END ---\n")

    # 1. Clean up Markdown
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    
    # 2. Try Parsing
    data = {}
    try:
        data = json.loads(text)
    except:
        try:
            data = ast.literal_eval(text)
        except:
            # Last ditch: Find the fixes list regex
            match = re.search(r'"fixes"\s*:\s*(\[.*\])', text, re.DOTALL)
            if match:
                try:
                    data = {"fixes": json.loads(match.group(1))}
                except:
                    pass
    return data

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
                # 1. Fix Filename
                fix["file"] = os.path.normpath(real_filename)
                
                # 2. Remove Hallucinated Line Numbers (The Magic Fix)
                if "original_code" in fix:
                    fix["original_code"] = clean_code_string(fix["original_code"])
                if "replacement_code" in fix:
                    fix["replacement_code"] = clean_code_string(fix["replacement_code"])

    return {"fixes": fixes, "reasoning": reasoning_output}