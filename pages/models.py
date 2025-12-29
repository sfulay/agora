import uuid
import random
import string
import json
import base64
import io
import string

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser
from django.core.files.base import ContentFile
from django.core.files import File
from django.core.files.storage import default_storage as storage
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from pydub import AudioSegment
from global_methods import *
from datetime import datetime
from django.contrib.postgres.fields import ArrayField

from pages.models import *
from .interview_settings import *

# Number of expected words in a second
wordpsec = 1.5


def jsp_log(message): 
  from datetime import datetime
  formatted_time = datetime.now().strftime("%H:%M:%S")
  print (f'[models.py] {formatted_time} -- {message}')


def process_audio(base64_message, audio_format):
  # Ensure audio_format is lowercased for consistency
  audio_format = audio_format.lower()
  # Modify format for MP4 audio
  jsp_log(f"Currently received audio format: {audio_format}")
  if audio_format in ['mp4', 'audio/mp4']:
    audio_format = 'mp4'  # FFmpeg recognizes 'mp4' for MP4 audio files
  elif audio_format in ['webm', 'audio/webm']:
    audio_format = 'webm'  # Add support for WebM format
  else: 
    audio_format

  base64_message = base64_message.split(",")[1]
  # Step 1: Decode the base64 string to bytes
  base64_bytes = base64.b64decode(base64_message)

  # Step 2: Convert the binary data to a BytesIO object (in-memory buffer)
  audio_data = io.BytesIO(base64_bytes)

  # Step 3: Read the audio from BytesIO, then convert & export it as WAV
  # The format is dynamically set based on the audio_format argument
  audio = AudioSegment.from_file(audio_data, format=audio_format)
  # Ensure audio is set to 16-bit samples (sample_width=2 bytes for 16 bit)
  audio = audio.set_sample_width(2)
  # Optional: Set a frame rate. Common rates: 16000, 44100, etc.
  audio = audio.set_frame_rate(16000)

  # Step 4: Export as 16-bit PCM WAV
  # mono channel, 16000 Hz
  buffer = io.BytesIO()
  audio.export(buffer, format="wav", parameters=["-ac", "1", "-ar", "16000"])
  buffer.seek(0)
  return buffer


class PerfMeasurement(models.Model):
  participant = models.ForeignKey('Participant', on_delete=models.CASCADE)
  details = models.TextField(blank=False, null=False, default="")
  start_time = models.DateTimeField(blank=False, null=False, auto_now_add=True)
  end_time = models.DateTimeField(blank=True, null=True)
  sec_passed = models.IntegerField(blank=False, null=False, default=0)

  def record(self, details_dict):
    self.end_time = timezone.now()
    elapsed_time = self.end_time - self.start_time
    self.sec_passed = int(elapsed_time.total_seconds())

    # Convert details_dict to a JSON string and store in details
    self.details = json.dumps(details_dict)

    # Save the changes to the database
    self.save()


class InterviewAudio(models.Model):
  # Foreign key to an InterviewQuestion instance. 
  question = models.ForeignKey('InterviewQuestion', on_delete=models.CASCADE)
  # This is true if this audio captures the interviewee's voice. It is false
  # otherwise (if it is the agent speaking). 
  user_speech = models.BooleanField(blank=False, null=False, default=False)
  # The audio file that is stored in the media storage. 
  audio_file = models.FileField(upload_to="InterviewAudios/")
  # Time of creation.
  created = models.DateTimeField(auto_now_add=True)


class InterviewQuestion(models.Model): 
  # The current question ID. This is an integer that starts from 1. 
  # Note that this is the global ID -- so it increments by counting the number
  # of questions that the interviewee has responded to globally. 
  question_id = models.IntegerField(blank=False, null=False, default=1)
  # The number of questions that we've administered so far. This is to 
  # uniquely retrieve and order the questions for analysis. 
  global_question_id = models.IntegerField(blank=False, null=False, default=1)
  # ForeignKeys to the Interview and Module instances. 
  interview = models.ForeignKey('Interview', on_delete=models.CASCADE)
  module = models.ForeignKey('InterviewModule', on_delete=models.CASCADE)
  # The main interview script defined variable for the question. 
  q_content = models.TextField(blank=False, null=False, default="")
  q_type = models.CharField(max_length=255, blank=False, null=False)
  q_requirement = models.TextField(blank=False, null=False, default="")
  q_condition = models.TextField(blank=False, null=False, default="")
  q_max_sec = models.FloatField(blank=False, null=False, default=1)
  # A comma separated list of audio ids that match the ordering of the 
  # q_content. e.g., aodishfj, aodg4adf,...  
  q_content_audio_ids = models.TextField(blank=False, null=False, default="")
  # This is the variable that stores the conversation. It is in a string 
  # format as below: 
  # Interviewer (Isabella): "Hello!"
  # Interviewee: "Hi"
  # ... And so on. 
  convo = models.TextField(blank=False, null=False, default="")
  # This turns True when the current question has ended. 
  completed = models.BooleanField(blank=False, null=False, default=False)
  # Time of creation.
  created = models.DateTimeField(auto_now_add=True)

  class Meta:
    # Defining the unique constraint for the question.
    constraints = [
      models.UniqueConstraint(fields=['question_id', 'interview', 'module'], 
                              name='unique_question_details')
    ]


  def convo_word_count(self):
    """
    Count the number of words that were uttered by the interviewee in this 
    conversation. 

    Parameters:
      None
    Returns: 
      word_count: <int> of the word_count
    """
    # We first translate the list of list self.convo into a string. This is 
    # basically done by counting the number of words that were uttered by the
    # interviewee (does not count the interviewer's utterance). 
    curr_utterances = ""
    rows = self.convo.split("\n")

    for r in rows: 
      if r[:len("interviewee")].lower() == "interviewee": 
        curr_utterances += f"{r} "
    word_count = len(curr_utterances.split())
    return word_count


  def max_sec_passed(self): 
    """
    This function calculates how many seconds have passed since the 
    conversation has started, and determine whether the max_sec has passed. 
    Note that the max_sec is manually defined in the interview script. 

    Parameters:
      None
    Returns: 
      <bool>: True if max_sec is passed. False otherwise. 
    """
    # We use a heuristics here -- we assume that a person can utter x words
    # per second, and this x is defined by the variable "wordpsec". 
    word_count = self.convo_word_count()
    if self.q_max_sec * wordpsec < word_count: 
      return True
    return False    


  def num_sec_passed(self): 
    """
    Count the number of seconds passed in the current question.

    Parameters:
      None
    Returns: 
      <bool>: True if max_sec is passed. False otherwise. 
    """
    # We use a heuristics here -- we assume that a person can utter x words
    # per second, and this x is defined by the variable "wordpsec". 

    sec_passed = self.convo_word_count()/wordpsec
    if sec_passed > self.q_max_sec: 
      sec_passed = self.q_max_sec
    return sec_passed


  def last_utt_num_sec_passed(self): 
    """
    Count the number of seconds passed in the current question.

    Parameters:
      None
    Returns: 
      <bool>: True if max_sec is passed. False otherwise. 
    """
    curr_utterances = ""
    rows = [self.convo.strip().split("\n")[-1]]
    for r in rows: 
      if r[:len("interviewee")].lower() == "interviewee": 
        curr_utterances += f"{r} "
    word_count = len(curr_utterances.split())

    sec_passed = word_count/wordpsec
    if sec_passed > self.q_max_sec: 
      sec_passed = self.q_max_sec
    return sec_passed


class InterviewUtterance(models.Model):
  """
  Model to store both interviewer and interviewee utterances and their associated audio IDs for each question.
  This provides a more structured way to access speech compared to parsing the convo field.
  """
  # Link to the associated InterviewQuestion
  question = models.ForeignKey('InterviewQuestion', on_delete=models.CASCADE, related_name='utterances')
  
  # The actual text of the utterance
  utterance_text = models.TextField(blank=False, null=False)
  
  # The audio ID associated with this utterance
  audio_id = models.IntegerField(blank=True, null=True)
  
  # Whether this is an interviewer (True) or interviewee (False) utterance
  is_interviewer = models.BooleanField(blank=False, null=False)
  
  # Whether this utterance should be redacted
  is_redacted = models.BooleanField(blank=False, null=False, default=False)
  
  # Order of utterance within the question
  sequence_number = models.IntegerField(blank=False, null=False, default=0)
  
  # Time of creation
  created = models.DateTimeField(auto_now_add=True)

  class Meta:
    ordering = ['sequence_number']
    
  def __str__(self):
    speaker = "Interviewer" if self.is_interviewer else "Interviewee"
    return f"{speaker} utterance {self.sequence_number} for Question {self.question.question_id}"


class Medley(models.Model):
  """
  Model to store 60-second audio medleys created from interview segments.
  A medley is a curated selection of interview segments that create a cohesive
  narrative about a participant's perspective on a specific recommendation.
  """
  # Link to the recommendation this medley is about
  recommendation = models.ForeignKey('Recommendation', on_delete=models.CASCADE, related_name='medleys', blank=True, null=True)

  # The participant whose interview this medley is from
  participant = models.ForeignKey('Participant', on_delete=models.CASCADE, related_name='medleys')

  # Selected segments in this medley (ManyToMany to preserve order)
  segments = models.ManyToManyField('InterviewSegment', related_name='medleys', blank=True)

  # Optional: utterances included in this medley
  utterances = models.ManyToManyField('InterviewUtterance', related_name='medleys', blank=True)

  # Total duration of the medley in seconds
  total_duration = models.FloatField(blank=False, null=False, default=0.0, help_text="Actual total duration in seconds")

  # GPT's estimated duration (may differ slightly from actual)
  gpt_estimated_duration = models.FloatField(blank=True, null=True, help_text="GPT's estimated duration in seconds")

  # Number of segments in the medley
  segment_count = models.IntegerField(blank=False, null=False, default=0)

  # GPT's reasoning for selecting these segments
  gpt_reasoning = models.TextField(blank=True, null=False, default="")

  # Whether the segments were reordered from their original sequence
  reordered = models.BooleanField(blank=False, null=False, default=False)

  # The recommendation text (stored for reference)
  recommendation_text = models.TextField(blank=True, null=False, default="")

  # Quality score for this medley
  quality_score = models.FloatField(
    validators=[MinValueValidator(0), MaxValueValidator(100)],
    null=True, blank=True,
    help_text="Quality score for the medley (0-100)"
  )

  # Timestamp when this medley was created
  created_at = models.DateTimeField(auto_now_add=True)

  class Meta:
    ordering = ['-created_at']
    verbose_name_plural = "Medleys"
    indexes = [
      models.Index(fields=['participant', 'recommendation']),
      models.Index(fields=['created_at']),
    ]

  def __str__(self):
    return f"Medley for {self.participant} - Recommendation {self.recommendation.id if self.recommendation else 'Custom'}"


class MetaMedley(models.Model):
  """
  Model to store meta-medleys: combined medleys from multiple participants.
  Created when a user selects a group of participants to see their collective perspective.
  """
  # Link to the recommendation this meta-medley is about
  recommendation = models.ForeignKey('Recommendation', on_delete=models.CASCADE, related_name='meta_medleys')
  
  # The participants included in this meta-medley (from top K by quality)
  participants = models.ManyToManyField('Participant', related_name='meta_medleys')
  
  # The source medleys used to create this meta-medley (top K individual medleys)
  source_medleys = models.ManyToManyField('Medley', related_name='meta_medleys')
  
  # Selected segments from across all participants
  # JSONField storing: [{"participant_username": "...", "segment_id": 123, "order": 1}, ...]
  selected_segments = models.JSONField(default=list, blank=True)
  
  # Total duration of the meta-medley in seconds (target: 60-90s)
  total_duration = models.FloatField(blank=False, null=False, default=0.0)
  
  # Number of segments in the meta-medley
  segment_count = models.IntegerField(blank=False, null=False, default=0)
  
  # GPT's reasoning for the narrative flow
  gpt_reasoning = models.TextField(blank=True, null=False, default="")
  
  # Cache key: hash of sorted participant usernames for deduplication
  participant_cache_key = models.CharField(max_length=100, blank=True, null=False, default="")
  
  # Version number for regenerations of the same participant set
  version = models.IntegerField(blank=False, null=False, default=1)
  
  # Timestamp when this meta-medley was created
  created_at = models.DateTimeField(auto_now_add=True)
  
  class Meta:
    ordering = ['-created_at']
    verbose_name_plural = "Meta Medleys"
    indexes = [
      models.Index(fields=['recommendation', 'participant_cache_key']),
      models.Index(fields=['created_at']),
    ]
  
  def __str__(self):
    participant_count = self.participants.count()
    return f"MetaMedley {self.id} - Rec {self.recommendation.id} - {participant_count} participants (v{self.version})"


class LivePrediction(models.Model):
  """
  Model to store live predictions about participant support for recommendations.
  Used during the recommendation deliberation process.
  """
  # Link to the recommendation this prediction is about
  recommendation = models.ForeignKey('Recommendation', on_delete=models.CASCADE, related_name='live_predictions')

  # The participant this prediction is for
  participant = models.ForeignKey('Participant', on_delete=models.CASCADE, related_name='live_predictions')

  # Predicted agreement level (0-100)
  predicted_agreement = models.IntegerField(
    validators=[MinValueValidator(0), MaxValueValidator(100)],
    help_text="Predicted agreement level (0-100)"
  )

  # Confidence in the prediction (0-100)
  confidence_score = models.IntegerField(
    validators=[MinValueValidator(0), MaxValueValidator(100)],
    help_text="Confidence in the prediction (0-100)"
  )

  # Reasoning for the prediction
  reasoning = models.TextField(
    help_text="Explanation for the predicted agreement level"
  )

  # Timestamp when this prediction was created
  created_at = models.DateTimeField(auto_now_add=True)

  class Meta:
    ordering = ['-created_at']
    unique_together = ('recommendation', 'participant')

  def __str__(self):
    return f"LivePrediction for {self.participant} on Rec #{self.recommendation.id} (Agreement: {self.predicted_agreement}%, Confidence: {self.confidence_score}%)"


class InterviewSegment(models.Model):
  """
  Model to store sentence-level segments of interview audio.
  Each segment represents a sentence with its own audio file.

  The audio files are stored with the following structure:
  InterviewAudios/interview{id}/module{id}/question{id}/user_{audio_id}/sentence_{seq}.wav
  """
  # Link to the original InterviewAudio object (the full audio file this segment came from)
  audio = models.ForeignKey('InterviewAudio', on_delete=models.CASCADE, related_name='segments')
  
  # Start and end times in SECONDS of the audio file
  start_time = models.FloatField(blank=False, null=False, help_text="Start time in seconds")
  end_time = models.FloatField(blank=False, null=False, help_text="End time in seconds")
  
  # The segment audio file stored in S3
  # upload_to will be dynamically set based on the interview/question/audio structure
  segment_audio_file = models.FileField(upload_to="InterviewAudios/", blank=True, null=True)
  
  # The transcribed text for this segment (sentence)
  segment_text = models.TextField(blank=False, null=False)
  
  # Sequence number within the parent audio file (1, 2, 3, ...)
  sequence_number = models.IntegerField(blank=False, null=False, default=1)
  
  # Optional: word count for this segment
  word_count = models.IntegerField(blank=True, null=True, help_text="Number of words in segment")
  
  # Timestamp when this segment was created
  created = models.DateTimeField(auto_now_add=True)
  
  class Meta:
    ordering = ['audio', 'sequence_number']
    unique_together = ['audio', 'sequence_number']  # Prevent duplicate sequence numbers
    indexes = [
      models.Index(fields=['audio', 'sequence_number']),
    ]
  
  def __str__(self):
    return f"Segment {self.sequence_number} of Audio {self.audio.id}"
  
  def get_s3_path(self):
    """
    Constructs the S3 path for this segment's audio file.
    Returns: InterviewAudios/interview{id}/module{id}/question{id}/user_{audio_id}/sentence_{seq}.wav
    """
    question = self.audio.question
    interview_id = question.interview.id
    module_id = question.module.id
    question_id = question.id
    audio_id = self.audio.id
    
    return f"InterviewAudios/interview{interview_id}/module{module_id}/question{question_id}/user_{audio_id}/sentence_{self.sequence_number:03d}.wav"
  
  @property
  def duration(self):
    """Returns the duration of this segment in seconds."""
    return self.end_time - self.start_time
  
  def get_parent_interview(self):
    """Helper to get the parent Interview object."""
    return self.audio.question.interview
  
  def get_parent_question(self):
    """Helper to get the parent InterviewQuestion object."""
    return self.audio.question


class InterviewModule(models.Model): 
  # The current module ID. This is an integer that starts from 1. 
  module_id = models.IntegerField(blank=False, null=False, default=1)
  # The question ID that we are currently administering. 
  curr_question_id = models.IntegerField(blank=False, null=False, default=1)
  # The number of all questions present. 
  question_count = models.IntegerField(blank=False, null=False, default=1)
  # ForeignKey to the Interview instances. 
  interview = models.ForeignKey('Interview', on_delete=models.CASCADE)
  # This turns True when the current question has ended. 
  completed = models.BooleanField(blank=False, null=False, default=False)

  class Meta:
    # Defining the unique constraint for the module.
    constraints = [
      models.UniqueConstraint(fields=['module_id', 'interview'], 
                              name='unique_module_details')
    ]


  def get_module_convo(self): 
    """
    Note that a module is composed of one or more questions, and each question
    maintains its own conversation history. This compiles the conversations 
    that have taken place for this module. 

    Parameters:
      None
    Returns: 
      convo: <str> or <list_of_list> of the compiled conversation.  
    """
    all_qs = (InterviewQuestion.objects.filter(module=self)
                                       .order_by('global_question_id'))
    # Pulling together all conversation. 
    convo = ""
    for q in all_qs: 
      convo += q.convo + "\n"
    return convo


  def generate_next_step(self, interviewer_summary, q, p_notes):
    """
    Note that a module is composed of one or more questions, and each question
    maintains its own conversation history. This compiles the conversations 
    that have taken place for this module. 

    Parameters:
      interviewer_summary: self.character attribute of the InterviewerAgent 
        class
      q: an instance of the Question class
      p_notes: self.p_notes attribute of the InterviewerAgent class
    Returns: 
      next_step: This is a dictionary of the following format: 
        {"completed": <bool (True if completed, False otherwise)>, 
         "next_utt": <str (of the next utterance)> or None}
    """
    # This is just for the start of the conversation -- we don't have to 
    # generate anything for our first interviewer utterance because we can 
    # just copy and paste from the script. That's what this does here: 
    next_step = {"completed": False, 
                 "next_utt": None, 
                 "skip_user_utt": False}

    if not q.convo:  
      # This is for conditional... 
      if q.q_type != "non-question" and q.q_condition != "": 
        conditional = run_gpt_generate_conditional(
          interviewer_summary, p_notes, q, self.get_module_convo())[0]
        # e.g., The interviewer do not know the participant's name.
        # If this is False, then the statement like above is False. 
        if conditional["determination"] == False: 
          next_step["next_utt"] = ""
          next_step["completed"] = True
          next_step["skip_user_utt"] = True
          return next_step

      # This is if we have the condition to proceed.
      next_step["next_utt"] = q.q_content
      if q.q_type == "non-question": 
        next_step["completed"] = True
        next_step["skip_user_utt"] = True
      return next_step

    # We have two types of questions that are beng asked: factual and 
    # qualitative. My current decision is that these two questions need to be
    # handled by two different LLM prompts, rather than one. This is because
    # the role and depth of the follow up questions are different. 
    # For the factual questions, we can largely progress as long as the 
    # interviewee has given us an answer (so the goal of the follow up is to 
    # ensure that they did). 
    # For the qualitative questions, however, we plan on expending all 
    # remaining time to get deeper perspective. 
    if q.q_type == "factual": 
      # For factual questions.
      try: 
        next_step.update(run_gpt_generate_factual_next_interview_step(
             interviewer_summary, p_notes, q, self.get_module_convo())[0])
      except: 
        next_step.update({"assessment": "", 
                          "completed": True, 
                          "next_utt": "",
                          "skip_user_utt": True})
      return next_step

    elif q.q_type == "qualitative": 
      # For qualitative questions.
      try: 
        next_step.update(run_gpt_generate_qualitative_next_interview_step(
             interviewer_summary, p_notes, q, self.get_module_convo())[0])
      except: 
        next_step.update({"assessment": "", 
                          "completed": True, 
                          "next_utt": "",
                          "skip_user_utt": True})
      return next_step

    else: 
      next_step.update({"completed": True, 
                        "next_utt": "", 
                        "skip_user_utt": True})
      return next_step

  def generate_notes(self): 
    """
    Note that a module is composed of one or more questions, and each question
    maintains its own conversation history. This compiles the conversations 
    that have taken place for this module. 

    Parameters:
      character: self.character attribute of the InterviewerAgent class
      q: an instance of the Question class
      p_notes: self.p_notes attribute of the InterviewerAgent class
    Returns: 
      notes: a dictionary where keys are keywords that describe the 
             interviewee, and values are one sentence/phrase expansion of that
             keyword. e.g., {"name": "Joon"}
    """
    # Creating the summary note based on the conversation that was had in the
    # question so far. 
    notes = {}
    try: 
      if self.get_module_convo().strip():
        notes = run_gpt_generate_module_notes(self.get_module_convo())[0]
    except: 
      notes = {}
    return notes


  def input_interviewee_utt(self, interviewee_utt): 
    """
    Main function that takes the interviewee input.

    Parameters:
      interviewee_utt: <str> of the interviewee input. 
    Returns: 
      None
    """
    # TODO
    return


class Interview(models.Model):
  # The participant of the study.
  participant = models.ForeignKey('Participant', on_delete=models.CASCADE, 
                                  blank=False, null=False)
  # The name of the interview script.
  script_v = models.CharField(blank=False, null=False, max_length=255, 
                              default="script_v1")
  # The summary that describes the interviewer. It is in <str> but its makeup
  # is actually a dictionary that looks like below. 
  # "interviewer_summary": {"name": "Isabella", 
  #                         "characteristics": "friendly and kind", 
  #                         "vocalizer": "Nova OpenAI tts-1"}
  # (* Dictionary in <str>)
  interviewer_summary = models.TextField(blank=False, null=False, default="")
  # The module and question ID that we are currently administering. 
  curr_module_id = models.IntegerField(blank=False, null=False, default=1)
  # The number of all modules present. This does not get updated. 
  module_count = models.IntegerField(blank=False, null=False, default=1)
  # The number of questions that we've administered so far. This is to 
  # uniquely retrieve and order the questions for analysis. This does get
  # updated with every question we add on.
  question_id_count = models.IntegerField(blank=False, null=False, default=1)
  # Participant note that gets updated as the interview progresses. Like
  # interviewer_summary, this is in <str> but it is actually a dictionary. 
  # (* Dictionary in <str>)
  p_notes = models.TextField(blank=False, null=False, default="{ }")
  pruned_p_notes = models.TextField(blank=False, null=False, default="{ }")
  # This is in <str> but it is basically a row of comma separated values. 
  # For instance, "My name is {curr_user.get_full_name()}." 
  # We maintain this so we can use it as special keywords when transcribing.
  optional_key_phrases = models.TextField(blank=False, null=False, default="")
  # The number of seconds passed for the completed question modules. This 
  # does not count the number of seconds passed in the ongoing question 
  # module, however.
  completed_sec = models.IntegerField(blank=False, null=False, default=0)
  completed_module_sec = models.IntegerField(blank=False, null=False, default=0)
  completed_question_sec = models.IntegerField(blank=False, null=False, default=0)
  # This turns True when the current question has ended. 
  completed = models.BooleanField(blank=False, null=False, default=False)
  # Time of creation.
  created = models.DateTimeField(auto_now_add=True)

  zipped_main = models.BooleanField(blank=False, null=False, default=False)
  zipped_audio = models.BooleanField(blank=False, null=False, default=False)

  class Meta:
        # Define the unique constraint
        unique_together = [['participant', 'script_v']]

  @classmethod
  def _find_audio_id_for_quote(cls, interview, quote, speaker):
      """Helper method to find the audio ID for a given quote in the interview"""
      questions = InterviewQuestion.objects.filter(interview=interview)
      for question in questions:
          # Split conversation into turns
          turns = question.convo.split('\n')
          audio_ids = question.q_content_audio_ids.split('\n')
          
          # Match turns with audio IDs
          for turn, audio_line in zip(turns, audio_ids):
              if turn.startswith(speaker) and quote in turn:
                  # Extract audio ID from line like "Interviewer: 123" or "Interviewee: 456"
                  return int(audio_line.split(': ')[1])
      return None

  def __str__(self):
    return "Interview Object"


  def get_interviewer_summary(self, in_dict=True):
    if in_dict: 
      return json.loads(self.interviewer_summary)
    return self.interviewer_summary


  def get_p_notes(self, in_dict=True):
    if in_dict: 
      return json.loads(self.p_notes)
    return self.p_notes


  def get_pruned_p_notes_notes(self, in_dict=True):
    if in_dict: 
      return json.loads(self.pruned_p_notes)
    return self.pruned_p_notes


  def update_p_notes(self, p_note_str):
    curr_p_notes = self.get_p_notes()
    curr_p_notes.update(json.loads(p_note_str))
    self.p_notes = json.dumps(curr_p_notes)
    self.save()


  # Pruning p notes in case needed
  def prune_p_notes(self, char_limit=8000, prune_num=10): 
    curr_p_notes = self.get_p_notes(True)
    curr_pruned_p_notes = self.get_pruned_p_notes_notes(True)

    pruned_p_notes = dict()
    if len(self.p_notes) >= char_limit and len(curr_p_notes) > prune_num: 
      rand_keys = random.sample(list(curr_p_notes.keys()), prune_num)
      for rk in rand_keys: 
        if rk != "name": 
          curr_pruned_p_notes.update({rk: curr_p_notes[rk]})
          curr_p_notes.pop(rk)

    self.p_notes = json.dumps(curr_p_notes)
    self.pruned_p_notes = json.dumps(curr_pruned_p_notes)
    self.save()


  def output_interviewer_utt(self, m, q): 
    """
    Main function that creates the next step for the current module.

    Parameters:
      m: current Module object.
      q: current Question object. 
    Returns: 
      next_step: This is a dictionary of the following format: 
                 {"completed": <bool (True if completed, False otherwise)>, 
                 "interviewer_utt": <str (of the next utterance)> or None}
      notes: a dictionary where keys are keywords that describe the 
             interviewee, and values are one sentence/phrase expansion of that
             keyword. e.g., {"name": "Joon"}
             Note that we send an emtpy {} if the module has not completed. 
    """
    self.completed_sec += q.last_utt_num_sec_passed()
    jsp_log(f"Number of seconds passed in curr_q: {self.completed_sec}")

    # Generating the next step. 
    next_step = {"completed": False, 
                 "next_utt": "", 
                 "skip_user_utt": False,
                 "completed_sec": self.completed_sec} 
    next_step.update(m.generate_next_step(
                       self.get_interviewer_summary(True), q, self.p_notes))
    if "<!user_first_name!>" in next_step["next_utt"]:
      # Use display_name if available, otherwise email prefix, otherwise prolific_id
      user_name = (self.participant.display_name or
                   (self.participant.email.split('@')[0] if self.participant.email else None) or
                   self.participant.prolific_id or
                   "there")
      next_step["next_utt"] = next_step["next_utt"].replace("<!user_first_name!>", user_name)

    # Once the next step is created, we do post processing. The main
    # conditional here is whether the current question's conversation has
    # ended. This is the case if next_step["interview_completed"] is True, or 
    # q.max_sec_passed() is True. 
    # (Basically, if LLM thinks the conversation has ended, or if we timed
    # out, then the conversation is done.)
    if next_step["completed"] or q.max_sec_passed() or q.convo.count("Interviewer:") >= 3:
      next_step["skip_user_utt"] = True
      if q.q_type != "non-question": 
        # If the conversation ended, for the last utterance, we overwrite the
        # original with a newly created short thank you note. We do that here.
        # It's worth noting that run_gpt_generate_q_end_thankyou always 
        # evaluate next_step["completed"] as True.
        try: 
          curr_module_convo = m.get_module_convo()
          jsp_log(f"DEBUG Feb 11: {curr_module_convo}")    
          if (curr_module_convo.count(':') < 3 
            and len(curr_module_convo.split()) < 20): 
            jsp_log(f"HEREEEEE")    
            next_step["completed"] = True
            next_step["skip_user_utt"] = True
            next_step["next_utt"] = ""
          else: 
            next_step.update(run_gpt_generate_q_end_thankyou(
                             self.get_interviewer_summary(True), 
                             q, self.p_notes, curr_module_convo)[0])
        except: 
          next_step["completed"] = True
      
      # marking the end of the conversation and incrementing the curr index. 
      q.completed = True
      m.curr_question_id += 1

      self.completed_question_sec += q.q_max_sec
      self.completed_sec = self.completed_question_sec

    # We check if the module has ended here. If it has, we set the completed
    # to be True, and create new notes.
    # Note that we return an empty notes if the module has not finished. 
    notes = {}
    if m.question_count < m.curr_question_id:
      m.completed = True
      next_step["skip_user_utt"] = True
      notes = m.generate_notes()

    self.save()
    m.save()
    q.save()
    jsp_log(f"DEBUG Feb 11 next step: {next_step}")    
    return next_step, notes


  def get_curr_module(self, started): 
    # Loading the current module instance that we are administering. 
    curr_module = InterviewModule.objects.filter(
                    interview=self,
                    module_id=self.curr_module_id)
    
    if started: 
      # When the user reloads, we want to make sure that we start from a clean
      # slate as far as the current module goes. 
      curr_module.delete()

    if not curr_module or started: 
      # Loading the current question instance that we are administering. 
      curr_script_path = f"{INTERVIEW_AGENT_PATH}/interview_script/"
      curr_script_path += f"{self.script_v}/module{self.curr_module_id}.json"
      curr_module_dict = read_json_file(curr_script_path)
      question_count = len(curr_module_dict.items())

      # If not curr_module, this means we just started the module and need to
      # create its instance. 
      curr_module = InterviewModule.objects.create(
                      interview=self,
                      module_id=self.curr_module_id,
                      question_count=question_count,
                      completed=False)
    else:
      curr_module = curr_module[0]
    return curr_module


  def get_curr_question(self, curr_module): 
    curr_questions = InterviewQuestion.objects.filter(module=curr_module)

    if not curr_questions: 
      # Loading the current question instance that we are administering. 
      curr_script_path = f"{INTERVIEW_AGENT_PATH}/interview_script/"
      curr_script_path += f"{self.script_v}/module{self.curr_module_id}.json"
      curr_module_dict = read_json_file(curr_script_path)

      # If not curr_question, this means we just started the question and need
      # to create its instance. 
      # Importantly, we will create all Question objects for the current
      # module here. 
      curr_questions = []
      count = 0
      for key, curr_question_dict in curr_module_dict.items(): 
        curr_question = InterviewQuestion.objects.create(
                          interview=self,
                          module=curr_module,
                          question_id=curr_module.curr_question_id+count,
                          global_question_id=self.question_id_count,
                          q_content=curr_question_dict["content"],
                          q_type=curr_question_dict["type"],
                          q_requirement=curr_question_dict["requirement"],
                          q_condition=curr_question_dict["condition"],
                          q_max_sec=curr_question_dict["max_sec"],
                          convo="",
                          completed=False)
        curr_questions += [curr_question]
        count += 1
        self.question_id_count += 1
      curr_question = curr_questions[0]

    else: 
      curr_question = curr_questions.filter(
                        question_id=curr_module.curr_question_id)[0]
      curr_questions = list(curr_questions)

    return curr_question


  def process_one_step(self, 
                       curr_user, 
                       started, 
                       user_utt, 
                       mime_type,
                       script_v,
                       total_sec): 
    """
    This prgresses the interview by one step. 

    Parameters:
      curr_user: current Participant instance
      started: Boolean that says whether this is the first signal of the
        session.
      user_utt: This is the user's current utterance.
      mime_type: This is the mime_type of the user_utt file.
    Returns: 
      step_packet
    """
    def create_and_save_audio(curr_module, curr_question, user_speech, audio):
      curr_audio = InterviewAudio()
      curr_audio.question = curr_question  
      curr_audio.user_speech = user_speech  
      curr_audio.save()

      user_speech_prefix = "user"
      if not user_speech: 
        user_speech_prefix = "interviewer"
      curr_filename = f"interview{self.id}/module{curr_module.id}/"
      curr_filename += f"question{curr_question.id}/"
      curr_filename += f"{user_speech_prefix}_{curr_audio.id}.wav"

      curr_audio.audio_file.save(curr_filename, audio, save=True)
      curr_audio.save()
      return curr_audio

    jsp_log(f"Starting process_one_step -- step 1: setting up")

    # Preparing step_packet. 
    step_packet = {"completed": False,
                   "module_completed": False,
                   "next_utt": None,
                   "interviewer_transcript": "",
                   "skip_user_utt": False,
                   "completed_sec": self.completed_sec,
                   "interview_completed": False,
                   "audio_url": None}

    curr_measurement = PerfMeasurement.objects.create(participant=curr_user)

    # [CHECK IF THE INTERVIEW IS COMPLETED]
    # Check if the interview has ended. If it has, we just return now. At 
    # this point, the only thing that really matters is that we set the 
    # completed variable to True, and send it away.  
    if (self.completed):
      step_packet["completed"] = True
      step_packet["interview_completed"] = True
      curr_user.module_completed(f"Interview ({script_v})")

      curr_measurement.record({"interview_id": self.id,
                               "module_id": None, 
                               "question_id": None, 
                               "user_utt_bool": False})
      return step_packet

    jsp_log(f"Starting process_one_step -- step 2: prune p_notes")

    # Pruning p notes in case needed
    self.prune_p_notes(char_limit=8000, prune_num=10)

    jsp_log(f"Starting process_one_step -- step 3: load modules")

    # [LOAD MODULE INSTANCE]
    curr_module = self.get_curr_module(started)

    # [LOAD QUESTION INSTANCE]
    curr_question = self.get_curr_question(curr_module)
    if user_utt: 
      jsp_log(f"Starting process_one_step -- step 3.5: process user content")

      # Assuming 'user_utt_wav' is your io.BytesIO object from the audio 
      # processing, transcribing.
      base64_message = user_utt
      user_utt_wav = process_audio(base64_message, mime_type)
      user_utt_txt = threaded_transcribe_voice(user_utt_wav, 
                       optional_key_phrases=[self.optional_key_phrases])

      user_utt_wav.seek(0)
      audio_file = ContentFile(user_utt_wav.read(), name="temp_audio.wav")
      curr_audio = create_and_save_audio(curr_module, curr_question, True,  
                                         audio_file)

      curr_question.convo += f"Interviewee: {user_utt_txt}\n"
      curr_question.q_content_audio_ids += f"Interviewee: {curr_audio.id}\n"

      # Create new InterviewUtterance entry for interviewee
      last_utterance = InterviewUtterance.objects.filter(question=curr_question).order_by('-sequence_number').first()
      next_sequence = (last_utterance.sequence_number + 1) if last_utterance else 0
      
      InterviewUtterance.objects.create(
        question=curr_question,
        utterance_text=user_utt_txt,
        audio_id=curr_audio.id,
        is_interviewer=False,
        sequence_number=next_sequence
      )

      curr_question.save()

    jsp_log(f"Starting process_one_step -- step 4: output_interviewer_utt")

    # [CREATING THE INTERVIEWER'S NEXT STEP AND NOTES]
    next_step, notes = self.output_interviewer_utt(curr_module, curr_question)
    step_packet.update(next_step)

    # If notes != {}, it means the module is done. 
    # If next_step["completed"] == True, it means the question is done. 
    # In both cases, the interviewer should speak again. 
    if notes != {} or step_packet["completed"]:
      step_packet["skip_user_utt"] = True

    jsp_log(f"Starting process_one_step -- step 5: generate voice")

    if step_packet["next_utt"]: 
      step_packet["interviewer_transcript"] = step_packet["next_utt"]
      audio_data = threaded_generate_voice(curr_input=step_packet["next_utt"], 
                                           voice="nova")
      # Use BytesIO to handle the binary data and save it as a Django File
      audio_file = File(io.BytesIO(audio_data))
      curr_audio = create_and_save_audio(curr_module, curr_question, False,  
                                         audio_file)
      curr_question.convo += f"Interviewer: {next_step['next_utt']}\n"
      curr_question.q_content_audio_ids += f"Interviewer: {curr_audio.id}\n"
      
      # Create new InterviewUtterance entry for interviewer
      last_utterance = InterviewUtterance.objects.filter(question=curr_question).order_by('-sequence_number').first()
      next_sequence = (last_utterance.sequence_number + 1) if last_utterance else 0
      
      InterviewUtterance.objects.create(
        question=curr_question,
        utterance_text=next_step['next_utt'],
        audio_id=curr_audio.id,
        is_interviewer=True,
        sequence_number=next_sequence
      )
      
      curr_question.save()
      step_packet["audio_url"] = curr_audio.audio_file.url

    jsp_log(f"Starting process_one_step -- step 5: check for module fin")

    # [CHECKING IF THE MODULE/INTERVIEW IS COMPLETED, AND UPDATE STATES]
    # If the module is done, process. 
    if curr_module.completed:
      self.completed_module_sec = self.completed_question_sec
      self.completed_sec = self.completed_question_sec
      self.update_p_notes(json.dumps(notes))
      self.curr_module_id += 1
      # We are checking if the interview is done. 
      if self.curr_module_id > self.module_count:
        self.completed = True
        self.completed_sec = total_sec
        self.completed_module_sec = total_sec
        self.completed_question_sec = total_sec
      step_packet["module_completed"] = True

    user_utt_bool = False
    if user_utt: user_utt_bool = True
    curr_measurement.record({"interview_id": self.id,
                             "module_id": curr_module.id, 
                             "question_id": curr_question.id, 
                             "user_utt_bool": user_utt_bool})

    jsp_log(f"Starting process_one_step -- step 6: fin")
    step_packet["curr_module_id"] = curr_module.module_id
    step_packet["module_count"] = self.module_count
    self.save()
    return step_packet

  def get_full_conversation(self):
      """
      Returns the full conversation transcript using InterviewUtterance objects.
      Each turn is a dict with 'speaker', 'utterance_text', and 'audio_id'.
      """
      # Single query with prefetch_related to get all utterances in one go
      utterances = InterviewUtterance.objects.filter(
          question__interview=self
      ).select_related('question').order_by(
          'question__global_question_id', 'sequence_number'
      )
      
      conversation = []
      for utt in utterances:
          conversation.append({
              "speaker": "Interviewer" if utt.is_interviewer else "Interviewee",
              "utterance_text": utt.utterance_text,
              "audio_id": utt.audio_id
          })
      return conversation




class Avatar(models.Model):
  sprite_sheet = models.ImageField(upload_to='UserAvatars/')
  front_static = models.ImageField(upload_to='UserAvatars/')

  front_gif = models.FileField(upload_to='UserAvatars/')
  back_gif = models.FileField(upload_to='UserAvatars/')
  left_gif = models.FileField(upload_to='UserAvatars/')
  right_gif = models.FileField(upload_to='UserAvatars/')

  # Generated avatar fields
  generated_image = models.ImageField(upload_to='GeneratedAvatars/', blank=True, null=True)
  is_generated = models.BooleanField(default=False)
  generation_prompt = models.TextField(blank=True, null=True)
  generation_model = models.CharField(max_length=50, blank=True, null=True)
  generated_date = models.DateTimeField(blank=True, null=True)


class TimeoutTimer(models.Model): 
  # The participant of the study.
  participant = models.ForeignKey('Participant', on_delete=models.CASCADE, 
                                  blank=False, null=False)
  created = models.DateTimeField(auto_now_add=True)
  endtime = models.DateTimeField(blank=True, null=True)
  cause = models.TextField(blank=True, null=False, default="")


  def __str__(self):
    return str(self.created)


  def time_up(self): 
    if not self.endtime: 
      return False 
    now = timezone.now()
    return now > self.endtime


  def get_remaining_datetime(self): 
    if not self.endtime: 
      return False

    now = timezone.now()
    difference = self.endtime - now

    return difference


  def get_remaining_seconds(self):
    if not self.endtime:
        return 0

    now = timezone.now()
    difference = self.endtime - now
    return max(0, int(difference.total_seconds()))


  def get_str_remaining_datetime(self): 
    if not self.endtime: 
      return False

    now = timezone.now()
    difference = self.endtime - now

    days = difference.days
    seconds = difference.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    return f"{days} days, {hours} hours, {minutes}"
  

  def get_str_remaining_days(self):
    if not self.endtime:
      return "No end time set"

    now = timezone.now()
    difference = self.endtime - now

    # Calculate the total difference in days including fractional part
    total_seconds = difference.total_seconds()
    days_remaining = total_seconds / 86400  # 86400 seconds in a day

    return f"{int(days_remaining)}"
    return f"{days_remaining:.1f}"


def generate_binary_string(length):
  return ''.join(random.choice(['0', '1']) for _ in range(length))


def dump_randomly_ordered_json(data):
    items = list(data.items())
    random.shuffle(items)
    # Create a new dictionary from the shuffled list of items
    shuffled_dict = dict(items)
    # Serialize the shuffled dictionary to a JSON string
    for count, key in enumerate(shuffled_dict.keys()): 
      if count == 0: 
        shuffled_dict[key]["current"] = True
    return json.dumps(shuffled_dict, indent=4)


class BehavioralStudyModule(models.Model):
  study_cond = models.CharField(max_length=127, blank=False, null=False,
    default="0101110010110010101001010010100001001011")
  
  study_rand_o_1 = models.TextField(blank=True, null=False, 
    default="{ 'study_num': { 'study_link': 'link', 'study_val_code': 'code' } }")

  study_rand_o_2 = models.TextField(blank=True, null=False, 
    default="{ 'study_num': { 'study_link': 'link', 'study_val_code': 'code' } }")


  def initialize(self): 
    self.study_cond = generate_binary_string(100)
    header, rows = read_file_to_list(behavioral_study_link_csv,  
                     header=True, 
                     strip_trail=True)

    study_dict = {}

    for count, row in enumerate(rows): 
      study_num = int(row[0])
      study_link = ""
      study_val_code = ""
      # Control condition
      if self.study_cond[study_num] == "0":
        study_link = row[1]
        study_val_code = row[3]
      # Treatment condition
      else:
        study_link = row[2]
        study_val_code = row[4]

      study_dict[f"study_{study_num}"] = {"study_link": study_link, 
                                          "study_val_code": study_val_code,
                                          "study_cond": self.study_cond[study_num], 
                                          "completed": False,
                                          "current": False}

    self.study_rand_o_1 = dump_randomly_ordered_json(study_dict)
    self.study_rand_o_2 = dump_randomly_ordered_json(study_dict)
    self.save()
    return 


  def get_study_rand_o_N(self, curr_round=1):
    if curr_round == 1:  
      data = json.loads(self.study_rand_o_1)
    if curr_round == 2: 
      data = json.loads(self.study_rand_o_2)
    return data


  def get_study_rand_o_1(self): 
    return self.get_study_rand_o_N(curr_round=1)

  def get_study_rand_o_2(self): 
    return self.get_study_rand_o_N(curr_round=2)


  def get_check_if_fin(self, curr_round=1): 
    curr_dict = self.get_study_rand_o_N(curr_round)

    print (curr_dict)
    for key, val in curr_dict.items(): 
      if curr_dict[key]["completed"] == False: 
        return False
    return True


  def get_verify_code(self, code, curr_round=1): 
    curr_study = None
    curr_dict = self.get_study_rand_o_N(curr_round)
    for key, val in curr_dict.items(): 
      if val["current"]: 
        curr_study = val
    if curr_study["study_val_code"] == code: 
      return True
    return False


  def get_move_to_next_study(self, curr_round=1): 
    curr_dict = self.get_study_rand_o_N(curr_round)
    just_turned = False
    editted = False
    for key, val in curr_dict.items(): 
      if just_turned: 
        just_turned = False
        curr_dict[key]["current"] = True
      if val["current"] and editted == False: 
        curr_dict[key]["current"] = False
        curr_dict[key]["completed"] = True
        print ("???")
        print (curr_dict)
        just_turned = True
        editted = True

    if curr_round == 1: 
      self.study_rand_o_1 = json.dumps(curr_dict, indent=4)
    else: 
      self.study_rand_o_2 = json.dumps(curr_dict, indent=4)
    self.save()


class Participant(AbstractUser): 
  """
  This is the main participant model class that extends user class of OAuth's
  base user class. 
  """
  avatar = models.OneToOneField(Avatar, blank=True, null=True, 
                                on_delete=models.CASCADE)
  email = models.EmailField(unique=True, blank=False, null=False)
  prolific_id = models.CharField(max_length=255, unique=True, blank=True, null=True)
  username = models.CharField(max_length=150, unique=True, blank=True, null=True)  # Make username optional
  display_name = models.CharField(max_length=150, blank=True, null=True)
  # Names of the completed modules. This is stored as a list of comma 
  # separated string row. 
  # e.g., Consent,Interview,SurveyPt-1,SurveyPt-2
  # Notice that there are no spaces in between the commas.
  completed_modules = models.TextField(blank=True, null=False, default="")
  # Names of the completed modules. This is stored as a list of comma 
  # separated string row. 
  # e.g., Consent,Interview,SurveyPt-1,SurveyPt-2
  # Notice that there are no spaces in between the commas.
  completed_modules_det = models.TextField(blank=True, null=False, default="")
  # Float for RMS value that marks the calibrated voice threshold for the 
  # current participant. 
  audio_calibration_float = models.FloatField(blank=False, null=False, 
                                              default=0.02)

  behavioral_activated = models.BooleanField(
                           blank=False, 
                           null=False, 
                           default=False)
  behavioral_module = models.ForeignKey(
                        'BehavioralStudyModule', 
                        on_delete=models.CASCADE, 
                        blank=True, 
                        null=True)

  camerer_activated = models.TextField(blank=True, null=False, default="")

  # Time of creation.
  created = models.DateTimeField(auto_now_add=True)

  age = models.IntegerField(null=True, blank=True)
  occupation = models.CharField(max_length=255, null=True, blank=True)
  
  # Avatar preference flag.
  use_generated_avatar = models.BooleanField(default=False)

  @property
  def has_completed_interview(self):
    """Check if user has completed any interviews"""
    completed_interviews = Interview.objects.filter(
        participant=self,
        completed=True
    ).exists()
    return completed_interviews

  def __str__(self):
    return self.email or self.prolific_id or self.username or f"User {self.id}"

  def get_avatar_url(self):
    """
    Get the appropriate avatar URL based on use_generated_avatar flag
    """
    if not self.avatar:
      return '/static/assets/img/avatars/default.png'
    
    if self.use_generated_avatar and self.avatar.generated_image:
      return self.avatar.generated_image.url
    elif self.avatar.front_static:
      return self.avatar.front_static.url
    else:
      return '/static/assets/img/avatars/default.png'


  def module_completed(self, module_name): 
    """
    Edits completed modules to indicate that the module denoted by module_name
    is completed. 

    The available module options are in the interview_settings.py

    Parameters:
      module_name: The name of the current module that we want to mark as 
      completed. 
    Returns: 
      None
    """
    if self.completed_modules: 
      self.completed_modules += f",{module_name}"
    else: 
      self.completed_modules = module_name
    self.save()


  def module_completed_det(self, module_name): 
    """
    Edits completed modules to indicate that the module denoted by module_name
    is completed. 

    The available module options are in the interview_settings.py

    Parameters:
      module_name: The name of the current module that we want to mark as 
      completed. 
    Returns: 
      None
    """
    if self.completed_modules_det: 
      self.completed_modules_det += f",{module_name}"
    else: 
      self.completed_modules_det = module_name
    self.save()


  def get_survey_link_pt2(self): 
    s = self.camerer_activated
    x = ""
    if len(s) > 4: 
      x = f"https://stanforduniversity.qualtrics.com/jfe/form/SV_1Huw5wFg3admF8O?1={s[0]}&2={s[1]}&3={s[2]}&4={s[3]}&5={s[4]}&email={self.email}"
    return x


  def get_survey_link_pt1(self): 
    x = f"https://stanforduniversity.qualtrics.com/jfe/form/SV_5i2P0DnXVhAb1IO?email={self.email}"
    return x


  def get_completed_modules(self): 
    """
    Returns a list of module name that are completed. 

    Returns: 
      <list> with the names of the completed modules. 
    """
    temp = self.completed_modules.split(",")
    ret = []
    for i in temp: 
      if i != "": 
        ret += [i]
    return ret


  def get_curr_modules(self): 
    """
    Returns a list of module name that are completed. 

    Returns: 
      <list> with the names of the completed modules. 
    """
    temp = self.completed_modules.split(",")
    ret = []
    for i in temp: 
      if i != "": 
        ret += [i]
    return ret[-1]


  def get_full_name(self): 
    """
    Returns the participant's Prolific ID.

    Returns: 
      <str> Prolific ID.  
    """
    return str(self.display_name)


class InterviewRecommendation(models.Model):
    participant = models.ForeignKey('Participant', 
                                  on_delete=models.CASCADE,
                                  null=True, blank=True)  # Allow null for global recommendations
    recommendation = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # Add this field

    def __str__(self):
        return f"Recommendation #{self.id}"

    def get_supporting_clips(self):
        return self.interviewclip_set.filter(supports=True)
        
    def get_opposing_clips(self):
        return self.interviewclip_set.filter(supports=False)

class InterviewClip(models.Model):
    recommendation = models.ForeignKey(InterviewRecommendation, on_delete=models.CASCADE)
    audio_file = models.FileField(upload_to='interview_clips/')
    audio_id = models.CharField(max_length=255, blank=True, null=True)
    transcript = models.TextField()
    supports = models.BooleanField()  # True if supports recommendation, False if opposes
    timestamp = models.DateTimeField()
    interview_id = models.IntegerField()

    def get_participant_avatar(self):
        try:
            interview = Interview.objects.get(id=self.interview_id)
            if interview.participant.avatar:
                # If avatar exists, return the front_static image
                return interview.participant.avatar.front_static.url
            # Return default avatar URL if no avatar exists
            return "/static/assets/img/avatars/default.png"
        except Interview.DoesNotExist:
            return "/static/assets/img/avatars/default.png"
        
    def get_participant_name(self):
        interview = Interview.objects.get(id=self.interview_id)
        return interview.participant.get_full_name()


class ParticipantRecommendationSupport(models.Model):
    """
    Model to store predictions about how likely a participant would support a recommendation.
    """
    recommendation = models.ForeignKey(InterviewRecommendation, on_delete=models.CASCADE)
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE)
    support_score = models.IntegerField(help_text="Score from 0-100 indicating level of support")
    confidence_score = models.IntegerField(help_text="Score from 0-100 indicating confidence in prediction")
    explanation = models.TextField(help_text="Explanation for why the participant would/wouldn't support")
    created_at = models.DateTimeField(auto_now_add=True)
    is_endorsed = models.BooleanField(default=False, help_text="Whether the participant has endorsed this explanation")
    user_modified_explanation = models.TextField(blank=True, null=True, help_text="User's modified explanation if they chose to edit it")
    last_modified = models.DateTimeField(auto_now=True, help_text="When the explanation was last modified")
    
    class Meta:
        unique_together = ('recommendation', 'interview')
    
    def __str__(self):
        return f"Support prediction for {self.interview.participant.get_full_name()} on recommendation #{self.recommendation.id}"
    
    def get_supporting_evidence(self):
        """Get clips that provide evidence for this prediction"""
        return InterviewClip.objects.filter(
            recommendation=self.recommendation,
            interview_id=self.interview.id
        )

    
class Recommendation(models.Model):
    rec_text = models.TextField()
    utterances = models.ManyToManyField('InterviewUtterance', related_name='recommendations', blank = True)
    base_rec = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='derived_recommendations')
    participant_who_edited = models.ForeignKey(Participant, null=True, blank=True, on_delete=models.SET_NULL, related_name='edited_recommendations')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    # AI-generated fields
    ai_rec_text = models.TextField(null=True, blank=True, help_text="AI-generated consensus recommendation text")
    ai_predicted_support = models.FloatField(null=True, blank=True, help_text="Average predicted support percentage for AI recommendation (0-100)")

    def __str__(self):
        return self.rec_text[:50]  # Show first 50 chars for admin display

class RecommendationParticipantSummary(models.Model):
    recommendation = models.ForeignKey(Recommendation, on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    summary = models.TextField(help_text="AI-generated summary of how the participant's experiences relate to this recommendation")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    best_utterance = models.ForeignKey(InterviewUtterance, on_delete=models.CASCADE, null=True, blank=True)
    predicted_agreement = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True, blank=True,
        help_text="Predicted agreement level (0-100)"
    )
    confidence_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True, blank=True,
        help_text="Confidence in the prediction (0-100)"
    )
    relevance_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True, blank=True,
        help_text="Relevance score (0-100)"
    )
    reasoning = models.TextField(
        null=True, blank=True,
        help_text="Reasoning for the predicted vote"
    )
    coherence_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True, blank=True,
        help_text="Coherence score (0-100)"
    )
    quality_score = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True, blank=True,
        help_text="Weighted quality score combining opinion, relevance, and depth (0-100)"
    )
    opinion_vs_experience_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True, blank=True,
        help_text="Opinion vs Experience score (0-100)"
    )
    pro_profiles_selected = models.BooleanField(
        default=False,
        help_text="Whether this participant was selected for pro profiles (70% from >50 support, 30% from <50 support)"
    )
    against_profiles_selected = models.BooleanField(
        default=False,
        help_text="Whether this participant was selected for against profiles (30% from >50 support, 70% from <50 support)"
    )

    class Meta:
        unique_together = ('recommendation', 'participant')
        verbose_name_plural = "Recommendation participant summaries"
    
    def __str__(self):
        return f"Summary for {self.participant.get_full_name()} on recommendation #{self.recommendation.id}"
  
class Narrative(models.Model):
    recommendation = models.ForeignKey(Recommendation, on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    global_summary = models.TextField(
        null=True, blank=True,
        help_text="AI-generated summary of the participant's experiences related to the recommendation"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        unique_together = ('recommendation', 'participant')
        
    def __str__(self):
        return f"Narrative for {self.participant.get_full_name()} on recommendation #{self.recommendation.id}"

class NarrativePart(models.Model):
    narrative = models.ForeignKey(Narrative, on_delete=models.CASCADE, related_name='parts')
    utterance = models.ForeignKey(
        InterviewUtterance, on_delete=models.CASCADE, null=True, blank=True,
        help_text="Reference to an utterance, if this part is a quote"
    )
    ai_explanation_text = models.TextField(
        null=True, blank=True,
        help_text="Text of the AI explanation, if this part is an explanation"
    )
    utterance_text_with_bold = models.TextField(
        null=True, blank=True,
        help_text="AI-generated utterance text with bold tags for highlighting"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        parts = []
        if self.utterance:
            parts.append(f"Utterance {self.utterance_id}")
        if self.ai_explanation_text:
            parts.append("AI Explanation")
        if not parts:
            return f"Empty NarrativePart for Narrative {self.narrative.id}"
        return f"{' and '.join(parts)} for Narrative {self.narrative.id}"

class ParticipantNarrative(models.Model):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    global_summary = models.TextField(
        null=True, blank=True,
        help_text="AI-generated summary of the participant's experiences"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    def __str__(self):
        return f"Narrative for {self.participant.get_full_name()}"
    
class ParticipantNarrativePart(models.Model):
    participant_narrative = models.ForeignKey(ParticipantNarrative, on_delete=models.CASCADE, related_name='parts')
    utterance = models.ForeignKey(InterviewUtterance, on_delete=models.CASCADE)
    utterance_text_with_bold = models.TextField(
        null=True, blank=True,
        help_text="AI-generated utterance text with bold tags for highlighting"
    )
    ai_explanation_text = models.TextField(
        null=True, blank=True,
        help_text="Text of the AI explanation, if this part is an explanation"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        parts = []
        if self.utterance:
            parts.append(f"Utterance {self.utterance_id}")
        if self.ai_explanation_text:
            parts.append("AI Explanation")
        if not parts:
            return f"Empty ParticipantNarrativePart for ParticipantNarrative {self.participant_narrative.id}"
        return f"{' and '.join(parts)} for ParticipantNarrative {self.participant_narrative.id}"

class RecommendationVote(models.Model):
    """
    Model to track participant votes on recommendations.
    """
    recommendation = models.ForeignKey(Recommendation, on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    
    # Agreement level from 1 (Strongly disagree) to 7 (Strongly agree)
    agreement_level = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(7)],
        help_text="Level of agreement with the recommendation (1-7)"
    )
    
    # Importance level from 1 (Not important at all) to 7 (Extremely important)
    importance_level = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(7)],
        help_text="Level of importance for implementing the recommendation (1-7)",
        null=True, blank=True
    )
    
    # Confidence level from 1 (Not at all) to 7 (Certain)
    confidence_level = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(7)],
        help_text="Level of confidence in the stance (1-7)",
        null=True, blank=True
    )
    
    # Explanation for the vote
    explanation = models.TextField(
        help_text="Explanation for the vote, including evidence from own and others' experiences"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('recommendation', 'participant')
        verbose_name = "Recommendation Vote"
        verbose_name_plural = "Recommendation Votes"
    
    def __str__(self):
        return f"Vote by {self.participant.get_full_name()} on recommendation #{self.recommendation.id}"


class DecisionFeedback(models.Model):
    """
    Model to track participant feedback on the decision outcome.
    """
    recommendation = models.ForeignKey(Recommendation, on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    
    # Decision outcome (PASS or NOT PASS)
    decision_outcome = models.CharField(
        max_length=10,
        choices=[('PASS', 'Pass'), ('NOT_PASS', 'Not Pass')],
        help_text="The decision outcome based on majority vote"
    )
    
    # Feedback questions on 7-point Likert scale
    trust_decision = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(7)],
        help_text="I trust that this decision accurately reflects participants' views (1-7)"
    )
    
    input_valuable = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(7)],
        help_text="I felt that my input was valuable (1-7)"
    )
    
    willing_abide = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(7)],
        help_text="I would be willing to abide by this decision (1-7)"
    )
    
    understand_others = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(7)],
        help_text="I understand why others voted the way they did on the decision (1-7)"
    )
    
    share_values = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(7)],
        help_text="I probably share common values with people that voted on this decision (1-7)"
    )
    
    confident_vote = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(7)],
        help_text="I am confident in my original vote on this proposal (1-7)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('recommendation', 'participant')
        verbose_name = "Decision Feedback"
        verbose_name_plural = "Decision Feedback"
    
    def __str__(self):
        return f"Decision feedback by {self.participant.get_full_name()} on recommendation #{self.recommendation.id}"


class ConnectionReport(models.Model):
    participant = models.ForeignKey(Participant, related_name='connection_reports', on_delete=models.CASCADE)
    target_participant = models.ForeignKey(Participant, related_name='connection_reports_received', on_delete=models.CASCADE)
    recommendation = models.ForeignKey(Recommendation, on_delete=models.CASCADE)
    connection_score = models.IntegerField(null=True, blank=True)
    connection_text = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PredictedVoteReport(models.Model):
    participant = models.ForeignKey(Participant, related_name='predicted_vote_reports', on_delete=models.CASCADE)
    target_participant = models.ForeignKey(Participant, related_name='predicted_vote_reports_received', on_delete=models.CASCADE)
    recommendation = models.ForeignKey(Recommendation, on_delete=models.CASCADE)
    predicted_vote_score = models.IntegerField(null=True, blank=True)
    predicted_vote_text = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Predicted vote report for {self.participant.get_full_name()} on recommendation #{self.recommendation.id}"


class ConnectionRequest(models.Model):
    from_user = models.ForeignKey(Participant, related_name='sent_requests', on_delete=models.CASCADE)
    to_user = models.ForeignKey(Participant, related_name='received_requests', on_delete=models.CASCADE)
    recommendation = models.ForeignKey(Recommendation, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('declined', 'Declined')], default='pending')

class ParticipantReflection(models.Model):
    user = models.ForeignKey(Participant, related_name='reflections', on_delete=models.CASCADE)
    target_participant = models.ForeignKey(Participant, related_name='reflected_on', on_delete=models.CASCADE)
    recommendation = models.ForeignKey(Recommendation, on_delete=models.CASCADE)
    connection_score = models.IntegerField(null=True, blank=True)
    connection_text = models.TextField(null=True, blank=True)
    vote_prediction = models.IntegerField(null=True, blank=True)
    vote_explanation = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Connection report for {self.participant.get_full_name()} on recommendation #{self.recommendation.id}"


class PredictionFeedback(models.Model):
    """
    Model to track user feedback on their predicted support scores.
    """
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    recommendation = models.ForeignKey(Recommendation, on_delete=models.CASCADE)
    feedback_type = models.CharField(
        max_length=20,
        choices=[
            ('too_high', 'My support is lower than predicted'),
            ('too_low', 'My support is higher than predicted'),
            ('neutral', 'I\'m neutral/unsure about this recommendation'),
            ('other', 'Other reason')
        ],
        help_text="Type of feedback provided"
    )
    feedback_text = models.TextField(
        blank=True,
        help_text="Additional comments from the user"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('participant', 'recommendation')
        verbose_name = "Prediction Feedback"
        verbose_name_plural = "Prediction Feedback"
    
    def __str__(self):
        return f"Feedback from {self.participant.get_full_name()} on recommendation #{self.recommendation.id}"


class ParticipantSimilarity(models.Model):
    """
    Cache for similarity-based participant selections
    """
    current_user = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='similarity_selections_as_current')
    recommendation = models.ForeignKey(Recommendation, on_delete=models.CASCADE)
    selected_participants = models.JSONField()  # Store as {"low": participant_id, "middle": participant_id, "high": participant_id}
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['current_user', 'recommendation']
        indexes = [
            models.Index(fields=['current_user', 'recommendation']),
        ]
    
    def __str__(self):
        return f"Similarity selection for {self.current_user} on {self.recommendation}"


# ===================== TELEMETRY MODELS =====================

class RecommendationTimeSpent(models.Model):
    """
    Track time spent on each recommendation
    """
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='recommendation_times')
    recommendation = models.ForeignKey(Recommendation, on_delete=models.CASCADE, related_name='participant_times')
    
    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(blank=True, null=True)
    duration_seconds = models.IntegerField(blank=True, null=True)
    
    # Session tracking
    session_id = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        unique_together = ['participant', 'recommendation', 'session_id']
        indexes = [
            models.Index(fields=['participant', 'recommendation']),
            models.Index(fields=['started_at']),
        ]
    
    def __str__(self):
        return f"{self.participant} - {self.recommendation} - {self.duration_seconds}s"
    
    def end_session(self):
        """End the session and calculate duration"""
        self.ended_at = timezone.now()
        if self.started_at:
            self.duration_seconds = int((self.ended_at - self.started_at).total_seconds())
        self.save()


class AvatarClick(models.Model):
    """
    Track avatar clicks with avatar type classification
    """
    AVATAR_TYPES = [
        ('featured', 'Featured Avatar'),
        ('current_user', 'Current User Avatar'),
        ('other', 'Other Avatar'),
    ]
    
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='avatar_clicks')
    recommendation = models.ForeignKey(Recommendation, on_delete=models.CASCADE, related_name='avatar_clicks')
    clicked_participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='clicks_received', help_text="The participant whose avatar was clicked")
    
    # Avatar classification
    avatar_type = models.CharField(max_length=20, choices=AVATAR_TYPES)
    
    # Context
    timestamp = models.DateTimeField(auto_now_add=True)
    session_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Position data
    click_x = models.IntegerField(blank=True, null=True)
    click_y = models.IntegerField(blank=True, null=True)

    # Created at and updated at
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['participant', 'recommendation']),
            models.Index(fields=['avatar_type', 'timestamp']),
            models.Index(fields=['clicked_participant']),
        ]
    
    def __str__(self):
        return f"{self.participant} clicked {self.clicked_participant} ({self.avatar_type}) on {self.recommendation}"

class MetaMedleyClick(models.Model):
    """
    Track meta-medley clicks
    """
    META_MEDLEY_TYPES = [
        ('bottom', 'Bottom (Against)'),
        ('middle', 'Middle (On the fence)'),
        ('top', 'Top (For)'),
    ]
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='meta_medley_clicks')
    recommendation = models.ForeignKey(Recommendation, on_delete=models.CASCADE, related_name='meta_medley_clicks')
    meta_medley_type = models.CharField(max_length=20, choices=META_MEDLEY_TYPES)
    session_id = models.CharField(max_length=255, null=True, blank=True, help_text="Session identifier for tracking")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return f"{self.participant} clicked {self.meta_medley_type} on {self.recommendation}"

class ParticipantProfileTime(models.Model):
    """
    Track time spent on participant profile modals
    """
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='profile_view_times')
    recommendation = models.ForeignKey(Recommendation, on_delete=models.CASCADE, related_name='profile_view_times')
    viewed_participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='profile_views_received', help_text="The participant whose profile was viewed")
    
    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(blank=True, null=True)
    duration_seconds = models.IntegerField(blank=True, null=True)
    
    # Session tracking
    session_id = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['participant', 'recommendation']),
            models.Index(fields=['viewed_participant']),
            models.Index(fields=['started_at']),
        ]
    
    def __str__(self):
        return f"{self.participant} viewed {self.viewed_participant} profile for {self.duration_seconds}s"
    
    def end_session(self):
        """End the session and calculate duration"""
        self.ended_at = timezone.now()
        if self.started_at:
            self.duration_seconds = int((self.ended_at - self.started_at).total_seconds())
        self.save()


class AudioClipListening(models.Model):
    """
    Track audio clip listening behavior
    """
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='audio_listening_sessions')
    recommendation = models.ForeignKey(Recommendation, on_delete=models.CASCADE, related_name='audio_listening_sessions')
    audio_clip = models.ForeignKey(InterviewClip, on_delete=models.CASCADE, related_name='listening_sessions', null=True, blank=True)
    audio_id = models.IntegerField(blank=True, null=True, help_text="Audio ID from InterviewUtterance")
    
    # Listening behavior
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(blank=True, null=True)
    duration_seconds = models.IntegerField(blank=True, null=True)
    
    # Audio progress tracking
    total_audio_duration = models.FloatField(blank=True, null=True, help_text="Total duration of audio clip in seconds")
    listened_duration = models.FloatField(blank=True, null=True, help_text="How much of the audio was actually listened to")
    completion_percentage = models.FloatField(blank=True, null=True, help_text="Percentage of audio completed (0-100)")
    
    # Playback events
    play_count = models.IntegerField(default=0, help_text="Number of times audio was played")
    pause_count = models.IntegerField(default=0, help_text="Number of times audio was paused")
    seek_count = models.IntegerField(default=0, help_text="Number of times user seeked in audio")
    
    # Session tracking
    session_id = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['participant', 'recommendation']),
            models.Index(fields=['audio_clip']),
            models.Index(fields=['started_at']),
        ]
    
    def __str__(self):
        return f"{self.participant} listened to {self.audio_clip} - {self.completion_percentage}% complete"
    
    def end_session(self):
        """End the session and calculate metrics"""
        self.ended_at = timezone.now()
        if self.started_at:
            self.duration_seconds = int((self.ended_at - self.started_at).total_seconds())
        
        # Calculate completion percentage
        if self.total_audio_duration and self.listened_duration:
            self.completion_percentage = min(100, (self.listened_duration / self.total_audio_duration) * 100)
        
        self.save()


class VotingScreenTime(models.Model):
    """
    Track time spent on voting screen (step 4)
    """
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='voting_screen_times')
    recommendation = models.ForeignKey(Recommendation, on_delete=models.CASCADE, related_name='voting_screen_times')
    
    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(blank=True, null=True)
    duration_seconds = models.IntegerField(blank=True, null=True)
    
    # Session tracking
    session_id = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['participant', 'recommendation']),
            models.Index(fields=['started_at']),
        ]
    
    def __str__(self):
        return f"{self.participant} - {self.recommendation} voting - {self.duration_seconds}s"
    
    def end_session(self):
        """End the session and calculate duration"""
        self.ended_at = timezone.now()
        if self.started_at:
            self.duration_seconds = int((self.ended_at - self.started_at).total_seconds())
        self.save()


# Utility functions for telemetry
def start_recommendation_session(participant, recommendation, session_id=None):
    """Start tracking time on a recommendation"""
    return RecommendationTimeSpent.objects.create(
        participant=participant,
        recommendation=recommendation,
        session_id=session_id
    )


def track_avatar_click(participant, recommendation, clicked_participant, avatar_type, click_x=None, click_y=None, session_id=None):
    """Track an avatar click"""
    return AvatarClick.objects.create(
        participant=participant,
        recommendation=recommendation,
        clicked_participant=clicked_participant,
        avatar_type=avatar_type,
        click_x=click_x,
        click_y=click_y,
        session_id=session_id
    )


def track_meta_medley_click(participant, recommendation, meta_medley_type, session_id=None):
    """Track a meta-medley button click"""
    return MetaMedleyClick.objects.create(
        participant=participant,
        recommendation=recommendation,
        meta_medley_type=meta_medley_type,
        session_id=session_id
    )


def start_profile_view_session(participant, recommendation, viewed_participant, session_id=None):
    """Start tracking time on a participant profile"""
    return ParticipantProfileTime.objects.create(
        participant=participant,
        recommendation=recommendation,
        viewed_participant=viewed_participant,
        session_id=session_id
    )


def start_audio_listening_session(participant, recommendation, audio_clip, total_duration=None, session_id=None):
    """Start tracking audio listening"""
    return AudioClipListening.objects.create(
        participant=participant,
        recommendation=recommendation,
        audio_clip=audio_clip,
        total_audio_duration=total_duration,
        session_id=session_id
    )


def start_voting_screen_session(participant, recommendation, session_id=None):
    """Start tracking time on voting screen"""
    return VotingScreenTime.objects.create(
        participant=participant,
        recommendation=recommendation,
        session_id=session_id
    )
