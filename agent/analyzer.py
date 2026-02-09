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
            "stop": ["User:", "System:"] # Removed ``` from stop tokens so we can catch markdown
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
    Robust JSON extraction that handles Markdown blocks and messy text.
    """
    try:
        # 1. Try to find content inside ```json ... ``` blocks first
        code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if code_block:
            text = code_block.group(1)
        
        # 2. If no block, just find the first '{' and the last '}'
        else:
            match_start = re.search(r"\{", text)
            match_end = re.search(r"\}", text[::-1]) # Search from end
            
            if not match_start or not match_end:
                return {}
            
            start = match_start.start()
            end = len(text) - match_end.start()
            text = text[start:end]

        # 3. Decode
        return json.loads(text)
    except Exception as e:
        print(f"⚠️ JSON Parse Error: {e}")
        return {}

def analyze_errors(error_lines: list[str], warning_lines: list[str] = None, root_dir: str = ".") -> dict:
    # 1. Select the first error to fix
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
    
    # Debug: Print what the model actually gave us
    # print(f"DEBUG RAW JSON: {json_output}")

    result = extract_json(json_output)
    
    # --- RETRY LOGIC ---
    # If extraction failed, try one more time asking nicely
    if not result:
        print("⚠️  Invalid JSON received. Retrying conversion step...")
        retry_input = json_input + "\n\nIMPORTANT: Your previous output was invalid. Output ONLY the raw JSON object. No text."
        json_output = call_ollama(retry_input, temp=0.1)
        result = extract_json(json_output)

    fixes = []
    if "fixes" in result:
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