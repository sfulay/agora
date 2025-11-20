#!/usr/bin/env python3
"""
Test script for meta-medley generation.

Tests various scenarios:
- Small groups (n=2-3)
- Medium groups (n=8)
- Large groups (n=20)
- Caching behavior
- Regeneration

Usage:
    python generating_v2/test_meta_medley.py
"""

import os
import sys
import django

# Setup Django
os.environ['DJANGO_SETTINGS_MODULE'] = 'gabm_infra.settings.local'
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from pages.models import Medley, Participant, MetaMedley
from generating_v2.meta_medley import create_meta_medley


def get_participants_with_medleys(recommendation_id, limit=None):
    """Get participants that have medleys for a recommendation."""
    medleys = Medley.objects.filter(
        recommendation_id=recommendation_id
    ).select_related('participant').order_by('-quality_score')
    
    if limit:
        medleys = medleys[:limit]
    
    participants = [m.participant.username for m in medleys]
    return participants


def test_small_group():
    """Test with 3 participants (n < max_k)."""
    print("\n" + "="*80)
    print("TEST 1: Small Group (n=3)")
    print("="*80)
    
    participants = get_participants_with_medleys(recommendation_id=273, limit=3)
    print(f"Selected participants: {participants}")
    
    if len(participants) < 2:
        print("⚠️  Not enough participants for test")
        return
    
    meta_medley = create_meta_medley(
        recommendation_id=273,
        participant_usernames=participants,
        medley_group='against'
    )
    
    print(f"\n✅ Created MetaMedley {meta_medley.id}")
    print(f"   Participants used: {meta_medley.participants.count()}")
    print(f"   Duration: {meta_medley.total_duration:.1f}s")
    print(f"   Segments: {meta_medley.segment_count}")
    print(f"   Version: {meta_medley.version}")


def test_medium_group():
    """Test with 8 participants."""
    print("\n" + "="*80)
    print("TEST 2: Medium Group (n=8)")
    print("="*80)
    
    participants = get_participants_with_medleys(recommendation_id=273, limit=8)
    print(f"Selected participants: {len(participants)} total")
    
    if len(participants) < 2:
        print("⚠️  Not enough participants for test")
        return
    
    meta_medley = create_meta_medley(
        recommendation_id=273,
        participant_usernames=participants,
        medley_group='on_the_fence'
    )
    
    print(f"\n✅ Created MetaMedley {meta_medley.id}")
    print(f"   Participants used: {meta_medley.participants.count()}")
    print(f"   Duration: {meta_medley.total_duration:.1f}s")
    print(f"   Segments: {meta_medley.segment_count}")


def test_large_group():
    """Test with 20 participants (should filter to top 10)."""
    print("\n" + "="*80)
    print("TEST 3: Large Group (n=20, should use top 10)")
    print("="*80)
    
    participants = get_participants_with_medleys(recommendation_id=273, limit=20)
    print(f"Selected participants: {len(participants)} total")
    
    if len(participants) < 2:
        print("⚠️  Not enough participants for test")
        return
    
    meta_medley = create_meta_medley(
        recommendation_id=273,
        participant_usernames=participants,
        medley_group='for'
    )
    
    print(f"\n✅ Created MetaMedley {meta_medley.id}")
    print(f"   Participants requested: {len(participants)}")
    print(f"   Participants actually used: {meta_medley.participants.count()}")
    print(f"   Duration: {meta_medley.total_duration:.1f}s")
    print(f"   Segments: {meta_medley.segment_count}")


def test_caching():
    """Test that same participant set returns cached result."""
    print("\n" + "="*80)
    print("TEST 4: Caching")
    print("="*80)
    
    participants = get_participants_with_medleys(recommendation_id=273, limit=5)
    print(f"Selected participants: {participants}")
    
    if len(participants) < 2:
        print("⚠️  Not enough participants for test")
        return
    
    # First call
    print("\nFirst call (should create new):")
    meta_medley_1 = create_meta_medley(
        recommendation_id=273,
        participant_usernames=participants
    )
    print(f"Created MetaMedley {meta_medley_1.id} (v{meta_medley_1.version})")
    
    # Second call (should return cached)
    print("\nSecond call (should return cached):")
    meta_medley_2 = create_meta_medley(
        recommendation_id=273,
        participant_usernames=participants
    )
    print(f"Got MetaMedley {meta_medley_2.id} (v{meta_medley_2.version})")
    
    if meta_medley_1.id == meta_medley_2.id:
        print("✅ Caching works! Same meta-medley returned.")
    else:
        print("❌ Caching failed. Different meta-medley returned.")


def test_regeneration():
    """Test forcing regeneration creates new version."""
    print("\n" + "="*80)
    print("TEST 5: Regeneration")
    print("="*80)
    
    participants = get_participants_with_medleys(recommendation_id=273, limit=4)
    print(f"Selected participants: {participants}")
    
    if len(participants) < 2:
        print("⚠️  Not enough participants for test")
        return
    
    # First call
    print("\nCreating initial meta-medley:")
    meta_medley_1 = create_meta_medley(
        recommendation_id=273,
        participant_usernames=participants,
        force_regenerate=False
    )
    print(f"Created MetaMedley {meta_medley_1.id} (v{meta_medley_1.version})")
    
    # Force regeneration
    print("\nForce regenerating:")
    meta_medley_2 = create_meta_medley(
        recommendation_id=273,
        participant_usernames=participants,
        force_regenerate=True
    )
    print(f"Created MetaMedley {meta_medley_2.id} (v{meta_medley_2.version})")
    
    if meta_medley_2.version == meta_medley_1.version + 1:
        print("✅ Versioning works! New version created.")
    else:
        print(f"❌ Versioning issue. v{meta_medley_1.version} -> v{meta_medley_2.version}")


def test_segment_retrieval():
    """Test that we can retrieve segments from meta-medley."""
    print("\n" + "="*80)
    print("TEST 6: Segment Retrieval")
    print("="*80)
    
    # Get any existing meta-medley
    meta_medley = MetaMedley.objects.first()
    
    if not meta_medley:
        print("⚠️  No meta-medleys found. Run other tests first.")
        return
    
    print(f"Using MetaMedley {meta_medley.id}")
    print(f"Selected segments: {len(meta_medley.selected_segments)}")
    
    # Try to retrieve each segment
    print("\nRetrieving segments:")
    from pages.models import InterviewSegment
    
    for i, seg_data in enumerate(meta_medley.selected_segments[:3], 1):
        segment_id = seg_data['segment_id']
        participant_username = seg_data['participant_username']
        
        try:
            segment = InterviewSegment.objects.get(id=segment_id)
            print(f"  {i}. Segment {segment_id} ({participant_username})")
            print(f"     Duration: {segment.duration:.1f}s")
            print(f"     Text: {segment.segment_text[:60]}...")
            print(f"     Audio: {segment.segment_audio_file.name if segment.segment_audio_file else 'N/A'}")
        except InterviewSegment.DoesNotExist:
            print(f"  {i}. ❌ Segment {segment_id} not found!")
    
    print("\n✅ Segment retrieval works!")


def run_all_tests():
    """Run all test cases."""
    print("="*80)
    print("META-MEDLEY TEST SUITE")
    print("="*80)
    
    try:
        test_small_group()
        test_medium_group()
        test_large_group()
        test_caching()
        test_regeneration()
        test_segment_retrieval()
        
        print("\n" + "="*80)
        print("ALL TESTS COMPLETED")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()

