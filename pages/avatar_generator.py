"""
Avatar generation utilities using DALL-E API
"""
import os
import requests
from io import BytesIO
from django.core.files.base import ContentFile
from django.utils import timezone
from openai import OpenAI
from pages.models import Participant, InterviewUtterance, Avatar


class AvatarGenerator:
    def __init__(self):
        self.client = OpenAI()  # Uses OPENAI_API_KEY from environment
    
    def extract_participant_characteristics(self, participant):
        """
        Extract characteristics from participant's interview transcripts
        """
        # Get all non-interviewer utterances for this participant
        utterances = InterviewUtterance.objects.filter(
            question__module__interview__participant=participant,
            is_interviewer=False
        ).values_list('utterance_text', flat=True)
        
        if not utterances:
            return None
        
        # Combine all utterances
        transcript = " ".join(utterances)
        
        # Use GPT to extract visual characteristics
        analysis_prompt = f"""Based on this interview transcript, create a brief description for generating a professional headshot avatar. Focus on:
- Apparent age range (young adult, middle-aged, older adult)
- Gender identity if mentioned or apparent
- Professional style or personality traits that could be visual
- Any physical descriptions mentioned
- Keep it appropriate for academic research

Transcript: {transcript[:3000]}

Provide a concise description (2-3 sentences) suitable for image generation:"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are helping create appropriate professional avatar descriptions for academic research participants."},
                    {"role": "user", "content": analysis_prompt}
                ],
                max_tokens=200,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error analyzing transcript for participant {participant.id}: {e}")
            return None
    
    def generate_avatar_image(self, description, participant_id):
        """
        Generate avatar image using DALL-E 3
        """
        if not description:
            description = "Professional headshot of a person, clean background, friendly expression"
        
        # Create a detailed prompt for DALL-E
        full_prompt = f"""Professional headshot avatar: {description}. 
Clean white or neutral background, facing forward, shoulders visible, 
professional lighting, friendly expression, suitable for academic interface, 
high quality portrait style. ONLY ONE PERSON IN THE IMAGE."""
        
        try:
            response = self.client.images.generate(
                model="dall-e-3",
                prompt=full_prompt,
                size="1024x1024",
                quality="standard",
                style="natural",
                n=1
            )
            
            image_url = response.data[0].url
            return image_url, full_prompt
            
        except Exception as e:
            print(f"Error generating image for participant {participant_id}: {e}")
            return None, full_prompt
    
    def download_and_save_avatar(self, image_url, participant):
        """
        Download the generated image and save it to the participant's avatar
        """
        try:
            # Download the image
            response = requests.get(image_url)
            response.raise_for_status()
            
            # Create or get existing avatar
            if not participant.avatar:
                avatar = Avatar.objects.create()
                participant.avatar = avatar
                participant.save()
            else:
                avatar = participant.avatar
            
            # Save the generated image
            image_content = BytesIO(response.content)
            filename = f"generated_avatar_{participant.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.png"
            
            avatar.generated_image.save(
                filename,
                ContentFile(response.content),
                save=False
            )
            
            # Update generation metadata
            avatar.is_generated = True
            avatar.generation_model = "dall-e-3"
            avatar.generated_date = timezone.now()
            avatar.save()
            
            print(f"Successfully saved generated avatar for participant {participant.id}")
            return True
            
        except Exception as e:
            print(f"Error saving avatar for participant {participant.id}: {e}")
            return False
    
    def generate_avatar_for_participant(self, participant_id):
        """
        Complete pipeline: analyze transcript, generate image, save avatar
        """
        try:
            participant = Participant.objects.get(id=participant_id)
        except Participant.DoesNotExist:
            print(f"Participant {participant_id} not found")
            return False
        
        print(f"Generating avatar for participant {participant_id} ({participant.prolific_id})")
        
        # Step 1: Extract characteristics from interview
        characteristics = self.extract_participant_characteristics(participant)
        if not characteristics:
            print(f"No interview data found for participant {participant_id}")
            characteristics = "Professional headshot of a person"
        
        print(f"Generated description: {characteristics}")
        
        # Step 2: Generate image with DALL-E
        image_url, prompt = self.generate_avatar_image(characteristics, participant_id)
        if not image_url:
            print(f"Failed to generate image for participant {participant_id}")
            return False
        
        # Step 3: Download and save the avatar
        success = self.download_and_save_avatar(image_url, participant)
        if success:
            # Update the avatar with the generation prompt
            participant.avatar.generation_prompt = prompt
            participant.avatar.save()
            
            # Automatically set participant to use the generated avatar
            participant.use_generated_avatar = True
            participant.save()
            print(f"Set participant {participant_id} to use generated avatar by default")
        
        return success
    
    def generate_avatars_for_participants(self, participant_ids):
        """
        Generate avatars for multiple participants
        """
        results = {}
        for participant_id in participant_ids:
            success = self.generate_avatar_for_participant(participant_id)
            results[participant_id] = success
        
        return results