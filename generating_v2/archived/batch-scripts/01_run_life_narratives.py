#!/usr/bin/env python3
"""
Simple script to run life narrative generation.
This demonstrates how to use the LifeNarrativeGenerator class.
"""

from life_narrative import LifeNarrativeGenerator
import pandas as pd

def run_life_narratives(delete_existing=False):
    """Run life narrative generation for all participants"""
    
    # Load participant data
    all_participants = pd.read_csv("data/participant_data_clean.csv")
    participant_usernames = all_participants["prolific_id"].tolist()
    
    # Initialize generator
    generator = LifeNarrativeGenerator()
    
    # Generate and save life narratives
    print(f"Processing {len(participant_usernames)} participants...")
    results = generator.save_life_narratives(participant_usernames, delete_existing=delete_existing)
    
    print(f"Completed! Processed {len(results)} participants.")
    return results

def run_single_participant(username):
    """Run life narrative generation for a single participant"""
    
    generator = LifeNarrativeGenerator()
    
    # Process single participant
    result = generator.process_participant(username)
    
    print(f"Generated narrative for {username}:")
    print(f"Summary: {result['life_summary']}")
    print(f"Number of narrative parts: {len(result['narrative_parts'])}")
    
    return result

if __name__ == "__main__":
    # Example usage:
    
    # Run for all participants
    results = run_life_narratives(delete_existing=True)
    
        # Or run for a single participant (uncomment and modify username)
    #result = run_single_participant("66ce5adac1cd4b6037be4a63")
   # print(result)
    
    print("Life narrative generation script ready!")
    print("Uncomment the desired function call above to run.") 