#!/usr/bin/env python3
"""
Simple script to run recommendation prediction generation.
This demonstrates how to use the RecommendationPredictionGenerator class.
"""

from rec_prediction import RecommendationPredictionGenerator
import pandas as pd

def run_rec_predictions():
    """Run recommendation prediction generation for all participants"""
    
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
    return results

def update_relevance_scores_only():
    """Update only the relevance scores using existing evidence"""
    
    # Load participant data
    all_participants = pd.read_csv("data/participant_data_clean.csv")
    participant_usernames = all_participants["prolific_id"].tolist()
    
    # Initialize generator
    generator = RecommendationPredictionGenerator()
    
    # Example recommendation IDs (modify as needed)
    recommendation_ids = [74, 75, 76]
    
    # Update only relevance scores
    print(f"Updating relevance scores for {len(participant_usernames)} participants for {len(recommendation_ids)} recommendations...")
    results = generator.update_relevance_scores_only(participant_usernames, recommendation_ids)
    
    print(f"Completed! Updated {len(results)} participant-recommendation combinations.")
    return results

def run_single_participant_recommendation(username, rec_text, display_name):
    """Run recommendation prediction for a single participant-recommendation combination"""
    
    generator = RecommendationPredictionGenerator()
    
    # Process single participant-recommendation combination
    result = generator.process_participant_recommendation(username, rec_text, display_name)
    #print(result)
    
    print(f"Generated prediction for {display_name} ({username}):")
    print(f"Predicted Agreement: {result['prediction']['predicted_agreement']}")
    print(f"Confidence Score: {result['prediction']['confidence_score']}")
    print(f"Reasoning: {result['prediction']['reasoning']}")
    print(f"Comprehensive Summary: {result['comprehensive_summary']}")
    print(f"Number of evidence pieces: {len(result['evidence_texts'])}")
    
    # Show bolded text examples
    if result['evidence_texts_bolded']:
        for i, text in enumerate(result['evidence_texts_bolded']):
            print(f"\nExample evidence with bolding: {text}")
            print(f"Explanation: {result['evidence_texts'][i]['explanation']}")
    
    if result['evidence_relevance']:
        print(f"Evidence Relevance: {result['evidence_relevance']['relevance_score']}")
        print(f"Evidence Depth: {result['evidence_relevance']['depth_score']}")
        print(f"Opinion vs. Experience: {result['evidence_relevance']['opinion_vs_experiences']}")
    
    return result

def test_individual_functions():
    """Test individual functions with example data"""
    
    generator = RecommendationPredictionGenerator()
    
    # Example data
    transcript = "Utterance 1: I think minimum wage should be higher. Utterance 2: I worked at a restaurant for 5 years."
    rec_text = "The federal minimum wage should be raised to $30 an hour."
    display_name = "John Doe"
    
    print("Testing individual functions...")
    
    # Test prediction
    prediction = generator.get_rec_prediction(transcript, rec_text, display_name)
    print(f"Prediction: {prediction}")
    
    # Test evidence extraction
    evidence = generator.get_rec_evidence(transcript, prediction['reasoning'], rec_text)
    print(f"Evidence: {evidence}")
    
    # Test evidence relevance
    evidence_relevance = generator.get_exp_relevance("I worked at a restaurant for 5 years.", rec_text)
    print(f"Evidence Relevance: {evidence_relevance}")
    
    # Test evidence summary
    evidence_summary = generator.get_exp_summary("I worked at a restaurant for 5 years.")
    print(f"Evidence Summary: {evidence_summary}")
    
    # Test comprehensive summary
    comprehensive_summary = generator.get_op_exp_summary(
        "I worked at a restaurant for 5 years.", 
        "", 
        rec_text
    )
    print(f"Comprehensive Summary: {comprehensive_summary}")

if __name__ == "__main__":
    # Example usage:
    
    # Update only relevance scores
    results = update_relevance_scores_only()
    
    # Or run for all participants (full re-processing)
    # results = run_rec_predictions()

    
    # Or run for a single participant-recommendation combination
    # result = run_single_participant_recommendation("5a198755f2e3460001edc5c9", "Companies should strongly prioritize hiring local workers instead of hiring foreign workers.", "John Doe")
    # ID with highly relevant experiences: 65eac68e5e28cd9f0261c326, 66ad6f2765f2ef7122225388 for the local vs foreign worker recommendation
    # ID with medium: 5a198755f2e3460001edc5c9

    # Or test individual functions
    # test_individual_functions()
    #print(result)
    print("Recommendation prediction script ready!")
    print("Uncomment the desired function call above to run.") 