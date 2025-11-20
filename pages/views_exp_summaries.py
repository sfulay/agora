#%%
import os
import numpy
import openai 
import json
import pandas as pd
from collections import defaultdict

PARTICIPANT_USERNAMES = ["janus", "suyash2", "marinar", "emily_kubin", "prerna_2", "bcroy", "dougb", "maya_d", "michielb"]
os.getcwd()
prompt_template_file = "generate_recs_climate"
prompt_dir = f"interviewer_agent/prompt_template/prompts"
# #%%
# setting = "local"
# if setting == "production":
#     %cd /var/app/current
# else: 
#     %cd ../
# %pwd 
# os.environ['DJANGO_SETTINGS_MODULE'] = f'gabm_infra.settings.{setting}'
# os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = "true"

# #%%
# import django
# django.setup()

from pages.models import Interview
from pages.models import InterviewQuestion
from pages.models import InterviewAudio
from pages.models import InterviewUtterance
from pages.models import Recommendation
from pages.models import RecommendationParticipantSummary
from pages.models import Participant


#%%
def call_gpt(prompt):
    response = openai.chat.completions.create(
        model="gpt-4.1", 
        messages=[
            {"role": "system", "content": "You are a helpful assistant that predicts how much a participant would agree with a specific recommendation, based on their prior statements and experiences."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

def generate_prompt(transcript, rec_text, name): 
    prompt = f"""
        You are an assistant that analyzes participant transcripts to predict how much a participant would agree with a specific recommendation, based on their prior statements and experiences.

        Your task is to return a JSON object that includes:
        1. A brief explanation (max 100 words) of why the participant would agree or disagree with the recommendation.
        2. A predicted agreement level (0–100), where 0 means total disagreement and 100 means complete agreement.
        3. A confidence score (0–100) reflecting how confident you are in your prediction.
        4. A relevance score (0-100) reflecting how relevant this person's experience is to the recommendation. Only give a high score if there are direct opinions or experiences that are relevant to the recommendation, either in favor or against the recommendation.
        5. A summary of how the participants' experience relate to the recommendation.
        6. The ID of the single utterance from the transcript that best supports your prediction.

        Here is the transcript for participant **{name}**:
        {transcript}

        Here is the recommendation:
        "{rec_text}"

        Return only a valid JSON object in the following format:
        {{
            "reasoning": "Your explanation here (max 100 words)",
            "predicted_agreement": <integer between 0 and 100>, 
            "confidence_score": <integer between 0 and 100>,
            "relevance_score": <integer between 0 and 100>,
            "summary": "Your summary here (max 100 words)",
            "best_utterance_id": <integer>
        }}
"""
    return prompt
def get_rec_summary(participant, transcript, recommendation):
    prompt = generate_prompt(transcript, recommendation.rec_text, participant.username)
    print("PROMPT:")
    print(prompt)
    response = call_gpt(prompt)
    print("RESPONSE:")
    print(response)
    return response

def write_rec_summaries(participant, transcript, recommendation):
    try:
        rec_summary = get_rec_summary(participant, transcript, recommendation)
        rec_summary["username"] = participant.username
        rec_summary["rec_text"] = recommendation.rec_text
    except Exception as e:
        print("Error getting rec summary for", participant.username, "and", recommendation.rec_text)
        return None
    
    try:
        best_utterance = InterviewUtterance.objects.get(id=int(rec_summary['best_utterance_id']))
    except Exception as e:
        print("Error getting best utterance for", participant.username, "and", recommendation.rec_text)
        best_utterance = None
        
    recommendation_summary = RecommendationParticipantSummary.objects.create(
        recommendation=recommendation,
        participant=participant,
        predicted_agreement=rec_summary['predicted_agreement'],
        confidence_score=rec_summary['confidence_score'],
        reasoning=rec_summary['reasoning'],
        relevance_score=rec_summary['relevance_score'], 
        summary=rec_summary['summary'],
        best_utterance = best_utterance
    )
    return recommendation_summary

#%%

def collect_transcripts():
    all_interview_utterances = InterviewUtterance.objects.select_related(
        'question__interview__participant'
    ).filter(
        question__interview__participant__username__in=PARTICIPANT_USERNAMES,
        question__interview__script_v="minwage_script_v2"
    ).order_by('question__interview', 'created')

    # Group by interview
    interview_transcripts = defaultdict(list)
    for utt in all_interview_utterances:
        participant = utt.question.interview.participant
        interview_transcripts[participant].append(utt.get_utterance_id())

    # Now, for each interview, join the utterances into a full transcript
    full_transcripts = {
        participant: "\n".join(utterances)
        for participant, utterances in interview_transcripts.items()
    }
    return full_transcripts
#%%

def generate_new_predictions(rec_text):
    recommendation_obj = Recommendation.objects.create(
                rec_text=rec_text
            )
    full_transcripts = collect_transcripts()
    for participant, transcript in full_transcripts.items():
        try:
            write_rec_summaries(participant, transcript, recommendation_obj)
        except Exception as e:
            print("Error writing rec summary for", participant.username, "and", recommendation_obj.rec_text)
            print(e)
            continue
    return recommendation_obj
# %%
def get_participant_transcript(participant):
    interview = Interview.objects.filter(participant=participant, completed=True).order_by('-created').first()
    if not interview:
        return ""
    utterances = InterviewUtterance.objects.filter(question__interview=interview, is_interviewer=False).order_by('question__global_question_id', 'sequence_number')
    transcript = "\n".join([utt.utterance_text for utt in utterances])
    return transcript

def get_participant_prediction_helper(participant_username, recommendation_obj):
    participant = Participant.objects.get(username=participant_username)
    transcript = get_participant_transcript(participant)
    rec_summary = write_rec_summaries(participant, transcript, recommendation_obj)
    return rec_summary
# %%
