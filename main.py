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
        
        # Re-use the same command
        success, new_logs = run_build(build_cmd)
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