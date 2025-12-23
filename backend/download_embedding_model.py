"""
Script to pre-download the sentence transformer embedding model for offline use.

Run this script once with internet connection to download the model.
The model will be cached locally and can be used offline afterwards.
"""

import os
import sys
from pathlib import Path
from sentence_transformers import SentenceTransformer #type: ignore

# Set the cache directory to be in the backend/embeddings folder for portability
EMBEDDINGS_DIR = Path(__file__).parent / "embeddings"
EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)

# Set environment variables for HuggingFace cache (using new HF_HOME instead of deprecated TRANSFORMERS_CACHE)
os.environ['HF_HOME'] = str(EMBEDDINGS_DIR)
os.environ['SENTENCE_TRANSFORMERS_HOME'] = str(EMBEDDINGS_DIR)
os.environ['TRANSFORMERS_CACHE'] = str(EMBEDDINGS_DIR)  # Keep for backwards compatibility

MODEL_NAME = "sentence-transformers/paraphrase-MiniLM-L3-v2"

def download_model():
    """Download and cache the embedding model"""
    print(f"Downloading embedding model: {MODEL_NAME}")
    print(f"Cache directory: {EMBEDDINGS_DIR}")
    print("-" * 60)
    
    try:
        # This will download the model and cache it
        model = SentenceTransformer(MODEL_NAME, cache_folder=str(EMBEDDINGS_DIR))
        
        print(f"\n✓ Model downloaded successfully!")
        print(f"✓ Model cached at: {EMBEDDINGS_DIR}")
        print(f"\nModel info:")
        print(f"  - Max sequence length: {model.max_seq_length}")
        print(f"  - Embedding dimension: {model.get_sentence_embedding_dimension()}")
        
        # Test the model with a sample sentence
        print(f"\nTesting model with sample text...")
        test_embedding = model.encode("This is a test sentence.")
        print(f"✓ Model test successful! Embedding shape: {test_embedding.shape}")
        
        print(f"\n" + "=" * 60)
        print(f"SUCCESS: Model is ready for offline use!")
        print(f"=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error downloading model: {e}")
        print(f"\nPlease ensure:")
        print(f"  1. You have internet connection")
        print(f"  2. You have sufficient disk space")
        print(f"  3. sentence-transformers package is installed")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Embedding Model Downloader")
    print("=" * 60)
    print()
    
    success = download_model()
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
