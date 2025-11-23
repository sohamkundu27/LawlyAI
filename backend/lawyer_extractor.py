import os
from typing import Any, Dict, List
import textwrap
import json
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GEMINI_MODEL_NAME = "models/gemini-2.0-flash"

def _configure_gemini() -> None:
    """Configures the Gemini client with the API key."""
    # api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    api_key = "AIzaSyBS8PzkdA1gSn_jcU20xH4IL7btXW6APhQ"
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY (or GOOGLE_API_KEY) environment variable is not set")
    genai.configure(api_key=api_key)

def _chunk_text(text: str, max_chars: int = 12000) -> List[str]:
    """Naive character-based chunking to keep prompts under token/size limits."""
    text = text.strip()
    if not text:
        return []
    return [text[i:i+max_chars] for i in range(0, len(text), max_chars)]

def _build_prompt(user_situation: str, doc_meta: Dict[str, Any], chunk_text: str) -> str:
    """
    Build a clear, extraction-style prompt for Gemini: we want JSON of lawyers.
    """
    title = doc_meta.get("title") or ""
    citation = doc_meta.get("citation") or ""
    doc_id = doc_meta.get("id") or ""

    return textwrap.dedent(f"""
    You are an expert legal-entity extraction assistant.

    TASK
    From the legal opinion text below, extract EVERY lawyer, attorney, or legal representative mentioned, including:
    - Attorneys for appellants, respondents, petitioners, intervenors, amici, etc.
    - Counsel who argued at any court.
    - City/State/County/Agency attorneys.
    - Law firms (as affiliation of those lawyers).
    - Any other named individuals clearly acting as lawyers.

    IMPORTANT
    - Be exhaustive: if in doubt whether a person is a lawyer/attorney/counsel, include them.
    - Do NOT include judges, justices, parties, corporations, or organizations unless they are law firms.
    - Try to infer the side (e.g., "Appellant", "Respondent", "Amicus", "Plaintiff", "Defendant") when the text makes it clear.
    - If the side is unclear, set side to null.
    - Include law firm or affiliation when specified (e.g., "Law Offices of John Smith", "Deputy City Attorney, City of Los Angeles").
    - INFER the primary specialty/practice area for each lawyer based on the nature of the case (e.g., "personal injury", "criminal defense", "family law", "corporate law", "employment law", "securities litigation"). Keep it concise (1-3 lowercase words).
    - INFER a match_score (integer 0-100) describing how well this lawyer's specialty matches the user's legal situation below. 0 = not relevant at all; 100 = perfect fit for that situation.
    - De-duplicate within this chunk by exact name string.

    OUTPUT FORMAT
    Return ONLY valid JSON. No prose, no comments.
    Structure:
    {{
      "lawyers": [
        {{
          "name": "Full Name",
          "side": "Appellant" | "Respondent" | "Petitioner" | "Plaintiff" | "Defendant" | "Amicus" | "Other" | null,
          "role": "Attorney for Appellant" | "Counsel who argued" | "Deputy City Attorney" | "City Attorney" | "Lawyer" | null,
          "firm_name": "Law Offices of John M. Werlich" | "City Attorney, City of Los Angeles" | null,
          "specialty": "personal injury" | "criminal defense" | "family law" | "general litigation" | null,
          "match_score": 0-100,
          "case_title": "{title}",
          "citation": "{citation}",
          "document_id": "{doc_id}"
        }}
      ]
    }}

    USER'S LEGAL SITUATION (use ONLY to judge relevance and match_score, never to filter results):
    "{user_situation}"

    LEGAL OPINION TEXT CHUNK:
    \"\"\"{chunk_text}\"\"\"
    """)

def _extract_from_chunk(user_situation: str, doc_meta: Dict[str, Any], chunk_text: str) -> List[Dict[str, Any]]:
    _configure_gemini()
    prompt = _build_prompt(user_situation, doc_meta, chunk_text)

    model = genai.GenerativeModel(GEMINI_MODEL_NAME)
    
    try:
        response = model.generate_content(prompt)
        
        # Safely parse JSON – handle model sometimes adding backticks or spaces.
        text = response.text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            # Remove possible language hints like "json"
            if text.lower().startswith("json"):
                text = text[4:].lstrip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object if there's extra text
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                try:
                    data = json.loads(text[start:end+1])
                except:
                    return []
            else:
                return []
        except Exception:
            return []

        lawyers = data.get("lawyers") or []
        # Ensure each item is a dict with at least "name"
        clean = []
        for l in lawyers:
            if not isinstance(l, dict):
                continue
            name = (l.get("name") or "").strip()
            if not name:
                continue
            
            firm_value = (l.get("firm_name") or l.get("firm_or_affiliation") or "").strip()
            specialty = (l.get("specialty") or "general litigation").strip() or "general litigation"
            try:
                match_score = int(l.get("match_score", 0))
            except (TypeError, ValueError):
                match_score = 0
            match_score = max(0, min(100, match_score))

            normalized = dict(l)
            normalized["firm_or_affiliation"] = firm_value
            normalized["specialty"] = specialty.lower()
            normalized["match_score"] = match_score

            clean.append(normalized)
        return clean
        
    except Exception as e:
        print(f"Error extracting from chunk: {e}")
        return []

def extract_lawyers_from_search_results(
    user_situation: str,
    search_results: List[Dict[str, Any]],
    max_docs: int = 5, # Reduced default to avoid hitting rate limits quickly
) -> List[Dict[str, Any]]:
    """
    Main entrypoint for calling from FastAPI.
    - user_situation: original user query/keywords describing the situation.
    - search_results: list of dicts with at least id/title/citation/document.
    - max_docs: safety cap to avoid over-calling Gemini.
    Returns a de-duplicated list of lawyers across all docs.
    """
    all_lawyers: List[Dict[str, Any]] = []

    # Process documents
    for doc in search_results[:max_docs]:
        doc_text = doc.get("document") or ""
        if not doc_text.strip():
            continue

        # Just take the first chunk or two to avoid processing huge full texts if not needed
        # Often lawyer info is at the start or end.
        # Let's take first 12000 chars which is usually enough for header info
        chunks = _chunk_text(doc_text)
        
        # Only process first chunk to be safe on rate limits for now, 
        # unless it's very short, then maybe check first 2
        chunks_to_process = chunks[:2] 
        
        for chunk in chunks_to_process:
            chunk_lawyers = _extract_from_chunk(user_situation, doc, chunk)
            all_lawyers.extend(chunk_lawyers)

    # De-duplicate across docs by case-insensitive name + citation + document_id
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for l in all_lawyers:
        # Create a unique key for the lawyer entry
        # We include citation/doc_id so we don't dedup the same lawyer across *different* cases
        # (We want to see if they appear in multiple cases)
        # Wait, the prompt says "de-duplicated list of lawyers across all docs". 
        # If the same lawyer is in multiple docs, do we want them once or once per doc?
        # "Extract EVERY lawyer... that could be useful"
        # Usually "find lawyers" implies finding unique people.
        # But knowing they are in multiple cases is useful.
        # Let's keep unique (Person, Case) pairs.
        
        name = (l.get("name") or "").strip()
        citation = (l.get("citation") or "").strip()
        doc_id = (l.get("document_id") or "").strip()
        
        key = (
            name.lower(),
            citation,
            doc_id,
        )
        
        if not name:
            continue
            
        if key in seen:
            continue
            
        seen.add(key)
        deduped.append(l)

    return deduped

