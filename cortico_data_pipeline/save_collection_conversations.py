import os
import sys
from pathlib import Path

import boto3
import django

# Add project root to path
sys.path.insert(0, "/Users/aliklemencic/Documents/GitHub/agora")

# Set up Django settings (uses local.py which connects to localhost:6543)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gabm_infra.settings.local")
django.setup()


from .cortico_conversation import CorticoConversation


def _s3_client() -> boto3.client:
    """Get the S3 client."""
    # Set up S3 client
    s3_client = boto3.client("s3")
    s3_bucket_name = "ccc-agora"
    return s3_client, s3_bucket_name


def _input_dirs(collection_id: str) -> str:
    """Get the input directory."""
    input_dir = f"cortico_data_pipeline/data/collection_{collection_id}"
    input_dirs = {
        "collection": input_dir,
        "transcripts": f"{input_dir}/transcripts",
        "audio": f"{input_dir}/audio",
    }
    return input_dirs



def save_collection_conversations(collection_id: str) -> None:
    """Save the conversations to S3."""
    s3_client, s3_bucket_name = _s3_client()
    # Get input directories and files
    input_dirs = _input_dirs(collection_id)
    conversation_transcripts = os.listdir(input_dirs["transcripts"])
    total_conversations = len(conversation_transcripts)

    print(f"\n{'='*60}")
    print(f"Processing collection {collection_id}: {total_conversations} conversations")
    print(f"{'='*60}\n")

    # Save conversations
    for i, transcript_file in enumerate(conversation_transcripts, 1):
        print(f"\n[Conversation {i}/{total_conversations}] Processing {transcript_file}")
        try:
            conversation = CorticoConversation(
                input_dir=Path(input_dirs['collection']),
                conversation_id=transcript_file.replace('.json', ''),
                s3_bucket_name=s3_bucket_name,
                s3_client=s3_client,
            )
            conversation.save_data()
            print(f"  ✓ Completed conversation {transcript_file.replace('.json', '')}")
        except Exception as e:
            print(
                f"  ✗ Error saving conversation {transcript_file.replace('.json', '')}: {e}"
            )
    
    print(f"\n{'='*60}")
    print(f"Finished processing collection {collection_id}")
    print(f"{'='*60}\n")


def save_single_conversation(collection_id: int, conversation_id: int) -> None:
    """Save a single conversation."""
    s3_client, s3_bucket_name = _s3_client()
    input_dirs = _input_dirs(collection_id)
    transcript_file = f"transcript_{conversation_id}.json"

    print(f"\n{'='*60}")
    print(f"Processing conversation {conversation_id}")
    print(f"{'='*60}\n")

    try:
        conversation = CorticoConversation(
            input_dir=Path(input_dirs["collection"]),
            conversation_id=conversation_id,
            s3_bucket_name=s3_bucket_name,
            s3_client=s3_client,
        )
        conversation.save_data()
        print(f"  ✓ Completed conversation {conversation_id}")
    except Exception as e:
        print(f"  ✗ Error saving conversation {transcript_file.replace('.json', '')}: {e}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 2:
        save_collection_conversations(sys.argv[1])
    else:
        print("Usage: python -m cortico_data_pipeline.save_collection_conversations <collection_id>")
