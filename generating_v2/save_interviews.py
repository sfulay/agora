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
from pages.models import Interview
import pandas as pd
from django.db import transaction
import random

# %%
users = pd.read_csv("data/all_df_clean_pass_concept_measures_joined.csv")
users_filt = users[users["assignment"].isin(["treatment", "control"])]
users_filt.to_csv("data/interview_users.csv", index=False)
users_filt = users_filt["PROLIFIC_PID"].tolist()
users_filt = list(set(users_filt))
users_filt
#%%
interviews = Interview.objects.filter(participant__prolific_id__in=users_filt)

interview_dict = {}
for interview in interviews:
    interview_dict[interview.participant.prolific_id] = interview.get_full_conversation()

interview_dict


# %%
# Save interview_dict to JSON file
output_file = "data/interviews.json"
with open(output_file, 'w') as f:
    json.dump(interview_dict, f, indent=2)

print(f"Saved {len(interview_dict)} interviews to {output_file}")

# %%
users
# %%
