import chromadb
from zhipuai import ZhipuAI
import os
from dotenv import load_dotenv
import hashlib


load_dotenv()
client_ai = ZhipuAI(api_key=os.getenv("API_KEY"))
client_db = chromadb.PersistentClient(path="./chroma_db")

try:
    collection = client_db.get_collection("documents")
except:
    collection = client_db.create_collection("documents")

def get_embedding(text):
    response = client_ai.embeddings.create(
        model="embedding-3",
        input=text
    )
    return response.data[0].embedding

def read_file(file_path: str, filename: str) -> str:
    ext = filename.split(".")[-1].lower()
    if ext == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        return "\n".join(page.extract_text() for page in reader.pages)
    elif ext == "docx":
        from docx import Document
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)
    elif ext in ["txt", "md"]:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        raise ValueError(f"不支持的文件类型：{ext}")

def chunk_text(text: str, chunk_size: int = 500) -> list:
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i+chunk_size].strip()
        if chunk:
            chunks.append(chunk)
    return chunks

def add_document(file_path: str, filename: str):
    text = read_file(file_path, filename)
    chunks = chunk_text(text)
    embeddings = [get_embedding(chunk) for chunk in chunks]
    ids = [hashlib.md5(f"{filename}{i}".encode()).hexdigest() for i in range(len(chunks))]
    collection.add(documents=chunks, embeddings=embeddings, ids=ids)
    return len(chunks)

def search(query: str, n_results: int = 3) -> list:
    embedding = get_embedding(query)
    results = collection.query(query_embeddings=[embedding], n_results=n_results)
    return results["documents"][0]