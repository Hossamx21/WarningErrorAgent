REASONING_PROMPT = """
You are a C Programming Expert.
Analyze the following Build Error and Source Code.
Identify the specific line causing the error and determine the correct C syntax.

Format your response like this:
1. LINE_CONTENT: (The exact content of the bad line)
2. FIX_EXPLANATION: (Why it is wrong)
3. CORRECTED_LINE: (The fixed line)
"""

JSON_CONVERSION_PROMPT = """
You are a Code Formatting Engine.
Convert the proposed fix into strict JSON.

CRITICAL RULES:
1. 'original_code' must be the EXACT code string from the file.
   - DO NOT include line numbers (e.g., "11:", "Line 10").
   - DO NOT add comments that aren't in the source.
2. 'replacement_code' must be the valid C code only.
3. If adding a missing header, include the existing adjacent line in 'original_code' to anchor the replacement.

Required JSON Structure:
{
  "fixes": [
    {
      "file": "filename.c",
      "original_code": "int x = 50",
      "replacement_code": "int x = 50;"
    }
  ]
}
"""