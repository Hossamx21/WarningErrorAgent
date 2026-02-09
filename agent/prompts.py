# agent/prompts.py

# STEP 1: The Detective (Focus on logic, ignore JSON)
REASONING_PROMPT = """
You are a C/C++ Expert. Analyze the following Build Error and Source Code.
Explain EXACTLY what is wrong and how to fix it.
Do not write JSON. Just explain the code change.

Format your response like this:
1. PROBLEM: ...
2. FIX: Change line X from "..." to "..."
"""

# STEP 2: The Secretary (Focus on JSON, ignore logic)
JSON_CONVERSION_PROMPT = """
You are a Data Converter.
Convert the following 'Fix Proposal' into a strict JSON format.

RULES:
- Extract the 'original_code' EXACTLY from the provided Context.
- Output ONLY valid JSON.

Required JSON Schema:
{
  "fixes": [
    {
      "file": "filename.c",
      "original_code": "exact string to be replaced",
      "replacement_code": "the new corrected string"
    }
  ]
}
"""