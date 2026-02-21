# agent/state.py
from typing import TypedDict, List, Dict, Any

class AgentState(TypedDict):
    # Git & Workspace info
    branch_name: str
    workspace_clean: bool
    
    # Build results
    build_logs: str
    build_success: bool
    error_lines: List[str]
    warning_lines: List[str]
    
    # AI Context & Output
    code_context: str
    proposed_fixes: List[Dict[str, Any]] # Will hold our JSON fixes
    reasoning: str
    current_issue: str #to identify error or warning we are targeting
    
    # Loop control
    retry_count: int

    