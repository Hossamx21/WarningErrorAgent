import subprocess
import uuid
import sys

def run_git_cmd(args: list[str], check: bool = True) -> bool:
    """Helper to run git commands cleanly."""
    try:
        subprocess.run(["git"] + args, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        return False

def is_clean_workspace() -> bool:
    """Returns True if there are no uncommitted changes."""
    # --porcelain gives machine-readable output. Empty means clean.
    res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    return not res.stdout.strip()

def create_fix_branch() -> str:
    """Creates a unique temporary branch for this fix attempt."""
    branch_name = f"ai-fix-{uuid.uuid4().hex[:8]}"
    if run_git_cmd(["checkout", "-b", branch_name]):
        return branch_name
    raise RuntimeError("Failed to create git branch")

def commit_change(file_path: str, message: str = "AI Auto-fix"):
    """Saves a snapshot of the current state."""
    run_git_cmd(["add", file_path])
    run_git_cmd(["commit", "-m", message])

def revert_to_main(temp_branch: str, original_branch: str = "main"):
    """Nukes the experiment and goes back to safety."""
    print(f"Start reverting to {original_branch}...")
    run_git_cmd(["checkout", original_branch])
    run_git_cmd(["branch", "-D", temp_branch])
    print(f"Reverted. Deleted branch {temp_branch}.")