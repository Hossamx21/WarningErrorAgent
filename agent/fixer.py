import os

def apply_fixes(fixes: list[dict], root_dir: str = ".") -> int:
    """
    Applies a list of fixes to the source code.
    Returns the number of successful fixes applied.
    """
    applied_count = 0

    for fix in fixes:
        # 1. Resolve path
        file_path = os.path.join(root_dir, fix["file"])
        
        if not os.path.exists(file_path):
            print(f"❌ Fixer Error: File not found: {file_path}")
            continue

        try:
            # 2. Read content
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            original = fix["original_code"]
            replacement = fix["replacement_code"]

            # 3. SAFETY CHECK: Verify exact match
            # We use count=1 to ensure we don't accidentally replace multiple occurrences 
            # if the code snippet is generic (like "return 0;").
            if original not in content:
                print(f"⚠️  Skipping fix for {fix['file']}: Original code not found or context mismatch.")
                # Debug help: print what we were looking for vs what might be there
                # print(f"   Wanted: {repr(original)}")
                continue

            # 4. Apply replacement
            new_content = content.replace(original, replacement, 1)

            # 5. Write back
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            print(f"✅ Applied fix to {fix['file']}")
            applied_count += 1

        except Exception as e:
            print(f"❌ Failed to write {file_path}: {e}")

    return applied_count