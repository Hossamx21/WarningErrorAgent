import os
import subprocess
import sys
from pathlib import Path
from agent.gcc import parse_gcc_output
from agent.git_utils import is_clean_workspace, create_branch, revert_changes, commit_changes
from agent.analyzer import analyze_errors
from agent.fixer import apply_fixes

# --- CONFIGURATION ---
root_dir = Path(__file__).resolve().parent
testcode_dir = root_dir / "testcode"
log_dir = root_dir / "logs"

# Ensure log directory exists
log_dir.mkdir(exist_ok=True)

# GCC CONFIGURATION
# Update this path if you move GCC
gcc_path = r"D:\eaton-ut\GCC-140200-64\GCC-140200-64\bin\gcc.exe"

# Add GCC bin folder to PATH so it can find DLLs
if os.path.exists(gcc_path):
    gcc_bin = str(Path(gcc_path).parent)
    os.environ["PATH"] += os.pathsep + gcc_bin

def run_build(cmd: str) -> tuple[bool, str]:
    """Runs the build command and returns (success, logs)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=True
        )
        # GCC writes errors to stderr, but we want everything
        logs = result.stdout + "\n" + result.stderr
        return (result.returncode == 0, logs)
    except Exception as e:
        return (False, str(e))

def main():
    print("🚀 Agent Starting...")

    # 1. GIT SAFETY CHECK
    if not is_clean_workspace():
        print("❌ Error: Workspace is not clean. Commit or stash changes first.")
        return

    # 2. INITIAL BUILD
    print("🔨 Running initial build...")
    
    # We use raw strings for paths to avoid issues
    source_file = testcode_dir / "test.c"
    output_file = testcode_dir / "test_app"
    
    # The build command
    build_cmd = f'"{gcc_path}" "{source_file}" -o "{output_file}" -Wall'
    
    success, logs = run_build(build_cmd)
    
    # Save logs
    with open(log_dir / "build.log", "w", encoding="utf-8") as f:
        f.write(logs)

    if success:
        print("✅ Build passed! Nothing to fix.")
        return

    # 3. PARSE ERRORS
    errors, warnings = parse_gcc_output(logs)
    if not errors and not warnings:
        print("❓ Build failed but no specific GCC errors found.")
        print("--- RAW BUILD LOGS ---")
        print(logs)
        return

    # 4. START FIX ATTEMPT
    branch_name = create_branch()
    print(f"🛡️  Switched to safe branch: {branch_name}")

    try:
        # Ask AI for fixes
        analysis = analyze_errors(errors, warnings, root_dir=str(root_dir))
        
        fixes = analysis.get("fixes", [])
        if not fixes:
            print("🤷 AI could not generate any fixes.")
            print("Start reverting to main...")
            revert_changes(branch_name)
            print(f"Reverted. Deleted branch {branch_name}.")
            return

        print(f"🤖 AI Suggests {len(fixes)} fixes...")
        
        # Apply the fixes to the files
        apply_fixes(fixes, root_dir=str(root_dir))
        
        # 5. VERIFY
        print("🔄 Verifying fix...")
        success, new_logs = run_build(build_cmd)

        if success:
            print("🎉 SUCCESS! The build passed.")
            print(f"✅ Code is fixed on branch: {branch_name}")
            # Optional: commit_changes(branch_name, "AI Fix: Auto-corrected build errors")
            return
        
        else:
            # --- INTELLIGENT PARTIAL SUCCESS CHECK ---
            print("💥 Fix failed to cure the entire build.")
            
            # Extract the specific error signature we tried to fix
            # (e.g., "expected ';' before 'printf'")
            old_error_sig = ""
            if errors:
                # Get the text after 'error:'
                parts = errors[0].split("error:")
                if len(parts) > 1:
                    old_error_sig = parts[1].strip()

            # Check if that specific error is GONE from the new logs
            if old_error_sig and old_error_sig not in new_logs:
                print(f"\n🚀 PARTIAL SUCCESS! The specific error: '{old_error_sig[:40]}...' is GONE.")
                print(f"⚠️  New errors may have appeared, but we will KEEP this fix.")
                print(f"👉 You are still on branch: {branch_name}")
                print("💡 TIP: Run the agent again to fix the remaining errors!")
                return
            
            # If the exact same error is still there, then it failed.
            print("❌ The fix didn't work. Reverting changes.")
            print("--- New Logs Preview ---")
            print("\n".join(new_logs.splitlines()[:5]))
            
            revert_changes(branch_name)
            print(f"Reverted. Deleted branch {branch_name}.")

    except Exception as e:
        print(f"⚠️ Critical Error: {e}")
        revert_changes(branch_name)
        print(f"Reverted. Deleted branch {branch_name}.")

if __name__ == "__main__":
    main()