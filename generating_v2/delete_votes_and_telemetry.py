
#%%
import os
import numpy
import openai 
import json
os.getcwd()
prompt_template_file = "generate_recs_climate"
prompt_dir = f"interviewer_agent/prompt_template/prompts"
setting = "local"
if setting == "production":
    %cd /var/app/current
else: 
    %cd ../
%pwd 
import sys
import django
from django.db import transaction

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gabm_infra.settings.local')
django.setup()
#%%
from pages.models import (
    RecommendationVote,
    DecisionFeedback,
    ConnectionReport,
    PredictedVoteReport,
    PredictionFeedback,
    RecommendationTimeSpent,
    AvatarClick,
    ParticipantProfileTime,
    AudioClipListening,
    VotingScreenTime,
    Participant
)
#%%
# ==================== CONFIGURATION ====================
# Set your Prolific ID here
import pandas as pd
treatment_assignment = pd.read_csv("data/treatment_assignments/treatment_control_assignment.csv")
PROLIFIC_ID = treatment_assignment.query(f"assignment == 'treatment'")["prolific_id"].values[0]  # Replace with actual Prolific ID
print(f"Deleting entries for Prolific ID: {PROLIFIC_ID}")

# Set to True to actually delete entries, False to just preview
DELETE_ENTRIES = False
# ======================================================
#%%
def delete_entries_by_prolific_id(prolific_id, delete_entries=False):
    """
    Find and delete all entries for a given Prolific ID from the specified models.
    
    Args:
        prolific_id (str): The Prolific ID to search for and delete entries for
        delete_entries (bool): If True, actually delete the entries. If False, just preview.
    """
    
    # First, check if the participant exists
    try:
        participant = Participant.objects.get(prolific_id=prolific_id)
        print(f"Found participant: {participant.get_full_name()} (ID: {participant.id})")
    except Participant.DoesNotExist:
        print(f"Error: No participant found with Prolific ID '{prolific_id}'")
        return
    
    # Define the models to check and delete from
    models_to_check = [
        ('RecommendationVote', RecommendationVote),
        ('DecisionFeedback', DecisionFeedback),
        ('ConnectionReport', ConnectionReport),
        ('PredictedVoteReport', PredictedVoteReport),
        ('PredictionFeedback', PredictionFeedback),
        ('RecommendationTimeSpent', RecommendationTimeSpent),
        ('AvatarClick', AvatarClick),
        ('ParticipantProfileTime', ParticipantProfileTime),
        ('AudioClipListening', AudioClipListening),
        ('VotingScreenTime', VotingScreenTime),
    ]
    
    total_deleted = 0
    
    print(f"\nSearching for entries with Prolific ID: {prolific_id}")
    print("=" * 60)
    
    # Show summary of what will be deleted
    print("\nSummary of entries to be deleted:")
    print("-" * 40)
    for model_name, model_class in models_to_check:
        try:
            count = model_class.objects.filter(participant=participant).count()
            if count > 0:
                print(f"  {model_name}: {count} entries")
        except Exception as e:
            print(f"  {model_name}: Error checking - {str(e)}")
    
    # Check if we should actually delete or just preview
    if not delete_entries:
        print(f"\nPREVIEW MODE - No entries will be deleted")
        print(f"To actually delete entries, set DELETE_ENTRIES = True in the configuration section")
        return
    
    with transaction.atomic():
        for model_name, model_class in models_to_check:
            try:
                # Find entries for this participant
                entries = model_class.objects.filter(participant=participant)
                count = entries.count()
                
                if count > 0:
                    print(f"\n{model_name}:")
                    print(f"  Found {count} entries")
                    
                    # Print details of entries before deletion
                    for i, entry in enumerate(entries[:5]):  # Show first 5 entries
                        print(f"    Entry {i+1}: ID={entry.id}, Created={entry.created_at}")
                    
                    if count > 5:
                        print(f"    ... and {count - 5} more entries")
                    
                    # Delete the entries
                    deleted_count, _ = entries.delete()
                    print(f"  Deleted {deleted_count} entries")
                    total_deleted += deleted_count
                else:
                    print(f"\n{model_name}: No entries found")
                    
            except Exception as e:
                print(f"\n{model_name}: Error - {str(e)}")
    
    print("\n" + "=" * 60)
    print(f"Summary: Deleted {total_deleted} total entries for Prolific ID '{prolific_id}'")
    
    # Verify deletion by checking again
    print(f"\nVerifying deletion...")
    remaining_entries = 0
    for model_name, model_class in models_to_check:
        try:
            count = model_class.objects.filter(participant=participant).count()
            if count > 0:
                print(f"  Warning: {count} entries still exist in {model_name}")
                remaining_entries += count
        except Exception as e:
            print(f"  Error checking {model_name}: {str(e)}")
    
    if remaining_entries == 0:
        print("  All entries successfully deleted!")
    else:
        print(f"  Warning: {remaining_entries} entries still remain")

def preview_entries(prolific_id):
    """
    Preview what entries exist for a Prolific ID without deleting them.
    
    Args:
        prolific_id (str): The Prolific ID to search for
    """
    
    # First, check if the participant exists
    try:
        participant = Participant.objects.get(prolific_id=prolific_id)
        print(f"Found participant: {participant.get_full_name()} (ID: {participant.id})")
    except Participant.DoesNotExist:
        print(f"Error: No participant found with Prolific ID '{prolific_id}'")
        return
    
    # Define the models to check
    models_to_check = [
        ('RecommendationVote', RecommendationVote),
        ('DecisionFeedback', DecisionFeedback),
        ('ConnectionReport', ConnectionReport),
        ('PredictedVoteReport', PredictedVoteReport),
        ('PredictionFeedback', PredictionFeedback),
        ('RecommendationTimeSpent', RecommendationTimeSpent),
        ('AvatarClick', AvatarClick),
        ('ParticipantProfileTime', ParticipantProfileTime),
        ('AudioClipListening', AudioClipListening),
        ('VotingScreenTime', VotingScreenTime),
    ]
    
    print(f"\nPreview of entries for Prolific ID: {prolific_id}")
    print("=" * 60)
    
    total_entries = 0
    for model_name, model_class in models_to_check:
        try:
            entries = model_class.objects.filter(participant=participant)
            count = entries.count()
            total_entries += count
            
            if count > 0:
                print(f"\n{model_name}: {count} entries")
                # Show sample entries
                for i, entry in enumerate(entries[:3]):  # Show first 3 entries
                    print(f"  Entry {i+1}: ID={entry.id}, Created={entry.created_at}")
                if count > 3:
                    print(f"  ... and {count - 3} more entries")
            else:
                print(f"\n{model_name}: No entries")
                
        except Exception as e:
            print(f"\n{model_name}: Error - {str(e)}")
    
    print(f"\nTotal entries found: {total_entries}")

# %%
delete_entries_by_prolific_id(PROLIFIC_ID, delete_entries=DELETE_ENTRIES)
# %%
