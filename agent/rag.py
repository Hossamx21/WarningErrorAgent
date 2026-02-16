import os
import chromadb
import requests
from pathlib import Path

# --- CONFIGURATION ---
# We store the database in a local folder named 'rag_db'
DB_PATH = os.path.join(os.getcwd(), "rag_db")
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"

def get_embedding(text: str) -> list[float]:
    """
    Calls Ollama to convert text into a vector (list of numbers).
    """
    payload = {
        "model": EMBED_MODEL,
        "prompt": text
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()["embedding"]
    except Exception as e:
        print(f"⚠️ Failed to get embedding from Ollama: {e}")
        return []

def chunk_file(filepath: str, chunk_size: int = 50) -> list[str]:
    """
    Reads a file and splits it into manageable blocks of lines.
    This helps the AI understand specific functions rather than huge files.
    """
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return []
    
    chunks = []
    # Split into chunks of `chunk_size` lines
    for i in range(0, len(lines), chunk_size):
        chunk = "".join(lines[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks

def build_vector_db(root_dir: str):
    """
    Scans the directory and adds all C/C++ files to the database.
    RUN THIS FUNCTION ONCE to initialize the DB.
    """
    print(f"🗄️ Initializing local Vector DB at: {DB_PATH}")
    
    # Initialize ChromaDB (Persistent means it saves to disk)
    client = chromadb.PersistentClient(path=DB_PATH)
    
    # Create or load a collection (think of this as a SQL table)
    collection = client.get_or_create_collection(name="c_codebase")
    
    root_path = Path(root_dir)
    # Files we care about
    file_extensions = ['.c', '.h', '.cpp', '.hpp']
    
    doc_count = 0
    
    print(f"🔍 Scanning {root_dir} for source files...")
    for ext in file_extensions:
        for file_path in root_path.rglob(f"*{ext}"):
            # Skip hidden folders (.git) or the DB folder itself
            if ".git" in str(file_path) or "rag_db" in str(file_path):
                continue
                
            print(f"   📄 Indexing: {file_path.name}")
            chunks = chunk_file(str(file_path))
            
            for i, chunk in enumerate(chunks):
                # 1. Get the vector embedding from Ollama
                vector = get_embedding(chunk)
                
                if vector:
                    doc_id = f"{file_path.name}_chunk_{i}"
                    
                    # 2. Save to database
                    collection.add(
                        ids=[doc_id],
                        embeddings=[vector],
                        documents=[chunk],
                        metadatas=[{"file": str(file_path)}]
                    )
                    doc_count += 1

    print(f"✅ Database built! Indexed {doc_count} chunks of code.")

def search_codebase(query: str, n_results: int = 3) -> list[dict]:
    """
    Searches the database for code related to the query.
    Expected usage: search_codebase("Init_System definition")
    """
    # Connect to the existing DB
    client = chromadb.PersistentClient(path=DB_PATH)
    collection = client.get_or_create_collection(name="c_codebase")
    
    # Convert query to vector
    query_vector = get_embedding(query)
    
    if not query_vector:
        return []
        
    # Perform similarity search
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=n_results
    )
    
    # Format the results for the Agent
    matches = []
    if results['documents']:
        # Chroma returns a list of lists, we grab the first (and only) query's results
        for i in range(len(results['documents'][0])):
            matches.append({
                "file": results['metadatas'][0][i]['file'],
                "code": results['documents'][0][i]
            })
            
    return matches

# --- SELF-RUNNER ---
# If you run `python agent/rag.py`, it will rebuild the DB.
if __name__ == "__main__":
    # Point this to your testcode folder
    target_dir = os.path.join(os.getcwd(), "testcode")
    
    if not os.path.exists(target_dir):
        print(f"❌ Error: Could not find directory: {target_dir}")
    else:
        build_vector_db(target_dir)