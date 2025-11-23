"""
FastAPI application for Hybrid Legal Search.

Run with:
    uvicorn backend.main:app --reload
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os

from backend.hybrid_search import HybridSearcher

app = FastAPI(title="Legal Hybrid Search API")

# Global searcher instance
searcher: Optional[HybridSearcher] = None

@app.on_event("startup")
def startup_event():
    """
    Initialize the HybridSearcher on startup.
    """
    global searcher
    # Check if dataset exists
    dataset_path = "./vectorized_dataset"
    if not os.path.exists(dataset_path):
        print(f"WARNING: Dataset path '{dataset_path}' not found.")
        print("Make sure you have run build_embeddings.py first.")
    
    try:
        searcher = HybridSearcher(dataset_path=dataset_path)
    except Exception as e:
        print(f"Error initializing searcher: {e}")
        # We don't raise here to allow the app to start, but endpoints will fail
        pass

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5

class SearchResult(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    state: Optional[str] = None
    citation: Optional[str] = None
    snippet: Optional[str] = None
    document: Optional[str] = None
    dense_score: float
    bm25_score: float
    combined_score: float

@app.post("/search-legal", response_model=List[SearchResult])
def search_legal(request: SearchRequest):
    """
    Search for legal cases using hybrid search (Vector + Keyword).
    """
    if searcher is None:
        raise HTTPException(status_code=503, detail="Search service not initialized (dataset load failed?)")
    
    try:
        results = searcher.search(request.query, top_k=request.top_k)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    """
    Simple health check endpoint.
    """
    status = "healthy" if searcher is not None else "degraded"
    return {"status": status}
