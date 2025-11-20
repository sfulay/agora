#!/usr/bin/env python3
"""
Meta-Medley Generator

Creates combined medleys from multiple participants' individual medleys.
Filters to top K participants by quality score and uses GPT to create
a cohesive 60-90 second group narrative.

Usage:
    from generating_v2.meta_medley import create_meta_medley
    
    meta_medley = create_meta_medley(
        recommendation_id=273,
        participant_usernames=['user1', 'user2', 'user3'],
        force_regenerate=False
    )
"""

import os
import sys
import json
import openai
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Setup Django if running as standalone script
if __name__ == "__main__":
    import django
    os.environ['DJANGO_SETTINGS_MODULE'] = 'gabm_infra.settings.local'
    os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    django.setup()

from pages.models import (
    Recommendation, Participant, Medley, MetaMedley, 
    InterviewSegment
)
from django.db import transaction

# Setup OpenAI
sys.path.append('interviewer_agent')
from interviewer_agent.interviewer_utils.settings import get_open_api_keyset
openai.api_key = get_open_api_keyset()["key"]


class MetaMedleyGenerator:
    """Generator for creating meta-medleys from multiple participant medleys."""
    
    def __init__(self, prompt_dir="generating_v2/prompts"):
        self.prompt_dir = Path(prompt_dir)
        self.max_k = 10  # Maximum participants to send to GPT
    
    def log(self, message):
        """Print timestamped log message."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")
    
    def get_group_context(self, medley_group: Optional[str]) -> Dict[str, str]:
        """Return stance-specific context for the GPT prompt."""
        default_context = {
            "group_name": "Mixed Perspectives",
            "group_support_stance": "Participants may hold a mix of supportive and skeptical viewpoints.",
            "segment_alignment_guidance": "You may include segments that contrast with one another as long as they stay relevant to the topic.",
            "diversity_guidance": "Showcase different people and angles while maintaining a coherent flow."
        }
        contexts = {
            "against": {
                "group_name": "Against",
                "group_support_stance": "Participants are predicted to oppose or reject the recommendation.",
                "segment_alignment_guidance": "Select only segments that express concerns, objections, harms, or reasons for opposing the recommendation. Do not introduce pro-recommendation arguments here.",
                "diversity_guidance": "Highlight varied people and angles that all support the opposing stance."
            },
            "on_the_fence": {
                "group_name": "On the fence",
                "group_support_stance": "Participants are predicted to feel ambivalent or undecided about the recommendation.",
                "segment_alignment_guidance": "Select segments that show nuance, trade-offs, questions, or mixed feelings. Avoid segments that are clearly all-in support or opposition without acknowledging uncertainty.",
                "diversity_guidance": "Include different participants weighing pros and cons, highlighting varied sources of uncertainty while keeping the tone balanced."
            },
            "for": {
                "group_name": "For",
                "group_support_stance": "Participants are predicted to support the recommendation.",
                "segment_alignment_guidance": "Select only segments that provide reasons, benefits, or positive outcomes supporting the recommendation. Do not introduce anti-recommendation arguments here.",
                "diversity_guidance": "Highlight varied people and angles that all reinforce the supportive stance."
            }
        }
        if medley_group:
            return contexts.get(medley_group, default_context)
        return default_context
    
    def generate_cache_key(self, participant_usernames: List[str], recommendation_id: int) -> str:
        """
        Generate a cache key for a set of participants and recommendation.
        Uses SHA256 hash to handle large participant sets.
        
        Args:
            participant_usernames: List of participant usernames
            recommendation_id: Recommendation ID
        
        Returns:
            Cache key string (hash of sorted usernames + rec_id)
        """
        sorted_usernames = sorted(participant_usernames)
        # Create a hash of the sorted usernames to handle large sets
        username_str = '_'.join(sorted_usernames)
        username_hash = hashlib.sha256(username_str.encode()).hexdigest()[:32]
        return f"rec{recommendation_id}_{username_hash}"
    
    def get_cached_meta_medley(self, cache_key: str) -> Optional[MetaMedley]:
        """
        Get the most recent meta-medley for a cache key.
        
        Args:
            cache_key: Cache key to look up
        
        Returns:
            Most recent MetaMedley or None
        """
        return MetaMedley.objects.filter(
            participant_cache_key=cache_key
        ).order_by('-version').first()
    
    def select_top_k_participants(
        self, 
        participant_usernames: List[str], 
        recommendation_id: int
    ) -> List[Dict]:
        """
        Select top K participants based on medley quality scores.
        
        Args:
            participant_usernames: List of participant usernames to consider
            recommendation_id: Recommendation ID
        
        Returns:
            List of dicts with participant, medley, and quality_score
            Sorted by quality_score DESC, limited to min(len, max_k)
        """
        n = len(participant_usernames)
        K = min(n, self.max_k)
        
        self.log(f"📊 Selecting top {K} from {n} participants")
        
        # Get latest medley for each participant
        medley_data = []
        for username in participant_usernames:
            try:
                participant = Participant.objects.get(username=username)
                medley = Medley.objects.filter(
                    recommendation_id=recommendation_id,
                    participant=participant
                ).order_by('-id').first()
                
                if medley:
                    medley_data.append({
                        'participant': participant,
                        'medley': medley,
                        'quality_score': medley.quality_score or 0
                    })
                else:
                    self.log(f"  ⚠️  No medley found for {username}")
            except Participant.DoesNotExist:
                self.log(f"  ⚠️  Participant {username} not found")
        
        if len(medley_data) < 2:
            raise ValueError(f"Need at least 2 participants with medleys, found {len(medley_data)}")
        
        # Sort by quality score descending
        medley_data.sort(key=lambda x: x['quality_score'], reverse=True)
        
        # Take top K
        top_k = medley_data[:K]
        
        self.log(f"✅ Selected {len(top_k)} participants:")
        for i, data in enumerate(top_k, 1):
            self.log(f"  {i}. {data['participant'].username} (quality: {data['quality_score']:.1f})")
        
        return top_k
    
    def prepare_medley_data_for_gpt(self, top_k_data: List[Dict]) -> str:
        """
        Format medley data for GPT prompt.
        
        Args:
            top_k_data: List of dicts with participant, medley, quality_score
        
        Returns:
            Formatted string for prompt
        """
        medley_descriptions = []
        
        for i, data in enumerate(top_k_data, 1):
            participant = data['participant']
            medley = data['medley']
            
            # Get segments with their details
            segments = medley.segments.all().order_by('id')
            segment_details = []
            
            for seg in segments:
                segment_details.append({
                    'segment_id': seg.id,
                    'text': seg.segment_text,
                    'duration': round(seg.duration, 2)
                })
            
            participant_block = f"""
PARTICIPANT {i}: {participant.username}
Quality Score: {data['quality_score']:.1f}
Total Medley Duration: {medley.total_duration:.1f}s
Number of Segments: {len(segment_details)}
GPT's Selection Reasoning: {medley.gpt_reasoning}

Available Segments (ID | Duration | Text):
"""
            for seg in segment_details:
                participant_block += f"  - ID {seg['segment_id']} | {seg['duration']}s | {seg['text']}\n"
            
            medley_descriptions.append(participant_block)
        
        return "\n".join(medley_descriptions)
    
    def call_gpt_for_meta_medley(
        self, 
        recommendation_text: str,
        medley_data_str: str,
        participant_count: int,
        group_context: Optional[Dict[str, str]] = None
    ) -> Dict:
        """
        Call GPT to select and order segments for meta-medley.
        
        Args:
            recommendation_text: The recommendation text
            medley_data_str: Formatted medley data
            participant_count: Number of participants
            group_context: Optional stance-specific instructions
        
        Returns:
            Parsed JSON response from GPT
        """
        # Load prompt template
        prompt_path = self.prompt_dir / "meta_medley_selection.txt"
        with open(prompt_path, 'r') as f:
            prompt_template = f.read()
        
        context = group_context or self.get_group_context(None)
        
        # Fill in template
        prompt = prompt_template.format(
            recommendation_text=recommendation_text,
            participant_count=participant_count,
            medley_data=medley_data_str,
            group_name=context["group_name"],
            group_support_stance=context["group_support_stance"],
            segment_alignment_guidance=context["segment_alignment_guidance"],
            diversity_guidance=context["diversity_guidance"]
        )
        
        self.log("🤖 Calling GPT-4o for meta-medley selection...")
        
        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert at creating compelling narrative medleys from multiple perspectives."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            self.log("✅ GPT selection complete")
            
            return result
            
        except Exception as e:
            self.log(f"❌ GPT call failed: {e}")
            raise
    
    def validate_and_calculate_duration(self, gpt_response: Dict, top_k_data: List[Dict]) -> float:
        """
        Validate GPT response and calculate actual duration.
        
        Args:
            gpt_response: GPT's response with selected_segments
            top_k_data: Top K participant data for validation
        
        Returns:
            Actual total duration in seconds
        
        Raises:
            ValueError: If duration exceeds hard limit or no segments selected
        """
        selected_segments = gpt_response.get('selected_segments', [])
        
        if not selected_segments:
            raise ValueError("GPT returned no segments")
        
        if len(selected_segments) < 6:
            self.log(f"⚠️  Warning: Only {len(selected_segments)} segments selected (recommended: 6-8)")
        
        if len(selected_segments) > 8:
            self.log(f"⚠️  Warning: {len(selected_segments)} segments selected (recommended: 6-8 for better duration control)")
        
        # Calculate actual duration by fetching segments from DB
        total_duration = 0.0
        missing_segments = []
        segment_durations = []
        segments_with_duration = []
        
        for seg_data in selected_segments:
            segment_id = seg_data['segment_id']
            try:
                segment = InterviewSegment.objects.get(id=segment_id)
                segment_durations.append(segment.duration)
                segments_with_duration.append((seg_data, segment.duration))
                total_duration += segment.duration
            except InterviewSegment.DoesNotExist:
                self.log(f"⚠️  Warning: Segment {segment_id} not found")
                missing_segments.append(segment_id)
        
        gpt_estimated = gpt_response.get('estimated_duration', 0)
        self.log(f"📊 Duration: {total_duration:.1f}s (GPT estimated: {gpt_estimated:.1f}s)")
        
        HARD_LIMIT = 120.0
        TARGET_MIN = 60.0
        TARGET_MAX = 90.0
        
        if total_duration > HARD_LIMIT:
            self.log(f"⚠️  Duration {total_duration:.1f}s exceeds hard limit of {HARD_LIMIT}s. Trimming longest segments...")
            trimmed_segments = list(selected_segments)
            trimmed_pairs = list(segments_with_duration)
            while total_duration > HARD_LIMIT and len(trimmed_pairs) > 2:
                # Remove the segment with the longest duration
                idx = max(range(len(trimmed_pairs)), key=lambda i: trimmed_pairs[i][1])
                removed_seg, removed_duration = trimmed_pairs.pop(idx)
                trimmed_segments.pop(idx)
                total_duration -= removed_duration
                self.log(f"   Removed segment {removed_seg['segment_id']} ({removed_duration:.1f}s). New total: {total_duration:.1f}s")
            if total_duration > HARD_LIMIT:
                raise ValueError(f"Duration still {total_duration:.1f}s after trimming. Need fewer/shorter segments.")
            else:
                self.log(f"✅ Trimmed to {total_duration:.1f}s with {len(trimmed_segments)} segments")
                gpt_response['selected_segments'] = trimmed_segments
        
        if total_duration < TARGET_MIN or total_duration > TARGET_MAX:
            self.log(f"⚠️  Warning: Duration {total_duration:.1f}s outside target range (60-90s) but within acceptable limits")
        
        return total_duration
    
    def create_meta_medley(
        self,
        recommendation_id: int,
        participant_usernames: List[str],
        force_regenerate: bool = False,
        medley_group: Optional[str] = None
    ) -> MetaMedley:
        """
        Main function to create a meta-medley.
        
        Args:
            recommendation_id: Recommendation ID
            participant_usernames: List of participant usernames
            force_regenerate: If True, create new version even if cached
            medley_group: Optional stance label ("against", "on_the_fence", "for")
        
        Returns:
            MetaMedley object
        """
        self.log("="*80)
        self.log(f"Creating Meta-Medley: Rec {recommendation_id} × {len(participant_usernames)} participants" + (f" [{medley_group}]" if medley_group else ""))
        self.log("="*80)
        
        # Validate inputs
        if len(participant_usernames) < 2:
            raise ValueError("Need at least 2 participants for meta-medley")
        
        # Get recommendation
        try:
            recommendation = Recommendation.objects.get(id=recommendation_id)
        except Recommendation.DoesNotExist:
            raise ValueError(f"Recommendation {recommendation_id} not found")
        
        # Generate cache key
        cache_key = self.generate_cache_key(participant_usernames, recommendation_id)
        
        # Check cache
        if not force_regenerate:
            cached = self.get_cached_meta_medley(cache_key)
            if cached:
                self.log(f"✅ Found cached meta-medley (v{cached.version}, ID: {cached.id})")
                return cached
        
        # Select top K participants
        top_k_data = self.select_top_k_participants(participant_usernames, recommendation_id)
        
        # Prepare data for GPT
        medley_data_str = self.prepare_medley_data_for_gpt(top_k_data)
        
        group_context = self.get_group_context(medley_group)
        
        # Call GPT
        gpt_response = self.call_gpt_for_meta_medley(
            recommendation_text=recommendation.rec_text,
            medley_data_str=medley_data_str,
            participant_count=len(top_k_data),
            group_context=group_context
        )
        
        # Validate and calculate actual duration
        actual_duration = self.validate_and_calculate_duration(gpt_response, top_k_data)
        
        # Determine version number
        existing = MetaMedley.objects.filter(participant_cache_key=cache_key)
        version = existing.count() + 1
        
        # Create MetaMedley object
        with transaction.atomic():
            meta_medley = MetaMedley.objects.create(
                recommendation=recommendation,
                selected_segments=gpt_response['selected_segments'],
                total_duration=actual_duration,
                segment_count=len(gpt_response['selected_segments']),
                gpt_reasoning=gpt_response.get('narrative_reasoning', ''),
                participant_cache_key=cache_key,
                version=version
            )
            
            # Add participants
            for data in top_k_data:
                meta_medley.participants.add(data['participant'])
            
            # Add source medleys
            for data in top_k_data:
                meta_medley.source_medleys.add(data['medley'])
        
        self.log(f"✅ Created MetaMedley (ID: {meta_medley.id}, v{version})")
        self.log(f"   Duration: {actual_duration:.1f}s")
        self.log(f"   Segments: {meta_medley.segment_count}")
        self.log(f"   Participants: {len(top_k_data)}")
        self.log("="*80)
        
        return meta_medley


# Convenience function for module-level access
def create_meta_medley(
    recommendation_id: int,
    participant_usernames: List[str],
    force_regenerate: bool = False,
    medley_group: Optional[str] = None
) -> MetaMedley:
    """
    Create a meta-medley from multiple participants.
    
    Args:
        recommendation_id: Recommendation ID
        participant_usernames: List of participant usernames
        force_regenerate: If True, create new version even if cached
        medley_group: Optional stance label ("against", "on_the_fence", "for")
    
    Returns:
        MetaMedley object
    
    Example:
        meta_medley = create_meta_medley(
            recommendation_id=273,
            participant_usernames=['user1', 'user2', 'user3'],
            medley_group='against'
        )
    """
    generator = MetaMedleyGenerator()
    return generator.create_meta_medley(
        recommendation_id=recommendation_id,
        participant_usernames=participant_usernames,
        force_regenerate=force_regenerate,
        medley_group=medley_group
    )


if __name__ == "__main__":
    # Example usage
    print("Meta-Medley Generator")
    print("="*80)
    print("This module creates combined medleys from multiple participants.")
    print("\nUsage:")
    print("  from generating_v2.meta_medley import create_meta_medley")
    print("  meta_medley = create_meta_medley(273, ['user1', 'user2', 'user3'])")

