print("🚀 STARTING RAG ENGINE...")

import requests
import numpy as np
from sentence_transformers import SentenceTransformer

# -----------------------------
# CONFIG
# -----------------------------
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5-coder:7b-instruct-q4_K_M"

print("⚙️ Loading embedding model...")
EMBED_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
print("✅ Embedding model loaded")

# -----------------------------
# NORMALIZATION (CRITICAL FIX)
# -----------------------------
def normalize(text):
    text = text.lower()
    text = text.replace("_", " ")
    return text

# -----------------------------
# VECTOR STORE
# -----------------------------
documents = []
embeddings = []

def add_document(text):
    print(f"➕ Adding document: {text}")
    documents.append(text)
    emb = EMBED_MODEL.encode(normalize(text))
    embeddings.append(emb)

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def retrieve(query, top_k=3):
    print(f"🔍 Retrieving for query: {query}")
    q_emb = EMBED_MODEL.encode(normalize(query))

    scores = [cosine_similarity(q_emb, e) for e in embeddings]
    top_idx = np.argsort(scores)[-top_k:][::-1]

    results = [documents[i] for i in top_idx]
    print(f"📄 Retrieved {len(results)} docs")
    return results

# -----------------------------
# LLM QUERY (STRICT + CONTROLLED)
# -----------------------------
def ask_llm(context, question):
    print("🤖 Sending request to Ollama...")

    prompt = f"""
You are a strict extraction engine for EDA manuals.

RULES:
1. Use ONLY the provided context.
2. Return the EXACT sentence(s) from the context.
3. Do NOT rephrase.
4. Do NOT summarize.
5. Do NOT format.
6. Do NOT explain.
7. If mapping is needed (e.g., "run ATPG" → "run_atpg"), still return the original sentence.
8. If not found, return: NOT_FOUND

CONTEXT:
{context}

QUESTION:
{question}
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )
        return response.json()["response"]

    except Exception as e:
        print("❌ Ollama request failed:", e)
        return "ERROR"

# -----------------------------
# DEMO DATA
# -----------------------------
print("📚 Adding demo documents...")

add_document("add_faults command is used to define faults in TMAX.")
add_document("run_atpg executes ATPG pattern generation.")
add_document("report_faults displays detected and undetected faults.")

# -----------------------------
# TEST QUERY
# -----------------------------
query = "How to run ATPG?"

# Expand query with likely command form
expanded_query = query + " run_atpg command"

print("🧠 Running retrieval...")
context_list = retrieve(expanded_query)
context = "\n".join(context_list)

print("🧠 Running retrieval...")
context_list = retrieve(query)
context = "\n".join(context_list)

print("\n=== CONTEXT ===")
print(context)

print("\n🧠 Asking LLM...")
answer = ask_llm(context, query)

print("\n=== ANSWER ===")
print(answer)

print("\n✅ DONE")
