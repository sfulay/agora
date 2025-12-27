import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click
import pandas as pd
import requests


@dataclass
class ConversationDownloader:
    """Class to download conversations from the Cortico API."""

    BASE_URL = "https://api.cortico.ai/v1"
    SNIPPETS_URL = f"{BASE_URL}/snippets"
    CONVERSATIONS_URL = f"{BASE_URL}/conversations"
    AUDIO_ENDPOINT = "/audio"

    api_key: str

    def __post_init__(self):
        self.headers = {"Authorization": f"Bearer {self.api_key}"}
        self.session = requests.Session()

    @staticmethod
    def _format_snippets(
        snippets: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        """Format snippets by conversation."""
        conversation_snippets = {}
        for snippet in snippets:
            conversation_id = snippet["conversation_id"]
            if conversation_id not in conversation_snippets:
                conversation_snippets[conversation_id] = []
            conversation_snippets[conversation_id].append(snippet)
        return conversation_snippets

    @staticmethod
    def _save_file(content: bytes, filename: str) -> None:
        """Save a file to the output directory."""
        try:
            with open(filename, "wb") as f:
                f.write(content)
            click.echo(f"File saved to {filename}")
        except Exception as e:
            click.echo(f"Error saving file {filename}: {e}")

    def _request_url(self, url: str) -> requests.Response:
        """Request a URL and return the response."""
        self.session.headers.update(self.headers)
        response = self.session.get(url)
        time.sleep(1)
        response.raise_for_status()
        return response

    def save_collection_conversation_audio(
        self, conversation_ids: str, output_dir: str
    ) -> list[dict[str, Any]]:
        """Download audio from all conversations in the given collection."""
        audio_dir = f"{output_dir}/audio"
        if not os.path.exists(audio_dir):
            os.makedirs(audio_dir)

        for conversation_id in conversation_ids:
            click.echo(f"Downloading audio for conversation {conversation_id}...")
            url = f"{self.CONVERSATIONS_URL}/{conversation_id}{self.AUDIO_ENDPOINT}"
            response = self._request_url(url)
            self._save_file(response.content, f"{audio_dir}/{conversation_id}.mp3")

    def save_collection_snippets(
        self, collection_id: str, output_dir: str
    ) -> list[dict[str, Any]]:
        """Download snippets from all conversations in the given collection."""
        transcripts_dir = f"{output_dir}/transcripts"
        if not os.path.exists(transcripts_dir):
            os.makedirs(transcripts_dir)

        click.echo(
            f"Downloading snippets from all conversations in collection {collection_id}..."
        )
        url = f"{self.SNIPPETS_URL}?collection_ids={collection_id}"

        # Get first page data
        response = self._request_url(url)
        all_snippets = response.json()
        pagination = json.loads(response.headers["X-Pagination"])
        num_pages = pagination["total_pages"]

        # Get remaining pages data
        for page in range(2, num_pages + 1):
            click.echo(f"Processing page {page} / {num_pages}...")
            page_url = f"{url}&page={page}"
            response = self._request_url(page_url)
            page_data = response.json()

            # Validate response is a list
            if not isinstance(page_data, list):
                click.echo(
                    f"Warning: Page {page} returned unexpected format: {type(page_data)}"
                )
                click.echo(f"Response content: {page_data}")
                continue

            all_snippets.extend(page_data)

        # Format and save snippets by conversation
        conversation_snippets = self._format_snippets(all_snippets)
        for conversation_id, snippets in conversation_snippets.items():
            self._save_file(
                json.dumps(snippets, indent=4).encode("utf-8"),
                f"{transcripts_dir}/{conversation_id}.json",
            )

        return list(conversation_snippets.keys())


def extract_speaker_ids(transcripts_dir: str) -> dict:
    """
    Extract all speaker IDs from transcript JSON files.

    Returns:
        dict: Mapping of conversation_id to set of speaker_ids found in that conversation
    """
    transcripts_path = Path(transcripts_dir)
    # Extract all unique speaker IDs across all transcripts
    all_speaker_ids = {
        utterance["speaker_id"]
        for json_file in transcripts_path.glob("*.json")
        for utterance in json.loads(json_file.read_text())
        if "speaker_id" in utterance
    }
    return list(all_speaker_ids)


def save_conversation_ids():
    transcripts_dir = Path()
    conversation_ids = [f.stem for f in transcripts_dir.glob("*.json")]
    df = pd.DataFrame({"prolific_id": conversation_ids})
    df.to_csv("data/participant_data_clean.csv", index=False)

    treatment_df = pd.DataFrame(
        {
            "PROLIFIC_PID": conversation_ids,
            "assignment": ["treatment"] * len(conversation_ids),  # or "control"
        }
    )

    treatment_df.to_csv(
        "data/all_df_clean_pass_concept_measures_joined.csv", index=False
    )


if __name__ == "__main__":
    transcript_dir = "cortico_data_pipeline/data/collection_447/transcripts"
    speaker_ids = extract_speaker_ids(transcript_dir)

    # Create participant CSV
    df = pd.DataFrame({"prolific_id": speaker_ids})
    df.to_csv("data/participant_data_clean.csv", index=False)

    # Create demographic CSV
    treatment_df = pd.DataFrame(
        {
            "PROLIFIC_PID": speaker_ids,
            "assignment": ["treatment"] * len(speaker_ids),
        }
    )

    treatment_df.to_csv(
        "data/all_df_clean_pass_concept_measures_joined.csv", index=False
    )
