from datasets import load_dataset

def download_case_law_dataset():
    """
    Download the HFforLegal/case-law dataset from Hugging Face.
    """
    print("Downloading HFforLegal/case-law dataset...")
    
    # Load the dataset
    dataset = load_dataset("HFforLegal/case-law")
    
    print(f"Dataset downloaded successfully!")
    print(f"Dataset info: {dataset}")
    
    # Print some information about the dataset
    if isinstance(dataset, dict):
        for split_name, split_data in dataset.items():
            print(f"\n{split_name} split:")
            print(f"  Number of examples: {len(split_data)}")
            if len(split_data) > 0:
                print(f"  Features: {split_data.features}")
                print(f"  Example: {split_data[0]}")
    else:
        print(f"Number of examples: {len(dataset)}")
        if len(dataset) > 0:
            print(f"Features: {dataset.features}")
            print(f"Example: {dataset[0]}")
    
    return dataset

if __name__ == "__main__":
    dataset = download_case_law_dataset()

