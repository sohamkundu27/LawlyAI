import sys
from datasets import load_dataset, get_dataset_config_names

# Based on analysis of HFforLegal/case-law
RECOMMENDED_CONFIG = None
RECOMMENDED_SPLIT = "us"

def debug_dataset(dataset_id="HFforLegal/case-law"):
    print(f"Debugging dataset: {dataset_id}")
    print("=" * 50)

    try:
        configs = get_dataset_config_names(dataset_id)
        print(f"Found {len(configs)} configurations: {configs}")
    except Exception as e:
        print(f"Error getting config names: {e}")
        configs = []

    print("-" * 50)

    successful_loads = []

    # 1. Try loading each specific config
    if configs:
        for config in configs:
            print(f"\nAttempting to load config: '{config}'")
            try:
                ds = load_dataset(dataset_id, config, split="train", trust_remote_code=True)
                num_rows = len(ds)
                features = list(ds.features.keys())
                print(f"  SUCCESS: Loaded '{config}' (split='train')")
                print(f"  Rows: {num_rows}")
                print(f"  Features: {features}")
                successful_loads.append({"config": config, "split": "train", "rows": num_rows})
            except Exception as e:
                print(f"  FAILED to load '{config}': {e}")

    # 2. Try loading without specific config (default)
    print("\n" + "-" * 50)
    print("Attempting default load strategies (no config specified)...")
    
    strategies = [
        {"name": "default (no split)", "kwargs": {}},
        {"name": "split='train'", "kwargs": {"split": "train"}},
        {"name": "split='all'", "kwargs": {"split": "all"}}
    ]

    for strategy in strategies:
        print(f"\nStrategy: {strategy['name']}")
        try:
            ds = load_dataset(dataset_id, **strategy['kwargs'], trust_remote_code=True)
            
            # Handle DatasetDict vs Dataset
            if hasattr(ds, "keys") and not hasattr(ds, "features"):  # DatasetDict
                print(f"  Result: DatasetDict with splits: {list(ds.keys())}")
                for split_name in ds.keys():
                    subset = ds[split_name]
                    print(f"    Split '{split_name}': {len(subset)} rows, features: {list(subset.features.keys())}")
                    successful_loads.append({"config": None, "split": split_name, "rows": len(subset)})
            else:  # Dataset
                print(f"  Result: Dataset with {len(ds)} rows")
                print(f"  Features: {list(ds.features.keys())}")
                successful_loads.append({"config": None, "split": "unknown", "rows": len(ds)})
                
        except Exception as e:
            print(f"  FAILED: {e}")

    print("\n" + "=" * 50)
    print("SUMMARY & RECOMMENDATION")
    print("=" * 50)

    if not successful_loads:
        print("No data could be loaded. The dataset might be empty, restricted, or require authentication.")
    else:
        # Find the one with the most rows
        best = max(successful_loads, key=lambda x: x['rows'])
        rec_config = best['config'] if best['config'] else "None (default)"
        rec_split = best['split']
        
        print(f"Successfully loaded {len(successful_loads)} variations.")
        print(f"Largest dataset found: Config='{rec_config}', Split='{rec_split}', Rows={best['rows']}")
        
        # Recommendation code block
        print("\nRECOMMENDED VARIABLE:")
        if best['config']:
            print(f'RECOMMENDED_CONFIG = "{best["config"]}"')
        else:
            print('RECOMMENDED_CONFIG = None  # Use default config')

if __name__ == "__main__":
    debug_dataset()
