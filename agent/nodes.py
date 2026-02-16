import os
import subprocess
import uuid
from pathlib import Path
from typing import Dict, Any

# Import our State and LLM Chain
from agent.state import AgentState
from agent.llm import fix_chain
from agent.rag import search_codebase  # We hook up RAG here!

# Import your existing helper for file snippets
from agent.context import get_code_snippet 

# --- CONFIGURATION ---
GCC_PATH = r"D:\eaton-ut\GCC-140200-64\GCC-140200-64\bin\gcc.exe"
# Ensure GCC is in PATH for DLLs
if os.path.exists(GCC_PATH):
    os.environ["PATH"] += os.pathsep + str(Path(GCC_PATH).parent)

TESTCODE_DIR = Path("testcode").resolve()
BUILD_CMD = f'"{GCC_PATH}" "{TESTCODE_DIR / "test.c"}" -o "{TESTCODE_DIR / "test_app"}" -Wall'


# --- NODE 1: CHECK WORKSPACE ---
def check_workspace_node(state: AgentState) -> Dict[str, Any]:
    """Ensures the git workspace is clean before starting."""
    # Run git status
    res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    if res.stdout.strip():
        # If dirty, we stop (or just flag it)
        return {"workspace_clean": False}
    return {"workspace_clean": True}


# --- NODE 2: CREATE BRANCH ---
def create_branch_node(state: AgentState) -> Dict[str, Any]:
    """Creates a temporary safety branch."""
    branch_name = f"ai-fix-{uuid.uuid4().hex[:8]}"
    subprocess.run(["git", "checkout", "-b", branch_name], check=False)
    print(f"🛡️  Switched to branch: {branch_name}")
    return {"branch_name": branch_name}


# --- NODE 3: RUN BUILD ---
def run_build_node(state: AgentState) -> Dict[str, Any]:
    """Runs GCC and parses errors."""
    print("🔨 Running build...")
    res = subprocess.run(BUILD_CMD, capture_output=True, text=True, shell=True)
    logs = res.stdout + "\n" + res.stderr
    
    # Simple Parse Logic (reusing your old logic)
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


# --- NODE 4: GATHER CONTEXT (With RAG!) ---
def get_context_node(state: AgentState) -> Dict[str, Any]:
    """
    Decides if we need RAG or just local file context.
    """
    if not state["error_lines"]:
        return {"code_context": ""}

    target_error = state["error_lines"][0]
    print(f"🕵️  Reasoning about: {target_error}")
    
    # 1. Get Local Context (File Snippet)
    # We use your existing function to get lines around the error
    local_context = get_code_snippet(target_error, str(Path.cwd()))
    
    # 2. RAG CHECK: Is this a "Missing Symbol" error?
    rag_context = ""
    if "undefined reference" in target_error or "implicit declaration" in target_error:
        print("🔎 Linker/Header error detected. Searching RAG database...")
        
        # Extract the missing symbol name (simple heuristic)
        # e.g., "undefined reference to 'Init_System'" -> query "Init_System"
        query = target_error.split("'")[1] if "'" in target_error else target_error
        
        results = search_codebase(query, n_results=2)
        if results:
            rag_context = "\n\n--- RAG SEARCH RESULTS ---\n"
            for res in results:
                rag_context += f"Found in {res['file']}:\n{res['code']}\n"

    # Combine them
    full_context = local_context + rag_context
    return {"code_context": full_context}


# --- NODE 5: GENERATE FIX (The LLM) ---
def generate_fix_node(state: AgentState) -> Dict[str, Any]:
    """Calls the Qwen model via LangChain."""
    error_msg = state["error_lines"][0]
    context = state["code_context"]
    
    print("🤖 AI is generating a fix...")
    try:
        # LangChain magic happens here
        result = fix_chain.invoke({
            "error_msg": error_msg,
            "code_context": context
        })
        # Result is already a Dict thanks to the Parser!
        # Access the list of fixes inside the Pydantic object
        fixes = result.get("fixes", [])
        return {"proposed_fixes": fixes}
    except Exception as e:
        print(f"💥 AI Generation Failed: {e}")
        return {"proposed_fixes": []}


# --- NODE 6: APPLY FIX ---
def apply_fix_node(state: AgentState) -> Dict[str, Any]:
    """Patches the files."""
    fixes = state.get("proposed_fixes", [])
    if not fixes:
        print("🤷 No fixes to apply.")
        return {}

    for fix in fixes:
        # Pydantic models might be dicts or objects depending on parsing
        # The JsonOutputParser returns dicts usually.
        file_path = fix['file']
        original = fix['original_code']
        replacement = fix['replacement_code']
        
        # Normalize path
        abs_path = Path(file_path).resolve()
        
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # The replacement (using exact string match)
            if original in content:
                new_content = content.replace(original, replacement)
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"✅ Applied fix to {abs_path.name}")
            else:
                print(f"⚠️ Fix Failed: Could not find original code in {abs_path.name}")
                
        except Exception as e:
            print(f"❌ File Error: {e}")
            
    return {}


# --- NODE 7: REVERT ---
def revert_node(state: AgentState) -> Dict[str, Any]:
    """Reverts changes if the build got worse."""
    branch = state["branch_name"]
    print(f"🔙 Reverting branch {branch}...")
    subprocess.run(["git", "checkout", "main"], capture_output=True)
    subprocess.run(["git", "branch", "-D", branch], capture_output=True)
    return {"workspace_clean": True}