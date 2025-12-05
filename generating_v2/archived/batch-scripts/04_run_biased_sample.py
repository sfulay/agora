#%%
import os
import numpy
import openai 
import json
import pandas as pd
os.getcwd()
prompt_template_file = "generate_recs_climate"
prompt_dir = f"interviewer_agent/prompt_template/prompts"

setting = "local"
if setting == "production":
    %cd /var/app/current
else: 
    %cd ../
%pwd 

os.environ['DJANGO_SETTINGS_MODULE'] = f'gabm_infra.settings.{setting}'
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = "true"

import django
django.setup()
from pages.models import Recommendation
from pages.models import RecommendationParticipantSummary
from pages.models import Participant
import pandas as pd
from django.db import transaction
import random
#%%
import numpy as np
from scipy.optimize import minimize

def optimize_weights_with_target_mean( support, target_mean):
    support = np.array(support)
    n = len(support)
    w_uniform = 1 / n

    # Initial guess: uniform weights
    initial_weights = np.ones(n) / n

    # Objective: minimize variance in weights (L2 distance from uniform)
    def objective(w):
        return np.sum((w - w_uniform) ** 2)

    # Constraints:
    constraints = [
        {'type': 'eq', 'fun': lambda w: np.sum(w) - 1},  # weights sum to 1
        {'type': 'eq', 'fun': lambda w: np.dot(w, support) - target_mean}  # weighted mean = target_mean
    ]

    # Bounds: weights must be between 0 and 1
    bounds = [(0, 1) for _ in range(n)]

    # Solve optimization
    result = minimize(objective, initial_weights, bounds=bounds, constraints=constraints)

    if result.success:
        weights = result.x
        # print("✅ Optimized Weights:", np.round(weights, 4))
        # print("Weighted Mean:", np.dot(weights, support))
        # print("Variance in weights:", np.var(weights))
        return weights
    else:
        raise RuntimeError("Optimization failed:", result.message)
# %%
def populate_profile_selections(rec_ids, participant_usernames, sample_sizes_dict):
    """
    Populate pro_profiles_selected and against_profiles_selected fields based on sampling requirements:
    - pro_profiles_selected: 70% from predicted_agreement > 50, 30% from predicted_agreement < 50
    - against_profiles_selected: 30% from predicted_agreement > 50, 70% from predicted_agreement < 50
    """
    
    # Get all relevant summaries
    rec_summaries = RecommendationParticipantSummary.objects.filter(
        recommendation__id__in=rec_ids, 
        participant__username__in=participant_usernames
    )
    
    print(f"Found {rec_summaries.count()} total summaries")
    
    # Reset all selections to False first
    rec_summaries.update(pro_profiles_selected=False, against_profiles_selected=False)
    
    # Group summaries by recommendation
    for rec_id in rec_ids:
        print(f"Processing recommendat ion {rec_id}")
        rec_summaries_single = rec_summaries.filter(recommendation_id=rec_id)
        supports = rec_summaries_single.values_list('predicted_agreement', flat=True)
        supports = [s for s in supports if s is not None]
        for for_against in ["for", "against"]:
            target_mean = 75 if for_against == "for" else 25
            weights = optimize_weights_with_target_mean(supports, target_mean)
            # Sample rec_summaries_for_rec according to weights
            rec_summaries_list = list(rec_summaries_single)
            #rec_summaries_qual_index = [i for i, s in enumerate(rec_summaries_list) if s.quality_score is not None and s.quality_score >= 70]
            #print(rec_summaries_qual_index)
            weights = np.array(weights)
            weights = weights / weights.sum()
            sample_size = sample_sizes_dict[rec_id]
            sampled_indices = np.random.choice(
                len(rec_summaries_list), 
                size=sample_size, 
                replace=False, 
                p=weights
            )
            #print(f"Sampled indices: {sampled_indices}")
            for i in sampled_indices:
                # if i in rec_summaries_qual_index:
                #   # print(f"Selected quality profile {i} for recommendation {rec_id}")
                #     rec_summaries_list[i].pro_profiles_selected = True
                #     rec_summaries_list[i].against_profiles_selected = True
                #     rec_summaries_list[i].save()
                #     sampled_indices = np.append(sampled_indices, i)
                # else:
                if for_against == "for":
                    rec_summaries_list[i].pro_profiles_selected = True
                    rec_summaries_list[i].save()
                else:
                    rec_summaries_list[i].against_profiles_selected = True
                    rec_summaries_list[i].save()
            
            selected_profiles = [rec_summaries_list[i] for i in sampled_indices]
            mean_predicted_agreement = np.mean([s.predicted_agreement for s in selected_profiles if s.predicted_agreement is not None])
            print(f"Mean predicted_agreement of selected {for_against} profiles: {mean_predicted_agreement}")
#%%

#%%


# %%
# Make buckets of predicted support: low, medium, and high
def bucket_predicted_support(support):
    if support is None:
        return "unknown"
    if support < 33:
        return "low"
    elif support < 66:
        return "medium"
    else:
        return "high"
def sample_profiles_by_support(rec_id, participant_usernames):
    rec_summaries_single = RecommendationParticipantSummary.objects.filter(
        recommendation__id=rec_id, 
        quality_score__gte=70,
        participant__username__in=participant_usernames
    )
    rec_summaries_single_df = pd.DataFrame(rec_summaries_single.values())

    rec_summaries_single_df["support_bucket"] = rec_summaries_single_df["predicted_agreement"].apply(bucket_predicted_support)
    # Group by support_bucket and sample at most 10 from each bucket
    sampled_dfs = []
    for bucket, group in rec_summaries_single_df.groupby("support_bucket"):
        if len(group) > 10:
            sampled_group = group.sample(n=10, random_state=42)
        else:
            sampled_group = group
        sampled_dfs.append(sampled_group)
    rec_summaries_sampled = pd.concat(sampled_dfs, ignore_index=True)
    print("Rec id: ", rec_id)
    print(rec_summaries_sampled["support_bucket"].value_counts())
    for id in rec_summaries_sampled["id"].unique():
        single_rec_summary = RecommendationParticipantSummary.objects.get(id=id)
        single_rec_summary.pro_profiles_selected = True
        single_rec_summary.against_profiles_selected = True
        single_rec_summary.save()

    return rec_summaries_sampled
# %%
sample_sizes_dict = {74:70, 75:60, 76: 50}
participant_usernames = pd.read_csv("data/participant_data_clean.csv")["prolific_id"].tolist()
# populate_profile_selections([74, 75, 76], participant_usernames, sample_sizes_dict)
# for rec_id in [74, 75, 76]:
#     sample_profiles_by_support(rec_id, participant_usernames)
# %%

from pages.models import RecommendationParticipantSummary
from pages.models import Recommendation
from pages.models import Participant

participant_usernames = pd.read_csv("data/participant_data_clean.csv")["prolific_id"].tolist()
all_rec_summaries = RecommendationParticipantSummary.objects.filter(
    recommendation__id__in=[74, 75, 76],
    participant__username__in=participant_usernames
)
all_rec_summaries_df = pd.DataFrame(all_rec_summaries.values())
all_rec_summaries_df["support_bucket"] = all_rec_summaries_df["predicted_agreement"].apply(bucket_predicted_support)
for rec_id in [74, 75, 76]:
    for pro_or_against in ["pro", "against"]:
        print(f"Recommendation {rec_id}, {pro_or_against} profiles selected:")
        rec_text = Recommendation.objects.get(id=rec_id).rec_text
        print(f"Recommendation text: {rec_text}")
        rec_summaries_single = all_rec_summaries_df.query(f"recommendation_id == {rec_id} and {pro_or_against}_profiles_selected == True")
        print(f"Recommendation {rec_id}, {pro_or_against} profiles selected: {len(rec_summaries_single)}")
       # print(rec_summaries_single["support_bucket"].value_counts())
        print(rec_summaries_single["predicted_agreement"].mean())
    
# %%# %%
shown = all_rec_summaries_df[(all_rec_summaries_df.pro_profiles_selected == True) | (all_rec_summaries_df.against_profiles_selected == True) & (all_rec_summaries_df.quality_score >= 70)]
len(shown.participant_id.unique())
# %%
shown.participant_id.unique()
# %%
[username for username in Participant.objects.filter(id__in=shown.participant_id.unique()).values_list('username', flat=True)]


# %%
