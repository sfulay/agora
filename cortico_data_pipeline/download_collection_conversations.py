import json
import os

import click
import dotenv

from cortico_data_pipeline.cortico_downloader import ConversationDownloader

from .prompt_gpt import facilitator, structural_highlights


@click.group()
def cli():
    """A simple CLI with multiple commands."""
    pass


@cli.command()
@click.argument("collection_id", type=str)
def download_collection_conversations(collection_id: str) -> None:
    """
    Download and save snippets from all conversations in the given collection.
    Assumes that a valid API key is set in the environment variables.

    Args:
        collection-id (str): The ID of the collection to download snippets from.
    """
    dotenv.load_dotenv()
    cortico_api_key = os.getenv("CORTICO_API_KEY")
    downloader = ConversationDownloader(api_key=cortico_api_key)

    output_dir = f"cortico_data_pipeline/data/collection_{collection_id}"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    conversation_ids = downloader.save_collection_snippets(collection_id, output_dir)
    downloader.save_collection_conversation_audio(conversation_ids, output_dir)


@cli.command()
@click.argument("collection_id", type=str)
def add_ai_fields_to_collection_transcripts(collection_id: str) -> None:
    """Add AI fields to the conversation utterances."""
    transcripts_dir = (
        f"cortico_data_pipeline/data/collection_{collection_id}/transcripts"
    )
    for transcript_file in os.listdir(transcripts_dir):
        with open(os.path.join(transcripts_dir, transcript_file), "r") as f:
            utterances = json.load(f)

        # Prompt GPT
        marked_facilitators = json.loads(facilitator(utterances))
        marked_structural_highlights = json.loads(structural_highlights(utterances))

        for utterance in utterances:
            id = utterance["id"]
            utterance["is_facilitator"] = marked_facilitators[id]
            utterance["question"] = marked_structural_highlights[id]

        with open(os.path.join(f"{transcripts_dir}_ai", transcript_file), "w") as f:
            json.dump(utterances, f)


if __name__ == "__main__":
    cli()