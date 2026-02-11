import os
import re

def get_code_snippet(error_line_str: str, root_dir: str) -> str:
    """
    Extracts code around the error AND the top of the file (for headers).
    """
    # 1. Parse filename and line number from error string
    # Matches: "folder/file.c:10: error:"
    match = re.search(r"([^:\s]+):(\d+):", error_line_str)
    if not match:
        return ""
    
    rel_path = match.group(1)
    line_num = int(match.group(2))
    
    # 2. Find the file
    abs_path = os.path.join(root_dir, rel_path)
    if not os.path.exists(abs_path):
        return f"File not found: {abs_path}"
    
    try:
        with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            
        total_lines = len(lines)
        snippet = ""

        # --- PART A: ALWAYS INCLUDE TOP OF FILE (For Headers) ---
        # We include lines 1-5 so the AI can see existing includes
        snippet += "--- [FILE START] ---\n"
        head_end = min(5, total_lines)
        for i in range(head_end):
            # Format: "  1: #include <stdlib.h>"
            snippet += f"{lines[i]}"
            
        # --- PART B: THE ERROR CONTEXT ---
        # If the error is far down, add a separator
        start_line = max(head_end, line_num - 5)
        end_line = min(total_lines, line_num + 5)
        
        if start_line > head_end:
            snippet += "\n... [SKIPPED CODE] ...\n\n"
            
        for i in range(start_line, end_line):
            # Note: i is 0-indexed, so line number is i+1
            snippet += f"{lines[i]}"
            
        return snippet

    except Exception as e:
        return f"Error reading file: {e}"