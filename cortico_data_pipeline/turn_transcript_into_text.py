#!/usr/bin/env python3
"""
Script to convert transcript JSON files to simple speaker: words format
"""

import json
from pathlib import Path


def extract_conversation(json_path: str, output_path: str = None):
    """
    Extract speaker names and words from transcript JSON.
    
    Args:
        json_path: Path to the transcript JSON file
        output_path: Optional path to save output (prints to console if not provided)
    """
    with open(json_path, 'r') as f:
        transcript = json.load(f)
    
    lines = []
    for utterance in transcript:
        speaker_name = utterance.get('speaker_name', 'Unknown')
        words = utterance.get('words', [])
        
        # Extract just the word text and join them
        text = ' '.join(word['word'] for word in words)
        
        lines.append(f"{speaker_name}: {text}")
    
    result = '\n\n'.join(lines)
    
    if output_path:
        with open(output_path, 'w') as f:
            f.write(result)
        print(f"Saved to {output_path}")
    else:
        print(result)
    
    return result


def process_collection(collection_id: int):
    """
    Process all transcripts in a collection folder.
    
    Args:
        collection_id: The collection ID to process
    """
    # Get the base path relative to this script
    base_path = Path(__file__).parent / "data" / f"collection_{collection_id}"
    transcripts_path = base_path / "transcripts"
    output_path = base_path / "formatted_transcripts"
    
    if not transcripts_path.exists():
        print(f"Error: Transcripts folder not found at {transcripts_path}")
        return
    
    # Create output directory if it doesn't exist
    output_path.mkdir(exist_ok=True)
    
    # Process all JSON files in the transcripts folder
    json_files = list(transcripts_path.glob("*.json"))
    
    if not json_files:
        print(f"No JSON files found in {transcripts_path}")
        return
    
    print(f"Processing {len(json_files)} transcripts from collection {collection_id}...")
    
    for json_file in json_files:
        output_file = output_path / f"{json_file.stem}_formatted.txt"
        extract_conversation(str(json_file), str(output_file))
    
    print(f"\nDone! Formatted transcripts saved to {output_path}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) >= 2:
        try:
            collection_id = int(sys.argv[1])
            process_collection(collection_id)
        except ValueError:
            print(f"Error: '{sys.argv[1]}' is not a valid collection ID (must be an integer)")
            sys.exit(1)
    else:
        print("Usage: python -m cortico_data_pipeline.turn_transcript_into_text <collection_id>")
        print("Example: python -m cortico_data_pipeline.turn_transcript_into_text 447")
        sys.exit(1)