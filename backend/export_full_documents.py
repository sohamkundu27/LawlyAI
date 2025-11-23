"""
Script to export full legal documents from the vectorized dataset to a JSONL file.

Usage:
    python backend/export_full_documents.py
"""

import os
import json
from datasets import load_from_disk
from tqdm import tqdm

def export_full_documents(input_path: str, output_path: str):
    """
    Exports document text and metadata to a JSONL file.
    """
    print(f"Loading dataset from {input_path}...")
    try:
        dataset = load_from_disk(input_path)
    except Exception as e:
        print(f"Error loading dataset: {e}")
        return

    print(f"Loaded {len(dataset)} records.")
    print(f"Exporting to {output_path}...")

    # Ensure output directory exists (though it should be inside input_path usually)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for row in tqdm(dataset, desc="Exporting"):
            # Extract fields
            doc_text = row.get("document")
            
            # Handle None/empty
            if doc_text is None:
                doc_text = ""
            
            # Create record
            record = {
                "id": row.get("id"),
                "title": row.get("title"),
                "state": row.get("state"),
                "citation": row.get("citation"),
                "document": doc_text
            }
            
            # Write line (json.dumps handles escaping newlines within the string automatically)
            # ensure_ascii=False preserves actual UTF-8 chars instead of \uXXXX escaping
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print("Export complete.")

if __name__ == "__main__":
    # Adjust paths if running from root or backend
    # The user specified ./vectorized_dataset which usually implies running from root
    INPUT_DATASET = "./vectorized_dataset"
    OUTPUT_FILE = "./vectorized_dataset/full_documents.jsonl"
    
    export_full_documents(INPUT_DATASET, OUTPUT_FILE)

