import os
import json
import openai
import pandas as pd
from django.db import transaction
from pathlib import Path
import sys
import random
# Django setup
# Add the parent directory to the Python path to find the Django project
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
# Django setup
os.environ['DJANGO_SETTINGS_MODULE'] = 'gabm_infra.settings.local'
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = "true"

import django
django.setup()

from pages.models import (
    Interview, InterviewUtterance, Participant, 
    ParticipantNarrative, ParticipantNarrativePart
)


class LifeNarrativeGenerator:
    def __init__(self, prompt_dir="generating_v2/prompts"):
        self.prompt_dir = Path(prompt_dir)
        self.prompts = self._load_prompts()
    
    def _load_prompts(self):
        """Load all prompt templates from the prompts directory"""
        prompts = {}
        for prompt_file in self.prompt_dir.glob("*.txt"):
            with open(prompt_file, 'r') as f:
                prompts[prompt_file.stem] = f.read()
        return prompts
    
    def call_gpt(self, prompt):
        """Call GPT-4 API to generate response"""
        response = openai.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that pulls out interesting excerpts and writes short summaries of those excerpts."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    
    def get_transcript(self, username):
        """Get full transcript for a participant"""
        interview = Interview.objects.get(participant__username=username)
        
        # Get ALL utterances from this participant's interview
        utterances = InterviewUtterance.objects.filter(
            question__interview=interview,
            is_interviewer=False  # Only get interviewee utterances
        ).order_by('question__global_question_id', 'sequence_number')
        
        # Create transcript from all utterances
        transcript_parts = []
        for utt in utterances:
            transcript_parts.append(f"Utterance {utt.id}: {utt.utterance_text}")
        return "\n".join(transcript_parts)
    
    def get_life_utterances(self, display_name, transcript):
        """Get life-related utterances from transcript"""
        prompt = self.prompts['life_utterances'].format(
            display_name=display_name,
            transcript=transcript
        )
        response = self.call_gpt(prompt)
        return response["utterances"]
    
    def generate_explanation(self, utterance, display_name):
        """Generate explanation for a single utterance"""
        prompt = self.prompts['life_explanation'].format(
            utterance=utterance,
            display_name=display_name
        )
        return self.call_gpt(prompt)
    
    def get_life_summary(self, display_name, life_narrative_parts):
        """Generate life summary from narrative parts"""
        all_utterances = [part['interviewee_utterance'] for part in life_narrative_parts]
        
        prompt = self.prompts['life_summary'].format(
            display_name=display_name,
            utterances=all_utterances
        )
        
        response = self.call_gpt(prompt)
        return response['summary']
    
    def assign_display_name(self, participant):
        """Assign display name to a participant"""
        names_list = json.load(open("data/assigned_names_list.json"))
        participants_df = pd.read_csv("data/participant_data_clean.csv")
        gender = participants_df[participants_df["prolific_id"] == participant.username]["Sex"].values[0]
        if gender in names_list:
            assigned_name = random.choice(names_list[gender])
            participant.display_name = assigned_name
            participant.save()
            return assigned_name
        else:
            print(f"Participant {participant.username} not found in names list")
            return None

    def process_participant(self, username):
        """Process a single participant to generate life narrative"""
        participant = Participant.objects.get(username=username)
        if participant.display_name is None:
            display_name = self.assign_display_name(participant)
        else:
            display_name = participant.display_name
        
        print(f"Processing {display_name} ({username})...")
        
        # Get transcript
        transcript = self.get_transcript(username)
        
        # Get life utterances
        life_utterances = self.get_life_utterances(display_name, transcript)
        
        # Generate explanations for each utterance
        narrative_parts = []
        for utterance_data in life_utterances:
            explanation = self.generate_explanation(
                utterance_data['interviewee_utterance'], 
                display_name
            )
            explanation['utterance_id'] = utterance_data['utterance_id']
            explanation['interviewee_utterance'] = utterance_data['interviewee_utterance']
            narrative_parts.append(explanation)
        
        # Generate life summary
        life_summary = self.get_life_summary(display_name, narrative_parts)
        
        return {
            'participant': participant,
            'narrative_parts': narrative_parts,
            'life_summary': life_summary
        }
    
    def save_life_narratives(self, participant_usernames, delete_existing=False):
        """Generate and save life narratives for multiple participants"""
        responses = []
        
        for username in participant_usernames:
            # Check if narrative already exists
            if ParticipantNarrative.objects.filter(participant__username=username).exists():
                print(f"Participant narrative already exists for {username}")
                if delete_existing:
                    ParticipantNarrative.objects.filter(participant__username=username).delete()
                else:
                    continue
            
            try:
                # Process participant
                result = self.process_participant(username)
                
                # Save to database
                with transaction.atomic():
                    participant_narrative = ParticipantNarrative.objects.create(
                        participant=result['participant']
                    )
                    
                    for part in result['narrative_parts']:
                        try:
                            utterance = InterviewUtterance.objects.get(id=part['utterance_id'])
                            utterance_text_with_bold = part['interviewee_utterance_bolded']
                        except InterviewUtterance.DoesNotExist:
                            print(f"Warning: Utterance {part['utterance_id']} not found")
                            utterance = None
                            utterance_text_with_bold = part['interviewee_utterance_bolded']
                        
                        ParticipantNarrativePart.objects.create(
                            participant_narrative=participant_narrative,
                            utterance=utterance,
                            ai_explanation_text=part.get('ai_explanation'),
                            utterance_text_with_bold=utterance_text_with_bold
                        )
                    
                    # Update with summary
                    ParticipantNarrative.objects.filter(
                        participant=result['participant']
                    ).update(global_summary=result['life_summary'])
                
                print(f"Successfully saved narrative for {username}")
                responses.append(result['narrative_parts'])
                
            except Exception as e:
                print(f"Error processing {username}: {str(e)}")
                continue
        
        return responses


def main():
    """Main function to run life narrative generation"""
    # Load participant data
    all_participants = pd.read_csv("data/participant_data_clean.csv")
    participant_usernames = all_participants["prolific_id"].tolist()
    
    # Initialize generator
    generator = LifeNarrativeGenerator()
    
    # Generate and save life narratives
    print(f"Processing {len(participant_usernames)} participants...")
    results = generator.save_life_narratives(participant_usernames)
    
    print(f"Completed! Processed {len(results)} participants.")


if __name__ == "__main__":
    main()
