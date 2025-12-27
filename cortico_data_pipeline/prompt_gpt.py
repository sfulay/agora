import json
from pathlib import Path
from typing import Any

import openai
from dotenv import load_dotenv

load_dotenv()

def _call_gpt(system_prompt: str, user_prompt: str, model: str = "gpt-4.1") -> dict[str, Any]:
    """Call GPT-4 API to generate response"""
    response = openai.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)


def _load_prompt_template(prompt_file_path: str) -> tuple[str | None, str | None]:
    """Load the prompt template from the given file path"""
    # Resolve path relative to this script's directory
    script_dir = Path(__file__).parent
    prompt_file = script_dir / prompt_file_path
    if prompt_file.exists():
        with open(prompt_file, 'r') as f:
            template = f.read()
        template_split = template.split("\n")
        system_prompt = template_split[0]
        user_prompt = "\n".join(template_split[1:])
        return system_prompt, user_prompt
    else:
        print(f"⚠️  Prompt template not found: {prompt_file}")
        return None, None


def structural_highlights(conversation_guide: dict, utterances: list) -> dict[str, Any]:
    """Add structural highlights to the utterances"""
    system_prompt, user_prompt = _load_prompt_template("prompts/structural_highlights.txt")
    user_prompt = user_prompt.format(conversation_guide=conversation_guide, utterances=utterances)
    return _call_gpt(system_prompt, user_prompt)


def facilitator(utterances: list) -> dict[str, Any]:
    """Mark the facilitator in the utterances"""
    system_prompt, user_prompt = _load_prompt_template("prompts/mark_facilitator.txt")
    user_prompt = user_prompt.format(utterances=utterances)
    return _call_gpt(system_prompt, user_prompt)


def recommendations(transcripts: list) -> dict[str, Any]:
    """Create recommendations from the transcripts"""
    system_prompt, user_prompt = _load_prompt_template("prompts/create_recommendations.txt")
    user_prompt = user_prompt.format(transcripts=transcripts)
    return _call_gpt(system_prompt, user_prompt)
