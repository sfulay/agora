#!/usr/bin/env python3
"""
Medley Generator - Creates 60-second audio medleys from interview segments.

This script selects interview segments to create a cohesive 60-second narrative
that introduces the participant and shows their perspective on a specific recommendation.

USAGE:
------
OPTION A: Generate to JSON files only (testing/development)
1. Set INTERVIEW_IDS - List of interview IDs to process
2. Set RECOMMENDATION_TEXT or RECOMMENDATION_ID - The recommendation to evaluate
3. Set TOPIC_CATEGORY - Filter segments to relevant questions
4. Run: python generating_v2/medley_individual.py

OPTION B: Batch process to database (production)
Use Django shell to process all interviews 202-325:

    python manage.py shell
    
    from generating_v2.medley_individual import batch_process_to_database
    
    # For minimum wage recommendation (273)
    results = batch_process_to_database(
        interview_ids=range(202, 326),
        recommendation_id=273,
        topic_category='minimum_wage'
    )
    
    # For immigration recommendation (269)
    results = batch_process_to_database(
        interview_ids=range(202, 326),
        recommendation_id=269,
        topic_category='immigration'
    )
    
    # For discrimination recommendation (270)
    results = batch_process_to_database(
        interview_ids=range(202, 326),
        recommendation_id=270,
        topic_category='discrimination'
    )



"""

import os
import json
import openai
import sys
from pathlib import Path
from datetime import datetime

# Django setup
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.environ['DJANGO_SETTINGS_MODULE'] = 'gabm_infra.settings.local'
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = "true"

import django
django.setup()

from pages.models import (
    Interview, InterviewSegment, InterviewAudio,
    InterviewRecommendation, Participant, Recommendation,
    Medley, LivePrediction, InterviewUtterance
)
from django.db import transaction

# Setup OpenAI
sys.path.append('interviewer_agent')
from interviewer_agent.interviewer_utils.settings import get_open_api_keyset
openai.api_key = get_open_api_keyset()["key"]

# ===================== QUESTION MAPPING CONFIGURATION =====================
# Map recommendation topics/categories to relevant global_question_ids
# This allows filtering interview segments to only include relevant questions

RECOMMENDATION_QUESTION_MAPPING = {
    # Minimum wage related recommendations
    'minimum_wage': {
        'description': 'Questions about minimum wage, labor, employment, income',
        'global_question_ids': [
            11,  # Background (for introduction)
            17,  # How min wage changes affect you/family
            18,  # Fair minimum wage
            19,  # What you'd do with extra money
            20,  # Concerns about $30/hour minimum wage
        ]
    },
    
    # Discrimination/equity related recommendations
    'discrimination': {
        'description': 'Questions about discrimination, hiring equity, race/gender',
        'global_question_ids': [
            11,  # Background (for introduction)
            21,  # Experienced discrimination
            22,  # Race/gender in hiring decisions affecting you
            23,  # Race/gender in hiring for inequality
        ]
    },
    
    # Immigration/hiring related recommendations
    'immigration': {
        'description': 'Questions about immigration, foreign workers, hiring preferences',
        'global_question_ids': [
            11,  # Background (for introduction)
            24,  # Worked with someone from another country
            25,  # Impacted by immigration policy
            26,  # Does origin matter for hiring
            27,  # Prioritize local vs foreign applicants
        ]
    },
    
    # Default: use all questions if no topic specified
    'all': {
        'description': 'Use all interview questions (no filtering)',
        'global_question_ids': None  # None means no filtering
    }
}


class MedleyGenerator:
    def __init__(self, prompt_dir="generating_v2/prompts"):
        self.prompt_dir = Path(prompt_dir)
        self.output_dir = Path("generating_v2/medleys")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._load_prompt_template()
    
    def _load_prompt_template(self):
        """Load the medley selection prompt template"""
        prompt_file = self.prompt_dir / "medley_selection.txt"
        if prompt_file.exists():
            with open(prompt_file, 'r') as f:
                self.prompt_template = f.read()
        else:
            print(f"⚠️  Prompt template not found: {prompt_file}")
            self.prompt_template = None
    
    def get_available_topics(self):
        """Get list of available topic categories"""
        return list(RECOMMENDATION_QUESTION_MAPPING.keys())
    
    def get_topic_info(self, topic_category):
        """Get information about a topic category"""
        if topic_category in RECOMMENDATION_QUESTION_MAPPING:
            mapping = RECOMMENDATION_QUESTION_MAPPING[topic_category]
            return {
                'category': topic_category,
                'description': mapping['description'],
                'question_count': len(mapping['global_question_ids']) if mapping['global_question_ids'] else 'all',
                'question_ids': mapping['global_question_ids']
            }
        return None
    
    def log(self, message):
        """Print timestamped log message"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")
    
    def get_interview_segments(self, interview_id, question_filter=None):
        """
        Get segments for an interview, optionally filtered by question IDs.
        
        Args:
            interview_id: Interview ID
            question_filter: List of global_question_ids to include, or None for all
        
        Returns:
            List of segment dictionaries with all necessary information
        """
        if question_filter:
            self.log(f"📊 Fetching segments for interview {interview_id} (filtered to {len(question_filter)} questions)")
        else:
            self.log(f"📊 Fetching segments for interview {interview_id} (all questions)")
        
        try:
            interview = Interview.objects.get(id=interview_id)
        except Interview.DoesNotExist:
            self.log(f"❌ Interview {interview_id} not found")
            return []
        
        # Get questions - filter by global_question_id if specified
        if question_filter:
            questions = interview.interviewquestion_set.filter(
                global_question_id__in=question_filter
            )
            self.log(f"   Filtered to {questions.count()} relevant questions")
        else:
            questions = interview.interviewquestion_set.all()
        
        audio_files = InterviewAudio.objects.filter(
            question__in=questions,
            user_speech=True
        )
        
        segments = InterviewSegment.objects.filter(
            audio__in=audio_files
        ).select_related('audio', 'audio__question').order_by('audio__created', 'sequence_number')
        
        # Format segments for GPT
        formatted_segments = []
        for seg in segments:
            formatted_segments.append({
                'segment_id': seg.id,
                'audio_id': seg.audio.id,
                'text': seg.segment_text,
                'duration': seg.duration,
                'start_time': seg.start_time,
                'end_time': seg.end_time,
                'sequence_number': seg.sequence_number,
                'question_id': seg.audio.question.id,
                'global_question_id': seg.audio.question.global_question_id
            })
        
        self.log(f"✅ Found {len(formatted_segments)} segments")
        return formatted_segments
    
    def get_recommendation_details(self, rec_id=None, rec_text=None):
        """
        Get recommendation details.
        
        Args:
            rec_id: Recommendation ID (optional if rec_text provided)
            rec_text: Direct recommendation text (optional if rec_id provided)
        
        Returns:
            Dictionary with recommendation information
        """
        # If direct text provided, use that
        if rec_text:
            return {
                'recommendation_id': rec_id or 'custom',
                'recommendation_text': rec_text,
                'participant': None
            }
        
        # Otherwise, try to get from database
        try:
            recommendation = InterviewRecommendation.objects.get(id=rec_id)
            return {
                'recommendation_id': rec_id,
                'recommendation_text': recommendation.recommendation,
                'participant': recommendation.participant.username if recommendation.participant else None
            }
        except InterviewRecommendation.DoesNotExist:
            self.log(f"❌ Recommendation {rec_id} not found")
            return None
    
    def call_gpt(self, prompt):
        """Call GPT-4 to select medley segments"""
        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that selects audio segments to create cohesive narrative medleys."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            self.log(f"❌ GPT call failed: {e}")
            return None

    def calculate_quality_score(self, opinion_score, relevance_score, depth_score):
        """
        Calculate weighted quality score combining all three metrics.
        Formula: (0.4 × Opinion_vs_Experience) + (0.4 × Relevance) + (0.2 × Depth)
        """
        if any(score is None for score in [opinion_score, relevance_score, depth_score]):
            return None
        
        quality_score = (0.4 * opinion_score) + (0.4 * relevance_score) + (0.2 * depth_score)
        return round(quality_score, 1)
    
    def create_medley(self, interview_id, rec_id=None, rec_text=None, topic_category='all'):
        """
        Create a 60-second medley for a specific interview and recommendation.  
        
        Args:
            interview_id: Interview ID
            rec_id: Recommendation ID (optional if rec_text provided)
            rec_text: Direct recommendation text (optional if rec_id provided)
            topic_category: Topic category key from RECOMMENDATION_QUESTION_MAPPING (default: 'all')
            
        Returns:
            Dictionary with medley data
        """
        self.log(f"\n{'='*80}")
        self.log(f"Creating Medley: Interview {interview_id} × Recommendation {rec_id or 'Custom'}")
        self.log(f"Topic Category: {topic_category}")
        self.log(f"{'='*80}")
        
        # Get question filter from mapping
        question_filter = None
        if topic_category in RECOMMENDATION_QUESTION_MAPPING:
            mapping = RECOMMENDATION_QUESTION_MAPPING[topic_category]
            question_filter = mapping['global_question_ids']
            self.log(f"📌 Using topic '{topic_category}': {mapping['description']}")
            if question_filter:
                self.log(f"   Filtering to {len(question_filter)} questions: {question_filter}")
        else:
            self.log(f"⚠️  Topic category '{topic_category}' not found, using all questions")
        
        # Get segments (with optional filtering)
        segments = self.get_interview_segments(interview_id, question_filter=question_filter)
        if not segments:
            self.log(f"❌ No segments found for interview {interview_id}")
            return None
        
        # Get recommendation details
        rec_details = self.get_recommendation_details(rec_id, rec_text)
        if not rec_details:
            return None
        
        # Get participant info
        try:
            interview = Interview.objects.get(id=interview_id)
            participant_username = interview.participant.username if interview.participant else "Unknown"
        except:
            participant_username = "Unknown"
        
        # Prepare prompt
        if not self.prompt_template:
            self.log("❌ No prompt template loaded")
            return None
        
        # Format segments for GPT
        segments_json = json.dumps(segments, indent=2)
        
        # Save input data for comparison
        input_data = {
            'interview_id': interview_id,
            'recommendation_id': rec_id,
            'recommendation_text': rec_details['recommendation_text'],
            'total_segments_available': len(segments),
            'segments': segments
        }
        
        # input_filename = f"interview_{interview_id}_rec_{rec_id or 'custom'}_input.json"
        # input_filepath = self.output_dir / input_filename
        # with open(input_filepath, 'w') as f:
        #     json.dump(input_data, f, indent=2)
        # self.log(f"💾 Saved input data to: {input_filepath}")
        
        prompt = self.prompt_template.format(
            recommendation_text=rec_details['recommendation_text'],
            segments_json=segments_json
        )
        
        self.log(f"🤖 Calling GPT to select segments...")
        gpt_response = self.call_gpt(prompt)
        
        if not gpt_response:
            return None
        
        self.log(f"✅ GPT selection complete")
        
        # Extract selected segment IDs
        selected_ids = gpt_response.get('selected_segment_ids', [])
        total_duration = gpt_response.get('total_duration', 0)
        reasoning = gpt_response.get('reasoning', '')
        reordered = gpt_response.get('reordered', False)
        quality_analysis = gpt_response.get('quality_analysis', {})
        # Get full segment details for selected IDs
        selected_segments = []
        actual_duration = 0
        
        for i, seg_id in enumerate(selected_ids, 1):
            # Find the segment in our list
            seg_data = next((s for s in segments if s['segment_id'] == seg_id), None)
            if seg_data:
                selected_segments.append({
                    **seg_data,
                    'medley_order': i,
                    'original_order': segments.index(seg_data) + 1
                })
                actual_duration += seg_data['duration']
        
        # Create medley output
        medley_data = {
            'interview_id': interview_id,
            'recommendation_id': rec_id,
            'participant': participant_username,
            'created_at': datetime.now().isoformat(),
            'total_duration': actual_duration,
            'gpt_estimated_duration': total_duration,
            'segment_count': len(selected_segments),
            'segments': selected_segments,
            'gpt_reasoning': reasoning,
            'reordered': reordered,
            'recommendation_text': rec_details['recommendation_text'],
            "quality_analysis": quality_analysis
        }
        
        self.log(f"📊 Medley Summary:")
        self.log(f"   Selected segments: {len(selected_segments)}")
        self.log(f"   Total duration: {actual_duration:.2f}s")
        self.log(f"   Reordered: {reordered}")
        self.log(f"   GPT reasoning: {reasoning[:100]}...")
        
        return medley_data
    
    def save_medley_json(self, medley_data):
        """
        Save medley data to JSON file.
        
        Args:
            medley_data: Dictionary with medley information
            
        Returns:
            Path to saved JSON file
        """
        interview_id = medley_data['interview_id']
        rec_id = medley_data['recommendation_id']
        
        filename = f"interview_{interview_id}_rec_{rec_id}.json"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(medley_data, f, indent=2)
        
        self.log(f"💾 Saved medley to: {filepath}")
        return filepath
    
    def generate_and_save(self, interview_id, rec_id=None, rec_text=None, topic_category='all'):
        """
        Generate and save a medley in one step.
        
        Args:
            interview_id: Interview ID
            rec_id: Recommendation ID (optional if rec_text provided)
            rec_text: Direct recommendation text (optional if rec_id provided)
            topic_category: Topic category key from RECOMMENDATION_QUESTION_MAPPING (default: 'all')
            
        Returns:
            Path to saved JSON file, or None if failed
        """
        medley = self.create_medley(interview_id, rec_id, rec_text, topic_category=topic_category)
        if medley:
            return self.save_medley_json(medley)
        return None
    
    def save_medley_to_db(self, medley_data, recommendation_obj, participant_obj):
        """
        Save medley data to the database.
        
        Args:
            medley_data: Dictionary with medley information (from create_medley)
            recommendation_obj: Recommendation model instance
            participant_obj: Participant model instance
            
        Returns:
            Tuple of (Medley object, LivePrediction object) or (None, None) if failed
        """
        try:
            with transaction.atomic():
                # Create Medley object
                medley = Medley.objects.create(
                    recommendation=recommendation_obj,
                    participant=participant_obj,
                    total_duration=medley_data['total_duration'],
                    gpt_estimated_duration=medley_data['gpt_estimated_duration'],
                    segment_count=medley_data['segment_count'],
                    gpt_reasoning=medley_data['gpt_reasoning'],
                    reordered=medley_data['reordered'],
                    recommendation_text=medley_data['recommendation_text'],
                    quality_score=medley_data.get('quality_score')
                )
                
                # Add segments to ManyToMany relationship
                segment_ids = [seg['segment_id'] for seg in medley_data['segments']]
                segments = InterviewSegment.objects.filter(id__in=segment_ids)
                medley.segments.set(segments)
                
                # Find corresponding utterances for each segment
                utterance_list = []
                for segment in segments:
                    audio_id = segment.audio.id
                    utterances = InterviewUtterance.objects.filter(audio_id=audio_id)
                    utterance_list.extend(utterances)
                
                # Add utterances to ManyToMany relationship
                if utterance_list:
                    medley.utterances.set(utterance_list)
                
                self.log(f"✅ Saved Medley to database (ID: {medley.id})")
                return medley
                
        except Exception as e:
            self.log(f"❌ Failed to save medley to database: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def process_and_save_to_db(self, interview_ids, recommendation_obj, topic_category='all'):
        """
        Process multiple interviews and save medleys to database.
        
        Args:
            interview_ids: List of interview IDs to process
            recommendation_obj: Recommendation model instance to link medleys to
            topic_category: Topic category for question filtering
            
        Returns:
            Dictionary with processing results
        """
        self.log(f"\n{'='*80}")
        self.log(f"BATCH PROCESSING TO DATABASE")
        self.log(f"{'='*80}")
        self.log(f"Interview IDs: {interview_ids}")
        self.log(f"Recommendation ID: {recommendation_obj.id}")
        self.log(f"Recommendation Text: {recommendation_obj.rec_text[:80]}...")
        self.log(f"Topic Category: {topic_category}")
        self.log(f"{'='*80}\n")
        
        results = {
            'successful': 0,
            'failed': 0,
            'medleys': [],
            'errors': []
        }
        
        for interview_id in interview_ids:
            try:
                # Get participant from interview
                interview = Interview.objects.get(id=interview_id)
                participant = interview.participant
                
                if not participant:
                    self.log(f"⚠️  Interview {interview_id} has no participant, skipping")
                    results['failed'] += 1
                    results['errors'].append({
                        'interview_id': interview_id,
                        'error': 'No participant found'
                    })
                    continue
                
                self.log(f"\n📝 Processing Interview {interview_id} (Participant: {participant.username})")
                
                # Create medley
                medley_data = self.create_medley(
                    interview_id=interview_id,
                    rec_text=recommendation_obj.rec_text,
                    topic_category=topic_category
                )
                
                if not medley_data:
                    self.log(f"❌ Failed to create medley for interview {interview_id}")
                    results['failed'] += 1
                    results['errors'].append({
                        'interview_id': interview_id,
                        'participant': participant.username,
                        'error': 'Medley creation failed'
                    })
                    continue
                
                # Calculate quality score
                quality_score = None
                if medley_data.get('quality_analysis'):
                    qa = medley_data['quality_analysis']
                    quality_score = self.calculate_quality_score(
                        qa.get('opinion_vs_experiences'),
                        qa.get('relevance_score'),
                        qa.get('depth_score')
                    )
                    medley_data['quality_score'] = quality_score
                
                # Save to database
                medley_obj = self.save_medley_to_db(
                    medley_data,
                    recommendation_obj,
                    participant
                )
                
                if medley_obj:
                    results['successful'] += 1
                    results['medleys'].append({
                        'interview_id': interview_id,
                        'participant': participant.username,
                        'medley_id': medley_obj.id,
                        'quality_score': quality_score
                    })
                else:
                    results['failed'] += 1
                    results['errors'].append({
                        'interview_id': interview_id,
                        'participant': participant.username,
                        'error': 'Database save failed'
                    })
                    
            except Interview.DoesNotExist:
                self.log(f"❌ Interview {interview_id} not found")
                results['failed'] += 1
                results['errors'].append({
                    'interview_id': interview_id,
                    'error': 'Interview not found'
                })
            except Exception as e:
                self.log(f"❌ Error processing interview {interview_id}: {e}")
                import traceback
                traceback.print_exc()
                results['failed'] += 1
                results['errors'].append({
                    'interview_id': interview_id,
                    'error': str(e)
                })
        
        # Print summary
        self.log(f"\n{'='*80}")
        self.log(f"BATCH PROCESSING COMPLETE")
        self.log(f"{'='*80}")
        self.log(f"✅ Successful: {results['successful']}")
        self.log(f"❌ Failed: {results['failed']}")
        if results['errors']:
            self.log(f"\nErrors:")
            for err in results['errors']:
                self.log(f"  - Interview {err['interview_id']}: {err['error']}")
        self.log(f"{'='*80}\n")
        
        return results


def batch_process_to_database(interview_ids, recommendation_id, topic_category='all'):
    """
    Convenience function to batch process interviews and save to database.
    
    Usage:
        from generating_v2.medley_individual import batch_process_to_database
        
        results = batch_process_to_database(
            interview_ids=range(202, 326),  # Interviews 202-325
            recommendation_id=74,            # Existing recommendation
            topic_category='minimum_wage'   # Filter to min wage questions
        )
    
    Args:
        interview_ids: List or range of interview IDs
        recommendation_id: Recommendation ID from database
        topic_category: Topic category for filtering (default: 'all')
    
    Returns:
        Dictionary with results
    """
    try:
        # Get recommendation object
        recommendation = Recommendation.objects.get(id=recommendation_id)
        
        # Initialize generator
        generator = MedleyGenerator()
        
        # Process and save
        results = generator.process_and_save_to_db(
            interview_ids=list(interview_ids),
            recommendation_obj=recommendation,
            topic_category=topic_category
        )
        
        return results
        
    except Recommendation.DoesNotExist:
        print(f"❌ Recommendation {recommendation_id} not found")
        return {'successful': 0, 'failed': len(list(interview_ids)), 'errors': ['Recommendation not found']}
    except Exception as e:
        print(f"❌ Error in batch processing: {e}")
        import traceback
        traceback.print_exc()
        return {'successful': 0, 'failed': len(list(interview_ids)), 'errors': [str(e)]}


def main():
    """Main function to generate medleys"""
    
    # List of interview IDs to generate medleys for
    INTERVIEW_IDS = [
        208,  # Testing
    ]
    
    # Option 1: Use a recommendation ID from the database
    RECOMMENDATION_ID = 270  # Set to None if using custom text
    
    # Option 2: Specify recommendation text directly (for testing)
    RECOMMENDATION_TEXT = """
    The federal minimum wage should be raised to $30 per hour.
    """
    
    # Topic category for question filtering
    # Options: 'minimum_wage', 'climate', 'healthcare', 'all' (or add more in RECOMMENDATION_QUESTION_MAPPING)
    TOPIC_CATEGORY = 'minimum_wage'  # Change this based on your recommendation
    
    generator = MedleyGenerator()
    
    if not INTERVIEW_IDS:
        print("⚠️  No interview IDs specified!")
        print("📝 Please add interview IDs to the INTERVIEW_IDS list")
        print("💡 Example: INTERVIEW_IDS = [10, 11, 12]")
        return
    
    # Validate configuration
    if not RECOMMENDATION_ID and not RECOMMENDATION_TEXT.strip():
        print("❌ Error: You must specify either RECOMMENDATION_ID or RECOMMENDATION_TEXT")
        return
    
    print(f"\n{'='*80}")
    print(f"MEDLEY GENERATION")
    print(f"{'='*80}")
    print(f"Interview IDs: {INTERVIEW_IDS}")
    print(f"Topic Category: {TOPIC_CATEGORY}")
    if RECOMMENDATION_ID:
        print(f"Recommendation ID: {RECOMMENDATION_ID}")
    else:
        print(f"Recommendation Text: {RECOMMENDATION_TEXT.strip()[:80]}...")
    print(f"{'='*80}\n")
    
    results = {
        'successful': 0,
        'failed': 0,
        'medleys': []
    }
    
    for interview_id in INTERVIEW_IDS:
        try:
            if RECOMMENDATION_TEXT and RECOMMENDATION_TEXT.strip():
                # Use custom recommendation text
                filepath = generator.generate_and_save(
                    interview_id, 
                    rec_id=RECOMMENDATION_ID, 
                    rec_text=RECOMMENDATION_TEXT.strip(),
                    topic_category=TOPIC_CATEGORY
                )
            else:
                # Use recommendation ID from database
                filepath = generator.generate_and_save(
                    interview_id, 
                    rec_id=RECOMMENDATION_ID,
                    topic_category=TOPIC_CATEGORY
                )
            
            if filepath:
                results['successful'] += 1
                results['medleys'].append(str(filepath))
            else:
                results['failed'] += 1
        except Exception as e:
            print(f"❌ Error processing interview {interview_id}: {e}")
            import traceback
            traceback.print_exc()
            results['failed'] += 1
    
    # Final summary
    print(f"\n{'='*80}")
    print(f"FINAL SUMMARY")
    print(f"{'='*80}")
    print(f"✅ Successful: {results['successful']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"📁 Medleys saved to: generating_v2/medleys/")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
