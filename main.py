import subprocess
import json
import os
from pathlib import Path

# Import your modules
from agent.analyzer import analyze_errors
from agent.fixer import apply_fixes
from parsers.gcc import extract_gcc_issues
from agent.git_utils import is_clean_workspace, create_fix_branch, revert_to_main, commit_change

def run_build(cmd="make"):
    """Runs the build and returns (success, logs)."""
    result = subprocess.run(
        cmd, 
        shell=True, 
        capture_output=True, 
        text=True,
        errors="ignore" # Ignore encoding errors
    )
    return result.returncode == 0, result.stderr + result.stdout

def main():
    root_dir = Path(".").resolve()
    test_dir = root_dir / "testcode"
    
    # 1. SAFETY CHECK
    if not is_clean_workspace():
        print("🛑 STOP: You have uncommitted changes. Please commit or stash them first.")
        return
    
# 2. INITIAL BUILD (To get the errors)
    print("🔨 Running initial build...")
    # FIX: Run GCC directly since 'make' is missing on Windows
    # We explicitly enable -Wall to ensure warnings appear for the test
    build_cmd = f"gcc {test_dir / 'test.c'} -o {test_dir / 'test_app'} -Wall"
    success, logs = run_build(build_cmd)
    if success:
        print("✅ Build passed! Nothing to fix.")
        return

    # 3. PARSE & ANALYZE
    errors, warnings = extract_gcc_issues(logs)
    if not errors:
        print("❌ Build failed but no specific GCC errors found.")
        # ADD THIS DEBUG BLOCK:
        print("--- RAW BUILD LOGS ---")
        print(logs)
        print("----------------------")
        return
    
    # 4. ENTER SANDBOX
    original_branch = subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()
    fix_branch = create_fix_branch()
    print(f"🛡️  Switched to safe branch: {fix_branch}")

    try:
        # Ask AI for solution
        analysis = analyze_errors(errors, warnings, root_dir=str(test_dir))
        
        if not analysis.get("fixes"):
            print("🤷 AI could not generate any fixes.")
            revert_to_main(fix_branch, original_branch)
            return

        print(f"🤖 AI Suggests {len(analysis['fixes'])} fixes...")

        # Apply fixes
        apply_fixes(analysis["fixes"], root_dir=str(test_dir))
        
        # Commit the attempt (so we can revert cleanly if needed)
        commit_change(".", message="AI: Attempted compile fix")

        # 5. VERIFY
        print("🔄 Verifying fix...")
        success, new_logs = run_build(f"make -C {test_dir}")

        if success:
            print("🎉 SUCCESS! The build passed.")
            print(f"👉 You are currently on branch '{fix_branch}'.")
            print(f"👉 To keep this, run: git checkout {original_branch} && git merge {fix_branch}")
        else:
            print("💥 Fix failed to cure the build.")
            print("Build output after fix:\n", new_logs[:500])
            revert_to_main(fix_branch, original_branch)

    except Exception as e:
        print(f"⚠️ Critical Error: {e}")
        revert_to_main(fix_branch, original_branch)

if __name__ == "__main__":
    main()