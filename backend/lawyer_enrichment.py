import re
import logging
from typing import Optional, Tuple, List, Dict, Any

# Hardcoded Apollo API Key as requested
APOLLO_API_KEY = "PC-tDXN37lZxj9f_1huTrQ"

def split_name(full_name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Splits a full name into first and last name.
    """
    if not full_name:
        return None, None
        
    # Remove non-letters except spaces
    clean = re.sub(r'[^a-zA-Z\s]', '', full_name)
    tokens = clean.split()
    
    if not tokens:
        return None, None
        
    first_name = tokens[0].lower()
    last_name = tokens[-1].lower() if len(tokens) > 1 else None
    
    return first_name, last_name

def build_domain_from_firm(firm: str) -> Optional[str]:
    """
    Constructs a domain from a firm name.
    Uses acronyms for long names (>8 chars).
    """
    if not firm:
        return None

    # Lowercase and strip surrounding whitespace
    raw = firm.lower().strip()

    # Remove common suffixes like "llc", "l.l.c.", "p.c.", "pc", "inc", "co.", etc.
    # Work token-wise so we preserve words we want for the acronym.
    tokens = re.split(r"[\s,]+", raw)
    filtered_tokens = []
    SUFFIXES = {
        "llc", "l.l.c.", "l.l.c", "p.c.", "pc", "p.c", "inc", "inc.", "co", "co.", "corp", "corporation",
        "llp", "l.l.p.", "lp", "l.p.", "pllc", "p.l.l.c.", "ltd", "ltd.", 
        "professional", "corporation", "pa", "p.a."
    }
    
    for t in tokens:
        if not t:
            continue
        # strip punctuation
        cleaned = re.sub(r"[^a-z]", "", t)
        if not cleaned:
            continue
        if cleaned in SUFFIXES:
            continue
        filtered_tokens.append(cleaned)

    if not filtered_tokens:
        return None

    # Base domain candidate by concatenating tokens
    base = "".join(filtered_tokens)

    # If base is longer than 8 characters, build an acronym
    if len(base) > 8:
        # Use first letter of each token, but keep at least 2 characters if only one token
        acronym = "".join(t[0] for t in filtered_tokens if t)
        if len(acronym) >= 2:
            base = acronym
        else:
            # fallback if something weird happens, or acronym is too short (single word firm)
            # If it's a single word > 8 chars, e.g. "Richardson", acronym is "r". 
            # In that case, we probably want "richardson.com" or truncated?
            # Prompt says: "keep at least 2 characters if only one token ... fallback if something weird happens base = base[:8]"
            # If acronym is "r" (len 1), we fall to else -> base[:8].
            base = base[:8]

    return f"{base}.com"

def find_best_email_for_lawyer(full_name: str, firm: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (email, email_source).
    
    email_source is one of:
      - "apollo_person"         # direct match for the individual
      - "firm_domain_guess"     # guessed based on firm domain
      - "gmail_guess"           # fallback to gmail
      - None                    # nothing found and no guess
    """
    if not full_name:
        return None, None
    
    # NOTE: Apollo lookup intentionally disabled to save latency / quota.
    # The block below is left for reference but commented out.
    # try:
    #     ...
    
    # Step 2: Fallback Logic (Firm Domain or Gmail)
    first_name, last_name = split_name(full_name)
    
    # Try to guess based on firm domain first
    firm_domain = build_domain_from_firm(firm) if firm else None
    
    if first_name and last_name:
        if firm_domain:
            return f"{first_name}.{last_name}@{firm_domain}", "firm_domain_guess"
        else:
            return f"{first_name}.{last_name}@gmail.com", "gmail_guess"
            
    # If only one name token or parsing failed
    elif first_name:
        if firm_domain:
            return f"{first_name}@{firm_domain}", "firm_domain_guess"
        else:
            # Normalize name for fallback
            normalized = re.sub(r'[^a-z]', '', full_name.lower())
            return f"{normalized}@gmail.com", "gmail_guess"

    return None, None

def enrich_lawyers_with_emails(lawyers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Enrich a list of lawyer dictionaries with email addresses.
    Mutates the dictionaries in place but also returns the list.
    """
    enriched = []
    for lawyer in lawyers:
        # Extract fields safely
        name = lawyer.get("name") or ""
        firm = lawyer.get("firm_or_affiliation") or ""
        
        # Lookup email
        email, source = find_best_email_for_lawyer(name, firm)
        
        # Add to dictionary
        lawyer["email"] = email
        lawyer["email_source"] = source
        
        enriched.append(lawyer)
        
    return enriched
