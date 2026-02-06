import os
import re

def get_code_snippet(error_line: str, root_dir: str, window: int = 5) -> str:
    """
    Parses a GCC error line and retrieves the surrounding source code.
    Input: "src/main.c:12: error: expected ';'"
    Output: "   11: int x = 1\n>> 12: return x;"
    """
    # Regex to find "filename:line_number:"
    match = re.search(r"([^:\s]+):(\d+):", error_line)
    if not match:
        return "[No file reference found in error]"

    file_path = os.path.join(root_dir, match.group(1))
    
    try:
        line_num = int(match.group(2))
    except ValueError:
        return "[Invalid line number]"

    if not os.path.exists(file_path):
        return f"[File not found: {file_path}]"

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            
        # Calculate window (1-based index to 0-based list)
        start = max(0, line_num - window - 1)
        end = min(len(lines), line_num + window)
        
        snippet = []
        for i in range(start, end):
            curr_line_num = i + 1
            # Mark the error line with '>>'
            prefix = ">> " if curr_line_num == line_num else "   "
            # Format: ">> 12: code content"
            snippet.append(f"{prefix}{curr_line_num:<4}: {lines[i].rstrip()}")
            
        return "\n".join(snippet)
        
    except Exception as e:
        return f"[Error reading file: {str(e)}]"