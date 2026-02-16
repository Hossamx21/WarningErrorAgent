# agent/llm.py
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List

# 1. Define the exact structure we want using Pydantic
# LangChain will automatically force Qwen to output this!
class CodeFix(BaseModel):
    file: str = Field(description="The absolute path to the file")
    original_code: str = Field(description="The exact contiguous block of code to replace. Use \\n for newlines.")
    replacement_code: str = Field(description="The corrected code. Use \\n for newlines.")

class FixList(BaseModel):
    fixes: List[CodeFix]

# 2. Initialize the model
llm = ChatOllama(
    model="qwen2.5-coder:7b",
    temperature=0.0,
    base_url="http://localhost:11434"
)

# 3. Setup the robust JSON parser
parser = JsonOutputParser(pydantic_object=FixList)

# 4. Create the LangChain Prompt
# Notice how we inject parser.get_format_instructions() to auto-generate the JSON rules
fix_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a strict C compiler repair agent.\n{format_instructions}"),
    ("user", "ERROR:\n{error_msg}\n\nCONTEXT:\n{code_context}\n\nGenerate the fix.")
])

# 5. Build the Chain
# This replaces our entire call_ollama and extract_json functions
fix_chain = fix_prompt | llm | parser