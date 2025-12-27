from openai import OpenAI
from django.core.files.base import ContentFile
from django.utils import timezone
from pathlib import Path
import requests
from typing import Any
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gabm_infra.settings.local')
from pages.models import Participant, Avatar, InterviewUtterance

# Allow Django queries in async context (for Jupyter/IPython)
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

def generate_chatgpt_avatars(participant_ids: list[int] = None, just_names: bool = False) -> dict[str, Any]:
    """
    Generate ChatGPT avatars for the participants using the create_avatars.txt prompt.
    Saves generated avatars to S3 and the database, deleting old avatars if they exist.

    Args:
        participant_ids: List of participant IDs to generate avatars for.
                        If None, generates for all participants.
        just_names: If True, only use the participant names in the prompt.

    Returns:
        Dictionary with 'updated' count and 'errors' list.
    """
    client = OpenAI()
    results = {"updated": 0, "skipped": 0, "errors": []}

    # Load the prompt template
    if just_names:
        prompt_template_path = Path(__file__).parent / "prompts" / "create_avatar_just_name.txt"
    else:
        prompt_template_path = Path(__file__).parent / "prompts" / "create_avatars.txt"
    if not prompt_template_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {prompt_template_path}")

    with open(prompt_template_path, "r") as f:
        prompt_template = f.read()

    # Get participants to process
    if participant_ids:
        participants = Participant.objects.filter(id__in=participant_ids)
    else:
        participants = Participant.objects.all()[30:]

    total = participants.count()
    print(f"Generating ChatGPT avatars for {total} participants...")

    for idx, participant in enumerate(participants, 1):
        print(
            f"\n[{idx}/{total}] Processing participant {participant.id} ({participant.display_name or participant.prolific_id})..."
        )

        try:
            # Get all non-interviewer utterances for this participant
            utterances = InterviewUtterance.objects.filter(
                question__module__interview__participant=participant,
                is_interviewer=False,
            ).values_list("utterance_text", flat=True)

            if not utterances:
                print("  -> No utterances found, skipping...")
                results["skipped"] += 1
                continue

            # Combine utterances into plain text for demographic inference
            utterance_text = " ".join([u for u in utterances if u])

            # Use GPT-4o to infer demographic information from utterances
            if not just_names:
                print("  -> Inferring demographics with GPT-4o...")
                summary_prompt = (
                    "Given the following utterances from a participant in a conversation, "
                    "generate demographic details of who you think this participant is. Include their likely age, gender, and race. "
                    "Be concise, only include likely age, gender, and race.\n"
                    "Utterances:\n"
                    f"{utterance_text}"
                )
                summary_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a careful summarizer and demographic guesser based on conversational context."
                        },
                        {
                            "role": "user",
                            "content": summary_prompt
                        }
                    ],
                    max_tokens=160,
                    temperature=0.4,
                )
                participant_summary = summary_response.choices[0].message.content.strip()
                print(f"  -> Demographic summary: {participant_summary}")
            else:
                participant_summary = ""

            # Get participant name
            participant_name = (
                participant.display_name
                or participant.prolific_id
                or f"Participant {participant.id}"
            )

            # Build the prompt from template
            prompt = prompt_template.replace("{participant name}", participant_name)
            if not just_names:
                prompt = prompt.replace("{utterances}", participant_summary)
            else:
                prompt = prompt.replace("{utterances}", "")

            # Truncate prompt to stay under DALL-E 3's 4000 character limit
            if len(prompt) > 2000:
                prompt = prompt[:1000] + "..."

            print("  -> Generating image with ChatGPT...")

            # Generate image using DALL-E 3
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                style="natural",
                n=1,
            )

            # Get the image (DALL-E 3 returns URL, not base64)
            image_url = response.data[0].url
            if not image_url:
                raise ValueError("No image URL received from API")
            
            img_response = requests.get(image_url)
            img_response.raise_for_status()
            image_bytes = img_response.content

            print("  -> Saving avatar to S3 and database...")

            # Delete old generated avatar if it exists
            if participant.avatar and participant.avatar.generated_image:
                old_image_name = participant.avatar.generated_image.name
                print(f"  -> Deleting old avatar: {old_image_name}")
                participant.avatar.generated_image.delete(save=False)

            # Get or create avatar
            if not participant.avatar:
                avatar = Avatar.objects.create()
                participant.avatar = avatar
            else:
                avatar = participant.avatar

            # Save the generated image (Django's storage backend handles S3 upload)
            filename = f"generated_avatar_{participant.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.png"
            avatar.generated_image.save(filename, ContentFile(image_bytes), save=False)

            # Update avatar metadata
            avatar.is_generated = True
            avatar.generation_model = "gpt-4o-dalle-3"  # Reflects two-step process: GPT-4o demographics + DALL-E 3
            avatar.generation_prompt = prompt[:2000]  # Store first 2000 chars of prompt
            avatar.generated_date = timezone.now()
            avatar.save()

            results["updated"] += 1
            print(f"  ✓ Successfully generated avatar for participant {participant.id}")

        except Exception as e:
            error_msg = (
                f"Failed to generate avatar for participant {participant.id}: {str(e)}"
            )
            results["errors"].append(error_msg)
            print(f"  ✗ {error_msg}")

    print(f"\n{'='*50}")
    print(
        f"Done! Updated: {results['updated']}, Skipped: {results['skipped']}, Errors: {len(results['errors'])}"
    )
    if results["errors"]:
        print("Errors:")
        for error in results["errors"]:
            print(f"  - {error}")

    return results

# %%
