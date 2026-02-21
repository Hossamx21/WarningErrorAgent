from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes import (
    check_workspace_node,
    create_branch_node,
    run_build_node,
    get_context_node,
    generate_fix_node,
    apply_fix_node,
    revert_node
)

# --- ROUTING LOGIC ---
def check_initial_build(state: AgentState):
    # LINE 1: Calculate if the 'error_lines' list has any items in it.
    has_errors = len(state.get("error_lines", [])) > 0
    
    # LINE 2: Calculate if the 'warning_lines' list has any items in it.
    has_warnings = len(state.get("warning_lines", [])) > 0
    
    # LINE 3 & 4: If either errors OR warnings exist, we route to "get_context" to start fixing.
    if has_errors or has_warnings:
        return "get_context"
        
    # LINE 5 & 6: Only if both lists are completely empty do we end the program.
    print("✅ Build passed with ZERO warnings. Code is perfect.")
    return "end"

def check_verification(state: AgentState):
    """
    Decides if the fix was good, partial, or bad.
    """
    if state.get("build_success"):
        print("🎉 Fix Verification Passed!")
        return "end"
    
    # --- PARTIAL SUCCESS LOGIC ---
    # We compare the NEW errors against the OLD target error.
    # Note: Ideally we would store 'target_error' in state. 
    # For now, we use a simple heuristic: Did the log change significantly?
    
    print("⚠️ Build still failing. Checking for partial progress...")
    # In a full production graph, we would have saved the specific error ID.
    # Here, we will assume if the agent applied a fix, we keep it 
    # unless it caused a catastrophic failure (like 100 new errors).
    
    current_errors = len(state.get("error_lines", []))
    # Heuristic: If we have fewer than 20 errors, it's likely progress or a shift.
    # If we have 100+, we probably broke a header file.
    if current_errors < 20:
         print("🚀 PARTIAL SUCCESS detected. Keeping changes.")
         return "end"
    
    return "revert"

# --- BUILD THE GRAPH ---
workflow = StateGraph(AgentState)

# 1. Add Nodes
workflow.add_node("setup", create_branch_node)
workflow.add_node("build", run_build_node)
workflow.add_node("get_context", get_context_node)
workflow.add_node("generate", generate_fix_node)
workflow.add_node("apply", apply_fix_node)
workflow.add_node("verify", run_build_node) # We reuse the build node!
workflow.add_node("revert", revert_node)

# 2. Add Edges (The Flow)
# Start -> Setup -> Build
workflow.set_entry_point("setup")
workflow.add_edge("setup", "build")

# Build -> Decision (End or Fix?)
workflow.add_conditional_edges(
    "build",
    check_initial_build,
    {
        "end": END,
        "get_context": "get_context"
    }
)

# Fix Loop: Context -> Gen -> Apply -> Verify
workflow.add_edge("get_context", "generate")
workflow.add_edge("generate", "apply")
workflow.add_edge("apply", "verify")

# Verify -> Decision (Keep or Revert?)
workflow.add_conditional_edges(
    "verify",
    check_verification,
    {
        "end": END,
        "revert": "revert"
    }
)

# Revert -> End
workflow.add_edge("revert", END)

# 3. Compile
app = workflow.compile()