#%%
import os
import sys
from pathlib import Path

# Add project root to path for Django imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gabm_infra.settings.local')
# Allow Django queries in async context (for Jupyter/IPython)
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
import django
django.setup()

# Now import Django models
from pages.models import Participant, Avatar, InterviewUtterance
from openai import OpenAI
import requests
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile

#%%
def view_prompt_template():
    """View the current prompt template being used"""
    prompt_file = project_root / "cortico_data_pipeline" / "prompts" / "create_avatars.txt"
    with open(prompt_file, 'r') as f:
        template = f.read()
    print("=" * 80)
    print("CURRENT PROMPT TEMPLATE:")
    print("=" * 80)
    print(template)
    print("=" * 80)
    return template

#%%
def get_participant_utterances(participant_id):
    """Fetch participant's utterances from database"""
    try:
        participant = Participant.objects.get(id=participant_id)
        # Get all non-interviewer utterances for this participant
        utterances = InterviewUtterance.objects.filter(
            question__module__interview__participant=participant,
            is_interviewer=False,
        ).values_list("utterance_text", flat=True)

        utterance_text = " ".join([u for u in utterances if u])
        # Using GPT-4o to generate a participant summary (age, gender, race, details) from utterances
        openai_client = OpenAI()
        summary_prompt = (
            "Given the following utterances from a participant in a conversation, "
            "generate demographic details of who you think this participant is. Include their likely age, gender, and race."
            "Be concise, only include likely age, gender, and race."
            "Utterances:\n"
            f"{utterance_text}"
        )
        summary_response = openai_client.chat.completions.create(
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
        print("\nDemographic summary (gpt-4o):")
        print(participant_summary)

        print(f"\nParticipant: {participant.display_name}")
        print(f"Found {len(utterances)} utterances")
        print(f"Combined text length: {len(utterance_text)} characters")

        return participant, participant_summary
    except Participant.DoesNotExist:
        print(f"Participant with ID {participant_id} not found")
        return None, None

#%%
def build_prompt(participant_display_name, utterances):
    """Build the actual prompt that will be sent to DALL-E 3"""
    prompt_file = project_root / "cortico_data_pipeline" / "prompts" / "create_avatars.txt"
    with open(prompt_file, 'r') as f:
        template = f.read()

    # Replace template variables
    prompt = template.replace("{participant name}", participant_display_name)
    prompt = prompt.replace("{utterances}", utterances)

    # Truncate to 2000 chars (DALL-E 3 limit is 4000, but being conservative)
    if len(prompt) > 2000:
        prompt = prompt[:2000]

    return prompt

#%%
def save_avatar_to_db(participant, img, prompt, image_url):
    """Save the generated avatar to database and S3"""
    # Delete existing avatar if present
    try:
        old_avatar = Avatar.objects.get(participant=participant)
        if old_avatar.image:
            old_avatar.image.delete(save=False)
        old_avatar.delete()
    except Avatar.DoesNotExist:
        pass

    # Create new avatar
    avatar = Avatar(participant=participant)
    avatar.generation_prompt = prompt[:2000] if len(prompt) > 2000 else prompt

    # Download image and save to avatar
    img_response = requests.get(image_url)
    avatar.image.save(
        f"avatar_{participant.id}.png",
        ContentFile(img_response.content),
        save=True
    )

    return avatar

#%%
def test_single_avatar(participant_id, save_to_db=False):
    """
    Test avatar generation for a single participant

    Args:
        participant_id: The participant ID to generate avatar for
        save_to_db: If True, saves to database and S3. If False, just shows the image
    """
    print(f"\n{'='*80}")
    print(f"TESTING AVATAR GENERATION FOR PARTICIPANT {participant_id}")
    print(f"{'='*80}\n")

    # Get participant data
    participant, utterances = get_participant_utterances(participant_id)
    if not participant:
        return None

    # Build prompt
    prompt = build_prompt(participant.display_name, utterances)

    print("\n" + "="*80)
    print("FINAL PROMPT SENT TO DALL-E 3:")
    print("="*80)
    print(prompt)
    print("="*80)
    print(f"\nPrompt length: {len(prompt)} characters")

    # Call OpenAI API
    print("\nCalling DALL-E 3 API...")
    client = OpenAI()

    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
            style="natural"
        )

        image_url = response.data[0].url
        print(f"✓ Image generated successfully!")
        print(f"Image URL: {image_url}")

        # Download and display image
        print("\nDownloading image...")
        img_response = requests.get(image_url)
        img = Image.open(BytesIO(img_response.content))

        # Save locally for viewing
        output_file = project_root / f"test_avatar_{participant_id}.png"
        img.save(output_file)
        print(f"✓ Saved to: {output_file}")

        # Optionally display (if running in Jupyter/IPython)
        try:
            from IPython.display import display
            display(img)
        except:
            print("(Run in Jupyter to see image inline)")

        if save_to_db:
            print("\nSaving to database and S3...")
            save_avatar_to_db(participant, img, prompt, image_url)
            print("✓ Saved to database and S3")
        else:
            print("\nℹ️  Not saving to database (save_to_db=False)")

        return img

    except Exception as e:
        print(f"✗ Error generating avatar: {e}")
        return None

#%%
def list_participants(limit=20):
    """List available participants for testing"""
    participants = Participant.objects.all()[:limit]
    print(f"\nAvailable Participants (showing first {limit}):")
    print("="*80)
    for p in participants:
        utterance_count = InterviewUtterance.objects.filter(question__module__interview__participant_id=p.id).count()
        print(f"ID: {p.id:4d} | Name: {p.display_name:30s} | Utterances: {utterance_count}")
    print("="*80)
    return participants

#%%
# =============================================================================
# QUICK TESTING SECTION - MODIFY AND RUN THIS CELL
# =============================================================================

# Step 1: View available participants
list_participants(limit=10)

# Step 2: View current prompt template
# view_prompt_template()

# Step 3: Test avatar generation for a specific participant
# Replace with actual participant ID from the list above
TEST_PARTICIPANT_ID = 90

# Test without saving to database (just to see the result)
test_single_avatar(TEST_PARTICIPANT_ID, save_to_db=False)

# Once you're happy with the result, save it to database:
# test_single_avatar(TEST_PARTICIPANT_ID, save_to_db=True)

# =============================================================================
# ITERATION WORKFLOW:
# 1. Run this cell to see current results
# 2. Edit the prompt template in: cortico_data_pipeline/prompts/create_avatars.txt
# 3. Re-run this cell to test the new prompt
# 4. Repeat until satisfied
# 5. Set save_to_db=True to save the final result
# =============================================================================

# %%
