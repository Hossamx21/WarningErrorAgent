import os
import subprocess
import uuid
from pathlib import Path
from typing import Dict, Any
from langchain_community.tools import DuckDuckGoSearchRun
from agent.state import AgentState
# IMPORT PARSER HERE
from agent.llm import fix_chain, parser 
from agent.rag import search_codebase 
from agent.context import get_code_snippet 

# --- CONFIGURATION ---
GCC_PATH = r"D:\eaton-ut\GCC-140200-64\GCC-140200-64\bin\gcc.exe"
if os.path.exists(GCC_PATH):
    os.environ["PATH"] += os.pathsep + str(Path(GCC_PATH).parent)

# Initialize the search tool
web_search_tool = DuckDuckGoSearchRun()

TESTCODE_DIR = Path("testcode").resolve()
# NOTE: We now build test.c AND math_utils.c together!
# Added -I"{TESTCODE_DIR}" so GCC finds your local headers!
BUILD_CMD = f'"{GCC_PATH}" "{TESTCODE_DIR / "test.c"}" "{TESTCODE_DIR / "math_utils.c"}" -I"{TESTCODE_DIR}" -o "{TESTCODE_DIR / "test_app"}" -Wall'

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
    current_retries = state.get("retry_count", 0)

    errors = state.get("error_lines", [])
    warnings = state.get("warning_lines", [])

    if errors:
        target_issue = errors[0]
        issue_type = "ERROR"
    elif warnings:
        target_issue = warnings[0]
        issue_type = "WARNING"
    else:
        return {"code_context": "", "current_issue": "", "retry_count": current_retries}

    print(f"🕵️  Reasoning about {issue_type}: {target_issue}")
    
    local_context = get_code_snippet(target_issue, str(Path.cwd()))
    
    # 1. RAG CONTEXT (Local Knowledge)
    rag_context = ""
    if "implicit declaration" in target_issue or "undefined reference" in target_issue:
        query = target_issue.split("'")[1] if "'" in target_issue else ""
        if query:
            from agent.rag import search_codebase
            results = search_codebase(query, n_results=1)
            if results:
                rag_context = f"\n\n--- RAG SEARCH RESULT ---\n{results[0]['code']}\n"

    # 2. WEB CONTEXT (Internet Knowledge) - NEW!
    web_context = ""
    # Trigger web search if it's a specific GCC flag OR if the AI is stuck (retry > 0)
    if "[-W" in target_issue or current_retries > 0:
        print("🌐 Asking the internet for help...")
        try:
            # We clean up the query so we don't search your local file paths.
            # E.g., splits "D:\...test.c:10: warning: unused variable" into just "warning: unused variable"
            clean_query = target_issue.split(":", 3)[-1].strip() if ":" in target_issue else target_issue
            
            # We append 'gcc C' to force it to look for C programming answers
            search_query = f"gcc C {clean_query} StackOverflow"
            
            # Call DuckDuckGo
            web_results = web_search_tool.invoke(search_query)
            web_context = f"\n\n--- WEB SEARCH RESULTS (StackOverflow/Docs) ---\n{web_results}\n"
            print("✅ Web search complete.")
        except Exception as e:
            print(f"⚠️ Web search failed: {e}")

    # Combine everything!
    full_context = local_context + rag_context + web_context
    
    return {
        "code_context": full_context,
        "current_issue": target_issue,
        "retry_count": current_retries + 1
    }
# --- NODE 5: GENERATE FIX (UPDATED!) ---
def generate_fix_node(state: AgentState) -> Dict[str, Any]:
    # LINE 1: Retrieve the exact issue (Error or Warning) we selected in the previous node.
    issue_msg = state.get("current_issue", "")
    
    # LINE 2: Retrieve the code blocks (Local + RAG) we gathered.
    context = state.get("code_context", "")
    
    print("🤖 AI is generating a fix...")
    try:
        # LINE 3 to 7: Trigger the LangChain LLM pipeline. 
        # We inject 'issue_msg' into the "error_msg" variable inside the prompt template.
        result = fix_chain.invoke({
            "error_msg": issue_msg, 
            "code_context": context,
            "format_instructions": parser.get_format_instructions()
        })
        
        # LINE 8 & 9: Extract the JSON list and update the state.
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