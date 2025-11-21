import os
import re
import json
import time
import base64
import io
import random
import string
import zipfile
import csv
import math
import random
from django.db.models import OuterRef, Subquery
from django.contrib.staticfiles.storage import staticfiles_storage
from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, StreamingHttpResponse
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.conf import settings
from django.templatetags.static import static
from django.core.files.storage import default_storage
from django.contrib import messages
from django.db.models import F, Value, IntegerField, Case, When
from django.db import transaction
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
    
    # Render the modal content template
from django.template.loader import render_to_string
from django.template import RequestContext
import random

import openai
from interviewer_agent.interviewer_utils.settings import get_open_api_keyset
from global_methods import *
from datetime import datetime, timedelta
from django.utils import timezone
from io import BytesIO
from PIL import Image, ImageSequence
from pydub import AudioSegment
from allauth.account.signals import user_logged_in, user_signed_up
from interviewer_agent.interviewer_utils.settings import *
from interviewer_agent.agent_modules.vocalize import *
from interviewer_agent.agent_modules.transcribe import *

from .forms import *
from .models import *
from .interview_settings import *


from allauth.account.signals import user_signed_up
from django.dispatch import receiver

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from pages.views_exp_summaries import *

# Cache for TF-IDF vectors to avoid recomputing
tfidf_cache = {
    'vectorizer': None,
    'vectors': None,
    'clip_ids': None
}

def controlled_randomness(weight):
  """
  Returns True or False based on the given weight.
  
  Parameters:
  - weight (float): A float value between 0 and 1 inclusive, where 0 means 
                    the function returns False 100% of the time,
                    1 means it returns True 100% of the time, and 0.5 means 
                    a 50% chance of True or False.
                    
  Returns:
  - bool: True or False based on the input weight.
  """
  # Check if the weight is at the boundaries
  if weight <= 0:
    return False
  elif weight >= 1:
    return True
  
  # Generate a random float between 0 and 1 and compare with the weight
  return random.random() < weight

def generate_random_string(n):
  return ''.join(random.choice('AB') for _ in range(n))

@receiver(user_signed_up)
def user_signed_up_request(sender, **kwargs):
  user = kwargs.pop('user')
  request = kwargs.pop('request')
  # Your custom logic here
  print(f"User {user.username} signed up.")
  # # For example, initializing user profile or setting default preferences.
  # if controlled_randomness(behavioral_study_activation_rate): 
  #   behs_module = BehavioralStudyModule.objects.create()
  #   behs_module.initialize()
  #   behs_module.save()
  #   user.behavioral_activated = True
  #   user.behavioral_module = behs_module
  #   user.save()

  user.camerer_activated = generate_random_string(5)
  user.save()

def jsp_log(message): 
  from datetime import datetime
  formatted_time = datetime.now().strftime("%H:%M:%S")
  print (f'[views.py] {formatted_time} -- {message}')


def generate_random_alphanumeric(length):
  # Combining letters and digits
  characters = string.ascii_letters + string.digits
  # Generating a random string of the given length
  random_string = ''.join(random.choice(characters) for i in range(length))
  return random_string


def extract_base_url(url):
    """
    Extract a specific substring from a URL.

    Args:
    url (str): The URL string.

    Returns:
    str: The extracted substring.
    """
    # Find the position of "/static/" and the start of the query string
    static_pos = url.find('/static/')
    query_start = url.find('?')

    # Extract the substring
    if static_pos != -1 and query_start != -1:
        return url[static_pos + len('/static/'):query_start]
    elif static_pos != -1:
        return url[static_pos + len('/static/'):]
    else:
        return "Invalid URL format"


def replace_file_num(url: str, new_num: int) -> str:
    """
    Replaces the number in the file path segment /5/ with a new number.

    Args:
    url (str): The original file path.
    new_num (int): The new number to replace with.

    Returns:
    str: The modified file path with the replaced number.
    """
    # Using regex to replace the number
    modified_url = re.sub(r'(\d+)(?=/\d{2}[A-Za-z]+/\d+\.)', 
                          str(new_num), url, 1)
    return modified_url


def get_curr_module(curr_user, list_completed_modules): 
  curr_ordered_modules = ordered_modules
  if curr_user.behavioral_activated: 
    curr_ordered_modules = ordered_modules_behavioral
  if curr_user.camerer_activated != "": 
    curr_ordered_modules = fin_ordered_modules

  for m in curr_ordered_modules: 
    if m not in list_completed_modules: 
      return m
  else: 
    return None


def home(request, det=None):
  if not request.user.is_authenticated:
    context = {}
    template = "pages/home/landing.html"
    return render(request, template, context)

  completed_modules = request.user.get_completed_modules()
  curr_module = get_curr_module(request.user, completed_modules)

  started_interviews = Interview.objects.filter(participant=request.user)
  started_interviews_scripts = [i.script_v for i in started_interviews]

  curr_timer = TimeoutTimer.objects.filter(participant=request.user)
  if curr_timer: 
    curr_timer = curr_timer[0]
  else: 
    curr_timer = None

  context = {"consent_form": ConsentForm(),
             "completed_modules": completed_modules,
             "curr_module": curr_module,
             "started_interviews_scripts": started_interviews_scripts,
             "curr_timer": curr_timer,
             "pilot": settings.PILOT,
             "phase_2_only": settings.PHASE_2_ONLY,
             "show_avatars": settings.SHOW_AVATARS}
  
  template = "pages/home/home.html"
  return render(request, template, context)


def create_avatar(request):
  if not request.user.is_authenticated:
    context = {}
    template = "pages/home/landing.html"
    return render(request, template, context)

  image_paths = {
    'base': [static(f'gabm/img/pipoya-sprites/5/00Skin/{i+1}.png') 
             for i in range(4)],
    'clothes': [static(f'gabm/img/pipoya-sprites/5/01Costume/{i+1}.png') 
                for i in range(46)],
    'eyes': [static(f'gabm/img/pipoya-sprites/5/02Eye/{i+1}.png') 
             for i in range(23)],
    'hair': [static(f'gabm/img/pipoya-sprites/5/03Hair/{i+1}.png') 
             for i in range(34)],
    'hat': [static(f'gabm/img/pipoya-sprites/5/05Hat/{i+1}.png') 
            for i in range(15)],
    'glasses': [static(f'gabm/img/pipoya-sprites/5/06Glasses/{i+1}.png') 
                for i in range(11)],
    'beard': [static(f'gabm/img/pipoya-sprites/5/09Beard/{i+1}.png') 
              for i in range(5)]}

  image_paths_all = dict()
  for key, frame_five_aws_paths in image_paths.items(): 
    for frame_five_aws_path in frame_five_aws_paths: 
      image_paths_all[frame_five_aws_path] = dict()
      for frame in range(1, 13): 
        base_url = extract_base_url(frame_five_aws_path)
        replace_file_num(base_url, frame)      
        image_paths_all[frame_five_aws_path][str(frame)] = static(
          f'{replace_file_num(base_url, frame)}')

  context = {"curr_user": request.user,
             'image_paths': image_paths,
             'image_paths_all': image_paths_all,
             'empty_path': static(f'gabm/img/pipoya-sprites/5/empty.png') }
  template = "pages/create_avatar/create_avatar.html"
  return render(request, template, context)


def interview(request, script_v):
  if not request.user.is_authenticated:
    context = {}
    template = "pages/home/landing.html"
    return render(request, template, context)

  try: 
    interview = Interview.objects.get(participant=request.user,  
                                      script_v=script_v)
    interview.completed_sec = interview.completed_module_sec
    interview.completed_question_sec = interview.completed_module_sec
    interview.save()
  except: 
    interview = None

  interview_completed = False 
  if not interview:
    interview_completed = True
  else: 
    if interview.completed: 
      interview_completed = interview.completed

  context = {"interview_completed": interview_completed,
             "interviewer_turn": None, 
             "interviewer_utt": None,
             "curr_module": None,
             "script_v": script_v,
             "user_avatar": request.user.avatar}

  template = "pages/interview/interview.html"
  return render(request, template, context)


def summary(request):
  if not request.user.is_authenticated:
    context = {}
    template = "pages/home/landing.html"
    return render(request, template, context)

  all_interviews = Interview.objects.all().order_by("-created")

  context = {"curr_user": request.user, 
             "all_interviews": all_interviews}
  template = "pages/summary/summary.html"
  return render(request, template, context)


def summary_unprocessed_v1(request):
  if not request.user.is_authenticated:
    context = {}
    template = "pages/home/landing.html"
    return render(request, template, context)

  all_interviews = Interview.objects.filter(completed_sec=2709).filter(zipped_main=False).order_by("-created")

  context = {"curr_user": request.user, 
             "all_interviews": all_interviews}
  template = "pages/summary/summary.html"
  return render(request, template, context)


def download_p_data(request, participant_username, script_v): 
  if not request.user.is_authenticated:
    context = {}
    template = "pages/home/landing.html"
    return render(request, template, context)

  # Loading the current user and preparing the context to return.
  curr_user = Participant.objects.get(username=participant_username)
  try: 
    curr_interview = Interview.objects.get(participant=curr_user,
                                            script_v=script_v)
    curr_interview.zipped_main = True
    curr_interview.save()
  except: 
    curr_interview = None

  if not curr_interview:
    context = {}
    template = "pages/home/content.html"
    return render(request, template, context)

  qs = (InterviewQuestion.objects.filter(interview=curr_interview)
                                 .order_by('global_question_id'))
  transcript = ""
  for q in qs: 
    transcript += q.convo + "\n"

  meta = {"user_name": participant_username, 
          "email": curr_user.email, 
          "script_v": script_v, 
          "prolific_id": curr_user.prolific_id    ,
          "completed_modules": curr_user.completed_modules,
          "camerer_activated": curr_user.camerer_activated, 
          "created": curr_user.created,
          "audio_calibration_float": curr_user.audio_calibration_float}
  meta['created'] = meta['created'].isoformat()

  # Create a byte stream to hold the ZIP file
  in_memory_zip = io.BytesIO()

  # Create a ZIP file
  with zipfile.ZipFile(in_memory_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr('interview.txt', transcript)
    # Convert the Python dictionary to a JSON string
    json_str = json.dumps(meta, indent=4)  # Use `indent` for pretty printing
    # Write the JSON string to a text file in the ZIP
    zf.writestr('meta.json', json_str)

  # Prepare the response, setting Content-Type and Content-Disposition
  # headers to trigger a file download
  response = HttpResponse(in_memory_zip.getvalue(), content_type='application/zip')
  response['Content-Disposition'] = f'attachment; filename="{participant_username}.zip"'
  # Make sure to seek to the start of the stream
  in_memory_zip.seek(0)

  return response


def download_p_audio_data(request, participant_username, script_v): 
  if not request.user.is_authenticated:
      context = {}
      template = "pages/home/landing.html"
      return render(request, template, context)

  # Loading the current user and preparing the context to return.
  curr_user = Participant.objects.get(username=participant_username)
  try: 
      curr_interview = Interview.objects.get(participant=curr_user, script_v=script_v)
      curr_interview.zipped_audio = True
      curr_interview.save()
  except: 
      curr_interview = None

  if not curr_interview:
      return summary(request)

  qs = InterviewQuestion.objects.filter(interview=curr_interview).order_by('global_question_id')
  audio_file_names = []
  for q in qs: 
      x = InterviewAudio.objects.filter(question=q).order_by("created")
      for i in x: 
          audio_file_names.append(i.audio_file.name)

  if not audio_file_names or len(audio_file_names) == 0:
      return HttpResponse("No audio files provided", status=400)

  # Convert the list of audio file names to JSON format
  json_content = json.dumps({'audio_files': audio_file_names})

  # Create a response with appropriate headers to prompt a file download
  response = HttpResponse(json_content, content_type='application/json')
  response['Content-Disposition'] = f'attachment; filename="{curr_user.email}.json"'
  
  return response



def cleanup_interview(interview):
  new_interview = ""
  interview = interview.split("\n\n")

  for i_count, module in enumerate(interview): 
    module = module.split("\n")

    if module: 
      if module[-1][:len("Interviewer: Thank you")].lower() == "Interviewer: Thank you".lower(): 
        module = module[:-1]

    module = "\n".join(module)

    if module: 
      new_interview += module.strip() + "\n\n"

  return new_interview


def transcript(request, participant_username, script_v):
    if not request.user.is_authenticated:
        context = {}
        template = "pages/home/landing.html"
        return render(request, template, context)

    # Loading the current user and preparing the context to return.
    curr_user = Participant.objects.get(username=participant_username)
    try: 
        curr_interview = Interview.objects.get(participant=curr_user,
                                            script_v=script_v)
    except: 
        curr_interview = None

    if not curr_interview:
        context = {}
        template = "pages/home/content.html"
        return render(request, template, context)

    # Get all questions for this interview, ordered by global_question_id
    questions = (InterviewQuestion.objects.filter(interview=curr_interview)
                                    .order_by('global_question_id'))
    # Debug output
    for question in questions:
        print(f"Question {question.global_question_id}:")
        for utterance in question.utterances.all():
            print(f"  - is_interviewer: {utterance.is_interviewer}, text: {utterance.utterance_text[:50]}...")
# views.py
    for question in questions:
        question.has_non_interviewer = any(not u.is_interviewer for u in question.utterances.all())

    context = {"curr_user": curr_user,
             "curr_interview": curr_interview, 
             "questions": questions,
             "script_v": script_v}
    template = "pages/transcript/transcript_edit.html"
    return render(request, template, context)


def login(request):
  return redirect('account_login')


def handler_calibration(request):
  if request.method == 'POST':
    curr_user = request.user
    calibration_float = float(request.POST.get('audioCalibrationFloat'))
    curr_user.audio_calibration_float = calibration_float
    curr_user.save()
    script_v = str(request.POST.get('script_v')).strip()
    return redirect('interview', script_v)  
  return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

def handler_consent(request):
  if request.method == 'POST':
    form = ConsentForm(request.POST)
    if form.is_valid():
      #participant_id = form.cleaned_data['participant_id']
      curr_user = request.user
      #curr_user.prolific_id = participant_id
      curr_user.module_completed("Consent")
      curr_user.save()
      return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
  else:
    form = ConsentForm()
  return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


def handler_upload_spritesheet(request):
  if request.method == 'POST':
    form = SpriteSheetForm(request.POST, request.FILES)

    if form.is_valid():
      curr_user = request.user
      if not curr_user.avatar: 
        curr_user.avatar = Avatar.objects.create()

      # Save spritesheet
      spritesheet_image = form.cleaned_data.get('spritesheet')
      curr_filename = f"avatar{curr_user.avatar.id}/spritesheet.png"
      curr_user.avatar.sprite_sheet.save(curr_filename, 
        spritesheet_image, save=True)

      # Save front png
      curr_png = form.cleaned_data.get('front')
      curr_filename = f"avatar{curr_user.avatar.id}/front.png"
      curr_user.avatar.front_static.save(curr_filename, curr_png, save=True)

      # Save gifs
      curr_gif = form.cleaned_data.get('right_gif')
      curr_filename = f"avatar{curr_user.avatar.id}/right_gif.gif"
      curr_user.avatar.right_gif.save(curr_filename, curr_gif, save=True)

      curr_gif = form.cleaned_data.get('left_gif')
      curr_filename = f"avatar{curr_user.avatar.id}/left_gif.gif"
      curr_user.avatar.left_gif.save(curr_filename, curr_gif, save=True)

      curr_gif = form.cleaned_data.get('front_gif')
      curr_filename = f"avatar{curr_user.avatar.id}/front_gif.gif"
      curr_user.avatar.front_gif.save(curr_filename, curr_gif, save=True)

      curr_gif = form.cleaned_data.get('back_gif')
      curr_filename = f"avatar{curr_user.avatar.id}/back_gif.gif"
      curr_user.avatar.back_gif.save(curr_filename, curr_gif, save=True)

      # Finish
      curr_user.module_completed("Avatar")
      curr_user.save()


  return home(request)
  

def handler_take_one_step(request): 
  if not request.user.is_authenticated:
    context = {}
    template = "pages/home/landing.html"
    return render(request, template, context)
  if request.method != 'POST':
    return JsonResponse({})

  jsp_log(f"Starting handler_take_one_step -- step 1: load var")

  # Convert the string to JSON (Python dictionary). This is what is retrieved
  # from the frontend. 
  # Note that curr_POST_body is a dictionary of the following form: 
  # var newData = {
  #               started: false, 
  #               user_utt: null, 
  #               script_v: "{{script_v}}", 
  #               mime_type: null
  #             };
  # where started is only True for the very first signal of the session
  # (important: not of the interview, but of the currently connected currently
  #  -- this is used for hading the reloading of the page), and where user_utt
  # is the user's response in audio form. 
  curr_POST_body = json.loads(request.body.decode('utf-8'))

  curr_script_path = f"{INTERVIEW_AGENT_PATH}/interview_script/"
  curr_script_path += curr_POST_body["script_v"]
  interview_meta = read_json_file(f"{curr_script_path}/meta.json")
  try: 
    curr_interview = Interview.objects.get(
                       participant=request.user,
                       script_v=curr_POST_body["script_v"])
  except: 
    # If not curr_interview, this means we need to create the Interview
    # objcet for the participant. So we do that here. 
    curr_interview = Interview.objects.create(
      participant=request.user,
      script_v=curr_POST_body["script_v"],
      interviewer_summary=json.dumps(interview_meta["interviewer_summary"]), 
      module_count=interview_meta["module_count"],
      p_notes="{ }",
      pruned_p_notes="{ }",
      optional_key_phrases=f"My name is {request.user.get_full_name()}.")

  jsp_log(f"Starting handler_take_one_step -- step 2: start process_one_step")
  # [RUNNING THE MAIN ONE_STEP FUNCTION]
  step_packet = curr_interview.process_one_step(request.user,  
                                                curr_POST_body["started"],
                                                curr_POST_body["user_utt"],
                                                curr_POST_body["mime_type"],
                                                curr_POST_body["script_v"],
                                                interview_meta["total_sec"])

  jsp_log(f"Starting handler_take_one_step -- step 3: progress viz prep")
  progress_circle_rad = int(360 
    * (step_packet["completed_sec"]/interview_meta["total_sec"]))
  if progress_circle_rad > 360: progress_circle_rad = 360
  progress_circle_url = f"{settings.STATIC_URL}gabm/img/progress_arcs_thick/"
  progress_circle_url += f"{progress_circle_rad}.png"
  step_packet.update({"progress_circle_rad": progress_circle_rad,
                      "progress_circle_url": progress_circle_url})

  fin_percent = int(
    step_packet["completed_sec"]/interview_meta["total_sec"] * 90)
  if fin_percent == 0: fin_percent = 1
  step_packet.update({"fin_percent": fin_percent})

  jsp_log(f"Starting handler_take_one_step -- step 4: fin")
  # time.sleep(10)
  return JsonResponse(step_packet)


def handler_upload_surveycode(request):
  if request.method == 'POST':
    form = SurveyCodeForm(request.POST)
    if form.is_valid():
      code = form.cleaned_data['code']
      curr_user = request.user

      completed_modules = curr_user.get_completed_modules()
      curr_module = get_curr_module(curr_user, completed_modules)

      curr_round = 1
      if "Behavioral Study Pt.2" == curr_module: 
        curr_round = 2
      
      curr_behavioral_mod = curr_user.behavioral_module
      if curr_behavioral_mod.get_verify_code(code, curr_round): 
        curr_behavioral_mod.get_move_to_next_study(curr_round)

      if curr_behavioral_mod.get_check_if_fin(curr_round): 
        curr_user.module_completed(curr_module)
        
      curr_behavioral_mod.save()
      curr_user.save()
  return home(request)


def handler_upload_experiment_code(request): 
  if request.method == 'POST':
    form = ExperimentCodeForm(request.POST)
    if form.is_valid():
      code = form.cleaned_data['code']
      curr_user = request.user

      completed_modules = curr_user.get_completed_modules()
      curr_module = get_curr_module(curr_user, completed_modules)

      curr_round = 1
      if "Behavioral Study Pt.2" == curr_module: 
        curr_round = 2
      
      curr_behavioral_mod = curr_user.behavioral_module
      if curr_behavioral_mod.get_verify_code(code, curr_round): 
        curr_behavioral_mod.get_move_to_next_study(curr_round)

      if curr_behavioral_mod.get_check_if_fin(curr_round): 
        curr_user.module_completed(curr_module)
        
      curr_behavioral_mod.save()
      curr_user.save()
  return home(request)

def handler_phase_one_complete(request):
    if request.method == 'POST':
        if request.user.is_authenticated:
            request.user.module_completed("phase_one")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

def handler_download_summaries(request, starting_index, desired_count): 
  # Fetching the interviews
  all_interviews = list(Interview.objects.all().order_by("-created"))[int(starting_index):int(starting_index) + int(desired_count)]

  # Create an in-memory bytes buffer to store the zip file
  zip_buffer = io.BytesIO()



  # Create a zip file in the buffer
  with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
      for interview in all_interviews:
          interview_summary = interview.p_notes
          participant_email = interview.participant.email.lower()
          file_name = f"{participant_email}.txt"
          
          # Write each interview summary to a file within the zip
          zip_file.writestr(file_name, interview_summary)

  # Set the buffer position to the beginning
  zip_buffer.seek(0)

  # Serve the zip file as a downloadable response
  response = HttpResponse(zip_buffer, content_type='application/zip')
  response['Content-Disposition'] = 'attachment; filename=interview_summaries.zip'
  
  return response


def download_p_list_of_fin_interview(request): 
  if not request.user.is_authenticated:
    context = {}
    template = "pages/home/landing.html"
    return render(request, template, context)

  # Loading the current user and preparing the context to return.
  all_users = Participant.objects.all().order_by("created")

  rows = []
  for curr_user in all_users:
    curr_row = []
    try: 
      if "Survey Pt.1" in curr_user.get_completed_modules(): 
        curr_interview = Interview.objects.get(participant=curr_user, script_v="minwage_script_v2")
        if curr_interview.zipped_main: 
          curr_row += [curr_user.prolific_id,  curr_user.created, curr_user.get_curr_modules()]
          rows += [curr_row]

    except: 
      pass
      

  # Create a buffer
  buffer = io.StringIO()
  # Create a CSV writer
  writer = csv.writer(buffer)
  # Write data to buffer
  for row in rows:
      writer.writerow(row)
  # Seek to the start of the stream
  buffer.seek(0)
  
  # Create a response
  response = HttpResponse(buffer, content_type='text/csv')
  response['Content-Disposition'] = 'attachment; filename="participant_list.csv"'
  
  return response


def zipped_reset_check(request, participant_username, script_v): 
  if not request.user.is_authenticated:
      context = {}
      template = "pages/home/landing.html"
      return render(request, template, context)

  # Loading the current user and preparing the context to return.
  curr_user = Participant.objects.get(username=participant_username)
  try: 
      curr_interview = Interview.objects.get(participant=curr_user, script_v=script_v)
      curr_interview.zipped_audio = False
      curr_interview.zipped_main = False
      curr_interview.save()
  except: 
      curr_interview = None
  
  return summary(request)


def survey_visualization(request):
    if not request.user.is_authenticated:
        return redirect('home')
        
    context = {
        "user": request.user,
        # Add any other context data needed for visualization
    }
    template = "pages/survey/visualization.html"
    return render(request, template, context)


def view_recommendations(request):
    if not request.user.is_authenticated:
        return redirect('home')
        
    # Get all recommendations (not filtered by participant)
    recommendations = InterviewRecommendation.objects.all().order_by('-created_at')
    
    # Prefetch related participant support predictions to optimize queries
    recommendations = recommendations.prefetch_related('participantrecommendationsupport_set__interview__participant')
    
    context = {
        'recommendations': recommendations,
        'user': request.user
    }
    return render(request, 'pages/recommendations.html', context)


def check_participant(request, interview_id):
    """API endpoint to check if the current user is the participant of an interview"""
    if request.method == 'GET':
        try:
            # Get the interview
            interview = Interview.objects.get(id=interview_id)
            
            # Check if the current user is the participant
            is_participant = request.user.is_authenticated and request.user.id == interview.participant.id
            
            return JsonResponse({
                'is_participant': is_participant
            })
        except Interview.DoesNotExist:
            return JsonResponse({'error': 'Interview not found'}, status=404)
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)


def edit_transcript(request, participant_username, script_v):
    if not request.user.is_authenticated:
        context = {}
        template = "pages/home/landing.html"
        return render(request, template, context)

    # Loading the current user and preparing the context to return.
    curr_user = Participant.objects.get(username=participant_username)
    try: 
        curr_interview = Interview.objects.get(participant=curr_user,
                                            script_v=script_v)
    except: 
        curr_interview = None

    if not curr_interview:
        context = {}
        template = "pages/home/content.html"
        return render(request, template, context)

    if request.method == 'POST':
        try:
            # Parse the JSON data from the request
            data = json.loads(request.body)
            question_id = data.get('question_id')
            utterances = data.get('utterances', {})
            redactions = data.get('redactions', {})

            # Get the question
            question = InterviewQuestion.objects.get(id=question_id, interview=curr_interview)
            
            # Update each utterance
            for utterance_name, new_text in utterances.items():
                utterance_id = utterance_name.split('_')[1]
                utterance = InterviewUtterance.objects.get(id=utterance_id, question=question)
                if not utterance.is_interviewer:  # Only update interviewee utterances
                    utterance.utterance_text = new_text.strip()
                    # Update redaction status
                    redact_name = f"redact_{utterance_id}"
                    if redact_name in redactions:
                        utterance.is_redacted = redactions[redact_name]
                    utterance.save()

            # Update the question's convo field
            utterances = question.utterances.all().order_by('sequence_number')
            new_convo = ""
            for utt in utterances:
                speaker = "Interviewer" if utt.is_interviewer else "Interviewee"
                text = "[REDACTED]" if (not utt.is_interviewer and utt.is_redacted) else utt.utterance_text
                new_convo += f"{speaker}: {text}\n"
            question.convo = new_convo
            question.save()

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    # If not POST, redirect to transcript view
    return redirect('transcript', participant_username=participant_username, script_v=script_v)

def get_completion_details(request):
    """API endpoint to get completion code and link for the study"""
    if request.method == 'GET':
        # These would typically come from your settings or environment variables
        completion_code = "DELIB2024"  # Replace with your actual completion code
        completion_link = "https://www.mit.edu/" # Replace with your actual completion link
        
        return JsonResponse({
            'completion_code': completion_code,
            'completion_link': completion_link
        })
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)


def get_top_n_relevant_participants(recommendation_id, participant_summaries, quality_threshold, use_extremes, current_user=None):
    """
    Returns the top n most relevant RecommendationParticipantSummary objects for a given recommendation,
    ordered by relevance_score (descending), then samples one participant from each decile group
    (lowest third, middle third, top third) based on support_score.

    If relevance_threshold is not None, only includes summaries with relevance_score > threshold.
    If current_user is provided and use_extremes=False, uses similarity-based selection.
    """
    print("Getting most relevant")
    # Apply filter to participant_summaries
    summaries = participant_summaries.filter(**{
        'recommendation_id': recommendation_id,
        'quality_score__gt': quality_threshold if quality_threshold is not None else -9999
    })

    # Sort by predicted_agreement (ascending) - handle None values
    summaries_sorted_by_support = sorted(
        summaries,
        key=lambda s: (s.predicted_agreement if s.predicted_agreement is not None else -9999)
    )

    total = len(summaries_sorted_by_support)
    if total < 3:
        # Not enough for thirds, just return all participants
        return [summary.participant for summary in summaries_sorted_by_support]
    print(f"Total: {total}")
    
    if not use_extremes:
        # NEW: Use similarity-based selection if current_user is provided
        # if current_user is not None:
        #     print(f"Using similarity-based selection for user: {current_user.username}")
        #     similar_participants = get_similarity_based_participants(current_user, recommendation_id)
            
        #     if similar_participants:
        #         # Return participants from all buckets that have selections
        #         selected_participants = []
        #         for bucket_name, participant in similar_participants.items():
        #             selected_participants.append(participant)
        #         return selected_participants
        #     else:
        #         print("Similarity selection failed, falling back to random sampling")
        
        # Fallback to original random sampling behavior
        low_group = [s for s in summaries_sorted_by_support if (s.predicted_agreement if s.predicted_agreement is not None else -9999) < 33]
        mid_group = [s for s in summaries_sorted_by_support if 33 <= (s.predicted_agreement if s.predicted_agreement is not None else -9999) <= 66]
        high_group = [s for s in summaries_sorted_by_support if (s.predicted_agreement if s.predicted_agreement is not None else -9999) > 66]

        sampled = []
        if low_group:
            sampled.append(random.choice(low_group))
        if mid_group:
            sampled.append(random.choice(mid_group))
        if high_group:
            sampled.append(random.choice(high_group))
        return [summary.participant for summary in sampled]
    
    else: 
        # Sort by predicted_agreement (ascending, None values treated as -9999)
        sorted_by_agreement = sorted(
            summaries_sorted_by_support,
            key=lambda s: (s.predicted_agreement if s.predicted_agreement is not None else -9999)
        )
        lowest = sorted_by_agreement[0]
        median = sorted_by_agreement[total // 2]
        highest = sorted_by_agreement[-1]
        return [lowest.participant, median.participant, highest.participant]


def get_narrative_parts_optimized(recommendation, participant_ids):
    """
    Optimized helper function to return narrative parts for multiple participants at once.
    """
    # Get all narratives and their parts in one query
    narratives = Narrative.objects.filter(
        recommendation=recommendation, 
        participant_id__in=participant_ids
    ).prefetch_related(
        'parts__utterance__question__interview',
        'parts__utterance__question__module'
    )
    
    narrative_parts_data = {}
    
    for narrative in narratives:
        participant_id = narrative.participant_id
        narrative_parts_data[participant_id] = []
        
        for part in narrative.parts.all():
            part_data = {
                'ai_explanation_text': part.ai_explanation_text,
                'utterance_text': part.utterance.utterance_text if part.utterance else None,
                'audio_url': None
            }
            
            if part.utterance and part.utterance.audio_id:
                try:
                    audio_url = f"InterviewAudios/interview{part.utterance.question.interview.id}/module{part.utterance.question.module.id}/question{part.utterance.question.id}/user_{part.utterance.audio_id}.wav"
                    part_data['audio_url'] = audio_url
                except:
                    part_data['audio_url'] = None
                    
            narrative_parts_data[participant_id].append(part_data)
    
    return narrative_parts_data

def get_or_create_user_recommendation_order(request):
    """
    Get or create a randomized recommendation order for the user using session storage.
    Only applies to recommendations 74, 75, 76.
    """
    # Check if user already has a randomized order in session
    if 'recommendation_order' not in request.session:
        # Create new randomized order
        recommendation_order = [74, 75, 76]
        random.shuffle(recommendation_order)
        
        # Store in session
        request.session['recommendation_order'] = recommendation_order
        request.session['current_index'] = 0
        request.session['completed'] = False
    
    return {
        'order': request.session['recommendation_order'],
        'current_index': request.session['current_index'],
        'completed': request.session['completed']
    }

def get_current_recommendation(request):
    """Get the current recommendation ID from the user's session"""
    user_order = get_or_create_user_recommendation_order(request)
    if user_order['current_index'] < len(user_order['order']):
        return user_order['order'][user_order['current_index']]
    return None

def advance_to_next_recommendation(request):
    """Advance to the next recommendation in the randomized order"""
    user_order = get_or_create_user_recommendation_order(request)
    
    if user_order['current_index'] < len(user_order['order']) - 1:
        # Move to next recommendation
        request.session['current_index'] = user_order['current_index'] + 1
        return True
    else:
        # Completed all recommendations
        request.session['completed'] = True
        return False

def view_recommendation_voting(request, recommendation_id):
    """View for the voting section only - this is the main entry point"""
    if not request.user.is_authenticated:
        return redirect('home')
    
    recommendation_id = int(recommendation_id)
    
    # Check if this is one of the randomized recommendations (74, 75, 76)
    if recommendation_id in [74, 75, 76]:
        # Check if user is accessing the correct recommendation in their order
        current_expected = get_current_recommendation(request)
        
        if current_expected != recommendation_id:
            # Redirect to the correct recommendation in their order
            return redirect(f'/recommendations/{current_expected}/')
    
    recommendation = Recommendation.objects.get(id=recommendation_id)
    # Get current index for display
    user_order = get_or_create_user_recommendation_order(request)
    cur_index = user_order['current_index']
    #condition = set_condition(request)
    condition = settings.CONDITION
    # If no vote exists, show the voting page
    return render(request, 'pages/recommendations/voting_section.html', {
        'recommendation': recommendation,
        'condition': condition,
        'cur_index': cur_index,
    })




def habermas_game(request, recommendation_id):
    if not request.user.is_authenticated:
        return redirect('home')
    try:
        recommendation = Recommendation.objects.get(id=recommendation_id)
    except Recommendation.DoesNotExist:
        messages.error(request, 'Recommendation not found.')
        return redirect('home')
    participant_summaries = RecommendationParticipantSummary.objects.filter(
        recommendation_id=recommendation_id
    ).select_related(
        'participant',
        'participant__avatar',
        'best_utterance',
        'best_utterance__question',
        'best_utterance__question__interview',
        'best_utterance__question__module'
    ).prefetch_related(
        'best_utterance__question__interview__participant'
    )
    if not participant_summaries.exists():
        messages.warning(request, 'No participant data available for this recommendation.')
        context = {
            'recommendation': recommendation,
            'participants_data': [],
            'most_relevant_participants_data': [],
            'user': request.user,
            'edit_form': EditableRecommendationForm(),
        }
        return render(request, 'pages/recommendations/habermas_game.html', context)
    participant_ids = list(participant_summaries.values_list('participant_id', flat=True))
    narrative_parts_data = get_narrative_parts_optimized(recommendation, participant_ids)
    participants_data = []
    support_values = []
    for participant_summary in participant_summaries:
        utterance = participant_summary.best_utterance
        audio_url = None
        if utterance and utterance.audio_id:
            audio_url = f"InterviewAudios/interview{utterance.question.interview.id}/module{utterance.question.module.id}/question{utterance.question.id}/user_{utterance.audio_id}.wav"
        if participant_summary.predicted_agreement is not None:
            support_values.append(participant_summary.predicted_agreement)
        participants_data.append({
            'participant': participant_summary.participant,
            'utterance_text': utterance.utterance_text if utterance else '',
            'audio_url': audio_url,
            'participant_summary': participant_summary.reasoning,
            'avatar_url': participant_summary.participant.get_avatar_url(),
            'narrative_parts': narrative_parts_data.get(participant_summary.participant_id, []),
            'predicted_agreement': participant_summary.predicted_agreement,
            'relevance_score': participant_summary.relevance_score,
        })
    mean_support = sum(support_values) / len(support_values) if support_values else None
    most_relevant_participants = get_top_n_relevant_participants(recommendation_id=recommendation_id, n=3, quality_threshold=80, use_extremes=False)
    most_relevant_participant_ids = {p.id for p in most_relevant_participants}
    most_relevant_participants_data = sorted(
        [data for data in participants_data if data['participant'].id in most_relevant_participant_ids],
        key=lambda x: x['predicted_agreement'] if x['predicted_agreement'] is not None else -1
    )
    # Prefill form with latest edit if exists
    edit_form = EditableRecommendationForm()
    if request.user.is_authenticated:
        try:
            editable = Recommendation.objects.filter(base_rec=recommendation, participant_who_edited=request.user).first()
            if editable:
                edit_form = EditableRecommendationForm(initial={'rec_text': editable.rec_text})
        except Exception:
            pass
    context = {
        'recommendation': recommendation,
        'participants_data': participants_data,
        'most_relevant_participants_data': most_relevant_participants_data,
        'user': request.user,
        'mean_support': mean_support,
        'edit_form': edit_form,
    }
    return render(request, 'pages/recommendations/habermas_game.html', context)

@require_POST
def edit_editable_recommendation(request, recommendation_id):
    if not request.user.is_authenticated:
        if request.headers.get('content-type') == 'application/json':
            return JsonResponse({'success': False, 'error': 'Authentication required.'}, status=403)
        else:
            return redirect('login')
    try:
        recommendation = Recommendation.objects.get(id=recommendation_id)
    except Recommendation.DoesNotExist:
        if request.headers.get('content-type') == 'application/json':
            return JsonResponse({'success': False, 'error': 'Recommendation not found.'}, status=404)
        else:
            return redirect('home')
    
    # Handle AJAX (JSON) and standard POST (form)
    if request.headers.get('content-type') == 'application/json':
        data = json.loads(request.body)
    else:
        data = request.POST
    
    form = EditableRecommendationForm(data)
    if form.is_valid():
        rec_text = form.cleaned_data['rec_text']
        new_recommendation = Recommendation.objects.create(rec_text=rec_text, base_rec=recommendation, participant_who_edited=request.user)

        
        if request.headers.get('content-type') == 'application/json':
            return JsonResponse({'success': True, 'new_recommendation_id': new_recommendation.id})
        else:
            messages.success(request, 'Your recommendation edit was submitted successfully!')
            return redirect('habermas_game', recommendation_id=recommendation_id)
    else:
        if request.headers.get('content-type') == 'application/json':
            return JsonResponse({'success': False, 'error': form.errors}, status=400)
        else:
            # Re-render the habermas_game page with form errors
            return habermas_game(request, recommendation_id)

def set_condition(request):
    treatment_assignment = pd.read_csv("data/treatment_assignments/treatment_control_assignment.csv")
    condition_row = treatment_assignment.query(f"prolific_id == '{request.user.prolific_id}'")
    if request.user.prolific_id == "Suyash2":
        return "treatment"
    if condition_row.empty:
        raise ValueError(f"prolific_id '{request.user.prolific_id}' not found in treatment assignment file.")
    condition = condition_row["assignment"].values[0]
    #settings.CONDITION = condition
    return condition

def generate_default_meta_medleys(recommendation_id, medley_type=None):
    """
    Generate 3 meta-medleys for bottom/middle/top 30 participants by support.
    Uses caching - only generates if not already cached.
    
    Args:
        recommendation_id: Recommendation ID
    
    Returns:
        Dict with 'bottom', 'middle', 'top' meta-medleys
    """
    from generating_v2.meta_medley import create_meta_medley
    from pages.models import LivePrediction
    
    # Get all participants with predictions, sorted by support
    predictions = LivePrediction.objects.filter(
        recommendation_id=recommendation_id
    ).select_related('participant').order_by('predicted_agreement')
    
    all_usernames = [p.participant.username for p in predictions]
    
    # Split into 3 groups of 30
    bottom_30 = all_usernames[:30] if len(all_usernames) >= 30 else all_usernames[:len(all_usernames)//3]
    middle_30 = all_usernames[30:60] if len(all_usernames) >= 60 else all_usernames[len(all_usernames)//3:2*len(all_usernames)//3]
    top_30 = all_usernames[60:90] if len(all_usernames) >= 90 else all_usernames[2*len(all_usernames)//3:]
    
    meta_medleys = {}
    
    def pick_subset(names, size, group_key):
        if len(names) <= size:
            return names
        if group_key == 'bottom':
            return names[:size]
        if group_key == 'top':
            return names[-size:]
        # middle group: take centered slice
        start = max(0, (len(names) - size) // 2)
        return names[start:start + size]
    
    def generate_group_medley(group_key, names, stance):
        if len(names) < 2:
            meta_medleys[group_key] = None
            return
        fallback_sizes = [24, 20, 16, 12, 10, 8, 6, 4, 3, 2]
        sizes_to_try = [len(names)] + [size for size in fallback_sizes if size < len(names)]
        seen_subsets = set()
        last_error = None
        for size in sizes_to_try:
            subset = pick_subset(names, size, group_key)
            subset_tuple = tuple(subset)
            if len(subset) < 2 or subset_tuple in seen_subsets:
                continue
            seen_subsets.add(subset_tuple)
            try:
                meta_medleys[group_key] = create_meta_medley(
                    recommendation_id,
                    subset,
                    medley_group=stance,
                    force_regenerate=(subset != names)
                )
                return
            except ValueError as e:
                last_error = str(e)
                print(f"Failed to create {group_key} meta-medley with {len(subset)} participants: {e}")
                continue
            except Exception as e:
                last_error = str(e)
                print(f"Unexpected error for {group_key} meta-medley: {e}")
                break
        print(f"Unable to create {group_key} meta-medley after fallbacks. Last error: {last_error}")
        meta_medleys[group_key] = None
    
    if medley_type is None:
        generate_group_medley('bottom', bottom_30, 'against')
        generate_group_medley('middle', middle_30, 'on_the_fence')
        generate_group_medley('top', top_30, 'for')
    elif medley_type == 'bottom':
        generate_group_medley(medley_type, bottom_30, 'against')
    elif medley_type == 'middle':
        generate_group_medley(medley_type, middle_30, 'on_the_fence')
    elif medley_type == 'top':
        generate_group_medley(medley_type, top_30, 'for')
    else:
        raise ValueError(f"Invalid medley type: {medley_type}")
    
    return meta_medleys


def submit_recommendation_vote(request, recommendation_id):
    """
    Handle submission of a recommendation vote.
    """
    if request.method != 'POST':
        return HttpResponseBadRequest('Only POST requests are allowed')
    try:
        recommendation = Recommendation.objects.get(id=recommendation_id)
    except Recommendation.DoesNotExist:
        return HttpResponseNotFound('Recommendation not found')
    
    # Get form data
    agreement_level = int(request.POST.get('agreement_level'))
    explanation = request.POST.get('explanation')
    
    # Validate input ranges
    if not (1 <= agreement_level <= 7):
        return HttpResponseBadRequest('Invalid agreement level value')
    
    # Create or update vote
    vote, created = RecommendationVote.objects.update_or_create(
        recommendation=recommendation,
        participant=request.user,
        defaults={
            'agreement_level': agreement_level,
            'explanation': explanation
        }
    )
    
    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    # For non-AJAX requests, render the recommendation detail page directly
    # Get all the data needed for the detail page
    participants_data = []
    support_values = []
    ### FOR NOW, ONLY SHOWING PROLIFIC PARTICIPANTS

    participant_usernames = pd.read_csv("data/participant_data_clean.csv")["prolific_id"].tolist()
    participant_summaries = RecommendationParticipantSummary.objects.filter(
        recommendation_id=recommendation_id,
        participant__username__in=participant_usernames
    ).select_related(
        'participant',
        'participant__avatar',
        'best_utterance',
        'best_utterance__question',
        'best_utterance__question__interview',
        'best_utterance__question__module'
    ).prefetch_related(
        'best_utterance__question__interview__participant'
    )
    
    # Selecting profiles based on vote, always include the person's own profile too
    if agreement_level >= 4:
        filtered_summaries = participant_summaries.filter(against_profiles_selected=True)
    else:
        filtered_summaries = participant_summaries.filter(pro_profiles_selected=True)
    
    # Always include the current user's own profile if it exists
    own_summary = participant_summaries.filter(participant=request.user).first()
    if own_summary and own_summary not in filtered_summaries:
        participant_summaries_with_own = list(filtered_summaries) + [own_summary]
    else:
        participant_summaries_with_own = list(filtered_summaries)

    for participant_summary in participant_summaries_with_own:
        participant = participant_summary.participant
        # Basic info
        avatar_url = participant.get_avatar_url()
        # Best utterance and audio
        utterance = participant_summary.best_utterance
        audio_url = None
        if utterance and utterance.audio_id:
            audio_url = f"InterviewAudios/interview{utterance.question.interview.id}/module{utterance.question.module.id}/question{utterance.question.id}/user_{utterance.audio_id}.wav"
        if participant_summary.predicted_agreement is not None:
            support_values.append(participant_summary.predicted_agreement)
        
        # Narrative parts - will be loaded dynamically via AJAX
        narrative_parts = []
        participant_narrative_parts = []
        
        # Reflection (if any)
        reflection = None
        
        # Connection request (if any)
        connection_request = None
        # # Randomly sample integer between -5 and 5
        # random_delta = random.randint(-10, 10)
        # # Add to relevance_score, cap at 100 and floor at 0
        # if participant_summary.quality_score is not None:
        #     participant_summary.relevance_score = participant_summary.quality_score
        participants_data.append({
            'participant': participant,
            'avatar_url': avatar_url,
            'age': participant.age,
            'occupation': participant.occupation,
            'utterance_text': utterance.utterance_text if utterance else "",
            'audio_url': audio_url,
            'participant_summary': participant_summary.summary,
            'narrative_parts': narrative_parts,
            'participant_narrative_parts': participant_narrative_parts,
            'predicted_agreement': participant_summary.predicted_agreement,
            'relevance_score': participant_summary.quality_score,
            'reflection': reflection,
            'connection_request': connection_request,
        })
    
    # Calculate mean support
    mean_support = sum(support_values) / len(support_values) if support_values else None

    # Generate 3 meta-medleys for bottom/middle/top 30 participants
    meta_medleys = generate_default_meta_medleys(recommendation_id)

    # Get most relevant participants and filter data
    most_relevant_participants = get_top_n_relevant_participants(
        recommendation_id,
        filtered_summaries,
        quality_threshold=70, 
        use_extremes=False,
        current_user=request.user
    )
    most_relevant_participant_ids = {p.id for p in most_relevant_participants}
    
    most_relevant_participants_data = sorted(
        [data for data in participants_data if data['participant'].id in most_relevant_participant_ids],
        key=lambda x: x['predicted_agreement'] if x['predicted_agreement'] is not None else -1
    )
    
    # Add featured_ids for highlighting the most relevant participants in the plot
    if 'most_relevant_participants_data' in locals():
        featured_ids = [int(d['participant'].id) for d in most_relevant_participants_data]
    else:
        featured_ids = []

    print(most_relevant_participants_data)
    # Get current index for display (for randomized recommendations)
    cur_index = None
    if recommendation_id in [74, 75, 76]:
        user_order = get_or_create_user_recommendation_order(request)
        cur_index = user_order['current_index']


    #condition = set_condition(request)
    condition = settings.CONDITION
    context = {
        'recommendation': recommendation,
        'participants_data': participants_data,
        'most_relevant_participants_data': most_relevant_participants_data,
        'featured_ids': featured_ids,
        'user': request.user,
        'mean_support': mean_support,
        'condition': condition,
        'pilot': settings.PILOT,
        'user_vote': agreement_level,  # Pass the vote to the template
        'cur_index': cur_index,
        'meta_medleys': meta_medleys,  # Add meta-medleys to context
    }
    
    return render(request, 'pages/recommendations/recommendation_detail.html', context)

def get_participant_prediction(request, recommendation_id, participant_username):
    """Get prediction for a single participant"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required.'}, status=403)
    
    try:
        recommendation_obj = Recommendation.objects.get(id=recommendation_id)
        prediction = get_participant_prediction_helper(participant_username, recommendation_obj)
        print("PREDICTION:")
        print(prediction)

        return JsonResponse({
            'participant_username': participant_username,
            'predicted_agreement': prediction.predicted_agreement,
            'relevance_score': prediction.relevance_score,
            'reasoning': prediction.reasoning,
            'status': 'complete'
        })
    except (Participant.DoesNotExist, Recommendation.DoesNotExist):
        return JsonResponse({
            'participant_username': participant_username,
            'status': 'pending'
        })


def get_participant_modal_content(request, recommendation_id, participant_id):
    """
    AJAX view to get modal content for a specific participant.
    This enables lazy loading of participant modals.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required.'}, status=403)
    
    try:
        recommendation = Recommendation.objects.get(id=recommendation_id)
        participant = Participant.objects.get(id=participant_id)
    except (Recommendation.DoesNotExist, Participant.DoesNotExist):
        return JsonResponse({'error': 'Recommendation or participant not found.'}, status=404)
    
    # Get participant summary
    try:
        participant_summary = RecommendationParticipantSummary.objects.get(
            recommendation=recommendation,
            participant=participant
        )
    except RecommendationParticipantSummary.DoesNotExist:
        return JsonResponse({'error': 'Participant data not found.'}, status=404)
    
    # Get narrative parts for this participant
    narrative = None
    participant_narrative = None
    
    try:
        narrative = Narrative.objects.select_related(
            'participant'
        ).prefetch_related(
            'parts__utterance__question__interview',
            'parts__utterance__question__module'
        ).get(recommendation=recommendation, participant=participant)
        all_narrative_parts = narrative.parts.all()
    except Narrative.DoesNotExist:
        all_narrative_parts = []

    try:
        participant_narrative = ParticipantNarrative.objects.select_related(
            'participant'
        ).prefetch_related(
            'parts__utterance__question__interview',
            'parts__utterance__question__module'
        ).get(participant=participant)
        all_participant_narrative_parts = participant_narrative.parts.all()
    except ParticipantNarrative.DoesNotExist:
        all_participant_narrative_parts = []

    # Build narrative parts data
    narrative_parts = []
    for part in all_narrative_parts:
        audio_url = None
        if part.utterance and part.utterance.audio_id:
            audio_url = f"InterviewAudios/interview{part.utterance.question.interview.id}/module{part.utterance.question.module.id}/question{part.utterance.question.id}/user_{part.utterance.audio_id}.wav"
        
        narrative_parts.append({
            'ai_explanation_text': part.ai_explanation_text,
            'utterance_text': part.utterance.utterance_text if part.utterance else None,
            'utterance_text_with_bold': part.utterance_text_with_bold if hasattr(part, 'utterance_text_with_bold') else None,
            'audio_url': audio_url,
            'audio_id': part.utterance.audio_id,
            'utterance': part.utterance
        })
    participant_narrative_parts = []
    for part in all_participant_narrative_parts:
        audio_url = None
        if part.utterance and part.utterance.audio_id:
            audio_url = f"InterviewAudios/interview{part.utterance.question.interview.id}/module{part.utterance.question.module.id}/question{part.utterance.question.id}/user_{part.utterance.audio_id}.wav"
        participant_narrative_parts.append({
            'ai_explanation_text': part.ai_explanation_text,
            'utterance_text': part.utterance.utterance_text if part.utterance else None,
            'utterance_text_with_bold': part.utterance_text_with_bold if hasattr(part, 'utterance_text_with_bold') else None,
            'audio_url': audio_url,
            'audio_id': part.utterance.audio_id,
            'utterance': part.utterance
        })

    # Get basic participant info
    avatar_url = participant.get_avatar_url()
    
    # Get previously saved reflection data
    try:
        connection_report = ConnectionReport.objects.get(
            participant=request.user,
            target_participant=participant,
            recommendation=recommendation
        )
    except ConnectionReport.DoesNotExist:
        connection_report = None
    
    try:
        vote_report = PredictedVoteReport.objects.get(
            participant=request.user,
            target_participant=participant,
            recommendation=recommendation
        )
    except PredictedVoteReport.DoesNotExist:
        vote_report = None
    
    # Get connection request status
    try:
        connection_request = ConnectionRequest.objects.get(
            from_user=request.user,
            to_user=participant,
            recommendation=recommendation
        )
    except ConnectionRequest.DoesNotExist:
        connection_request = None
    
    # Build context for template rendering
    context = {
        'recommendation': recommendation,
        'data': {
            'participant': participant,
            'avatar_url': avatar_url,
            'age': participant.age,
            'occupation': participant.occupation,
            'narrative_parts': narrative_parts,
            'participant_narrative_parts': participant_narrative_parts,
            'predicted_agreement': participant_summary.predicted_agreement,
            'relevance_score': participant_summary.relevance_score,
            'life_summary': participant_narrative.global_summary if participant_narrative else None,
            'rec_summary': narrative.global_summary if narrative else None,
            'reflection': {
                'connection_score': connection_report.connection_score if connection_report else None,
                'connection_text': connection_report.connection_text if connection_report else None,
                'vote_prediction': vote_report.predicted_vote_score if vote_report else None,
                'vote_explanation': vote_report.predicted_vote_text if vote_report else None,
            },
            'connection_request': connection_request,
        }
    }


    # Add MEDIA_URL to the context
    context['MEDIA_URL'] = settings.MEDIA_URL

    modal_html = render_to_string('pages/recommendations/participant_modal_content.html', context, request=request)
    
    return JsonResponse({
        'modal_html': modal_html,
        'participant_id': participant_id,
        'participant_name': participant.get_full_name()
    })









@csrf_exempt
@require_POST
def submit_reflection(request):
    print("=== SUBMIT REFLECTION CALLED ===")
    print("Request body:", request.body)
    data = json.loads(request.body)
    print("Parsed data:", data)
    user = request.user
    recommendation_id = data['recommendation_id']
    target_participant_id = data['target_participant_id']
    connection_score = int(data['connection_score'])
    connection_text = data['connection_text']
    vote_prediction = int(data['vote_prediction'])
    vote_explanation = data['vote_explanation']
    print("Processed values:", {
        'user': user.id,
        'recommendation_id': recommendation_id,
        'target_participant_id': target_participant_id,
        'connection_score': connection_score,
        'vote_prediction': vote_prediction
    })

    recommendation = Recommendation.objects.get(id=recommendation_id)
    target_participant = Participant.objects.get(id=target_participant_id)

    # Save ConnectionReport
    connection_report, created = ConnectionReport.objects.update_or_create(
        participant=user,
        target_participant=target_participant,
        recommendation=recommendation,
        defaults={
            'connection_score': connection_score,
            'connection_text': connection_text,
        }
    )
    print(f"ConnectionReport {'created' if created else 'updated'}: {connection_report.id}")

    # Save PredictedVoteReport
    vote_report, created = PredictedVoteReport.objects.update_or_create(
        participant=user,
        target_participant=target_participant,
        recommendation=recommendation,
        defaults={
            'predicted_vote_score': vote_prediction,
            'predicted_vote_text': vote_explanation,
        }
    )
    print(f"PredictedVoteReport {'created' if created else 'updated'}: {vote_report.id}")

    return JsonResponse({'success': True})


@csrf_exempt
@require_POST
def submit_feedback(request):
    """
    Handle submission of feedback on predicted support scores.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Authentication required.'}, status=403)
    
    try:
        data = json.loads(request.body)
        recommendation_id = data['recommendation_id']
        feedback_type = data['feedback_type']
        feedback_text = data.get('feedback_text', '')
        
        recommendation = Recommendation.objects.get(id=recommendation_id)
        
        # Save or update feedback
        feedback, created = PredictionFeedback.objects.update_or_create(
            participant=request.user,
            recommendation=recommendation,
            defaults={
                'feedback_type': feedback_type,
                'feedback_text': feedback_text
            }
        )
        
        return JsonResponse({'success': True})
        
    except (Recommendation.DoesNotExist, KeyError, json.JSONDecodeError) as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': 'An error occurred while saving feedback.'}, status=500)


@csrf_exempt
@require_POST
def send_connection_request(request):
    """
    Handle sending connection requests between participants.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Authentication required.'}, status=403)
    
    try:
        data = json.loads(request.body)
        target_participant_id = data['target_participant_id']
        recommendation_id = data['recommendation_id']
        
        target_participant = Participant.objects.get(id=target_participant_id)
        recommendation = Recommendation.objects.get(id=recommendation_id)
        
        # Check if connection request already exists
        existing_request = ConnectionRequest.objects.filter(
            from_user=request.user,
            to_user=target_participant,
            recommendation=recommendation
        ).first()
        
        if existing_request:
            return JsonResponse({'success': True, 'message': 'Connection request already sent'})
        
        # Create new connection request
        connection_request = ConnectionRequest.objects.create(
            from_user=request.user,
            to_user=target_participant,
            recommendation=recommendation,
            status='pending'
        )
        
        return JsonResponse({'success': True, 'message': 'Connection request sent successfully'})
        
    except (Participant.DoesNotExist, Recommendation.DoesNotExist, KeyError, json.JSONDecodeError) as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': 'An error occurred while sending connection request.'}, status=500)

def get_similarity_based_participants(current_user, recommendation_id):
    """
    Get similarity-based participant selection for a user and recommendation
    
    Args:
        current_user: Participant object
        recommendation_id: ID of the recommendation
    
    Returns:
        dict: Selected participants for each bucket, or None if failed
    """
    try:
        # Import ParticipantSimilarity dynamically to avoid import issues
        from .models import ParticipantSimilarity
        
        # Check if we have cached results (less than 24 hours old)
        cached_similarity = ParticipantSimilarity.objects.filter(
            current_user=current_user,
            recommendation_id=recommendation_id,
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).first()
        
        if cached_similarity:
            print(f"Using cached similarity results for {current_user.username}")
            selected_ids = cached_similarity.selected_participants
            return {
                bucket_name: Participant.objects.get(id=participant_id)
                for bucket_name, participant_id in selected_ids.items()
            }
        
        # Check if user has Module 3 & 4 responses
        if not has_module_responses(current_user):
            print(f"Warning: User {current_user.username} missing Module 3/4 responses, falling back to random sampling")
            return None
            
        # Get buckets and select similar participants
        buckets = get_participant_buckets(recommendation_id, current_user)
        selected_participants = select_similar_participants(current_user, buckets)
        
        if selected_participants:
            # Cache the results
            selected_ids = {
                bucket_name: participant.id
                for bucket_name, participant in selected_participants.items()
            }
            
            # Save to database
            ParticipantSimilarity.objects.update_or_create(
                current_user=current_user,
                recommendation_id=recommendation_id,
                defaults={'selected_participants': selected_ids}
            )
            
            print(f"Successfully selected and cached participants for {current_user.username}")
            return selected_participants
        else:
            print(f"No participants selected for {current_user.username}")
            return None
        
    except Exception as e:
        print(f"Error calculating similarities for {current_user.username}: {e}")
        return None

def has_module_responses(participant):
    """
    Check if participant has Module 3 and 4 responses
    """
    try:
        interview = Interview.objects.get(participant=participant, script_v="minwage_script_v2")
        module3 = InterviewModule.objects.get(interview=interview, module_id=3)
        module4 = InterviewModule.objects.get(interview=interview, module_id=4)
        
        # Check if both modules have interviewee utterances
        module3_utterances = InterviewUtterance.objects.filter(
            question__module=module3,
            is_interviewer=False
        ).exists()
        
        module4_utterances = InterviewUtterance.objects.filter(
            question__module=module4,
            is_interviewer=False
        ).exists()
        
        return module3_utterances and module4_utterances
        
    except (Interview.DoesNotExist, InterviewModule.DoesNotExist):
        return False

def get_module_responses(participant, module_id):
    """
    Extract responses from specific module for a participant
    """
    try:
        interview = Interview.objects.get(participant=participant, script_v="minwage_script_v2")
        module = InterviewModule.objects.get(interview=interview, module_id=module_id)
        questions = InterviewQuestion.objects.filter(module=module)
        
        # Get all interviewee utterances from this module
        utterances = InterviewUtterance.objects.filter(
            question__in=questions,
            is_interviewer=False
        ).order_by('question__global_question_id', 'sequence_number')
        
        if not utterances.exists():
            return ""
        
        return " ".join([utt.utterance_text for utt in utterances])
    
    except (Interview.DoesNotExist, InterviewModule.DoesNotExist):
        return ""

def get_participant_buckets(recommendation_id, current_user=None):
    """
    Group participants by agreement buckets for a recommendation
    Excludes the current user from all buckets
    """
    # Add a threshold for relevance_score (e.g., only include relevance_score > 50)
    summaries = list(RecommendationParticipantSummary.objects.filter(
        recommendation_id=recommendation_id,
        relevance_score__gt=80  # You can adjust this threshold as needed
    ).select_related('participant').order_by('predicted_agreement'))
    
    # Exclude current user if provided
    if current_user:
        summaries = [s for s in summaries if s.participant.id != current_user.id]
    
    if not summaries:
        return {'low': [], 'middle': [], 'high': []}
    
    # Group by predicted_agreement: 0-33 (low), 33-66 (middle), >66 (high)
    buckets = {
        'low': [s for s in summaries if (s.predicted_agreement if s.predicted_agreement is not None else -9999) < 33],
        'middle': [s for s in summaries if 33 <= (s.predicted_agreement if s.predicted_agreement is not None else -9999) <= 66],
        'high': [s for s in summaries if (s.predicted_agreement if s.predicted_agreement is not None else -9999) > 66]
    }
    
    return buckets

def create_similarity_prompt(current_user_module3, current_user_module4, bucket_participants, bucket_name):
    """
    Create prompt for LLM to select most similar participant
    """
    # Format participant responses for the prompt
    participant_responses = []
    for i, summary in enumerate(bucket_participants):
        module3_text = get_module_responses(summary.participant, 3)
        module4_text = get_module_responses(summary.participant, 4)
        
        participant_responses.append(f"""
Username: {summary.participant.username}
Background: {module3_text}
Important Relationship: {module4_text}
        """)
    
    participants_text = "\n".join(participant_responses)
    
    prompt = f"""
You are an expert at identifying people with similar life experiences and backgrounds.

Current user's background: {current_user_module3}
Current user's important relationship: {current_user_module4}

From the following {len(bucket_participants)} participants in the {bucket_name} agreement group, 
select the ONE who has the most similar background and relationship experiences.

Consider:
- Similar family background (rural/urban, economic status, family structure)
- Similar life experiences (education, work history, challenges faced)
- Similar relationship dynamics (mentors, family members, friends who shaped them)
- Similar values and perspectives on life

Participants in {bucket_name} group:
{participants_text}

Return ONLY the username of the most similar participant.
"""
    return prompt

def call_gpt(prompt, max_retries=3):
    """
    Call GPT-4 with retry logic - returns username instead of JSON
    """
    for attempt in range(max_retries):
        try:
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert at identifying people with similar life experiences and backgrounds. Return only the username of the most similar participant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            print(f"Attempt {attempt + 1} failed: {e}, retrying...")

def get_llm_selection_with_retry(current_user_module3, current_user_module4, bucket_participants, bucket_name, max_retries=3):
    """
    Get LLM selection with retry logic and validation
    """
    for attempt in range(max_retries):
        try:
            prompt = create_similarity_prompt(current_user_module3, current_user_module4, bucket_participants, bucket_name)
            username = call_gpt(prompt)
            
            # Find participant by username
            valid_usernames = [summary.participant.username for summary in bucket_participants]
            if username not in valid_usernames:
                raise ValueError(f"Invalid username: {username}")
            
            # Get the participant ID
            selected_participant = next(summary.participant for summary in bucket_participants if summary.participant.username == username)
            return selected_participant.id
            
        except Exception as e:
            if attempt == max_retries - 1:
                # Final fallback: random selection
                print(f"LLM selection failed after {max_retries} attempts, using random selection")
                return bucket_participants[0].participant.id
            else:
                print(f"Attempt {attempt + 1} failed: {e}, retrying...")

def select_similar_participants(current_user, buckets):
    """
    Select similar participants using LLM-based selection
    """
    # Implementation details...
    pass


# ===================== TELEMETRY VIEWS =====================

@csrf_exempt
@require_POST
def start_recommendation_tracking(request):
    """
    Start tracking time spent on a recommendation
    """
    try:
        data = json.loads(request.body)
        
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'User not authenticated'}, status=401)
        
        recommendation_id = data.get('recommendation_id')
        session_id = data.get('session_id')
        
        if not recommendation_id:
            return JsonResponse({'error': 'Missing recommendation_id'}, status=400)
        
        try:
            recommendation = Recommendation.objects.get(id=recommendation_id)
        except Recommendation.DoesNotExist:
            return JsonResponse({'error': 'Recommendation not found'}, status=404)
        
        # Start tracking session
        from .models import start_recommendation_session as start_recommendation_session_func
        tracking_session = start_recommendation_session_func(
            participant=request.user,
            recommendation=recommendation,
            session_id=session_id
        )
        
        return JsonResponse({
            'success': True, 
            'tracking_id': tracking_session.id,
            'started_at': tracking_session.started_at.isoformat()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def end_recommendation_tracking(request):
    """
    End tracking time spent on a recommendation
    """
    try:
        data = json.loads(request.body)
        
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'User not authenticated'}, status=401)
        
        session_id = data.get('session_id')
        recommendation_id = data.get('recommendation_id')
        
        if not session_id:
            return JsonResponse({'error': 'Missing session_id'}, status=400)
        
        try:
            # Find the most recent active tracking session for this user and session
            tracking_session = RecommendationTimeSpent.objects.filter(
                participant=request.user,
                session_id=session_id,
                ended_at__isnull=True
            ).order_by('-started_at').first()
            
            if not tracking_session:
                return JsonResponse({'error': 'No active tracking session found'}, status=404)
            
            tracking_session.end_session()
            
            return JsonResponse({
                'success': True,
                'duration_seconds': tracking_session.duration_seconds,
                'ended_at': tracking_session.ended_at.isoformat()
            })
            
        except RecommendationTimeSpent.DoesNotExist:
            return JsonResponse({'error': 'Tracking session not found'}, status=404)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def track_avatar_click(request):
    """
    Track avatar clicks with avatar type classification
    """
    try:
        data = json.loads(request.body)
        
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'User not authenticated'}, status=401)
        
        # Debug: Check user type
        print(f"User type: {type(request.user)}")
        print(f"User ID: {request.user.id}")
        print(f"Is Participant: {hasattr(request.user, 'avatar')}")
        
        recommendation_id = data.get('recommendation_id')
        clicked_participant_id = data.get('participant_id')  # Frontend sends 'participant_id'
        avatar_type = data.get('avatar_type')
        click_x = data.get('click_x')
        click_y = data.get('click_y')
        session_id = data.get('session_id')
        
        if not all([recommendation_id, clicked_participant_id, avatar_type]):
            return JsonResponse({'error': 'Missing required fields'}, status=400)
        
        try:
            recommendation = Recommendation.objects.get(id=recommendation_id)
            clicked_participant = Participant.objects.get(id=clicked_participant_id)
        except (Recommendation.DoesNotExist, Participant.DoesNotExist):
            return JsonResponse({'error': 'Recommendation or participant not found'}, status=404)
        
        # Validate avatar type
        valid_types = ['featured', 'current_user', 'other']
        if avatar_type not in valid_types:
            return JsonResponse({'error': 'Invalid avatar type'}, status=400)
        
        # Track the click
        from .models import track_avatar_click as track_avatar_click_func
        avatar_click = track_avatar_click_func(
            participant=request.user,
            recommendation=recommendation,
            clicked_participant=clicked_participant,
            avatar_type=avatar_type,
            click_x=click_x,
            click_y=click_y,
            session_id=session_id
        )
        
        return JsonResponse({
            'success': True,
            'click_id': avatar_click.id,
            'timestamp': avatar_click.timestamp.isoformat()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        import traceback
        print(f"Telemetry error in track_avatar_click: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def track_meta_medley_click(request):
    """
    Track meta-medley button clicks
    """
    try:
        data = json.loads(request.body)

        if not request.user.is_authenticated:
            return JsonResponse({'error': 'User not authenticated'}, status=401)

        recommendation_id = data.get('recommendation_id')
        meta_medley_type = data.get('meta_medley_type')
        session_id = data.get('session_id')

        if not all([recommendation_id, meta_medley_type]):
            return JsonResponse({'error': 'Missing required fields'}, status=400)

        try:
            recommendation = Recommendation.objects.get(id=recommendation_id)
        except Recommendation.DoesNotExist:
            return JsonResponse({'error': 'Recommendation not found'}, status=404)

        # Validate meta_medley_type
        valid_types = ['bottom', 'middle', 'top']
        if meta_medley_type not in valid_types:
            return JsonResponse({'error': 'Invalid meta_medley_type'}, status=400)

        # Track the click
        from .models import track_meta_medley_click as track_meta_medley_click_func
        meta_medley_click = track_meta_medley_click_func(
            participant=request.user,
            recommendation=recommendation,
            meta_medley_type=meta_medley_type,
            session_id=session_id
        )

        return JsonResponse({
            'success': True,
            'click_id': meta_medley_click.id,
            'created_at': meta_medley_click.created_at.isoformat()
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        import traceback
        print(f"Telemetry error in track_meta_medley_click: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def start_profile_tracking(request):
    """
    Start tracking time spent on participant profile modal
    """
    try:
        data = json.loads(request.body)
        
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'User not authenticated'}, status=401)
        
        recommendation_id = data.get('recommendation_id')
        viewed_participant_id = data.get('participant_id')  # Frontend sends 'participant_id'
        session_id = data.get('session_id')
        
        if not all([recommendation_id, viewed_participant_id]):
            return JsonResponse({'error': 'Missing required fields'}, status=400)
        
        try:
            recommendation = Recommendation.objects.get(id=recommendation_id)
            viewed_participant = Participant.objects.get(id=viewed_participant_id)
        except (Recommendation.DoesNotExist, Participant.DoesNotExist):
            return JsonResponse({'error': 'Recommendation or participant not found'}, status=404)
        
        # Start tracking session
        from .models import start_profile_view_session as start_profile_view_session_func
        tracking_session = start_profile_view_session_func(
            participant=request.user,
            recommendation=recommendation,
            viewed_participant=viewed_participant,
            session_id=session_id
        )
        
        return JsonResponse({
            'success': True,
            'tracking_id': tracking_session.id,
            'started_at': tracking_session.started_at.isoformat()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        import traceback
        print(f"Telemetry error in start_profile_tracking: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def end_profile_tracking(request):
    """
    End tracking time spent on participant profile modal
    """
    try:
        data = json.loads(request.body)
        
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'User not authenticated'}, status=401)
        
        session_id = data.get('session_id')
        recommendation_id = data.get('recommendation_id')
        participant_id = data.get('participant_id')
        
        if not session_id:
            return JsonResponse({'error': 'Missing session_id'}, status=400)
        
        try:
            # Find the most recent active tracking session for this user and session
            tracking_session = ParticipantProfileTime.objects.filter(
                participant=request.user,
                session_id=session_id,
                ended_at__isnull=True
            ).order_by('-started_at').first()
            
            if not tracking_session:
                return JsonResponse({'error': 'No active tracking session found'}, status=404)
            
            tracking_session.end_session()
            
            return JsonResponse({
                'success': True,
                'duration_seconds': tracking_session.duration_seconds,
                'ended_at': tracking_session.ended_at.isoformat()
            })
            
        except ParticipantProfileTime.DoesNotExist:
            return JsonResponse({'error': 'Tracking session not found'}, status=404)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def start_audio_tracking(request):
    """
    Start tracking audio clip listening
    """
    print("DEBUG: start_audio_tracking view called")
    try:
        data = json.loads(request.body)
        print(f"DEBUG: Received data: {data}")
        
        if not request.user.is_authenticated:
            print("DEBUG: User not authenticated")
            return JsonResponse({'error': 'User not authenticated'}, status=401)
        
        recommendation_id = data.get('recommendation_id')
        audio_clip_id = data.get('audio_clip_id')
        total_duration = data.get('total_duration')
        session_id = data.get('session_id')
        
        print(f"DEBUG: recommendation_id={recommendation_id}, audio_clip_id={audio_clip_id}")
        
        if not all([recommendation_id, audio_clip_id]):
            print("DEBUG: Missing required fields")
            return JsonResponse({'error': 'Missing required fields'}, status=400)
        
        try:
            recommendation = Recommendation.objects.get(id=recommendation_id)
            # Look for InterviewUtterance with this audio_id instead of InterviewClip
            try:
                audio_utterance = InterviewUtterance.objects.get(audio_id=audio_clip_id)
                print(f"DEBUG: Found recommendation and audio utterance")
            except InterviewUtterance.DoesNotExist:
                print(f"DEBUG: InterviewUtterance with audio_id {audio_clip_id} not found")
                return JsonResponse({'error': 'Audio clip not found'}, status=404)
        except Recommendation.DoesNotExist as e:
            print(f"DEBUG: Recommendation not found error: {e}")
            return JsonResponse({'error': 'Recommendation not found'}, status=404)
        
        # Start tracking session - create AudioClipListening with audio_id
        try:
            from .models import AudioClipListening
            tracking_session = AudioClipListening.objects.create(
                participant=request.user,
                recommendation=recommendation,
                audio_clip=None,  # We don't have InterviewClip objects
                audio_id=audio_clip_id,  # Store the audio_id from InterviewUtterance
                total_audio_duration=total_duration,
                session_id=session_id
            )
            print(f"DEBUG: Created tracking session: {tracking_session.id} for audio_id: {audio_clip_id}")
        except Exception as e:
            print(f"DEBUG: Error creating tracking session: {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': f'Error creating tracking session: {str(e)}'}, status=500)
        
        return JsonResponse({
            'success': True,
            'tracking_id': tracking_session.id,
            'started_at': tracking_session.started_at.isoformat()
        })
        
    except json.JSONDecodeError as e:
        print(f"DEBUG: JSON decode error: {e}")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"DEBUG: Unexpected error in start_audio_tracking: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def update_audio_tracking(request):
    """
    Update audio tracking with listening progress
    """
    print("DEBUG: update_audio_tracking view called")
    try:
        data = json.loads(request.body)
        print(f"DEBUG: Received data: {data}")
        
        if not request.user.is_authenticated:
            print("DEBUG: User not authenticated")
            return JsonResponse({'error': 'User not authenticated'}, status=401)
        
        # Frontend sends listened_duration directly, not tracking_id
        listened_duration = data.get('listened_duration')
        event_type = data.get('event_type')  # 'timeupdate', 'play', 'pause', 'seek'
        
        print(f"DEBUG: listened_duration={listened_duration}, event_type={event_type}")
        
        if listened_duration is None:
            print("DEBUG: Missing listened_duration")
            return JsonResponse({'error': 'Missing listened_duration'}, status=400)
        
        # Get the most recent audio tracking session for this user
        try:
            tracking_session = AudioClipListening.objects.filter(
                participant=request.user,
                ended_at__isnull=True  # Still active session
            ).order_by('-started_at').first()
            
            print(f"DEBUG: Found tracking session: {tracking_session}")
            
            if not tracking_session:
                print("DEBUG: No active audio tracking session found")
                return JsonResponse({'error': 'No active audio tracking session found'}, status=404)
            
            # Update listening duration
            tracking_session.listened_duration = listened_duration
            
            # Update event counters
            if event_type == 'play':
                tracking_session.play_count += 1
            elif event_type == 'pause':
                tracking_session.pause_count += 1
            elif event_type == 'seek':
                tracking_session.seek_count += 1
            
            tracking_session.save()
            print(f"DEBUG: Updated tracking session successfully")
            
            return JsonResponse({'success': True})
            
        except AudioClipListening.DoesNotExist:
            print("DEBUG: AudioClipListening.DoesNotExist")
            return JsonResponse({'error': 'Tracking session not found'}, status=404)
        
    except json.JSONDecodeError as e:
        print(f"DEBUG: JSON decode error: {e}")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"DEBUG: Unexpected error in update_audio_tracking: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def end_audio_tracking(request):
    """
    End tracking audio clip listening
    """
    print("DEBUG: end_audio_tracking view called")
    try:
        data = json.loads(request.body)
        print(f"DEBUG: Received data: {data}")
        
        if not request.user.is_authenticated:
            print("DEBUG: User not authenticated")
            return JsonResponse({'error': 'User not authenticated'}, status=401)
        
        # Frontend sends listened_duration directly, not tracking_id
        listened_duration = data.get('listened_duration')
        print(f"DEBUG: listened_duration={listened_duration}")
        
        # Get the most recent audio tracking session for this user
        try:
            tracking_session = AudioClipListening.objects.filter(
                participant=request.user,
                ended_at__isnull=True  # Still active session
            ).order_by('-started_at').first()
            
            print(f"DEBUG: Found tracking session: {tracking_session}")
            
            if not tracking_session:
                print("DEBUG: No active audio tracking session found")
                return JsonResponse({'error': 'No active audio tracking session found'}, status=404)
            
            # Update final listening duration
            if listened_duration is not None:
                tracking_session.listened_duration = listened_duration
            
            tracking_session.end_session()
            print(f"DEBUG: Ended tracking session successfully")
            
            return JsonResponse({
                'success': True,
                'duration_seconds': tracking_session.duration_seconds,
                'completion_percentage': tracking_session.completion_percentage,
                'ended_at': tracking_session.ended_at.isoformat()
            })
            
        except AudioClipListening.DoesNotExist:
            print("DEBUG: AudioClipListening.DoesNotExist")
            return JsonResponse({'error': 'Tracking session not found'}, status=404)
        
    except json.JSONDecodeError as e:
        print(f"DEBUG: JSON decode error: {e}")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"DEBUG: Unexpected error in end_audio_tracking: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def start_voting_tracking(request):
    """
    Start tracking time spent on voting screen (step 4)
    """
    try:
        data = json.loads(request.body)
        
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'User not authenticated'}, status=401)
        
        recommendation_id = data.get('recommendation_id')
        session_id = data.get('session_id')
        
        if not recommendation_id:
            return JsonResponse({'error': 'Missing recommendation_id'}, status=400)
        
        try:
            recommendation = Recommendation.objects.get(id=recommendation_id)
        except Recommendation.DoesNotExist:
            return JsonResponse({'error': 'Recommendation not found'}, status=404)
        
        # Start tracking session
        from .models import start_voting_screen_session as start_voting_screen_session_func
        tracking_session = start_voting_screen_session_func(
            participant=request.user,
            recommendation=recommendation,
            session_id=session_id
        )
        
        return JsonResponse({
            'success': True,
            'tracking_id': tracking_session.id,
            'started_at': tracking_session.started_at.isoformat()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def end_voting_tracking(request):
    """
    End tracking time spent on voting screen (step 4)
    """
    try:
        data = json.loads(request.body)
        
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'User not authenticated'}, status=401)
        
        session_id = data.get('session_id')
        recommendation_id = data.get('recommendation_id')
        
        if not session_id:
            return JsonResponse({'error': 'Missing session_id'}, status=400)
        
        try:
            # Find the most recent active tracking session for this user and session
            tracking_session = VotingScreenTime.objects.filter(
                participant=request.user,
                session_id=session_id,
                ended_at__isnull=True
            ).order_by('-started_at').first()
            
            if not tracking_session:
                return JsonResponse({'error': 'No active tracking session found'}, status=404)
            
            tracking_session.end_session()
            
            return JsonResponse({
                'success': True,
                'duration_seconds': tracking_session.duration_seconds,
                'ended_at': tracking_session.ended_at.isoformat()
            })
            
        except VotingScreenTime.DoesNotExist:
            return JsonResponse({'error': 'Tracking session not found'}, status=404)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def get_telemetry_summary(request):
    """
    Get telemetry summary for research analysis
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    
    participant = request.user
    recommendation_id = request.GET.get('recommendation_id')
    
    # Build filters
    filters = {'participant': participant}
    if recommendation_id:
        filters['recommendation_id'] = recommendation_id
    
    # Get summary data
    recommendation_times = RecommendationTimeSpent.objects.filter(**filters)
    avatar_clicks = AvatarClick.objects.filter(**filters)
    profile_times = ParticipantProfileTime.objects.filter(**filters)
    audio_sessions = AudioClipListening.objects.filter(**filters)
    voting_times = VotingScreenTime.objects.filter(**filters)
    
    summary = {
        'recommendation_time_avg': recommendation_times.aggregate(avg_time=models.Avg('duration_seconds'))['avg_time'],
        'total_avatar_clicks': avatar_clicks.count(),
        'avatar_clicks_by_type': list(avatar_clicks.values('avatar_type').annotate(count=models.Count('id'))),
        'profile_time_avg': profile_times.aggregate(avg_time=models.Avg('duration_seconds'))['avg_time'],
        'audio_completion_avg': audio_sessions.aggregate(avg_completion=models.Avg('completion_percentage'))['avg_completion'],
        'voting_time_avg': voting_times.aggregate(avg_time=models.Avg('duration_seconds'))['avg_time'],
        'total_audio_sessions': audio_sessions.count(),
        'total_profile_views': profile_times.count(),
    }
    
    return JsonResponse(summary)


@require_GET
def export_telemetry_data(request):
    """
    Export telemetry data for research analysis (admin only)
    """
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    # Get parameters
    participant_id = request.GET.get('participant_id')
    recommendation_id = request.GET.get('recommendation_id')
    data_type = request.GET.get('data_type', 'all')  # all, recommendation_times, avatar_clicks, etc.
    
    # Build filters
    filters = {}
    if participant_id:
        filters['participant_id'] = participant_id
    if recommendation_id:
        filters['recommendation_id'] = recommendation_id
    
    # Convert to CSV
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    if data_type == 'recommendation_times' or data_type == 'all':
        # Recommendation times
        writer.writerow(['RECOMMENDATION TIMES'])
        writer.writerow(['id', 'participant_id', 'recommendation_id', 'started_at', 'ended_at', 'duration_seconds', 'session_id'])
        
        for record in RecommendationTimeSpent.objects.filter(**filters).select_related('participant', 'recommendation'):
            writer.writerow([
                record.id, record.participant.id, record.recommendation.id,
                record.started_at, record.ended_at, record.duration_seconds, record.session_id
            ])
        writer.writerow([])
    
    if data_type == 'avatar_clicks' or data_type == 'all':
        # Avatar clicks
        writer.writerow(['AVATAR CLICKS'])
        writer.writerow(['id', 'participant_id', 'recommendation_id', 'clicked_participant_id', 'avatar_type', 'timestamp', 'click_x', 'click_y', 'session_id'])
        
        for record in AvatarClick.objects.filter(**filters).select_related('participant', 'recommendation', 'clicked_participant'):
            writer.writerow([
                record.id, record.participant.id, record.recommendation.id,
                record.clicked_participant.id, record.avatar_type, record.timestamp,
                record.click_x, record.click_y, record.session_id
            ])
        writer.writerow([])
    
    if data_type == 'profile_times' or data_type == 'all':
        # Profile times
        writer.writerow(['PROFILE TIMES'])
        writer.writerow(['id', 'participant_id', 'recommendation_id', 'viewed_participant_id', 'started_at', 'ended_at', 'duration_seconds', 'session_id'])
        
        for record in ParticipantProfileTime.objects.filter(**filters).select_related('participant', 'recommendation', 'viewed_participant'):
            writer.writerow([
                record.id, record.participant.id, record.recommendation.id,
                record.viewed_participant.id, record.started_at, record.ended_at,
                record.duration_seconds, record.session_id
            ])
        writer.writerow([])
    
    if data_type == 'audio_sessions' or data_type == 'all':
        # Audio sessions
        writer.writerow(['AUDIO SESSIONS'])
        writer.writerow(['id', 'participant_id', 'recommendation_id', 'audio_clip_id', 'started_at', 'ended_at', 'duration_seconds', 'total_audio_duration', 'listened_duration', 'completion_percentage', 'play_count', 'pause_count', 'seek_count', 'session_id'])
        
        for record in AudioClipListening.objects.filter(**filters).select_related('participant', 'recommendation', 'audio_clip'):
            writer.writerow([
                record.id, record.participant.id, record.recommendation.id,
                record.audio_clip.id, record.started_at, record.ended_at,
                record.duration_seconds, record.total_audio_duration, record.listened_duration,
                record.completion_percentage, record.play_count, record.pause_count,
                record.seek_count, record.session_id
            ])
        writer.writerow([])
    
    if data_type == 'voting_times' or data_type == 'all':
        # Voting times
        writer.writerow(['VOTING TIMES'])
        writer.writerow(['id', 'participant_id', 'recommendation_id', 'started_at', 'ended_at', 'duration_seconds', 'session_id'])
        
        for record in VotingScreenTime.objects.filter(**filters).select_related('participant', 'recommendation'):
            writer.writerow([
                record.id, record.participant.id, record.recommendation.id,
                record.started_at, record.ended_at, record.duration_seconds, record.session_id
            ])
    
    # Return CSV response
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="telemetry_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    return response



@csrf_exempt
@require_POST
def submit_decision_feedback(request, terminal_rec_id=76):
    """
    Handle submission of decision feedback via AJAX.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Authentication required.'}, status=403)
    
    try:
        data = json.loads(request.body)
        recommendation_id = data['recommendation_id']
        decision_outcome = data['decision_outcome']
        feedback_responses = data['feedback_responses']
        condition = data['condition']
        recommendation = Recommendation.objects.get(id=recommendation_id)
        
        # Save or update decision feedback
        feedback, created = DecisionFeedback.objects.update_or_create(
            recommendation=recommendation,
            participant=request.user,
            defaults={
                'decision_outcome': decision_outcome,
                'trust_decision': feedback_responses['trust_decision'],
                'input_valuable': feedback_responses['input_valuable'],
                'willing_abide': feedback_responses['willing_abide'],
                'understand_others': feedback_responses['understand_others'],
                'share_values': feedback_responses['share_values'],
                'confident_vote': feedback_responses['confident_vote'],
            }
        )
        
        # Check if this is one of the randomized recommendations (74, 75, 76)
        if recommendation_id in [74, 75, 76]:
            # Advance to next recommendation in the randomized order
            if advance_to_next_recommendation(request):
                # There's a next recommendation in the randomized order
                next_recommendation_id = get_current_recommendation(request)
                
                return JsonResponse({
                    'success': True,
                    'redirect_url': f'/recommendations/{next_recommendation_id}/'
                })
            else:
                # Completed all recommendations in the randomized order
                #treatment_url = f"https://mit.co1.qualtrics.com/jfe/form/SV_9vsoCyYrtbAcRee"
                treatment_url = "https://mit.co1.qualtrics.com/jfe/form/SV_d0BW6PrAM4Ltg7c"
                #control_url = f"https://mit.co1.qualtrics.com/jfe/form/SV_3rZAGKFsiFYJoTs"
                control_url = "https://mit.co1.qualtrics.com/jfe/form/SV_7VRZPx2cu9BOoFo"
                
                if condition == "treatment":
                    redirect_url = treatment_url
                else:
                    redirect_url = control_url
                return JsonResponse({
                    'success': True, 
                    'redirect_url': f'{redirect_url}?PROLIFIC_PID={request.user.prolific_id}'
                })
        else:
            # For other recommendations, use the original logic
            next_recommendation_id = int(recommendation_id) + 1
            try:
                if next_recommendation_id > terminal_rec_id:
                    return JsonResponse({
                        'success': True, 
                        'redirect_url': f'{redirect_url}?PROLIFIC_PID={request.user.prolific_id}'
                    })
                else:
                    next_recommendation = Recommendation.objects.get(id=next_recommendation_id)
                    return JsonResponse({
                        'success': True,
                        'redirect_url': f'/recommendations/{next_recommendation_id}/'
                    })
            except Recommendation.DoesNotExist:
                return JsonResponse({
                    'success': True,
                    'redirect_url': '/'
                })
        
    except (Recommendation.DoesNotExist, KeyError, json.JSONDecodeError) as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': 'An error occurred while saving feedback.'}, status=500)


def calculate_leaderboard_for_base_rec(base_rec_id, participant_username=None):
    """
    Calculate leaderboard data for all recommendations derived from a base recommendation
    OPTIMIZED: Uses single query with database aggregation
    """
    from django.db.models import Avg, Count, Q
    
    try:
        # Build query filters
        rec_filter = Q(base_rec_id=base_rec_id) | Q(id=base_rec_id)
        
        # Add user filter at database level if provided
  
        rec_filter &= Q(participant_who_edited__username=participant_username)
        
        # Single optimized query with database aggregation
        recommendations = Recommendation.objects.filter(
            rec_filter
        ).select_related(
            'participant_who_edited'
        ).annotate(
            # Calculate average agreement and count of valid predictions
            avg_agreement=Avg('live_predictions__predicted_agreement'),
            summary_count=Count('live_predictions', 
                               filter=Q(live_predictions__predicted_agreement__isnull=False))
        ).filter(
            # Only include recommendations that have summaries with predictions
            summary_count__gt=0
        ).order_by('-id')  # Order by ID (higher ID = more recent)
        
        # Build leaderboard data efficiently
        leaderboard_data = []
        latest_rec_id = recommendations.first().id if recommendations.exists() else None
        
        for rec in recommendations:
            # Create preview text
            #text_preview = rec.rec_text[:150] + "..." if len(rec.rec_text) > 150 else rec.rec_text
            text_preview = rec.rec_text
            leaderboard_data.append({
                'recommendation_id': rec.id,
                'mean_support': round(rec.avg_agreement, 1) if rec.avg_agreement else 0,
                'total_predictions': rec.summary_count,
                'editor_name': rec.participant_who_edited.username if rec.participant_who_edited else 'Original',
                'editor_id': rec.participant_who_edited.id if rec.participant_who_edited else None,
                'rec_text': text_preview,
                'is_original': rec.participant_who_edited is None,
                'is_latest': rec.id == latest_rec_id,
                'rec_id_for_sorting': rec.id  # Use ID for recent sorting since no created_at field
            })
        
        return leaderboard_data
        
    except Exception as e:
        print(f"Error calculating leaderboard: {str(e)}")
        return []


def recommendation_editor(request, recommendation_id):
    """
    View for the dynamic recommendation editor page
    """
    if not request.user.is_authenticated:
        return redirect("login")

    # Check for control condition (pass ?condition=control in URL to hide avatars)
    # Treatment (default): show_avatars=True - avatars visible
    # Control: show_avatars=False - no avatars, but predictions still work
    #show_avatars = request.GET.get('condition') != 'control'
    show_avatars = settings.SHOW_AVATARS
    print("SHOW AVATARS: ", show_avatars)
    try:
        recommendation = Recommendation.objects.get(id=recommendation_id)
        
        # Get all participants with existing summaries for this recommendation
        summaries = LivePrediction.objects.filter(
            recommendation=recommendation
        ).select_related('participant').annotate(
            quality_score=Subquery(
                Medley.objects.filter(
                    recommendation=OuterRef('recommendation'),
                    participant=OuterRef('participant')
                ).values('quality_score')[:1]
            )
        )
        
        participant_data = []
        for summary in summaries:
            participant = summary.participant
            avatar_url = participant.get_avatar_url()
            print(participant.display_name)
            if participant.display_name == "Savannah":
                print("DEBUG: Participant: ", summary.predicted_agreement)
            print(summary.predicted_agreement)
            print(summary.confidence_score)
            participant_data.append({
                "username": participant.username,
                "display_name": participant.display_name,
                "predicted_agreement": summary.predicted_agreement,
                "confidence_score": summary.confidence_score,
                "quality_score": summary.quality_score if summary.quality_score else 0,
                "avatar_url": avatar_url,
            })
        
        # Generate meta-medleys
        meta_medleys = generate_default_meta_medleys(recommendation_id)
       # print("DEBUG: Participant data: ", participant_data["Savannah"])
        context = {
            "recommendation": recommendation,
            "participant_data": participant_data,
            "original_text": recommendation.rec_text,
            "ai_rec_text": recommendation.ai_rec_text,
            "ai_predicted_support": recommendation.ai_predicted_support,
            "show_avatars": show_avatars,
            "meta_medleys": meta_medleys,
        }
        
        return render(request, "pages/recommendations/recommendation_editor.html", context)
        
    except Recommendation.DoesNotExist:
        return HttpResponseNotFound("Recommendation not found")


def process_single_participant(username, new_rec_text, base_recommendation):
    """
    Process a single participant with new recommendation text
    Returns participant data for streaming response
    """
    try:
        participant = Participant.objects.get(username=username)
        display_name = participant.display_name or username
        
        # Ensure avatar URL is always available
        try:
            avatar_url = participant.get_avatar_url()
        except Exception as e:
            print(f"Error getting avatar URL for {username}: {e}")
            avatar_url = '/static/assets/img/avatars/default.png'
        
        # Import the prediction generator
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent
        sys.path.insert(0, str(project_root))
        
        from generating_v2.rec_prediction import RecommendationPredictionGenerator
        from generating_v2.medley_individual import MedleyGenerator
        # Initialize generator
        generator = RecommendationPredictionGenerator()
        medley_generator = MedleyGenerator()
        # Process with new recommendation text (using fast optimized version)
        result = generator.process_participant_recommendation_fast(
            username, new_rec_text, display_name
        )
        interview_id = Interview.objects.get(participant=participant).id
        medley_result = medley_generator.create_medley(interview_id=interview_id, rec_text=new_rec_text)
        # Calculate quality score
        quality_score = None
        if medley_result['quality_analysis']:
            quality_score = medley_generator.calculate_quality_score(
                medley_result['quality_analysis']['opinion_vs_experiences'],
                medley_result['quality_analysis']['relevance_score'],
                medley_result['quality_analysis']['depth_score']
            )
        print(f"DEBUG: Medley result: {medley_result}")
        print(f"DEBUG: Result: {result}")
        return {
            "status": "success",
            "username": username,   
            "display_name": display_name,
            "predicted_agreement": result["prediction"]["predicted_agreement"],
            "confidence_score": result["prediction"]["confidence_score"],
            "quality_score": quality_score,
            "reasoning": result["prediction"]["reasoning"],
            "avatar_url": avatar_url,
            "medley_result": medley_result,
        }
        
    except Exception as e:
        return {
            "status": "error",
            "username": username,
            "error": str(e)
        }

@csrf_exempt
def recompute_recommendation_stream(request, recommendation_id):
    """
    Streaming API endpoint for parallel recommendation recomputation
    Uses Server-Sent Events to send real-time updates
    """
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)
    
    def event_stream():
        try:
            # Get recommendation text from GET parameter for EventSource compatibility
            new_rec_text = request.GET.get('rec_text', '').strip()
            
            if not new_rec_text:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Recommendation text is required'})}\n\n"
                return
            
            base_recommendation = Recommendation.objects.get(id=recommendation_id)
            
            # Find the true base recommendation (original) to maintain consistent lineage
            true_base_recommendation = base_recommendation.base_rec or base_recommendation
            
            # Create a new recommendation with the edited text, always pointing to the original base
            new_recommendation = Recommendation.objects.create(
                rec_text=new_rec_text,
                base_rec=true_base_recommendation,
                participant_who_edited=request.user
            )
            
            # Send initial status
            yield f"data: {json.dumps({'type': 'started', 'new_recommendation_id': new_recommendation.id})}\n\n"
            participant_data = pd.read_csv("data/all_df_clean_pass_concept_measures_joined.csv")
            participant_data = participant_data[participant_data["assignment"].isin(["treatment", "control"])]
            participant_data = participant_data["PROLIFIC_PID"].tolist()
            participants_with_data = Participant.objects.filter(
                username__in=participant_data
            ).distinct()
            # Filter to only participants who have completed interviews
            participants_with_data = [p for p in participants_with_data if p.has_completed_interview]
            from random import sample
            participant_usernames = [p.username for p in participants_with_data]
            #participant_ids = [p.id for p in participants_with_data]
            #print(participant_ids)
            total_participants = len(participant_usernames)
            
            yield f"data: {json.dumps({'type': 'total_count', 'total': total_participants})}\n\n"
            
            completed_count = 0
            successful_results = []
            
            # Process participants in parallel (max 16 concurrent)
            with ThreadPoolExecutor(max_workers=min(16, total_participants)) as executor:
                # Submit all tasks
                future_to_participant = {
                    executor.submit(process_single_participant, username, new_rec_text, base_recommendation): username 
                    for username in participant_usernames
                }
                
                # Process completed results as they come in
                for future in as_completed(future_to_participant):
                    participant_username = future_to_participant[future]
                    
                    try:
                        result = future.result()
                        completed_count += 1
                        
                        if result['status'] == 'success':
                            # Debug logging
                            print(f"DEBUG: Processing successful result for {result['username']}")
                            print(f"DEBUG: Avatar URL: {result.get('avatar_url', 'NOT_FOUND')}")
                            
                            # Save to database
                            participant = Participant.objects.get(username=result['username'])
                            medley_data = result['medley_result']

                            with transaction.atomic():
                                # Calculate quality score from quality_analysis
                                quality_score = result.get('quality_score')

                                # Create Medley object
                                medley = Medley.objects.create(
                                    recommendation=new_recommendation,
                                    participant=participant,
                                    total_duration=medley_data['total_duration'],
                                    gpt_estimated_duration=medley_data['gpt_estimated_duration'],
                                    segment_count=medley_data['segment_count'],
                                    gpt_reasoning=medley_data['gpt_reasoning'],
                                    reordered=medley_data['reordered'],
                                    recommendation_text=medley_data['recommendation_text'],
                                    quality_score=quality_score
                                )

                                # Add segments to ManyToMany relationship
                                segment_ids = [seg['segment_id'] for seg in medley_data['segments']]
                                segments = InterviewSegment.objects.filter(id__in=segment_ids)
                                medley.segments.set(segments)

                                # Find corresponding utterances for each segment
                                utterance_list = []
                                for segment in segments:
                                    # Get the audio_id from the segment's audio
                                    audio_id = segment.audio.id
                                    # Find InterviewUtterances that match this audio_id
                                    utterances = InterviewUtterance.objects.filter(audio_id=audio_id)
                                    utterance_list.extend(utterances)

                                # Add utterances to ManyToMany relationship
                                if utterance_list:
                                    medley.utterances.set(utterance_list)

                                # Create LivePrediction object
                                live_prediction = LivePrediction.objects.create(
                                    recommendation=new_recommendation,
                                    participant=participant,
                                    predicted_agreement=result['predicted_agreement'],
                                    confidence_score=result['confidence_score'],
                                    reasoning=result['reasoning']
                                )
       
                            
                            successful_results.append(result)
                            
                            # Send participant update
                            yield f"data: {json.dumps({'type': 'participant_update', 'participant': result, 'completed': completed_count, 'total': total_participants})}\n\n"
                        
                        else:
                            # Send error for this participant
                            yield f"data: {json.dumps({'type': 'participant_error', 'username': result['username'], 'error': result['error'], 'completed': completed_count, 'total': total_participants})}\n\n"
                    
                    except Exception as e:
                        completed_count += 1
                        yield f"data: {json.dumps({'type': 'participant_error', 'username': participant_username, 'error': str(e), 'completed': completed_count, 'total': total_participants})}\n\n"
            
            # Ensure all database transactions are committed before calculating leaderboard
            from django.db import connection
            connection.close()  # Force close connection to ensure all commits are processed
            
            # Small delay to ensure database consistency
            import time
            time.sleep(0.1)
            
            # Get leaderboard data for completion message using the true base recommendation
            leaderboard_data = calculate_leaderboard_for_base_rec(true_base_recommendation.id)
            
            # Send completion message with leaderboard
            yield f"data: {json.dumps({'type': 'completed', 'successful_count': len(successful_results), 'total': total_participants, 'new_recommendation_id': new_recommendation.id, 'leaderboard': leaderboard_data})}\n\n"
            
        except Recommendation.DoesNotExist:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Recommendation not found'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['Access-Control-Allow-Origin'] = '*'
    return response


def get_meta_medley_panel(request, recommendation_id, medley_type):
    """
    API endpoint to get meta-medley panel content for bottom/middle/top groups.
    
    Args:
        medley_type: 'bottom' | 'middle' | 'top'
    """
    try:
        from pages.models import MetaMedley, LivePrediction, InterviewSegment
        
        recommendation = Recommendation.objects.get(id=recommendation_id)
        
        # Generate or get cached meta-medleys
        meta_medleys = generate_default_meta_medleys(recommendation_id, medley_type)
        meta_medley = meta_medleys.get(medley_type)
        
        if not meta_medley:
            return JsonResponse({'error': f'No meta-medley found for {medley_type}'}, status=404)
        
        # Get participant data with support scores
        participants_data = []
        participants_lookup = {}
        for participant in meta_medley.participants.all():
            prediction = LivePrediction.objects.filter(
                recommendation=recommendation,
                participant=participant
            ).first()
            
            # Get individual medley
            individual_medley = Medley.objects.filter(
                recommendation=recommendation,
                participant=participant
            ).order_by('-id').first()
            
            participant_entry = {
                'username': participant.username,
                'display_name': participant.display_name or participant.username,
                'avatar_url': participant.get_avatar_url(),
                'support': prediction.predicted_agreement if prediction else None,
                'individual_medley_duration': individual_medley.total_duration if individual_medley else None,
                'individual_medley_id': individual_medley.id if individual_medley else None,
                'segments': []
            }
            participants_data.append(participant_entry)
            participants_lookup[participant.username] = participant_entry
        
        # Sort by support
        participants_data.sort(key=lambda x: x['support'] if x['support'] is not None else -1)
        
        utterance_cache = {}
        utterance_audio_cache = {}
        
        # Build segment data for meta-medley playback and grouped quotes
        segments_data = []
        for seg_info in meta_medley.selected_segments:
            segment = InterviewSegment.objects.get(id=seg_info['segment_id'])
            
            # Parent utterance lookup (expanded quote + full audio)
            parent_utterance = None
            if segment.audio_id:
                if segment.audio_id not in utterance_cache:
                    parent_utterance = InterviewUtterance.objects.filter(audio_id=segment.audio_id).order_by('sequence_number').first()
                    utterance_cache[segment.audio_id] = parent_utterance
                else:
                    parent_utterance = utterance_cache[segment.audio_id]
            
            if parent_utterance:
                expanded_text = parent_utterance.utterance_text
                if parent_utterance.audio_id not in utterance_audio_cache:
                    utterance_audio_cache[parent_utterance.audio_id] = f"InterviewAudios/interview{parent_utterance.question.interview.id}/module{parent_utterance.question.module.id}/question{parent_utterance.question.id}/user_{parent_utterance.audio_id}.wav"
                quote_audio_url = utterance_audio_cache[parent_utterance.audio_id]
            else:
                expanded_text = segment.segment_text
                quote_audio_url = None
            
            # Audio for sequential playback (segment-level)
            if segment.segment_audio_file and segment.segment_audio_file.name:
                playback_audio_url = segment.segment_audio_file.name
            else:
                playback_audio_url = segment.get_s3_path()
            
            segment_entry = {
                'segment_id': seg_info['segment_id'],
                'participant_username': seg_info['participant_username'],
                'order': seg_info['order'],
                'text': segment.segment_text,
                'expanded_text': expanded_text,
                'duration': segment.duration,
                'audio_url': playback_audio_url,
                'quote_audio_url': quote_audio_url,
                'participant_display_name': participants_lookup.get(seg_info['participant_username'], {}).get('display_name', seg_info['participant_username'])
            }
            segments_data.append(segment_entry)
            
            participant_bucket = participants_lookup.get(seg_info['participant_username'])
            if participant_bucket is not None:
                participant_bucket['segments'].append({
                    'segment_id': seg_info['segment_id'],
                    'text': segment.segment_text,
                    'expanded_text': expanded_text,
                    'duration': segment.duration,
                    'audio_url': quote_audio_url,
                    'order': seg_info['order']
                })
        
        # Sort grouped segments by order for consistency
        for participant_entry in participants_data:
            participant_entry['segments'].sort(key=lambda x: x['order'])
        
        # Sort by order for playback
        segments_data.sort(key=lambda x: x['order'])
        
        # Calculate support range
        support_scores = [p['support'] for p in participants_data if p['support'] is not None]
        support_range = f"{min(support_scores):.0f}-{max(support_scores):.0f}%" if support_scores else "N/A"
        
        # Determine title and styling based on type
        medley_info = {
            'bottom': {
                'title': 'Against',
                'icon': 'fa-thumbs-down',
                'color': '#ff6b6b',
            },
            'middle': {
                'title': 'On the fence', 
                'icon': 'fa-balance-scale',
                'color': '#ffa726',
            },
            'top': {
                'title': 'For',
                'icon': 'fa-thumbs-up',
                'color': '#66bb6a',
            }
        }
        
        context = {
            'meta_medley': meta_medley,
            'medley_type': medley_type,
            'medley_info': medley_info[medley_type],
            'participants_data': participants_data,
            'participants_data_json': json.dumps(participants_data),
            'segments_data': segments_data,
            'segments_data_json': json.dumps(segments_data),
            'support_range': support_range,
            'participant_count': len(participants_data),
            'segment_count': len(segments_data),
            'recommendation': recommendation,
            'MEDIA_URL': settings.MEDIA_URL,
        }
        
        return render(request, 'pages/recommendations/meta_medley_panel.html', context)
        
    except Exception as e:
        print(f"Error in get_meta_medley_panel: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


def get_medley_participant_modal(request, recommendation_id, participant_username):
    """
    API endpoint to get medley modal content showing LivePrediction and Medley data
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)

    try:
        recommendation = Recommendation.objects.get(id=recommendation_id)
        participant = Participant.objects.get(username=participant_username)

        # Get Medley object with prefetched relationships (latest if multiple exist)
        medley = Medley.objects.prefetch_related(
            'segments__audio__question__interview',
            'segments__audio__question__module',
            'utterances__question__interview',
            'utterances__question__module'
        ).filter(recommendation=recommendation, participant=participant).order_by('-id').first()

        # Get LivePrediction
        try:
            live_prediction = LivePrediction.objects.get(
                recommendation=recommendation,
                participant=participant
            )
        except LivePrediction.DoesNotExist:
            live_prediction = None

        # Build segment data with audio URLs
        segments_data = []
        if medley:
            for segment in medley.segments.all().order_by('sequence_number'):
                # Try segment_audio_file first, otherwise use get_s3_path()
                audio_url = None
                if segment.segment_audio_file:
                    audio_url = segment.segment_audio_file.name
                else:
                    # Use the get_s3_path method which constructs the proper path
                    audio_url = segment.get_s3_path()

                segments_data.append({
                    'text': segment.segment_text,
                    'audio_url': audio_url,
                    'duration': segment.duration,
                    'sequence': segment.sequence_number
                })

        # Build utterance data with audio URLs
        utterances_data = []
        if medley:
            for utterance in medley.utterances.all().order_by('question__global_question_id', 'sequence_number'):
                audio_url = None
                if utterance.audio_id:
                    audio_url = f"InterviewAudios/interview{utterance.question.interview.id}/module{utterance.question.module.id}/question{utterance.question.id}/user_{utterance.audio_id}.wav"

                utterances_data.append({
                    'text': utterance.utterance_text,
                    'audio_url': audio_url,
                    'audio_id': utterance.audio_id,
                    'is_interviewer': utterance.is_interviewer
                })

        # Get basic participant info
        avatar_url = participant.get_avatar_url()

        # Create stitched medley text
        stitched_medley_text = " ... ".join([seg['text'] for seg in segments_data]) if segments_data else ""

        # Get support percentage
        support_percentage = live_prediction.predicted_agreement if live_prediction else None

        # Build context for template rendering
        context = {
            'recommendation': recommendation,
            'data': {
                'participant': participant,
                'avatar_url': avatar_url,
                'medley': medley,
                'live_prediction': live_prediction,
                'segments_data': segments_data,
                'utterances_data': utterances_data,
                'stitched_medley_text': stitched_medley_text,
                'support_percentage': support_percentage,
            }
        }

        # Add MEDIA_URL to the context
        context['MEDIA_URL'] = settings.MEDIA_URL
        modal_html = render_to_string('pages/recommendations/medley_modal_content.html', context, request=request)

        return JsonResponse({
            'modal_html': modal_html,
            'participant_id': participant.id,
            'participant_name': participant.get_full_name()
        })

    except Recommendation.DoesNotExist:
        return JsonResponse({'error': 'Recommendation not found'}, status=404)
    except Participant.DoesNotExist:
        return JsonResponse({'error': 'Participant not found'}, status=404)
    except Exception as e:
        import traceback
        print(f"Error in get_medley_participant_modal: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)


def get_editor_participant_modal(request, recommendation_id, participant_username):
    """
    API endpoint to get participant modal content for the editor
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    try:
        recommendation = Recommendation.objects.get(id=recommendation_id)
        participant = Participant.objects.get(username=participant_username)
        
        # Get participant summary
        try:
            participant_summary = RecommendationParticipantSummary.objects.get(
                recommendation=recommendation,
                participant=participant
            )
        except RecommendationParticipantSummary.DoesNotExist:
            return JsonResponse({'error': 'Participant data not found'}, status=404)
        
        # Get narrative parts
        narrative = None
        participant_narrative = None
        
        try:
            narrative = Narrative.objects.select_related('participant').prefetch_related(
                'parts__utterance__question__interview',
                'parts__utterance__question__module'
            ).get(recommendation=recommendation, participant=participant)
            all_narrative_parts = narrative.parts.all()
        except Narrative.DoesNotExist:
            all_narrative_parts = []
            
        try:
            participant_narrative = ParticipantNarrative.objects.select_related('participant').prefetch_related(
                'parts__utterance__question__interview',
                'parts__utterance__question__module'
            ).get(participant=participant)
            all_participant_narrative_parts = participant_narrative.parts.all()
        except ParticipantNarrative.DoesNotExist:
            all_participant_narrative_parts = []
        
        # Build narrative parts data
        narrative_parts = []
        for part in all_narrative_parts:
            audio_url = None
            if part.utterance and part.utterance.audio_id:
                audio_url = f"InterviewAudios/interview{part.utterance.question.interview.id}/module{part.utterance.question.module.id}/question{part.utterance.question.id}/user_{part.utterance.audio_id}.wav"
            
            narrative_parts.append({
                'ai_explanation_text': part.ai_explanation_text,
                'utterance_text': part.utterance.utterance_text if part.utterance else None,
                'utterance_text_with_bold': part.utterance_text_with_bold if hasattr(part, 'utterance_text_with_bold') else None,
                'audio_url': audio_url,
                'audio_id': part.utterance.audio_id if part.utterance else None,
                'utterance': part.utterance
            })
            
        participant_narrative_parts = []
        for part in all_participant_narrative_parts:
            audio_url = None
            if part.utterance and part.utterance.audio_id:
                audio_url = f"InterviewAudios/interview{part.utterance.question.interview.id}/module{part.utterance.question.module.id}/question{part.utterance.question.id}/user_{part.utterance.audio_id}.wav"
            
            participant_narrative_parts.append({
                'ai_explanation_text': part.ai_explanation_text,
                'utterance_text': part.utterance.utterance_text if part.utterance else None,
                'utterance_text_with_bold': part.utterance_text_with_bold if hasattr(part, 'utterance_text_with_bold') else None,
                'audio_url': audio_url,
                'audio_id': part.utterance.audio_id if part.utterance else None,
                'utterance': part.utterance
            })
        
        # Get basic participant info
        avatar_url = participant.get_avatar_url()
        
        # Get previously saved reflection data (simplified for editor)
        try:
            connection_report = ConnectionReport.objects.get(
                participant=request.user,
                target_participant=participant,
                recommendation=recommendation
            )
        except ConnectionReport.DoesNotExist:
            connection_report = None
            
        try:
            vote_report = PredictedVoteReport.objects.get(
                participant=request.user,
                target_participant=participant,
                recommendation=recommendation
            )
        except PredictedVoteReport.DoesNotExist:
            vote_report = None
            
        # Get connection request status
        try:
            connection_request = ConnectionRequest.objects.get(
                from_user=request.user,
                to_user=participant,
                recommendation=recommendation
            )
        except ConnectionRequest.DoesNotExist:
            connection_request = None
        
        # Build context for template rendering
        context = {
            'recommendation': recommendation,
            'data': {
                'participant': participant,
                'avatar_url': avatar_url,
                'age': participant.age,
                'occupation': participant.occupation,
                'narrative_parts': narrative_parts,
                'participant_narrative_parts': participant_narrative_parts,
                'predicted_agreement': participant_summary.predicted_agreement,
                'relevance_score': participant_summary.relevance_score,
                'life_summary': participant_narrative.global_summary if participant_narrative else None,
                'rec_summary': narrative.global_summary if narrative else None,
                'reflection': {
                    'connection_score': connection_report.connection_score if connection_report else None,
                    'connection_text': connection_report.connection_text if connection_report else None,
                    'vote_prediction': vote_report.predicted_vote_score if vote_report else None,
                    'vote_explanation': vote_report.predicted_vote_text if vote_report else None,
                },
                'connection_request': connection_request,
            }
        }
        
        # Add MEDIA_URL to the context
        context['MEDIA_URL'] = settings.MEDIA_URL
        modal_html = render_to_string('pages/recommendations/participant_modal_content.html', context, request=request)
        
        return JsonResponse({
            'modal_html': modal_html,
            'participant_id': participant.id,
            'participant_name': participant.get_full_name()
        })
        
    except Recommendation.DoesNotExist:
        return JsonResponse({'error': 'Recommendation not found'}, status=404)
    except Participant.DoesNotExist:
        return JsonResponse({'error': 'Participant not found'}, status=404)
    except Exception as e:
        import traceback
        print(f"Error in get_editor_participant_modal: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)


def get_leaderboard(request, recommendation_id):
    """
    API endpoint to get leaderboard data for a recommendation
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    print("USER REQUESTED: ")
    print(request.user)
    try:
        recommendation = Recommendation.objects.get(id=recommendation_id)
        base_rec_id = recommendation.base_rec_id or recommendation.id
       
        
        # Calculate leaderboard data
        leaderboard_data = calculate_leaderboard_for_base_rec(base_rec_id, request.user.username)
        
        return JsonResponse({
            'success': True,
            'leaderboard_data': leaderboard_data,
            'current_recommendation_id': recommendation.id,
            'current_user_id': request.user.id
        })
        
    except Recommendation.DoesNotExist:
        return JsonResponse({'error': 'Recommendation not found'}, status=404)
    except Exception as e:
        print(f"Error in get_leaderboard: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

