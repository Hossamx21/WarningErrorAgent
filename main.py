import sys
from agent.graph import app
from agent.nodes import check_workspace_node

def main():
    print("🚀 LangGraph Agent Starting...")

    # 1. Quick Safety Check
    # We run this manually just to exit early if needed, 
    # though it could be part of the graph.
    initial_check = check_workspace_node({})
    if not initial_check["workspace_clean"]:
        print("❌ Workspace is dirty. Please commit changes.")
        sys.exit(1)

    # 2. Define Initial State
    initial_state = {
        "workspace_clean": True,
        "branch_name": "",
        "retry_count": 0,
        "error_lines": [],
        "build_logs": "",
        "code_context": ""
    }

    # 3. Run the Graph!
    # The graph handles all the looping, logic, and state updates.
    try:
        app.invoke(initial_state)
        print("\n✅ Agent finished execution.")
    except Exception as e:
        print(f"\n💥 Critical Agent Error: {e}")

if __name__ == "__main__":
    main()