#%%
import colorsys
import json
import re
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

import boto3
import requests
from django.core.files.base import ContentFile
from django.utils import timezone
from openai import OpenAI
from PIL import Image, ImageDraw
from pydub import AudioSegment

from ..pages.models import (
    Avatar,
    Interview,
    InterviewAudio,
    InterviewModule,
    InterviewQuestion,
    InterviewSegment,
    InterviewUtterance,
    Participant,
    Recommendation,
)
from .prompt_gpt import facilitator, recommendations, structural_highlights
#%%

@dataclass
class CorticoConversation:
    """Class to save Cortico conversation data to the database."""

    input_dir: Path
    conversation_id: int
    s3_bucket_name: str
    s3_client: boto3.client = boto3.client("s3")
    participants: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Load files."""
        self.transcript_dir = Path(f"{self.input_dir}/transcripts")
        self._load_transcript(
            Path(f"{self.transcript_dir}/{self.conversation_id}.json")
        )
        # self._load_conversation_guide(Path(f"{self.input_dir}/conversation_guide.json"))
        self._load_audio(Path(f"{self.input_dir}/audio/{self.conversation_id}.mp3"))

    def _load_transcript(self, transcript_file: Path) -> str:
        """Load the transcript from the file."""
        with open(transcript_file, "r") as f:
            transcript = f.read()
        self.transcript = json.loads(transcript)

    def _load_conversation_guide(self, conversation_guide_file: Path) -> str:
        """Load the conversation guide from the file."""
        with open(conversation_guide_file, "r") as f:
            conversation_guide_data = f.read()
        self.conversation_guide = json.loads(conversation_guide_data)

    def _load_audio(self, audio_file: Path) -> None:
        """Load the audio from the file."""
        self.audio = AudioSegment.from_file(audio_file)

    def save_data(self) -> None:
        """Save the conversation data to the database."""
        total_turns = len(self.transcript)
        print(
            f"  Conversation {self.conversation_id}: {total_turns} speaker turns to process"
        )
        for turn_num, speaker_turn in enumerate(self.transcript, 1):
            self._process_speaker_turn(speaker_turn, turn_num, total_turns)

        # TODO: set all interviews to complete

    def _process_speaker_turn(
        self, speaker_turn: dict[str, Any], turn_num: int = 0, total_turns: int = 0
    ) -> None:
        """Process a speaker turn in the conversation."""
        print(
            f"  [Turn {turn_num}/{total_turns}] Speaker {speaker_turn.get('speaker_id', -1)}"
        )
        speaker_id = str(speaker_turn.get("speaker_id", -1))
        if speaker_id not in self.participants:
            print(f"    -> New participant: {speaker_id}")
            self._process_new_participant(
                speaker_id, speaker_turn.get("speaker_name", "unknown")
            )
        # question_theme = speaker_turn.get("question", "unknown")
        # question = (
        #     self.participants.get(participant_id)
        #     .get("questions")
        #     .get(question_theme)
        #     .get("question")
        # )
        print(f"    -> Creating utterance {speaker_turn.get('id', -1)}")
        self._create_utterance(speaker_turn)

    def _process_new_participant(
        self, participant_id: str, participant_name: str
    ) -> None:
        """Process a new participant in the conversation."""
        participant = self._create_participant(participant_id, participant_name)
        self._create_interview(participant)

    def _create_participant(self, speaker_id: str, speaker_name: str) -> Participant:
        """Create a participant if they don't exist."""
        participant, _ = Participant.objects.get_or_create(
            prolific_id=speaker_id,
            defaults={
                "username": speaker_id,
                "display_name": speaker_name,
                "email": f"{speaker_id}@cortico.com",
            },
        )
        self.participants.update(
            {speaker_id: {"participant": participant, "utterance_count": 0}}
        )
        self._create_avatar_png(participant)
        participant.use_generated_avatar = True
        participant.save()
        return participant

    def _create_avatar_png(
        self, participant: Participant, size: int = 256
    ) -> Image.Image:
        """
        Create a circular avatar PNG with a new solid color.
        """
        # Generate unique, visually distinct hue using golden ratio with participant's unique ID
        hue = (participant.id * 0.618033988749895) % 1.0

        # Vary saturation and value slightly based on ID to increase uniqueness
        saturation = 0.5 + (((participant.id * 7) % 20) / 100)  # 0.5-0.7
        value = 0.8 + (((participant.id * 13) % 15) / 100)  # 0.8-0.95

        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
        color = int(r * 255), int(g * 255), int(b * 255)

        # Create image
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([(0, 0), (size, size)], fill=color)

        # Create avatar
        avatar = Avatar.objects.create()
        participant.avatar = avatar
        participant.save()

        # Convert image to bytes
        img_buffer = BytesIO()
        img.save(img_buffer, format="PNG")
        img_buffer.seek(0)

        # Save the generated image
        filename = f"generated_avatar_{participant.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.png"
        avatar.generated_image.save(
            filename, ContentFile(img_buffer.read()), save=False
        )

        # Update generation metadata
        avatar.is_generated = True
        avatar.generation_model = "cortico-data-pipeline"
        avatar.generated_date = timezone.now()
        avatar.save()

    def _create_interview(self, participant: Participant) -> Interview:
        """Create an interview for the participant."""
        interview, _ = Interview.objects.get_or_create(
            participant=participant,
            script_v=f"{self.s3_bucket_name}_{participant.prolific_id}",
            question_id_count=1,
        )
        interview_module, _ = InterviewModule.objects.get_or_create(interview=interview)
        question, _ = InterviewQuestion.objects.get_or_create(
            interview=interview,
            module=interview_module,
            q_content="",
            q_type="",
        )
        self.participants[participant.prolific_id].update(
            {
                "interview": interview,
                "interview_question": question,
                "interview_module": interview_module,
            }
        )
        # self._create_interview_questions(interview, participant)
        return interview

    def _create_interview_questions(
        self, interview: Interview, participant: Participant
    ) -> None:
        """Create interview questions for the participant."""
        self.participants[participant.username].setdefault("questions", {})
        for theme, content in self.conversation_guide.items():
            interview_module, _ = InterviewModule.objects.get_or_create(
                interview=interview
            )
            question, _ = InterviewQuestion.objects.get_or_create(
                interview=interview,
                module=interview_module,
                q_content=content,
                q_type=theme,
            )
            self.participants[participant.username]["questions"].update(
                {
                    theme: {
                        "question": question,
                        "module": interview_module,
                    }
                }
            )

    def _create_utterance(self, speaker_turn: dict[str, Any]) -> None:
        """Create an utterance for the participant."""
        # Get turn data
        words = speaker_turn.get("words", [])
        text = " ".join(w["word"] for w in words)
        # is_interviewer = speaker_turn.get("is_facilitator", False)

        # Get question
        question = self.participants.get(str(speaker_turn.get("speaker_id"))).get(
            "interview_question"
        )

        # Process the audio
        s3_path_prefix = f"interview{question.interview.id}/module{question.module.id}/question{question.id}"
        audio = self._process_utterance_audio(
            text,
            speaker_turn.get("audio_start_offset"),
            speaker_turn.get("audio_end_offset"),
            question,
            s3_path_prefix,
        )

        # Create utterance
        utterance, _ = InterviewUtterance.objects.get_or_create(
            question=question,
            utterance_text=text,
            is_interviewer=False,
            sequence_number=question.module.curr_question_id,
            audio_id=audio.id,
        )
        # Update current question counter
        question.module.curr_question_id += 1
        question.module.save()

        # Save info
        # participant_id = speaker_turn.get("speaker_id")
        # participant_utterance_data = self.participants.get(participant_id).get(
        #     "utterances", []
        # )
        # participant_utterance_data.append({"utterance": utterance, "audio": audio})
        # self.participants[participant_id].update(
        #     {
        #         "utterances": participant_utterance_data,
        #     }
        # )

    def _process_utterance_audio(
        self,
        utterance_text: str,
        start_time: float,
        end_time: float,
        question: InterviewQuestion,
        s3_path_prefix: str,
    ) -> InterviewAudio:
        """Process the audio for the utterance."""
        print(f"    -> Processing audio ({start_time:.1f}s - {end_time:.1f}s)")
        utterance_count = question.module.curr_question_id
        # Create audio
        audio = InterviewAudio.objects.create(question=question, user_speech=True)
        # Convert seconds to milliseconds for pydub
        start_ms = int(start_time * 1000)
        end_ms = int(end_time * 1000)
        audio_clip = self._clip_audio(start_ms, end_ms)

        # Upload to S3
        audio_s3_path = f"InterviewAudios/{s3_path_prefix}/user_{audio.id}"
        self._upload_audio_to_s3(audio_clip, f"{audio_s3_path}.wav")
        self._upload_audio_to_s3(
            audio_clip, f"{audio_s3_path}/sentence_{utterance_count:03d}.wav"
        )
        audio.audio_file = f"{audio_s3_path}.wav"
        audio.save()

        # self._split_audio_by_sentences(speaker_turn, audio)
        self._create_interview_segment(
            audio,
            {"start": start_time, "end": end_time, "text": utterance_text},
            utterance_count,
        )

        return audio

    def _clip_audio(self, start_time: float, end_time: float) -> None:
        """Clip the conversation audio."""
        audio_clip = self.audio[start_time:end_time]
        return audio_clip

    def _upload_audio_to_s3(self, audio_clip: AudioSegment, s3_path: str) -> None:
        """Upload the audio clip to S3."""
        # Export to BytesIO
        segment_buffer = BytesIO()
        audio_clip.export(segment_buffer, format="wav")
        segment_buffer.seek(0)
        # Read the bytes immediately to avoid I/O issues
        segment_bytes = segment_buffer.read()

        s3_buffer = BytesIO(segment_bytes)
        self.s3_client.upload_fileobj(
            s3_buffer,
            self.s3_bucket_name,
            f"media/{s3_path}",
            ExtraArgs={"ContentType": "audio/wav"},
        )
        return segment_bytes

    def _split_audio_by_sentences(
        self, speaker_turn: dict[str, Any], audio_obj: InterviewAudio
    ) -> None:
        """Split the audio by sentences."""
        # Get data
        participant_data = self.participants.get(speaker_turn.get("speaker_id"))
        question = (
            participant_data.get("questions")
            .get(speaker_turn.get("question"))
            .get("question")
        )

        # Split and save sentences
        sentences = self._extract_sentences(speaker_turn)
        for i, sentence in enumerate(sentences):
            count = i + 1
            s3_path = (
                f"InterviewAudios/interview{question.interview.id}"
                f"/module{question.module.id}/question{question.id}"
                f"/user_{audio_obj.id}/sentence_{count:03d}.wav"
            )
            try:
                self._process_sentence_audio(sentence, s3_path, count, audio_obj)
            except Exception as e:
                print(
                    f"❌ S3 upload failed for audio {audio_obj.id} sentence {count}: {e}"
                    f"❌ S3 upload failed for audio {audio_obj.id} sentence {count}: {e}"
                )

    @staticmethod
    def _extract_sentences(speaker_turn: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract sentences from the speaker turn."""
        words = speaker_turn.get("words", [])
        if not words:
            return []

        sentences = []
        current_words = []

        for w in words:
            current_words.append(w)

            # Check if this word ends with sentence punctuation
            if re.search(r"[.!?]$", w["word"]):
                sentences.append(current_words)
                current_words = []

        # catch any remaining words (partial final sentence)
        if current_words:
            sentences.append(current_words)

        # Build sentence objects
        results = []
        for s in sentences:
            text = " ".join(w["word"] for w in s)
            start = s[0]["start"]
            end = s[-1]["end"]
            results.append({"sentence": text, "start": start, "end": end})

        return results

    def _process_sentence_audio(
        self,
        sentence: dict[str, Any],
        s3_path: str,
        sequence_number: int,
        audio: InterviewAudio,
    ) -> None:
        """Process the audio for the sentence."""
        # Clip audio
        start_ms = int(sentence["start"] * 1000)
        end_ms = int(sentence["end"] * 1000)
        sentence_clip = self._clip_audio(start_ms, end_ms)

        # Upload to S3
        self._upload_audio_to_s3(sentence_clip, s3_path)

        # Create interview segment
        self._create_interview_segment(audio, sentence, sequence_number)

    def _create_interview_segment(
        self,
        audio: InterviewAudio,
        sentence: dict[str, Any],
        count: int,
    ) -> None:
        """Create an interview segment for the sentence."""
        start_time = sentence["start"]
        end_time = sentence["end"]
        text = sentence["text"]
        word_count = len(text.split())
        segment = InterviewSegment.objects.create(
            audio=audio,
            start_time=start_time,
            end_time=end_time,
            segment_text=text,
            sequence_number=count,
            word_count=word_count,
        )
        # Build the S3 path that matches where _upload_audio_to_s3 already saved the file
        s3_path = (
            f"InterviewAudios/interview{audio.question.interview.id}"
            f"/module{audio.question.module.id}/question{audio.question.id}"
            f"/user_{audio.id}/sentence_{count:03d}.wav"
        )
        # Set the path directly to reference the already-uploaded S3 file
        segment.segment_audio_file.name = s3_path
        segment.save()

    def prompt_gpt_for_recommendations(self) -> None:
        """Prompt GPT for recommendations for the conversation."""
        transcripts = [json.load(open(f)) for f in self.transcript_dir.glob("*.json")]
        recommendations_json = recommendations(transcripts)
        output_file = self.input_dir / "recommendations.json"
        with open(output_file, "w") as f:
            json.dump(recommendations_json, f)

    def save_recommendations(self) -> None:
        """Save the recommendations for the conversation."""
        recommendations_json = json.load(open(self.input_dir / "recommendations.json"))
        for recommendation in recommendations_json:
            recommendation_obj = Recommendation.objects.create(rec_text=recommendation)
            recommendation_obj.save()

    def get_structural_highlights(self) -> None:
        """Get the structural highlights for the conversation."""
        structural_highlights_json = structural_highlights(
            self.conversation_guide, self.transcript
        )
        print(structural_highlights_json)

    def get_facilitator(self) -> None:
        """Get the facilitator for the conversation."""
        facilitator_json = facilitator(self.transcript)
        return facilitator_json


def regenerate_avatars(
    participant_ids: list[int] = None, size: int = 256
) -> dict[int, bool]:
    """Regenerate the avatars for the participants."""
    results = {"updated": 0, "errors": []}

    # Get participants to update
    if participant_ids:
        participants = Participant.objects.filter(id__in=participant_ids)
    else:
        participants = Participant.objects.all()

    for participant in participants:
        try:
            # Generate unique color using golden ratio with participant's unique ID
            hue = (participant.id * 0.618033988749895) % 1.0

            # Vary saturation and value slightly based on ID to increase uniqueness
            saturation = 0.5 + (((participant.id * 7) % 20) / 100)  # 0.5-0.7
            value = 0.8 + (((participant.id * 13) % 15) / 100)  # 0.8-0.95

            r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
            color = int(r * 255), int(g * 255), int(b * 255)

            # Create image
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.ellipse([(0, 0), (size, size)], fill=color)

            # Get or create avatar
            if not participant.avatar:
                avatar = Avatar.objects.create()
                participant.avatar = avatar
            else:
                avatar = participant.avatar

            # Convert image to bytes
            img_buffer = BytesIO()
            img.save(img_buffer, format="PNG")
            img_buffer.seek(0)

            # Save the generated image (this will upload to S3)
            filename = f"generated_avatar_{participant.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.png"
            avatar.generated_image.save(
                filename, ContentFile(img_buffer.read()), save=False
            )

            # Update avatar metadata
            avatar.is_generated = True
            avatar.generated_date = timezone.now()
            avatar.save()

            results["updated"] += 1
            print(
                f"✓ Updated avatar for participant {participant.id} ({participant.display_name})"
            )

        except Exception as e:
            error_msg = (
                f"Failed to update avatar for participant {participant.id}: {str(e)}"
            )
            results["errors"].append(error_msg)
            print(f"✗ {error_msg}")

    print(
        f"\nDone! Updated {results['updated']} avatars with {len(results['errors'])} errors."
    )
    return results


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
        participants = Participant.objects.all()

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

            # Combine utterances into a transcript
            utterances_text = "\n".join(
                f"- {u}" for u in utterances[:50]
            )  # Limit to 50 utterances

            # Get participant name
            participant_name = (
                participant.display_name
                or participant.prolific_id
                or f"Participant {participant.id}"
            )

            # Build the prompt from template
            prompt = prompt_template.replace("{participant name}", participant_name)
            if not just_names:
                prompt = prompt.replace("{utterances}", utterances_text)
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
            avatar.generation_model = "gpt-image-1"
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
