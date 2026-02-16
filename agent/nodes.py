import os
import subprocess
import uuid
from pathlib import Path
from typing import Dict, Any

from agent.state import AgentState
# IMPORT PARSER HERE
from agent.llm import fix_chain, parser 
from agent.rag import search_codebase 
from agent.context import get_code_snippet 

# --- CONFIGURATION ---
GCC_PATH = r"D:\eaton-ut\GCC-140200-64\GCC-140200-64\bin\gcc.exe"
if os.path.exists(GCC_PATH):
    os.environ["PATH"] += os.pathsep + str(Path(GCC_PATH).parent)

TESTCODE_DIR = Path("testcode").resolve()
# NOTE: We now build test.c AND math_utils.c together!
BUILD_CMD = f'"{GCC_PATH}" "{TESTCODE_DIR / "test.c"}" "{TESTCODE_DIR / "math_utils.c"}" -o "{TESTCODE_DIR / "test_app"}" -Wall'


# --- NODE 1: CHECK WORKSPACE ---
def check_workspace_node(state: AgentState) -> Dict[str, Any]:
    res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    return {"workspace_clean": not bool(res.stdout.strip())}


# --- NODE 2: CREATE BRANCH ---
def create_branch_node(state: AgentState) -> Dict[str, Any]:
    branch_name = f"ai-fix-{uuid.uuid4().hex[:8]}"
    subprocess.run(["git", "checkout", "-b", branch_name], check=False)
    print(f"🛡️  Switched to branch: {branch_name}")
    return {"branch_name": branch_name}


# --- NODE 3: RUN BUILD ---
def run_build_node(state: AgentState) -> Dict[str, Any]:
    print("🔨 Running build...")
    res = subprocess.run(BUILD_CMD, capture_output=True, text=True, shell=True)
    logs = res.stdout + "\n" + res.stderr
    
    errors = []
    warnings = []
    for line in logs.splitlines():
        if ": error:" in line or ": fatal error:" in line:
            errors.append(line.strip())
        elif ": warning:" in line:
            warnings.append(line.strip())
            
    success = (res.returncode == 0)
    print(f"Build Success: {success} | Errors: {len(errors)}")
    
    return {
        "build_success": success,
        "build_logs": logs,
        "error_lines": errors,
        "warning_lines": warnings
    }


# --- NODE 4: GATHER CONTEXT ---
def get_context_node(state: AgentState) -> Dict[str, Any]:
    if not state["error_lines"]:
        return {"code_context": ""}

    target_error = state["error_lines"][0]
    print(f"🕵️  Reasoning about: {target_error}")
    
    local_context = get_code_snippet(target_error, str(Path.cwd()))
    
    rag_context = ""
    # Check for implicit declaration (missing header) or undefined reference (linker)
    if "implicit declaration" in target_error or "undefined reference" in target_error:
        print("🔎 Linker/Header error detected. Searching RAG database...")
        
        # Extract the function name (e.g. 'add_numbers')
        # This is a simple split; regex would be safer but this works for now
        parts = target_error.split("'")
        if len(parts) > 1:
            query = parts[1] # 'add_numbers'
            results = search_codebase(query, n_results=1)
            
            if results:
                rag_context = f"\n\n--- RAG SEARCH RESULT (Found in {results[0]['file']}) ---\n{results[0]['code']}\n"
            else:
                print("🤷 RAG found nothing relevant.")

    full_context = local_context + rag_context
    return {"code_context": full_context}


# --- NODE 5: GENERATE FIX (UPDATED!) ---
def generate_fix_node(state: AgentState) -> Dict[str, Any]:
    error_msg = state["error_lines"][0]
    context = state["code_context"]
    
    print("🤖 AI is generating a fix...")
    try:
        # --- THE FIX IS HERE ---
        # We must pass format_instructions explicitly!
        result = fix_chain.invoke({
            "error_msg": error_msg,
            "code_context": context,
            "format_instructions": parser.get_format_instructions()
        })
        
        fixes = result.get("fixes", [])
        return {"proposed_fixes": fixes}
    except Exception as e:
        print(f"💥 AI Generation Failed: {e}")
        return {"proposed_fixes": []}


# --- NODE 6: APPLY FIX ---
def apply_fix_node(state: AgentState) -> Dict[str, Any]:
    fixes = state.get("proposed_fixes", [])
    if not fixes:
        print("🤷 No fixes to apply.")
        return {}

    for fix in fixes:
        # LangChain's parser returns a dict
        file_path = fix['file']
        original = fix['original_code']
        replacement = fix['replacement_code']
        
        abs_path = Path(file_path).resolve()
        
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Normalize line endings just in case
            content_norm = content.replace("\r\n", "\n")
            original_norm = original.replace("\r\n", "\n")
            
            if original_norm in content_norm:
                new_content = content_norm.replace(original_norm, replacement)
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"✅ Applied fix to {abs_path.name}")
            else:
                print(f"⚠️ Fix Failed: Could not find original code block in {abs_path.name}")
                # Debug print to help you see what failed
                # print(f"Looking for:\n{original_norm!r}")
                
        except Exception as e:
            print(f"❌ File Error: {e}")
            
    return {}


# --- NODE 7: REVERT ---
def revert_node(state: AgentState) -> Dict[str, Any]:
    branch = state["branch_name"]
    print(f"🔙 Reverting branch {branch}...")
    subprocess.run(["git", "checkout", "main"], capture_output=True)
    subprocess.run(["git", "branch", "-D", branch], capture_output=True)
    return {"workspace_clean": True}