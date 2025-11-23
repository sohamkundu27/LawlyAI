"""
Hybrid Search Module

This module implements a HybridSearcher class that combines:
1. Dense vector search using FAISS (Cosine Similarity)
2. Sparse keyword search using BM25 (Okapi BM25)

Usage:
    searcher = HybridSearcher(dataset_path="./vectorized_dataset")
    results = searcher.search("query string", top_k=5)
"""

import os
import pickle
import numpy as np
import faiss
from datasets import load_from_disk
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
from typing import List, Dict, Any

class HybridSearcher:
    def __init__(self, dataset_path: str = "./vectorized_dataset"):
        """
        Initialize the HybridSearcher.
        
        Args:
            dataset_path: Path to the directory containing the saved Hugging Face dataset.
        """
        print(f"Loading dataset from {dataset_path}...")
        self.dataset = load_from_disk(dataset_path)
        print(f"Loaded {len(self.dataset)} documents.")
        
        self.dataset_path = dataset_path
        
        # Load embedding model
        print("Loading SentenceTransformer model...")
        self.model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
        
        # Build FAISS Index
        print("Building FAISS index...")
        self._build_faiss_index()
        
        # Build BM25 Index
        print("Building BM25 index...")
        self._build_bm25_index()
        
        print("Hybrid Searcher initialized successfully.")

    def _build_faiss_index(self):
        """
        Builds a FAISS IndexFlatIP for cosine similarity.
        """
        # Extract embeddings
        # Assuming 'embedding' column exists and contains lists of floats
        if "embedding" not in self.dataset.column_names:
            raise ValueError("Dataset must have an 'embedding' column.")

        embeddings = np.array(self.dataset["embedding"], dtype=np.float32)
        
        # Normalize embeddings for Cosine Similarity (IndexFlatIP operates on dot product)
        faiss.normalize_L2(embeddings)
        
        self.dimension = embeddings.shape[1]
        self.faiss_index = faiss.IndexFlatIP(self.dimension)
        self.faiss_index.add(embeddings)
        print(f"FAISS index built with {self.faiss_index.ntotal} vectors.")

    def _build_bm25_index(self):
        """
        Builds a BM25 index using simple tokenization, with caching.
        """
        # Check for cached index
        cache_path = os.path.join(self.dataset_path, "bm25_index.pkl")
        
        if os.path.exists(cache_path):
            print(f"Loading BM25 index from cache: {cache_path}")
            try:
                with open(cache_path, "rb") as f:
                    self.bm25 = pickle.load(f)
                print("BM25 index loaded from cache.")
                return
            except Exception as e:
                print(f"Failed to load BM25 cache: {e}. Rebuilding...")

        # Simple tokenization: lowercase and split by whitespace
        # Using the 'document' column for text content
        if "document" not in self.dataset.column_names:
            raise ValueError("Dataset must have a 'document' column.")
            
        print("Tokenizing documents for BM25...")
        self.tokenized_docs = [
            doc.lower().split() if doc else [] 
            for doc in self.dataset["document"]
        ]
        print("Building BM25Okapi index...")
        self.bm25 = BM25Okapi(self.tokenized_docs)
        
        # Save cache
        print(f"Saving BM25 index to cache: {cache_path}")
        try:
            with open(cache_path, "wb") as f:
                pickle.dump(self.bm25, f)
            print("BM25 index cached successfully.")
        except Exception as e:
            print(f"Warning: Failed to cache BM25 index: {e}")

    def _normalize_scores(self, scores: np.ndarray) -> np.ndarray:
        """
        Normalize scores to [0, 1] using Min-Max normalization.
        """
        if len(scores) == 0:
            return scores
        min_score = np.min(scores)
        max_score = np.max(scores)
        if max_score == min_score:
            return np.zeros_like(scores)
        return (scores - min_score) / (max_score - min_score)

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Perform hybrid search.
        
        Args:
            query: Search query string.
            top_k: Number of results to return.
            
        Returns:
            List of result dictionaries with metadata and scores.
        """
        # 1. Dense Search (FAISS)
        # Encode query
        query_embedding = self.model.encode([query], convert_to_numpy=True)
        faiss.normalize_L2(query_embedding)
        
        # Search more candidates than top_k for re-ranking (e.g., 50 or 100)
        candidate_k = min(len(self.dataset), max(50, top_k * 2))
        
        # D: Dense scores (cosine similarity), I: Indices
        D, I = self.faiss_index.search(query_embedding, candidate_k)
        dense_scores = D[0]
        indices = I[0]
        
        # 2. Keyword Search (BM25)
        # Tokenize query
        tokenized_query = query.lower().split()
        
        # We need to compute BM25 scores for the *same* candidates found by FAISS
        # or we could score all and intersect, but scoring only candidates is faster for re-ranking.
        # Alternatively, standard hybrid search might retrieve top N from BM25 AND top N from FAISS and merge.
        # But the prompt asks to "computes BM25 scores for all docs or at least the top N candidates".
        # Calculating BM25 for ALL docs every time might be slow for large datasets, 
        # but 100k is manageable. Let's stick to scoring the candidates found by FAISS 
        # OR we can get top N from BM25 independently and merge pools.
        
        # The prompt says: "computes BM25 scores for all docs or at least the top N candidates"
        # followed by "combine them".
        # Let's compute BM25 for the candidates retrieved by FAISS to keep it simple and fast.
        # However, this might miss documents that have high keyword overlap but low semantic similarity.
        # A better approach usually is retrieval from both, then merge. 
        # Given "computes BM25 scores for ... top N candidates", I will score the indices returned by FAISS.
        
        # Actually, to get a true hybrid result, we ideally want candidates from BOTH methods.
        # But strictly following "computes BM25 scores for ... top N candidates", I will score the candidates from FAISS.
        # Wait, if I only score FAISS candidates, I can't find keyword-only matches.
        # Let's retrieve top N from BM25 as well, merge the sets of indices, and then score/rank.
        
        # Let's expand the pool:
        # Get top N dense
        # Get top N sparse
        # Union them
        # Score all in union
        
        # But to strictly follow the simplest interpretation of "computes BM25 scores for all docs or at least the top N candidates"
        # and "normalizes both score lists":
        # If I compute for ALL docs, I get a score for everyone.
        # If I compute for top N candidates (from FAISS), I only have scores for those.
        
        # Let's try the "Compute for all docs" approach for BM25 since 100k is small enough for BM25 
        # and it allows true hybrid ranking.
        
        bm25_scores_all = self.bm25.get_scores(tokenized_query)
        
        # Now we need dense scores for all docs too? No, that defeats the purpose of ANN.
        # So we must restrict to a set of candidates.
        # Standard approach: 
        # 1. Get top N from FAISS -> indices_dense, scores_dense
        # 2. Get top N from BM25 -> indices_sparse, scores_sparse
        # 3. Combine: Union of indices.
        # 4. For each index in Union:
        #       final_score = 0.7 * norm_dense + 0.3 * norm_sparse
        #       (fill missing dense/sparse scores with min or 0)
        
        # Let's implement this "Merge Pool" approach which is robust.
        
        # Step 1: FAISS Top N
        candidate_limit = 50 # Arbitrary N >= top_k
        D_faiss, I_faiss = self.faiss_index.search(query_embedding, candidate_limit)
        dense_hits = {idx: score for idx, score in zip(I_faiss[0], D_faiss[0])}
        
        # Step 2: BM25 Top N
        # rank_bm25 doesn't have a fast "get_top_n_with_scores" that returns indices easily without sorting all.
        # But get_scores returns a numpy array. We can np.argsort.
        bm25_scores_all = np.array(bm25_scores_all)
        top_bm25_indices = np.argsort(bm25_scores_all)[::-1][:candidate_limit]
        sparse_hits = {idx: bm25_scores_all[idx] for idx in top_bm25_indices}
        
        # Step 3: Union of candidates
        all_indices = set(dense_hits.keys()) | set(sparse_hits.keys())
        
        # Prepare combined results
        combined_results = []
        
        # We need to normalize the scores across the *candidates* (or globally).
        # Global normalization is better but we only have partial dense scores.
        # We will normalize based on the max/min seen in the retrieval sets.
        
        # Normalize Dense
        dense_vals = list(dense_hits.values())
        if dense_vals:
            d_min, d_max = min(dense_vals), max(dense_vals)
            d_norm_fn = lambda x: (x - d_min) / (d_max - d_min) if d_max > d_min else 0.0
        else:
            d_norm_fn = lambda x: 0.0
            
        # Normalize BM25
        sparse_vals = list(sparse_hits.values())
        if sparse_vals:
            s_min, s_max = min(sparse_vals), max(sparse_vals)
            s_norm_fn = lambda x: (x - s_min) / (s_max - s_min) if s_max > s_min else 0.0
        else:
            s_norm_fn = lambda x: 0.0
            
        for idx in all_indices:
            # Get raw scores, defaulting to 0 (or min) if not in the specific top-k
            # Using 0.0 for missing might be harsh if scores are usually high, 
            # but reasonable for "not in top N".
            d_raw = dense_hits.get(idx, 0.0) # Or use d_min? 0 is fine for "low relevance".
            s_raw = sparse_hits.get(idx, 0.0)
            
            # Since we only have dense scores for the top N from FAISS, 
            # treating others as 0 implies they are very far.
            # Same for BM25.
            
            d_norm = d_norm_fn(d_raw) if idx in dense_hits else 0.0
            s_norm = s_norm_fn(s_raw) if idx in sparse_hits else 0.0
            
            combined_score = 0.7 * d_norm + 0.3 * s_norm
            
            combined_results.append({
                "idx": idx,
                "dense_score": float(d_raw),
                "bm25_score": float(s_raw),
                "combined_score": float(combined_score)
            })
            
        # Sort by combined score
        combined_results.sort(key=lambda x: x["combined_score"], reverse=True)
        
        # Top K
        top_results = combined_results[:top_k]
        
        # Fetch actual data
        final_output = []
        for res in top_results:
            dataset_idx = int(res["idx"]) # datasets indices are ints
            row = self.dataset[dataset_idx]
            
            # Create result dict
            final_output.append({
                "id": row.get("id"),
                "title": row.get("title"),
                "state": row.get("state"),
                "citation": row.get("citation"),
                "snippet": row.get("document", "")[:200] + "...", # Short snippet
                "document": row.get("document", ""),
                "dense_score": res["dense_score"],
                "bm25_score": res["bm25_score"],
                "combined_score": res["combined_score"]
            })
            
        return final_output
