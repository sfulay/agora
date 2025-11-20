"""
Demographic-based avatar generation utilities using DALL-E API
"""
import os
import pandas as pd
import requests
from io import BytesIO
from django.core.files.base import ContentFile
from django.utils import timezone
from openai import OpenAI
from pages.models import Participant, Avatar, InterviewUtterance


class DemographicAvatarGenerator:
    def __init__(self, csv_path='data/all_df_clean_pass_concept_measures_joined.csv'):
        self.client = OpenAI()  # Uses OPENAI_API_KEY from environment
        self.demographic_data = self._load_demographic_data(csv_path)
    
    def _load_demographic_data(self, csv_path):
        """Load demographic data from CSV file"""
        try:
            df = pd.read_csv(csv_path)
            # Create a dictionary mapping PROLIFIC_PID to demographic info
            demographic_dict = {}
            for _, row in df.iterrows():
                prolific_pid = row['PROLIFIC_PID']
                demographic_dict[prolific_pid] = {
                    'age': row.get('age'),
                    'gender': row.get('gender'),  # 1=Female, 2=Male, etc.
                    'ethnicity': row.get('Ethnicity simplified'),
                    'sex': row.get('Sex')  # Male/Female string
                }
            return demographic_dict
        except Exception as e:
            print(f"Error loading demographic data: {e}")
            return {}
    
    def _map_gender_code(self, gender_code):
        """Map gender codes to descriptive text"""
        gender_mapping = {
            1: "woman",
            2: "man",
            3: "non-binary person",
            4: "other gender identity"
        }
        return gender_mapping.get(gender_code, "person")
    
    def _get_age_description(self, age):
        """Use exact age"""
        if pd.isna(age) or age is None:
            return "adult"
        
        age = int(age)
        return f"{age}-year-old"
    
    def generate_demographic_description(self, participant):
        """Generate description based on participant demographics"""
        prolific_id = participant.prolific_id
        
        if not prolific_id or prolific_id not in self.demographic_data:
            return "Professional headshot of a person, clean background, friendly expression"
        
        demo = self.demographic_data[prolific_id]
        
        # Build description from demographic data
        parts = []
        
        # Age description
        age_desc = self._get_age_description(demo.get('age'))
        parts.append(age_desc)
        
        # Gender/Sex description
        if demo.get('sex') and pd.notna(demo.get('sex')) and demo.get('sex') != 'CONSENT_REVOKED':
            if demo['sex'].lower() == 'male':
                parts.append("man")
            elif demo['sex'].lower() == 'female':
                parts.append("woman")
        elif demo.get('gender'):
            gender_desc = self._map_gender_code(demo.get('gender'))
            parts.append(gender_desc)
        
        # Ethnicity description
        if demo.get('ethnicity') and pd.notna(demo.get('ethnicity')) and demo.get('ethnicity') not in ['CONSENT_REVOKED', 'DATA_EXPIRED']:
            ethnicity = demo['ethnicity']
            if ethnicity.lower() == 'white':
                parts.append("of European descent")
            elif ethnicity.lower() == 'black':
                parts.append("of African descent")
            elif ethnicity.lower() == 'asian':
                parts.append("of Asian descent")
            elif ethnicity.lower() == 'mixed':
                parts.append("of mixed ethnic background")
            elif ethnicity.lower() == 'other':
                parts.append("of diverse ethnic background")
            elif ethnicity.lower() == 'hispanic':
                parts.append("of Hispanic/Latino descent")
            elif ethnicity.lower() == 'native american':
                parts.append("of Native American descent")
            else:
                # Handle any other ethnicities that might appear
                parts.append(f"of {ethnicity} descent")
        
        # Combine into description
        if parts:
            description = " ".join(parts)
        else:
            description = "person"
        
        return f"Professional headshot of a {description}"
    
    def extract_interview_context(self, participant):
        """Extract personality/style cues from interview transcripts"""
        # Get a sample of utterances from the participant
        utterances = InterviewUtterance.objects.filter(
            question__module__interview__participant=participant,
            is_interviewer=False
        )[:5]  # Just get first 5 utterances for context
        
        if not utterances.exists():
            return None
        
        # Combine utterances into a sample
        transcript_sample = " ".join([utt.utterance_text for utt in utterances])
        
        # Use GPT to extract style/personality cues for visual representation
        analysis_prompt = f"""Based on this brief interview sample, suggest 2-3 subtle visual style cues for a professional headshot (focusing on things like expression, clothing style, or general demeanor - NOT physical features). Keep it very brief and professional.

Interview sample: {transcript_sample[:1000]}

Respond with just 2-3 descriptive phrases separated by commas (e.g. "confident expression, business attire, warm demeanor"):"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Use cheaper model for this analysis
                messages=[
                    {"role": "system", "content": "You extract subtle professional style cues from text for avatar generation. Keep responses brief and appropriate."},
                    {"role": "user", "content": analysis_prompt}
                ],
                max_tokens=100,
                temperature=0.7
            )
            
            style_cues = response.choices[0].message.content.strip()
            return style_cues
            
        except Exception as e:
            print(f"Error extracting interview context: {e}")
            return None
    
    def generate_avatar_image(self, description, participant_id):
        """Generate avatar image using DALL-E 3 with improved centering"""
        # Create a detailed prompt for DALL-E with specific composition instructions
        full_prompt = f"""1:1 stylized gouache editorial illustration of a person with the following description: {description}. Facing forward, candid, serene, natural expression. Simple matte, painterly, blocky brushstrokes, visible texture. Occasional thick illustrative contour lines, minimal blending. Serene colors. Bright, crisp 6500K daylight lighting. Avoiding yellow or warm or aged tones, gradients. Background: big blue sky, ample space around head. 1:1. Only one person in the image."""
        
        try:
            response = self.client.images.generate(
                model="dall-e-3",
                prompt=full_prompt,
                size="1024x1024",
                quality="standard",
                n=1
            )
            
            image_url = response.data[0].url
            return image_url, full_prompt
            
        except Exception as e:
            print(f"Error generating image for participant {participant_id}: {e}")
            return None, full_prompt
    
    def download_and_save_avatar(self, image_url, participant):
        """Download and save the generated avatar"""
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
            filename = f"demographic_avatar_{participant.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.png"
            
            avatar.generated_image.save(
                filename,
                ContentFile(response.content),
                save=False
            )
            
            # Update generation metadata
            avatar.is_generated = True
            avatar.generation_model = "dall-e-3-demographic"
            avatar.generated_date = timezone.now()
            avatar.save()
            
            print(f"Successfully saved demographic avatar for participant {participant.id}")
            return True
            
        except Exception as e:
            print(f"Error saving avatar for participant {participant.id}: {e}")
            return False
    
    def generate_enhanced_description(self, participant):
        """Generate description combining demographics and interview context"""
        # Start with demographic base
        base_description = self.generate_demographic_description(participant)
        
        # Try to add interview context for variation
       # interview_context = self.extract_interview_context(participant)
        

        
        return base_description
    
    def generate_avatar_for_participant(self, participant_id):
        """Complete pipeline: get demographics + interview context, generate image, save avatar"""
        try:
            participant = Participant.objects.get(id=participant_id)
        except Participant.DoesNotExist:
            print(f"Participant {participant_id} not found")
            return False
        
        print(f"Generating enhanced avatar for participant {participant_id} ({participant.prolific_id})")
        
        # Step 1: Generate enhanced description from demographics + interview
        enhanced_description = self.generate_enhanced_description(participant)
        #interview_status = " (with interview context)" if has_interview_data else " (demographics only)"
       # print(f"Generated description{interview_status}: {enhanced_description}")
        
        # Step 2: Generate image with DALL-E
        image_url, prompt = self.generate_avatar_image(enhanced_description, participant_id)
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
            print(f"Set participant {participant_id} to use enhanced avatar by default")
        
        return success
    
    def generate_avatars_for_participants(self, participant_ids):
        """Generate demographic avatars for multiple participants"""
        results = {}
        for participant_id in participant_ids:
            success = self.generate_avatar_for_participant(participant_id)
            results[participant_id] = success
        
        return results
    
    def get_demographic_info(self, participant_id):
        """Debug method to see demographic info and enhanced description for a participant"""
        try:
            participant = Participant.objects.get(id=participant_id)
            prolific_id = participant.prolific_id
            
            if prolific_id and prolific_id in self.demographic_data:
                demo = self.demographic_data[prolific_id]
                print(f"Participant {participant_id} ({prolific_id}):")
                print(f"  Age: {demo.get('age')}")
                print(f"  Gender: {demo.get('gender')}")
                print(f"  Sex: {demo.get('sex')}")
                print(f"  Ethnicity: {demo.get('ethnicity')}")
                
                # Show both demographic and enhanced descriptions
                base_description = self.generate_demographic_description(participant)
                enhanced_description, has_interview = self.generate_enhanced_description(participant)
                
                print(f"  Base demographic description: {base_description}")
                if has_interview:
                    print(f"  Enhanced with interview context: {enhanced_description}")
                else:
                    print(f"  No interview data available for enhancement")
                
                return demo
            else:
                print(f"No demographic data found for participant {participant_id}")
                return None
        except Participant.DoesNotExist:
            print(f"Participant {participant_id} not found")
            return None