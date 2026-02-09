import subprocess
import uuid

def run_git(args: list[str]) -> tuple[bool, str]:
    """Helper to run git commands."""
    try:
        # We use check=False so we can handle errors manually
        res = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            check=False
        )
        return (res.returncode == 0, res.stdout.strip())
    except Exception as e:
        return (False, str(e))

def is_clean_workspace() -> bool:
    """Returns True if there are no IMPORTANT uncommitted changes."""
    success, output = run_git(["status", "--porcelain"])
    
    if not output:
        return True # Completely clean
        
    # Filter out lines that are just pycache or logs to be annoying
    lines = output.splitlines()
    for line in lines:
        # If the change is NOT in pycache or logs, then it's a real dirty state
        if "__pycache__" not in line and "logs/" not in line and ".pyc" not in line:
            print(f"⚠️  Uncommitted change detected: {line}")
            return False
            
    return True

def create_branch() -> str:
    """Creates a new branch with a unique name."""
    branch_name = f"ai-fix-{uuid.uuid4().hex[:8]}"
    run_git(["checkout", "-b", branch_name])
    return branch_name

def revert_changes(branch_name: str):
    """Reverts changes by switching back to main and deleting the temp branch."""
    # 1. Switch back to main (or master)
    run_git(["checkout", "main"]) 
    
    # 2. Force delete the temporary branch
    run_git(["branch", "-D", branch_name])

def commit_changes(branch_name: str, message: str):
    """Commits the changes on the current branch."""
    run_git(["add", "."])
    run_git(["commit", "-m", message])