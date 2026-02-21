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
    Decides if the fix was good, and if we should keep looping.
    """
    
    # VARIABLES: has_errors, has_warnings
    # RELATIONSHIP: Evaluates to True if the length of the lists in the state is greater than 0.
    has_errors = len(state.get("error_lines", [])) > 0
    has_warnings = len(state.get("warning_lines", [])) > 0
    
    # 1. THE PERFECT EXIT
    # If both lists are completely empty, the build is flawless.
    if not has_errors and not has_warnings:
        print("🎉 Code is perfect! Zero Errors, Zero Warnings.")
        return "end" # Signals LangGraph to terminate the execution.
        
    # 2. THE INFINITE LOOP BREAKER
    # VARIABLE: state.get("retry_count")
    # RELATIONSHIP: Reads the counter we incremented in 'get_context_node'.
    # If the AI has tried and failed 4 times, we force a stop to prevent an infinite loop.
    if state.get("retry_count", 0) >= 4:
        print("🛑 Reached maximum AI retries (4). Stopping to prevent infinite loop.")
        return "end" 
        
    # 3. THE CONTINUOUS LOOP
    # VARIABLE: current_errors
    # RELATIONSHIP: Checks the raw count of errors.
    current_errors = len(state.get("error_lines", []))
    
    # If the build failed, but it didn't completely explode (less than 20 errors),
    # we assume the AI is making progress or still has warnings to fix.
    if current_errors < 20:
         print("🔄 Issue addressed, but compiler is still complaining. Looping back to Agent...")
         
         # Returning "get_context" tells LangGraph to draw an edge back to the start
         # of the AI processing pipeline, feeding the NEW warnings/errors back into the loop.
         return "get_context"
    
    # 4. THE CATASTROPHIC FAILURE
    # If the error count is 20+, the AI likely broke a core header file. 
    # We trigger the revert node to undo the Git commit.
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