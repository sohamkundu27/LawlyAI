"""
DEPRECATED: This file is superseded by backend/app.py.
Please run `uvicorn backend.app:app --reload` instead.
"""

"""
FastAPI application for Hybrid Legal Search.

Run with:
    python backend/main.py
    OR
    uvicorn backend.main:app --reload
"""

import sys
import os
from contextlib import asynccontextmanager

# Add project root to sys.path so imports work regardless of where script is run
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn

# Try absolute import first (for uvicorn backend.main:app), fallback to relative (for direct python execution)
try:
    from backend.hybrid_search import HybridSearcher
    from backend.lawyer_extractor import extract_lawyers_from_search_results
    from backend.lawyer_enrichment import enrich_lawyers_with_emails
except ImportError:
    from hybrid_search import HybridSearcher
    from lawyer_extractor import extract_lawyers_from_search_results
    from lawyer_enrichment import enrich_lawyers_with_emails

# Global searcher instance
searcher: Optional[HybridSearcher] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager to handle startup and shutdown events.
    """
    global searcher
    # Startup
    dataset_path = "./vectorized_dataset"
    if not os.path.exists(dataset_path):
        # Try finding it relative to this file if not in cwd
        current_dir = os.path.dirname(os.path.abspath(__file__))
        alt_path = os.path.join(current_dir, "vectorized_dataset")
        if os.path.exists(alt_path):
            dataset_path = alt_path
        else:
            print(f"WARNING: Dataset path '{dataset_path}' not found.")
            print("Make sure you have run build_embeddings.py first.")
    
    try:
        searcher = HybridSearcher(dataset_path=dataset_path)
        print("Searcher initialized successfully.")
    except Exception as e:
        print(f"Error initializing searcher: {e}")
    
    yield
    
    # Shutdown
    searcher = None

app = FastAPI(title="Legal Hybrid Search API", lifespan=lifespan)

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
    # Add extracted lawyers directly to the search result
    extracted_lawyers: Optional[List[Dict[str, Any]]] = []

@app.post("/search-legal", response_model=List[SearchResult])
def search_legal(request: SearchRequest):
    """
    Search for legal cases using hybrid search (Vector + Keyword) AND automatically extract lawyers from them.
    """
    if searcher is None:
        raise HTTPException(status_code=503, detail="Search service not initialized (dataset load failed?)")
    
    try:
        # 1. Get Search Results
        results = searcher.search(request.query, top_k=request.top_k)
        
        # 2. Extract Lawyers using Gemini
        # This returns a flat list of unique lawyers found across all documents
        all_extracted_lawyers = extract_lawyers_from_search_results(
            query=request.query,
            search_results=results
        )
        
        # 2.5. Enrich Lawyers with Emails (Apollo + Heuristics)
        all_extracted_lawyers = enrich_lawyers_with_emails(all_extracted_lawyers)
        
        # 3. Attach extracted lawyers back to their respective case documents
        # We match them by 'document_id' or 'citation'
        for res in results:
            res_id = res.get("id")
            # Initialize the list
            res['extracted_lawyers'] = []
            
            if res_id:
                # Filter lawyers that belong to this document
                # The extractor preserves document_id in the lawyer dict
                res['extracted_lawyers'] = [
                    l for l in all_extracted_lawyers 
                    if l.get("document_id") == res_id
                ]
        
        return results
        
    except Exception as e:
        # Log error but try to return results without lawyers if extraction fails?
        # Or fail hard? Let's fail hard for now so we know it's broken.
        print(f"Error in search/extraction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    """
    Simple health check endpoint.
    """
    status = "healthy" if searcher is not None else "degraded"
    return {"status": status}

if __name__ == "__main__":
    # Allow running this file directly
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
