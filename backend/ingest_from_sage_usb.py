"""
Optimized ChromaDB Ingestion Script for SAGE_USB Data

This script ingests preprocessed NCERT educational content from the SAGE_USB folder
into ChromaDB collections with the new faster embedding model (paraphrase-MiniLM-L3-v2).

Features:
- Automatic detection of processed text files from SAGE_USB
- Batch processing for efficient ingestion
- Progress tracking and statistics
- Error handling and logging
- Supports both text files and mathematical equations

Compatible with Python 3.7+
"""

import os
import sys
import logging
import time
from pathlib import Path
from typing import List, Dict, Any
import glob
import re

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config_loader import ConfigLoader
from src.db_handler import ChromaDBHandler


def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/ingestion.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def find_sage_usb_folder():
    """
    Find SAGE_USB folder - check common locations
    Returns path to SAGE_USB folder or None
    """
    possible_locations = [
        Path("../SAGE_USB"),
        Path("../../SAGE_USB"),
        Path.home() / "SAGE_USB",
        Path("D:/SAGE_USB"),
        Path("E:/SAGE_USB"),
        Path("F:/SAGE_USB"),
    ]
    
    # Also check all drives on Windows
    import string
    if os.name == 'nt':
        for drive in string.ascii_uppercase:
            drive_path = Path(f"{drive}:/SAGE_USB")
            possible_locations.append(drive_path)
    
    for path in possible_locations:
        if path.exists() and path.is_dir():
            return path
    
    return None


def extract_class_number(filename: str) -> int:
    """
    Extract class number from filename
    Handles patterns like: class_10_math.txt, 10_science.txt, etc.
    """
    # Try different patterns
    patterns = [
        r'class[_\s]?(\d{1,2})',
        r'^(\d{1,2})[_\s]',
        r'_(\d{1,2})_',
    ]
    
    filename_lower = filename.lower()
    for pattern in patterns:
        match = re.search(pattern, filename_lower)
        if match:
            class_num = int(match.group(1))
            if 1 <= class_num <= 12:
                return class_num
    
    return None


def load_text_file(file_path: Path) -> List[str]:
    """
    Load and split text file into chunks
    Returns list of text chunks
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split by double newlines or sections
        chunks = []
        
        # First try to split by section markers
        if '===' in content or '---' in content:
            sections = re.split(r'={3,}|-{3,}', content)
            for section in sections:
                section = section.strip()
                if section and len(section) > 50:
                    chunks.append(section)
        else:
            # Split by paragraphs
            paragraphs = content.split('\n\n')
            current_chunk = ""
            
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                
                # If adding this paragraph exceeds chunk size, save current chunk
                if len(current_chunk) + len(para) > 800:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = para
                else:
                    current_chunk += "\n\n" + para if current_chunk else para
            
            if current_chunk:
                chunks.append(current_chunk)
        
        return chunks
    
    except Exception as e:
        logging.error(f"Error loading file {file_path}: {e}")
        return []


def ingest_data_to_chromadb(sage_usb_path: Path, db_handler: ChromaDBHandler, logger: logging.Logger):
    """
    Ingest all processed data from SAGE_USB into ChromaDB
    """
    logger.info(f"Starting ingestion from: {sage_usb_path}")
    
    # Find all text files
    all_text_files = list(sage_usb_path.glob("**/*.txt"))
    
    # Filter to only include processed NCERT files (class_X_subject_processed.txt pattern)
    text_files = [
        f for f in all_text_files 
        if 'class_' in f.name.lower() and '_processed.txt' in f.name.lower()
    ]
    
    logger.info(f"Found {len(text_files)} NCERT processed files (out of {len(all_text_files)} total .txt files)")
    
    stats = {
        'total_files': len(text_files),
        'processed_files': 0,
        'total_chunks': 0,
        'errors': 0,
        'by_class': {i: 0 for i in range(1, 13)}
    }
    
    start_time = time.time()
    
    for file_path in text_files:
        try:
            logger.info(f"Processing: {file_path.name}")
            
            # Extract class number from filename
            class_num = extract_class_number(file_path.name)
            
            if class_num is None:
                logger.warning(f"Could not extract class number from {file_path.name}, skipping")
                continue
            
            # Load and chunk the file
            chunks = load_text_file(file_path)
            
            if not chunks:
                logger.warning(f"No chunks extracted from {file_path.name}")
                continue
            
            # Extract metadata
            subject = "general"
            if "math" in file_path.name.lower():
                subject = "mathematics"
            elif "science" in file_path.name.lower():
                subject = "science"
            elif "english" in file_path.name.lower():
                subject = "english"
            elif "social" in file_path.name.lower():
                subject = "social_studies"
            
            # Batch insert chunks
            batch_data = []
            for i, chunk in enumerate(chunks):
                metadata = {
                    'source_file': file_path.name,
                    'subject': subject,
                    'class_num': class_num,
                    'chunk_id': i,
                    'type': 'content'  # Not a question
                }
                
                batch_data.append({
                    'question': chunk,  # Using 'question' field as content field
                    'metadata': metadata
                })
            
            # Insert batch
            db_handler.batch_insert(class_num, batch_data)
            
            stats['processed_files'] += 1
            stats['total_chunks'] += len(chunks)
            stats['by_class'][class_num] += len(chunks)
            
            logger.info(f"[OK] Inserted {len(chunks)} chunks from {file_path.name} into class{class_num}")
            
        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {e}")
            stats['errors'] += 1
            continue
    
    elapsed_time = time.time() - start_time
    
    # Print statistics
    logger.info("\n" + "="*60)
    logger.info("INGESTION COMPLETED")
    logger.info("="*60)
    logger.info(f"Total files processed: {stats['processed_files']}/{stats['total_files']}")
    logger.info(f"Total chunks ingested: {stats['total_chunks']}")
    logger.info(f"Errors: {stats['errors']}")
    logger.info(f"Time taken: {elapsed_time:.2f} seconds")
    logger.info(f"Chunks per second: {stats['total_chunks']/elapsed_time:.2f}")
    logger.info("\nChunks per class:")
    for class_num, count in stats['by_class'].items():
        if count > 0:
            logger.info(f"  Class {class_num}: {count} chunks")
    logger.info("="*60)
    
    return stats


def main():
    """Main ingestion workflow"""
    logger = setup_logging()
    
    logger.info("="*60)
    logger.info("SAGE ChromaDB Ingestion - OPTIMIZED VERSION")
    logger.info("="*60)
    
    # Load configuration
    logger.info("Loading configuration...")
    config_path = Path(__file__).parent / "config.yaml"
    config_loader = ConfigLoader(str(config_path))
    config = config_loader.load_config()
    
    logger.info(f"Embedding model: {config.chromadb.embedding_function}")
    logger.info(f"ChromaDB path: {config.chromadb.persist_directory}")
    
    # Find SAGE_USB folder
    logger.info("\nSearching for SAGE_USB folder...")
    sage_usb_path = find_sage_usb_folder()
    
    if sage_usb_path is None:
        logger.error("SAGE_USB folder not found!")
        logger.error("Please ensure SAGE_USB is accessible and contains processed data.")
        logger.error("You can also edit this script to add custom paths.")
        sys.exit(1)
    
    logger.info(f"[OK] Found SAGE_USB at: {sage_usb_path}")
    
    # Confirm with user
    print("\n" + "="*60)
    print("IMPORTANT: This will RECREATE all ChromaDB collections!")
    print(f"ChromaDB Location: {config.chromadb.persist_directory}")
    print(f"Data Source: {sage_usb_path}")
    print(f"Embedding Model: {config.chromadb.embedding_function}")
    print("="*60)
    response = input("\nDo you want to proceed? (yes/no): ").strip().lower()
    
    if response != 'yes':
        logger.info("Ingestion cancelled by user.")
        sys.exit(0)
    
    # Initialize ChromaDB handler
    logger.info("\nInitializing ChromaDB handler...")
    
    # Clear existing database (optional - user confirmed)
    chromadb_path = Path(config.chromadb.persist_directory)
    if chromadb_path.exists():
        logger.info("Existing ChromaDB found. It will be reset with new data.")
    
    db_handler = ChromaDBHandler(config)
    logger.info("[OK] ChromaDB handler initialized")
    
    # Reset all collections for clean start
    logger.info("\nResetting all class collections...")
    for class_num in range(1, 13):
        try:
            db_handler.reset_collection(class_num)
            logger.info(f"[OK] Reset class{class_num}")
        except Exception as e:
            logger.warning(f"Error resetting class{class_num}: {e}")
    
    # Start ingestion
    logger.info("\nStarting data ingestion...")
    stats = ingest_data_to_chromadb(sage_usb_path, db_handler, logger)
    
    # Verify ingestion
    logger.info("\nVerifying ingestion...")
    all_stats = db_handler.get_all_collection_stats()
    
    for class_name, class_stats in all_stats.items():
        if 'error' not in class_stats:
            count = class_stats.get('document_count', 0)
            logger.info(f"  {class_name}: {count} documents")
    
    logger.info("\n[OK] Ingestion complete! ChromaDB is ready for use.")


if __name__ == "__main__":
    main()

