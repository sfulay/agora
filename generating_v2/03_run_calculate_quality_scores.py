#!/usr/bin/env python3
"""
Simple script to calculate quality scores from existing database data.
This calculates the weighted quality score without re-running any generation.
"""

import os
import sys
import django
from pathlib import Path

# Django setup
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.environ['DJANGO_SETTINGS_MODULE'] = 'gabm_infra.settings.local'
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = "true"

django.setup()

from pages.models import RecommendationParticipantSummary

def calculate_quality_score(opinion_score, relevance_score, depth_score):
    """
    Calculate weighted quality score combining all three metrics.
    Formula: (0.4 × Opinion_vs_Experience) + (0.4 × Relevance) + (0.2 × Depth)
    """
    if any(score is None for score in [opinion_score, relevance_score, depth_score]):
        return None
    
    quality_score = (0.4 * opinion_score) + (0.4 * relevance_score) + (0.2 * depth_score)
    return round(quality_score, 1)

def update_quality_scores():
    """Update quality scores for all existing RecommendationParticipantSummary records"""
    
    # Get all summaries that have relevance_score, coherence_score, and opinion_vs_experience_score
    summaries = RecommendationParticipantSummary.objects.filter(
        relevance_score__isnull=False,
        coherence_score__isnull=False,
        opinion_vs_experience_score__isnull=False
    ).select_related('participant', 'recommendation')
    
    print(f"Found {summaries.count()} summaries to update...")
    
    updated_count = 0
    for summary in summaries:
        opinion_score = summary.opinion_vs_experience_score
        relevance_score = summary.relevance_score
        depth_score = summary.coherence_score
        
        # Calculate quality score
        quality_score = calculate_quality_score(opinion_score, relevance_score, depth_score)
        
        if quality_score is not None:
            summary.quality_score = quality_score
            summary.save()
            updated_count += 1
            
            print(f"Updated {summary.participant.username} - Recommendation {summary.recommendation.id}:")
            print(f"  Opinion vs Experience: {opinion_score}")
            print(f"  Relevance: {relevance_score}")
            print(f"  Depth: {depth_score}")
            print(f"  Quality Score: {quality_score}")
            print("-" * 50)
    
    print(f"\nCompleted! Updated quality scores for {updated_count} summaries.")

if __name__ == "__main__":
    update_quality_scores() 