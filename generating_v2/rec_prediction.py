import os
import json
import openai
import pandas as pd
from django.db import transaction
from pathlib import Path
import sys
# Django setup
# Add the parent directory to the Python path to find the Django project
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.environ['DJANGO_SETTINGS_MODULE'] = 'gabm_infra.settings.local'
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = "true"

import django
django.setup()

from pages.models import (
    Interview, InterviewUtterance, Participant, 
    Recommendation, RecommendationParticipantSummary,
    Narrative, NarrativePart
)


class RecommendationPredictionGenerator:
    def __init__(self, prompt_dir="generating_v2/prompts"):
        self.prompt_dir = Path(prompt_dir)
        self.prompts = self._load_prompts()
        self.transcript_cache = {}  # Cache for transcript data
    
    def _load_prompts(self):
        """Load all prompt templates from the prompts directory"""
        prompts = {}
        for prompt_file in self.prompt_dir.glob("*.txt"):
            with open(prompt_file, 'r') as f:
                prompts[prompt_file.stem] = f.read()
        return prompts
    
    def call_gpt(self, prompt, use_fast_model=False):
        """Call GPT-4 API to generate response"""
        model = "gpt-4o-mini" if use_fast_model else "gpt-4.1"
        response = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that analyzes participant transcripts and makes predictions about their views on recommendations."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    
    def get_transcript(self, username):
        """Get full transcript for a participant (with caching)"""
        if username in self.transcript_cache:
            return self.transcript_cache[username]
            
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
        transcript = "\n".join(transcript_parts)
        
        # Cache the transcript
        self.transcript_cache[username] = transcript
        return transcript
    
    def get_rec_prediction(self, transcript, rec_text, display_name):
        """Get prediction for participant agreement with recommendation"""
        prompt = self.prompts['rec_prediction'].format(
            transcript=transcript,
            rec_text=rec_text,
            display_name=display_name
        )
        return self.call_gpt(prompt)
    
    def get_rec_evidence(self, transcript, reasoning, rec_text):
        """Get relevant opinions and experiences from transcript"""
        prompt = self.prompts['rec_evidence'].format(
            transcript=transcript,
            reasoning=reasoning,
            rec_text=rec_text
        )
        return self.call_gpt(prompt)
    
    def get_exp_relevance(self, experiences, rec_text):
        """Evaluate relevance and depth of experiences"""
        prompt = self.prompts['rec_exp_relevance'].format(
            experiences=experiences,
            rec_text=rec_text
        )
        return self.call_gpt(prompt)
    
    def get_rec_exp_summary(self, experiences):
        """Generate summary of experiences (using fast model)"""
        prompt = self.prompts['rec_exp_summary'].format(
            experiences=experiences
        )
        response = self.call_gpt(prompt, use_fast_model=True)
        return response['summary']
    
    def get_utterance_texts(self, utterance_ids):
        """Get actual text content for given utterance IDs"""
        utterances = InterviewUtterance.objects.filter(id__in=utterance_ids)
        return [utt.utterance_text for utt in utterances]
    
    def get_evidence_texts_with_bolding(self, evidence_data):
        """Get evidence texts with bolding from evidence data"""
        evidence_texts = []
        
        # Process evidence
        for evidence in evidence_data.get('evidence', []):
            evidence_texts.append({
                'utterance_id': evidence['utterance_id'],
                'text': evidence['utterance_text_bolded'],
                'explanation': evidence['relevance_explanation']
            })
        
        return evidence_texts
    
    def get_rec_exp_summary(self, experiences):
        """Generate comprehensive summary of experiences (using fast model)"""
        prompt = self.prompts['rec_exp_summary'].format(
            experiences=experiences
        )
        response = self.call_gpt(prompt, use_fast_model=True)
        return response['summary']
    
    def calculate_quality_score(self, opinion_score, relevance_score, depth_score):
        """
        Calculate weighted quality score combining all three metrics.
        Formula: (0.4 × Opinion_vs_Experience) + (0.4 × Relevance) + (0.2 × Depth)
        """
        if any(score is None for score in [opinion_score, relevance_score, depth_score]):
            return None
        
        quality_score = (0.4 * opinion_score) + (0.4 * relevance_score) + (0.2 * depth_score)
        return round(quality_score, 1)
    
    def process_participant_recommendation_fast(self, username, rec_text, display_name):
        """Optimized version that combines GPT calls for faster processing"""
        print(f"Processing {display_name} ({username}) for recommendation (optimized)...")
        
        # Get transcript
        transcript = self.get_transcript(username)
        live_prediction_prompt = self.prompts['live_prediction'].format(
            transcript=transcript,
            rec_text=rec_text,
            display_name=display_name
        )
        print(f"DEBUG: Live prediction prompt: {live_prediction_prompt}")

        try:
            live_prediction_result = self.call_gpt(live_prediction_prompt)
            
            # Extract components with fallbacks
            prediction = live_prediction_result.get('prediction', {
                'predicted_agreement': 50,
                'confidence_score': 50,
                'reasoning': 'Unable to generate prediction'
            })
        except Exception as e:
            print(f"Error in fast GPT call for {username}: {e}")
            # Fallback to individual calls
            return self.process_participant_recommendation(username, rec_text, display_name)
        
        
        return {
            'prediction': prediction,
        }

    def process_participant_recommendation(self, username, rec_text, display_name):
        """Process a single participant-recommendation combination"""
        print(f"Processing {display_name} ({username}) for recommendation...")
        
        # Get transcript
        transcript = self.get_transcript(username)
        
        # Get prediction
        prediction = self.get_rec_prediction(transcript, rec_text, display_name)
        reasoning = prediction['reasoning']
        predicted_agreement = prediction['predicted_agreement']
        confidence_score = prediction['confidence_score']
        
        # Get evidence
        evidence = self.get_rec_evidence(transcript, reasoning, rec_text)
        
        # Get actual text content with bolding
        evidence_texts = self.get_evidence_texts_with_bolding(evidence)
        
        # Process evidence for relevance and summary
        evidence_relevance = None
        comprehensive_summary = None
        if evidence_texts:
            evidence_text = "\n".join([ev['text'] for ev in evidence_texts])
            evidence_relevance = self.get_exp_relevance(evidence_text, rec_text)
            comprehensive_summary = self.get_rec_exp_summary(evidence_text)
        
        return {
            'prediction': prediction,
            'evidence': evidence,
            'evidence_texts': evidence_texts,
            'evidence_relevance': evidence_relevance,
            'comprehensive_summary': comprehensive_summary,
            'evidence_texts_bolded': [ev['text'] for ev in evidence_texts]
        }
    
    def update_relevance_scores_only(self, participant_usernames, recommendation_ids):
        """Update only the relevance scores using existing evidence, without re-processing narratives"""
        responses = []
        
        for rec_id in recommendation_ids:
            try:
                recommendation = Recommendation.objects.get(id=rec_id)
                rec_text = recommendation.rec_text
                print(f"\nProcessing recommendation: {rec_text}")
                
                for username in participant_usernames:
                    print(f"Processing {username} for recommendation {rec_id}")
                    
                    try:
                        participant = Participant.objects.get(username=username)
                        
                        # Get existing summary
                        try:
                            summary = RecommendationParticipantSummary.objects.get(
                                recommendation=recommendation,
                                participant=participant
                            )
                        except RecommendationParticipantSummary.DoesNotExist:
                            print(f"No existing summary found for {username}, skipping...")
                            continue
                        
                        # Get existing narrative and evidence
                        try:
                            narrative = Narrative.objects.get(
                                recommendation=recommendation,
                                participant=participant
                            )
                            narrative_parts = narrative.parts.all()
                        except Narrative.DoesNotExist:
                            print(f"No existing narrative found for {username}, skipping...")
                            continue
                        
                        # Extract existing evidence text
                        evidence_texts = []
                        for part in narrative_parts:
                            if part.utterance_text_with_bold:
                                evidence_texts.append(part.utterance_text_with_bold)
                        
                        if not evidence_texts:
                            print(f"No evidence texts found for {username}, skipping...")
                            continue
                        
                        # Combine all evidence texts
                        combined_evidence = "\n".join(evidence_texts)
                        
                        # Re-run only the relevance scoring
                        evidence_relevance = self.get_exp_relevance(combined_evidence, rec_text)
                        
                        # Calculate quality score
                        quality_score = None
                        if evidence_relevance:
                            quality_score = self.calculate_quality_score(
                                evidence_relevance['opinion_vs_experiences'],
                                evidence_relevance['relevance_score'],
                                evidence_relevance['depth_score']
                            )
                        
                        # Update only the relevance scores in the database
                        with transaction.atomic():
                            summary.relevance_score = evidence_relevance['relevance_score'] if evidence_relevance else 0
                            summary.coherence_score = evidence_relevance['depth_score'] if evidence_relevance else 0
                            summary.opinion_vs_experience_score = evidence_relevance['opinion_vs_experiences'] if evidence_relevance else 0
                            summary.quality_score = quality_score
                            summary.save()
                        
                        # Debug: Print raw evidence relevance data
                        if evidence_relevance:
                            print(f"RAW DATA for {username}:")
                            print(f"  Opinion vs Experience: {evidence_relevance['opinion_vs_experiences']}")
                            print(f"  Relevance Score: {evidence_relevance['relevance_score']}")
                            print(f"  Depth Score: {evidence_relevance['depth_score']}")
                            print(f"  Quality Score: {quality_score}")
                            print(f"  Explanation: {evidence_relevance['explanation']}")
                            print(f"  Saved to DB: opinion_vs_experience_score = {evidence_relevance['opinion_vs_experiences']}")
                        
                        print(f"Successfully updated relevance scores for {username}")
                        responses.append({
                            'username': username,
                            'evidence_relevance': evidence_relevance
                        })
                        
                    except Exception as e:
                        print(f"Error processing {username} for recommendation {rec_id}: {str(e)}")
                        continue
                        
            except Recommendation.DoesNotExist:
                print(f"Recommendation {rec_id} not found")
                continue
        
        return responses

    def save_recommendation_summaries(self, participant_usernames, recommendation_ids):
        """Generate and save recommendation summaries for multiple participants"""
        responses = []
        
        for rec_id in recommendation_ids:
            try:
                recommendation = Recommendation.objects.get(id=rec_id)
                rec_text = recommendation.rec_text
                print(f"\nProcessing recommendation: {rec_text}")
                
                for username in participant_usernames:
                    # Check if summary already exists
                    if RecommendationParticipantSummary.objects.filter(
                        recommendation=recommendation, 
                        participant__username=username
                    ).exists():
                        print(f"Summary already exists for {username} and recommendation {rec_id}")
                        continue
                    
                    try:
                        participant = Participant.objects.get(username=username)
                        display_name = participant.display_name
                        
                        # Process participant-recommendation combination
                        result = self.process_participant_recommendation(
                            username, rec_text, display_name
                        )
                        
                        # Save to database
                        with transaction.atomic():
                            # Get best utterance if available
                            best_utterance = None
                            if result['evidence_texts']:
                                try:
                                    best_utterance = InterviewUtterance.objects.get(
                                        id=result['evidence_texts'][0]['utterance_id']
                                    )
                                except InterviewUtterance.DoesNotExist:
                                    pass
                            
                            # Calculate quality score
                            quality_score = None
                            if result['evidence_relevance']:
                                quality_score = self.calculate_quality_score(
                                    result['evidence_relevance']['opinion_vs_experiences'],
                                    result['evidence_relevance']['relevance_score'],
                                    result['evidence_relevance']['depth_score']
                                )
                            
                            # Create summary
                            summary = RecommendationParticipantSummary.objects.create(
                                recommendation=recommendation,
                                participant=participant,
                                predicted_agreement=result['prediction']['predicted_agreement'],
                                confidence_score=result['prediction']['confidence_score'],
                                reasoning=result['prediction']['reasoning'],
                                relevance_score=result['evidence_relevance']['relevance_score'] if result['evidence_relevance'] else 0,
                                opinion_vs_experience_score=result['evidence_relevance']['opinion_vs_experiences'] if result['evidence_relevance'] else 0,
                                summary=result['comprehensive_summary'],
                                best_utterance=best_utterance,
                                coherence_score=result['evidence_relevance']['depth_score'] if result['evidence_relevance'] else 0,
                                quality_score=quality_score
                            )
                            
                            # Create Narrative for storing evidence parts
                            narrative = Narrative.objects.create(
                                recommendation=recommendation,
                                participant=participant
                            )
                            
                            # Create NarrativePart objects for evidence
                            for evidence in result['evidence_texts']:
                                try:
                                    utterance = InterviewUtterance.objects.get(id=evidence['utterance_id'])
                                    utterance_text_with_bold = evidence['text']
                                except InterviewUtterance.DoesNotExist:
                                    print(f"Warning: Utterance {evidence['utterance_id']} not found")
                                    utterance = None
                                    utterance_text_with_bold = evidence['text']
                                
                                NarrativePart.objects.create(
                                    narrative=narrative,
                                    utterance=utterance,
                                    ai_explanation_text=evidence['explanation'],
                                    utterance_text_with_bold=utterance_text_with_bold
                                )
                            
                            # Update narrative with global summary
                            Narrative.objects.filter(
                                recommendation=recommendation,
                                participant=participant
                            ).update(global_summary=result['comprehensive_summary'])
                        
                        # Debug: Print raw evidence relevance data
                        if result['evidence_relevance']:
                            print(f"RAW DATA for {username}:")
                            print(f"  Opinion vs Experience: {result['evidence_relevance']['opinion_vs_experiences']}")
                            print(f"  Relevance Score: {result['evidence_relevance']['relevance_score']}")
                            print(f"  Depth Score: {result['evidence_relevance']['depth_score']}")
                            print(f"  Quality Score: {quality_score}")
                            print(f"  Explanation: {result['evidence_relevance']['explanation']}")
                            print(f"  Saved to DB: opinion_vs_experience_score = {result['evidence_relevance']['opinion_vs_experiences']}")
                        
                        print(f"Successfully saved summary for {username}")
                        responses.append(result)
                        
                    except Exception as e:
                        print(f"Error processing {username} for recommendation {rec_id}: {str(e)}")
                        continue
                        
            except Recommendation.DoesNotExist:
                print(f"Recommendation {rec_id} not found")
                continue
        
        return responses


def main():
    """Main function to run recommendation prediction generation"""
    # Load participant data
    all_participants = pd.read_csv("data/participant_data_clean.csv")
    participant_usernames = all_participants["prolific_id"].tolist()
    
    # Initialize generator
    generator = RecommendationPredictionGenerator()
    
    # Example recommendation IDs (modify as needed)
    recommendation_ids = [74, 75, 76]
    
    # Generate and save recommendation summaries
    print(f"Processing {len(participant_usernames)} participants for {len(recommendation_ids)} recommendations...")
    results = generator.save_recommendation_summaries(participant_usernames, recommendation_ids)
    
    print(f"Completed! Processed {len(results)} participant-recommendation combinations.")


if __name__ == "__main__":
    main()
