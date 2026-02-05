from parsers.gcc import extract_gcc_issues
from agent.analyzer import analyze_errors
from agent.confidence import is_confident
from agent.fixer import apply_fixes
import json
import subprocess
from pathlib import Path
from agent.memory import (
    load_memory,
    save_memory,
    create_signature,
    current_time
)

root_dir = Path(__file__).resolve().parent
log_path = root_dir / "logs" / "build.log"
testcode_dir = root_dir / "testcode"
fix_root = root_dir

if testcode_dir.exists():
    fix_root = testcode_dir
    # build_cmd = "make -C testcode"
    # result = subprocess.run(
    #     build_cmd,
    #     shell=True,
    #     capture_output=True,
    #     text=True,
    #     encoding="utf-8",
    #     errors="ignore",
    # )
    # log_path.parent.mkdir(parents=True, exist_ok=True)
    # log_path.write_text(
    #     (result.stdout or "") + (result.stderr or ""),
    #     encoding="utf-8",
    #     errors="ignore",
    # )
    pass

with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
    log_text = f.read()

errors, warnings = extract_gcc_issues(log_text)

if not errors and not warnings:
    print("✅ No build issues detected")
    exit(0)

#result = analyze_errors(errors, warnings)
memory = load_memory()
signature = create_signature(errors + warnings)

result = None

# 1️⃣ Try memory first
for entry in memory:
    if entry["error_signature"] == signature:
        print("♻️ Known error found in memory")
        result = entry
        break

# 2️⃣ If not found, ask AI and remember
if result is None:
    print("🧠 New error, asking AI...")
    result = analyze_errors(errors, warnings)
    result["error_signature"] = signature
    result["timestamp"] = current_time()
    memory.append(result)
    save_memory(memory)


# Retry strategy if confidence is low
if not is_confident(result):
    print("⚠️ Low confidence result, retrying with reduced context")
    result = analyze_errors(errors[:50], warnings[:50])

if result.get("fixes"):
    print("🔍 Generated Fixes:")
    print(json.dumps(result["fixes"], indent=2))

# 3️⃣ Apply fixes if confident
if result.get("fixes") and result.get("confidence", 0) >= 0.7:
    print(f"🔧 Confidence HIGH ({result['confidence']}), applying {len(result['fixes'])} fixes...")
    apply_fixes(result["fixes"], root_dir=str(fix_root))

# Save outputs
with open("output/report.json", "w") as f:
    json.dump(result, f, indent=2)

with open("output/report.md", "w") as f:
    f.write(f"""
# Build Failure Report

**Root Cause**
{result['root_cause']}

**Category**
{result['error_category']}

**Blocking**
{result['blocking']}

**Suggested Fix**
{result['suggested_fix']}

**Confidence**
{result['confidence']}

**Warnings (first 50)**
""" + "\n".join(warnings[:50]))

print("📄 Report generated in output/")
