import json
from pathlib import Path

from prompt_gpt import recommendations


def prompt_gpt_for_recommendations(collection_id: str) -> None:
    """Prompt GPT for recommendations from the transcripts"""
    transcript_dir = Path(f"cortico_data_pipeline/data/collection_{collection_id}/formatted_transcripts")
    transcripts = [open(f).read() for f in transcript_dir.glob("*.txt")]
    recommendations_json = recommendations(transcripts)
    output_file = Path(f"cortico_data_pipeline/data/collection_{collection_id}/recommendations.json")
    with open(output_file, "w") as f:
        json.dump(recommendations_json, f)


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 2:
        prompt_gpt_for_recommendations(str(sys.argv[1]))
    else:
        print("Usage: python -m cortico_data_pipeline.prompt_gpt_for_recommendations <collection_id>")