# retriever_custom.py
# -*- coding: utf-8 -*-
"""
Custom Retriever với BM25+pyvi + Dense + Reranker
- BM25: rank-bm25 với pyvi tokenization (tốt hơn Weaviate built-in)
- Dense: Weaviate vector search với Alibaba-NLP/gte-multilingual-base
- Reranker: BAAI/bge-reranker-v2-m3
- Hybrid: alpha tuning based on query patterns
"""

import os
import re
import json
import pickle
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple

import torch
import weaviate
from pyvi import ViTokenizer
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer, CrossEncoder

# ---------------- ENV SETUP ----------------
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
torch.backends.mps.is_available = lambda: False
torch.set_num_threads(1)

# ---------------- CONFIG ----------------
BM25_INDEX_FILE = Path("bm25_index.pkl")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Reranking config: lấy nhiều candidates để rerank có hiệu quả
CANDIDATE_MULTIPLIER = 4  # Lấy 4x số chunks cần thiết làm candidates

# ---------------- PATTERNS ----------------
LEGAL_HINT_RE = re.compile(r"\b(Chương|Mục|Điều|Khoản|Điểm)\s+[IVXLC\d]+", re.IGNORECASE)
NUMERIC_INFO_RE = re.compile(r"\b(\d+)\s*(giờ|km/h|triệu|nghìn|đồng|lần|ngày|tháng|năm|%|phần trăm|cm3|cc|tấn|km|m|kW|điểm|giấy phép lái xe)\b", re.IGNORECASE)

def tune_alpha(query: str, base_alpha: float = 0.55) -> float:
    """Dynamic alpha tuning based on query pattern"""
    alpha = base_alpha
    
    if LEGAL_HINT_RE.search(query):
        alpha = max(0.30, base_alpha - 0.25)   # Thiên keyword
    elif NUMERIC_INFO_RE.search(query):
        alpha = max(0.40, base_alpha - 0.15)
    else:
        alpha = min(0.75, base_alpha + 0.20)   # Thiên semantic
    
    return alpha

# ---------------- LOAD MODELS ----------------
print(f"🔹 Loading embedding model on {DEVICE}...")
emb_model = SentenceTransformer("Alibaba-NLP/gte-multilingual-base", device=DEVICE, trust_remote_code=True)
print("✓ Embedding model loaded")

print(f"🔹 Loading reranker model on {DEVICE}...")
reranker = CrossEncoder("BAAI/bge-reranker-v2-m3", device=DEVICE)
print("✓ Reranker loaded")

print("🌐 Connecting to Weaviate...")
client = weaviate.connect_to_local(skip_init_checks=True)
weaviate_collection = client.collections.get("LawChunks")
print("✓ Connected to Weaviate")

# ---------------- BUILD/LOAD BM25 INDEX ----------------
def load_chunks_from_weaviate():
    """Load chunks từ Weaviate (luôn fresh, không cache)"""
    resp = weaviate_collection.query.fetch_objects(
        limit=10000,
        return_properties=[
            "law", "chapter", "section", "article_no", "article_title",
            "clause_no", "point", "clause_head", "text",
            "enriched_text", "display_citation"
        ]
    )
    
    chunks = []
    for obj in resp.objects:
        chunks.append(obj.properties)
    
    return chunks

def build_bm25_index(chunks):
    """Build BM25 index với pyvi tokenization"""
    print("\n🔨 Building BM25 index với pyvi...")
    
    tokenized_corpus = []
    for c in chunks:
        # Combine fields for BM25 (giống eval code)
        fields = [
            c.get("article_no", ""),
            c.get("article_title", ""),
            c.get("clause_no", ""),
            c.get("point", ""),
            c.get("clause_head", ""),
            c.get("text", ""),
        ]
        combined = " ".join([f for f in fields if f])
        
        # Tokenize với pyvi
        tokenized = ViTokenizer.tokenize(combined)
        tokenized_corpus.append(tokenized.split())
    
    bm25 = BM25Okapi(tokenized_corpus)
    
    # Cache chỉ BM25 object (không cache chunks)
    with open(BM25_INDEX_FILE, "wb") as f:
        pickle.dump(bm25, f)
    
    print(f"✓ BM25 index built: {len(chunks)} chunks")
    return bm25

# Load chunks (luôn fresh từ Weaviate)
print("📂 Loading chunks from Weaviate...")
chunks_cache = load_chunks_from_weaviate()
print(f"✓ Loaded {len(chunks_cache)} chunks")

# Load or build BM25 index
if BM25_INDEX_FILE.exists():
    print("📂 Loading cached BM25 index...")
    with open(BM25_INDEX_FILE, "rb") as f:
        bm25_index = pickle.load(f)
    print(f"✓ BM25 index loaded")
else:
    bm25_index = build_bm25_index(chunks_cache)

# ---------------- RETRIEVAL FUNCTIONS ----------------
def retrieve_bm25(query: str, k: int) -> Tuple[List[int], List[float]]:
    """BM25 retrieval với pyvi"""
    tokenized_query = ViTokenizer.tokenize(query).split()
    scores = bm25_index.get_scores(tokenized_query)
    top_indices = np.argsort(-scores)[:k]
    top_scores = scores[top_indices]
    return top_indices.tolist(), top_scores.tolist()

def retrieve_dense(query: str, k: int) -> List[Dict]:
    """Dense vector search từ Weaviate"""
    q_vec = emb_model.encode([query], normalize_embeddings=True)[0]
    
    resp = weaviate_collection.query.near_vector(
        near_vector=q_vec.tolist(),
        limit=k,
        return_metadata=["distance"],
        return_properties=[
            "law", "chapter", "section", "article_no", "article_title",
            "clause_no", "point", "clause_head", "text",
            "enriched_text", "display_citation"
        ]
    )
    
    results = []
    for obj in resp.objects:
        p = obj.properties
        # Convert distance to similarity score (1 - distance)
        score = 1.0 - obj.metadata.distance if obj.metadata.distance else 0.0
        results.append({
            "props": p,
            "score": score
        })
    
    return results

def retrieve_hybrid(query: str, alpha: float, k: int) -> List[Dict]:
    """
    Hybrid: alpha * dense + (1-alpha) * bm25
    alpha=0 → pure keyword, alpha=1 → pure vector
    """
    # BM25 scores
    bm25_indices, bm25_scores = retrieve_bm25(query, k)
    bm25_scores_norm = np.array(bm25_scores) / (np.max(bm25_scores) + 1e-8)
    
    # Dense scores
    dense_results = retrieve_dense(query, k)
    
    # Merge scores by chunk
    # Create mapping: bm25 chunk → score
    bm25_score_map = {}
    for idx, score in zip(bm25_indices, bm25_scores_norm):
        chunk = chunks_cache[idx]
        key = chunk.get("display_citation", "")
        bm25_score_map[key] = score
    
    # Combine
    combined = []
    for dense_res in dense_results:
        citation = dense_res["props"].get("display_citation", "")
        dense_score = dense_res["score"]
        bm25_score = bm25_score_map.get(citation, 0.0)
        
        hybrid_score = alpha * dense_score + (1 - alpha) * bm25_score
        combined.append({
            "props": dense_res["props"],
            "score": hybrid_score
        })
    
    # Add BM25-only results (not in dense top-k)
    dense_citations = {r["props"].get("display_citation", "") for r in dense_results}
    for idx in bm25_indices:
        chunk = chunks_cache[idx]
        citation = chunk.get("display_citation", "")
        if citation not in dense_citations:
            bm25_score = bm25_score_map.get(citation, 0.0)
            hybrid_score = (1 - alpha) * bm25_score
            combined.append({
                "props": chunk,
                "score": hybrid_score
            })
    
    # Sort by hybrid score
    combined.sort(key=lambda x: x["score"], reverse=True)
    return combined[:k]

def rerank(query: str, candidates: List[Dict], final_k: int) -> List[Dict]:
    """Rerank với CrossEncoder"""
    if not candidates:
        return []
    
    # Prepare texts
    texts = [c["props"].get("enriched_text", "") for c in candidates]
    pairs = [[query, text] for text in texts]
    
    # Rerank
    scores = reranker.predict(pairs)
    
    # Sort
    for i, c in enumerate(candidates):
        c["rerank_score"] = float(scores[i])
    
    candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
    return candidates[:final_k]

# ---------------- MAIN RETRIEVE FUNCTION ----------------
# ---------------- MAIN RETRIEVE FUNCTION ----------------
def retrieve(question: str, k: int = 5, raw: bool = False):
    """
    Main retrieval function
    Args:
        question: Câu hỏi
        k: Số lượng chunk cần lấy
        raw: Nếu True trả về list dict (cho Quiz), nếu False trả về string (cho Chatbot)
    """
    # Ensure k is integer
    k = int(k) if k else 5
    
    # Dynamic alpha tuning
    alpha = tune_alpha(question, base_alpha=0.55)
    
    # Hybrid search
    num_candidates = min(k * CANDIDATE_MULTIPLIER, 30)
    candidates = retrieve_hybrid(question, alpha, num_candidates)
    
    # Rerank
    top_results = rerank(question, candidates, k)
    
    # --- MỚI: Trả về dữ liệu thô nếu cần (Cho Quiz) ---
    if raw:
        return top_results

    # --- CŨ: Format thành text để cho Chatbot ---
    contexts = []
    sources = []
    
    for res in top_results:
        p = res["props"]
        
        law = (p.get("law") or "").strip()
        chapter = (p.get("chapter") or "").strip()
        section = (p.get("section") or "").strip()
        article_no = (p.get("article_no") or "").strip()
        article_title = (p.get("article_title") or "").strip()
        clause_no = (p.get("clause_no") or "")
        clause_head = (p.get("clause_head") or "").strip()
        point = (p.get("point") or "").strip()
        body_for_ctx = (p.get("text") or "").strip()
        display_citation = (p.get("display_citation") or "").strip()
        
        lines = []
        
        # Add citation reference at the top
        if display_citation:
            lines.append(f"[Căn cứ: {display_citation}]")
        
        # Luật / Chương / Mục / Điều
        if law: lines.append(law)
        if chapter: lines.append(chapter)
        if section: lines.append(section)
        if article_no or article_title:
            art_line = f"Điều {article_no}".strip()
            if article_title: art_line += f". {article_title}"
            lines.append(art_line)
        
        # Phân biệt: có Điểm hay không
        if point:
            if clause_no and clause_head:
                lines.append(f"Khoản {clause_no}. {clause_head}")
            elif clause_no:
                lines.append(f"Khoản {clause_no}")
            
            lines.append(f"Điểm {point})")
            
            if body_for_ctx: lines.append(body_for_ctx)
        else:
            if clause_no: lines.append(f"Khoản {clause_no}")
            if body_for_ctx: lines.append(body_for_ctx)
        
        ctx_chunk = "\n".join(lines).strip()
        if ctx_chunk:
            contexts.append(ctx_chunk)
        
        # Source citation
        src = p.get("display_citation", "")
        sources.append(f"{src}" if src else "")
    
    context = "\n\n".join(contexts)
    return context, sources
def retrieve_random(k: int = 10):
    """

    Function for generating random questions 

    Lấy ngẫu nhiên k đoạn văn bản luật từ Database.
    Kỹ thuật: Tạo một vector ngẫu nhiên và tìm kiếm theo vector đó.
    """
    # Model gte-multilingual-base có chiều vector là 768
    # Tạo một vector ngẫu nhiên kích thước 768
    import numpy as np
    random_vector = np.random.rand(768).tolist()
    
    # Query Weaviate bằng vector ngẫu nhiên này
    # Nó sẽ trả về các đoạn văn bản có vector gần nhất (ngẫu nhiên)
    resp = weaviate_collection.query.near_vector(
        near_vector=random_vector,
        limit=k,
        return_properties=["enriched_text", "display_citation"]
    )
    
    results = []
    for obj in resp.objects:
        results.append({
            "props": obj.properties,
            "score": 0.0 # Score không quan trọng khi random
        })
        
    return results
# ---------------- CLEANUP ----------------
import atexit

def cleanup():
    """Close Weaviate connection on exit"""
    try:
        if client:
            client.close()
    except:
        pass

atexit.register(cleanup)
