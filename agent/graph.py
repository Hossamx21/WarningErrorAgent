from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.nodes import (
    create_branch_node,
    run_build_node,
    get_context_node,
    generate_fix_node,
    apply_fix_node,
    revert_node
)

# --- 1. ROUTING LOGIC ---

def check_initial_build(state: AgentState):
    """Routes the initial build."""
    has_errors = len(state.get("error_lines", [])) > 0
    has_warnings = len(state.get("warning_lines", [])) > 0
    
    if has_errors or has_warnings:
        return "get_context"
        
    print("✅ Build passed with ZERO warnings. Code is perfect.")
    return "end"

def check_verification(state: AgentState):
    """Routes the verification build (The Loop Engine)."""
    has_errors = len(state.get("error_lines", [])) > 0
    has_warnings = len(state.get("warning_lines", [])) > 0
    
    if not has_errors and not has_warnings:
        print("🎉 Code is perfect! Zero Errors, Zero Warnings.")
        return "end"
        
    if state.get("retry_count", 0) >= 4:
        print("🛑 Reached maximum AI retries (4). Stopping to prevent infinite loop.")
        return "end"
        
    current_errors = len(state.get("error_lines", []))
    if current_errors < 20:
         print("🔄 Issue addressed, but compiler is still complaining. Looping back to Agent...")
         return "get_context"
    
    return "revert"


# --- 2. BUILD THE GRAPH ---

workflow = StateGraph(AgentState)

# Register all our worker nodes
workflow.add_node("setup", create_branch_node)
workflow.add_node("build", run_build_node)
workflow.add_node("get_context", get_context_node)
workflow.add_node("generate", generate_fix_node)
workflow.add_node("apply", apply_fix_node)
workflow.add_node("verify", run_build_node) # We use the build node again to verify
workflow.add_node("revert", revert_node)

# Step A: Start the pipeline
workflow.set_entry_point("setup")
workflow.add_edge("setup", "build")

# Step B: The Initial Build Routing (This is likely what went missing!)
workflow.add_conditional_edges(
    "build",
    check_initial_build,
    {
        "end": END,
        "get_context": "get_context"
    }
)

# Step C: The AI Fix Pipeline
workflow.add_edge("get_context", "generate")
workflow.add_edge("generate", "apply")
workflow.add_edge("apply", "verify")

# Step D: The Loop/Verification Routing
workflow.add_conditional_edges(
    "verify",
    check_verification,
    {
        "end": END,
        "revert": "revert",
        "get_context": "get_context"
    }
)

# Step E: Failure Revert
workflow.add_edge("revert", END)

# Compile into an executable application
app = workflow.compile()