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
    root_dir = Path(__file__).resolve().parent
    # --- ADD THIS BLOCK ---
# We point to the specific compiler executable
    gcc_path = r"D:\eaton-ut\GCC-140200-64\GCC-140200-64\bin\gcc.exe"

# CRITICAL FIX: We tell Windows where to find the DLLs (libgcc_s_seh-1.dll, etc.)
# by adding the compiler's 'bin' folder to the environment PATH for this script.
    gcc_bin_folder = str(Path(gcc_path).parent)
    os.environ["PATH"] += os.pathsep + gcc_bin_folder
# ----------------------

    log_path = root_dir / "logs" / "build.log"
    test_dir = root_dir / "testcode"
    
    # 1. SAFETY CHECK
    if not is_clean_workspace():
        print("🛑 STOP: You have uncommitted changes. Please commit or stash them first.")
        return
    
# 2. INITIAL BUILD (To get the errors)
    print("🔨 Running initial build...")
    
    # Use the variable we defined at the top
    build_cmd = f'"{gcc_path}" "{test_dir / "test.c"}" -o "{test_dir / "test_app"}" -Wall'
    
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
        success, new_logs = run_build(build_cmd)

        if success:
            print("🎉 SUCCESS! The build passed.")
            # Delete the branch since we are done (or merge it)
            # For now, let's keep it so you can see the victory
            print(f"✅ Code is fixed on branch: {branch_name}")
            return

        else:
            # CHECK FOR PROGRESS
            # If the original error is GONE, but new errors appeared, we made progress!
            print("💥 Fix failed to cure the build.")
            print("Build output after fix:")
            
            # Print only the first few lines of the new log
            print("\n".join(new_logs.splitlines()[:10]))

            # --- NEW LOGIC: DETECT PROGRESS ---
            # If the old error is gone, keep the change!
            # We check if the specific error line we tried to fix is still in the logs
            old_error_signature = error_lines[0].split("error:")[1].strip() if len(error_lines) > 0 else ""
            
            if old_error_signature and old_error_signature not in new_logs:
                 print(f"\n🚀 PARTIAL SUCCESS! The error '{old_error_signature[:30]}...' is gone.")
                 print(f"⚠️ New errors appeared, but we will KEEP the current fix on branch {branch_name}.")
                 print("You can run the agent again to fix the new errors.")
                 return
            # ----------------------------------

            print("Start reverting to main...")
            revert_changes(branch_name)
            print(f"Reverted. Deleted branch {branch_name}.")

if __name__ == "__main__":
    main()