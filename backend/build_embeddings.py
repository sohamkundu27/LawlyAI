"""
Script to build vectorized embeddings for a Hugging Face dataset.

This script:
1. Loads a dataset from Hugging Face Hub
2. Computes sentence embeddings for a specified text column
3. Saves the augmented dataset with embeddings locally
4. Optionally pushes the dataset back to Hugging Face Hub
"""

import argparse
import os
from typing import List, Dict, Any

from datasets import load_dataset, Dataset
from sentence_transformers import SentenceTransformer
import numpy as np
from tqdm import tqdm


def validate_dataset(dataset: Dataset, text_column: str) -> None:
    """
    Validate that the dataset contains the required text column.
    
    Args:
        dataset: The loaded dataset
        text_column: Name of the column to validate
        
    Raises:
        ValueError: If the text column doesn't exist in the dataset
    """
    if text_column not in dataset.column_names:
        available_columns = ", ".join(dataset.column_names)
        raise ValueError(
            f"Text column '{text_column}' not found in dataset. "
            f"Available columns: {available_columns}"
        )


def embed_batch(
    batch: Dict[str, List[Any]],
    text_column: str,
    model: SentenceTransformer
) -> Dict[str, List[List[float]]]:
    """
    Compute embeddings for a batch of texts.
    
    Args:
        batch: Dictionary containing batch data with text_column
        text_column: Name of the column containing text to embed
        model: SentenceTransformer model for encoding
        
    Returns:
        Dictionary with 'embedding' key containing list of embedding vectors
    """
    texts = batch[text_column]
    
    # Handle None/empty strings - convert to empty string for encoding
    cleaned = [t if t is not None and t != "" else "" for t in texts]
    
    # Encode texts to embeddings (returns numpy array)
    embeddings = model.encode(cleaned, convert_to_numpy=True, show_progress_bar=False)
    
    # Convert to list of lists (each embedding is a list of floats)
    embeddings_list = embeddings.tolist()
    
    return {"embedding": embeddings_list}


def build_embeddings(
    dataset_id: str,
    split: str,
    model_name: str,
    text_column: str,
    batch_size: int,
    output_dir: str,
    push_to_hub: bool,
    new_dataset_id: str = None,
    limit: int = None
) -> None:
    """
    Main function to build embeddings for a dataset.
    
    Args:
        dataset_id: Hugging Face dataset ID
        split: Dataset split name (e.g., "train")
        model_name: SentenceTransformer model name
        text_column: Column name containing text to embed
        batch_size: Batch size for processing
        output_dir: Directory to save the vectorized dataset
        push_to_hub: Whether to push the dataset to Hugging Face Hub
        new_dataset_id: New dataset ID for HF Hub (if None, uses dataset_id + "-embeddings")
        limit: Limit the number of rows to process
    """
    print("=" * 80)
    print("Building Vectorized Dataset")
    print("=" * 80)
    print(f"Dataset ID: {dataset_id}")
    print(f"Split: {split}")
    print(f"Model: {model_name}")
    print(f"Text Column: {text_column}")
    print(f"Batch Size: {batch_size}")
    print("=" * 80)
    
    # Load the dataset
    print(f"\nLoading dataset '{dataset_id}' (split: '{split}')...")
    # Use verification_mode="no_checks" to handle dataset integrity issues
    try:
        dataset = load_dataset(dataset_id, split=split, verification_mode="no_checks")
    except Exception as e:
        # If that fails, try without split specification
        print(f"Warning: Error loading with split '{split}': {e}")
        print("Attempting to load without split specification...")
        full_dataset = load_dataset(dataset_id, verification_mode="no_checks")
        if isinstance(full_dataset, dict):
            if split in full_dataset:
                dataset = full_dataset[split]
            else:
                # Use the first available split
                split_name = list(full_dataset.keys())[0]
                print(f"Split '{split}' not found. Using '{split_name}' instead.")
                dataset = full_dataset[split_name]
        else:
            dataset = full_dataset
    
    print(f"Dataset loaded: {len(dataset)} rows")
    
    # Apply limit if specified
    if limit is not None and len(dataset) > limit:
        print(f"\nLimiting dataset to first {limit} rows...")
        dataset = dataset.select(range(limit))
        print(f"Dataset size after limiting: {len(dataset)} rows")
    
    print(f"Columns: {', '.join(dataset.column_names)}")
    
    # Validate text column exists
    validate_dataset(dataset, text_column)
    
    # Load the sentence transformer model
    print(f"\nLoading model '{model_name}'...")
    model = SentenceTransformer(model_name)
    print("Model loaded successfully!")
    
    # Create embedding function with model and text_column bound
    def embed_batch_wrapper(batch):
        return embed_batch(batch, text_column, model)
    
    # Compute embeddings using map with batching
    print(f"\nComputing embeddings (batch size: {batch_size})...")
    dataset_with_embeddings = dataset.map(
        embed_batch_wrapper,
        batched=True,
        batch_size=batch_size,
        desc="Computing embeddings"
    )
    
    print(f"Embeddings computed for {len(dataset_with_embeddings)} rows")
    
    # Check embedding dimension
    if len(dataset_with_embeddings) > 0:
        embedding_dim = len(dataset_with_embeddings[0]["embedding"])
        print(f"Embedding dimension: {embedding_dim}")
    
    # Save dataset locally
    print(f"\nSaving dataset to '{output_dir}'...")
    os.makedirs(output_dir, exist_ok=True)
    dataset_with_embeddings.save_to_disk(output_dir)
    print(f"Dataset saved successfully to {output_dir}")
    
    # Optionally save as parquet for easier inspection
    parquet_path = os.path.join(output_dir, "dataset.parquet")
    print(f"Saving parquet file to '{parquet_path}'...")
    dataset_with_embeddings.to_parquet(parquet_path)
    print("Parquet file saved successfully")
    
    # Optionally push to Hugging Face Hub
    if push_to_hub:
        if new_dataset_id is None:
            new_dataset_id = dataset_id + "-embeddings"
        
        print(f"\nPushing dataset to Hugging Face Hub as '{new_dataset_id}'...")
        
        # Check for HF token
        hf_token = os.getenv("HF_TOKEN")
        if hf_token is None:
            print("Warning: HF_TOKEN environment variable not set.")
            print("Attempting to push without explicit token (will use cached credentials if available)...")
        
        dataset_with_embeddings.push_to_hub(
            new_dataset_id,
            token=hf_token
        )
        print(f"Dataset pushed successfully to '{new_dataset_id}'")
    
    print("\n" + "=" * 80)
    print("Process completed successfully!")
    print("=" * 80)


def main():
    """Main entry point."""
    # Hardcoded configuration for ease of use
    dataset_id = "HFforLegal/case-law"
    split = "us"
    limit = 100000
    
    # Other defaults
    model_name = "sentence-transformers/all-mpnet-base-v2"
    text_column = "document"
    batch_size = 64
    output_dir = "./vectorized_dataset"
    push_to_hub = False
    new_dataset_id = None

    print(f"Running with hardcoded configuration:")
    print(f"  Dataset: {dataset_id}")
    print(f"  Split: {split}")
    print(f"  Limit: {limit}")

    # Run the main function
    build_embeddings(
        dataset_id=dataset_id,
        split=split,
        model_name=model_name,
        text_column=text_column,
        batch_size=batch_size,
        output_dir=output_dir,
        push_to_hub=push_to_hub,
        new_dataset_id=new_dataset_id,
        limit=limit
    )


if __name__ == "__main__":
    main()

