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
# %%
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
    Participant,
    Interview
)
# %%
treatment_assignment = pd.read_csv("data/treatment_assignments/treatment_control_assignment.csv")
participant_data = pd.read_csv("data/all_df_clean_pass_concept_measures_joined.csv")
participant_data = participant_data[participant_data["assignment"].isin(["treatment", "control"])]
# %%
ids = participant_data["PROLIFIC_PID"].tolist()
# %%
len(ids)
ids_with_interviews = sorted(list(Interview.objects.filter(participant__prolific_id__in=ids).values_list('id', flat=True)))
len(ids_with_interviews)
#%%
rec_id = 74
recommendation = Recommendation.objects.get(id=rec_id)
recommendation.rec_text
# %%
df_high_support = pd.DataFrame(RecommendationParticipantSummary.objects.filter(participant__username__in=ids,
 recommendation__id=74, quality_score__gt=80, predicted_agreement__gt=80).prefetch_related('participant').values())
df_low_support = pd.DataFrame(RecommendationParticipantSummary.objects.filter(participant__username__in=ids,
 recommendation__id=74, quality_score__gt=60, predicted_agreement__lt=80).prefetch_related('participant').values())

prolific_ids = pd.DataFrame(Participant.objects.filter(username__in=ids).values()).filter(["id", "prolific_id"])
print(len(df_high_support))
print(df_high_support["predicted_agreement"].mean())
print(len(df_low_support))
print(df_low_support["predicted_agreement"].mean())
combined_df = pd.concat([df_high_support, df_low_support])
combined_df = combined_df.merge(prolific_ids, left_on="participant_id", right_on="id", how="left")
combined_df.to_csv("data/habermas_participants.csv", index=False)
# %%
import matplotlib.pyplot as plt
print(combined_df["predicted_agreement"].mean())
print(len(combined_df))
plt.hist(combined_df["predicted_agreement"])


# %%
combined_df['prolific_id'].unique()

# %%
