import threading
import queue
import io
import openai
import time

from pydub import AudioSegment
from google.cloud import speech

import sys
import os

OPENAI_API_KEY = "" # Percy
KEY_OWNER = "Percy Liang"

# DEBUG = False
DEBUG = True

STORAGE_DIR = "storage"

GOOGLE_CRED_PATH = ""

INTERVIEW_AGENT_PATH = "interviewer_agent"
openai.api_key = OPENAI_API_KEY


def jsp_log(message): 
  from datetime import datetime
  formatted_time = datetime.now().strftime("%H:%M:%S")
  print (f'[transcribe.py] {formatted_time} -- {message}')


def transcribe_voice(audio_buffer, optional_key_phrases=["my name is Joon"]):
  """
  Transcribes voice from an audio buffer using Google Speech-to-Text and 
  OpenAI's Whisper.

  The function first converts the audio buffer to an AudioSegment object to 
  determine its duration. If the audio is shorter than 20 seconds, it uses 
  Google's Speech-to-Text API for transcription, leveraging a service account 
  for authentication and enabling automatic punctuation.

  (Note: even when we use Google API, we still run this through Whisper, 
  which is more accurate. This is to compensate for Whisper's downside, which
  is that it is weak against empty audio as it hallucinates.)

  In case there are no results from Google's API, or if the audio is longer 
  than 20 seconds, the function then utilizes OpenAI's Whisper model. The 
  model is provided with the language setting and optional key phrases to 
  assist in the transcription process.

  Args:
    audio_buffer (BytesIO): A buffer containing the audio data.
    optional_key_phrases (list of str, optional): A list of key phrases that
      may be present in the audio. Useful for improving the accuracy of 
      transcription in case of specific or hard-to-spell words. 
      Defaults to ["my name is Joon"].

  Returns:
      str: The transcribed text.
  """
  duration_seconds = len(AudioSegment.from_file(audio_buffer)) / 1000.0  
  jsp_log("Starting to actually transcribe user's voice")
  jsp_log(f"Audio duration: {duration_seconds} seconds")

  if duration_seconds < 20: 
    # Use service account credentials by specifying the private key file
    g_client = speech.SpeechClient.from_service_account_json(GOOGLE_CRED_PATH)

    # The buffer's bytes can be directly used as the content
    content = audio_buffer.getvalue()
    audio = speech.RecognitionAudio(content=content)

    # Configure the request with the desired parameters
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        language_code="en-US",
        enable_automatic_punctuation=True  # Enable automatic punctuation
    )
    # Transcribe the audio file
    response = g_client.recognize(config=config, audio=audio)

    jsp_log(f"From Google API: {response.results}")
    if not response.results: 
      jsp_log("Ending transcription with an empty str")
      return ""

  # For capturing hard to spell words, like names
  optional_key_phrases = ', '.join(optional_key_phrases)
  audio_buffer.name = "file.wav"
  whisper_completion = openai.audio.transcriptions.create(
    model="whisper-1", 
    file=audio_buffer,
    language="en",
    prompt=optional_key_phrases)
  user_speech = whisper_completion.text

  jsp_log(f"Whisper API keyword: {optional_key_phrases}")
  jsp_log(f"From Whisper API: {user_speech}")
  return user_speech


def threaded_transcribe_voice(audio_buffer, 
                              optional_key_phrases=["my name is Joon"], 
                              timeout=50, 
                              max_retries=3):
  """
  Transcribes voice from an audio buffer using a threaded approach with 
  retries and timeout handling.

  This function creates a thread to handle the transcription process. It 
  retries the transcription up to a specified number of times if it fails or 
  times out. The function uses the `transcribe_voice` function for the actual 
  transcription.

  Args:
    audio_buffer (BytesIO): A buffer containing the audio data.
    optional_key_phrases (list of str, optional): A list of key phrases 
      that may be present in the audio. Useful for improving the accuracy 
      of transcription in case of specific or hard-to-spell words.
      Defaults to ["my name is Joon"].
    timeout (int, optional): The maximum number of seconds to wait for a 
      transcription to complete before timing out. Defaults to 8 seconds.
    max_retries (int, optional): The maximum number of times to retry the 
      transcription in case of failure or timeout. Defaults to 3 retries.

  Returns:
    str: The transcribed text, or a placeholder string "..." if 
      transcription fails after maximum retries.
  """
  # Function to be executed in a thread
  def transcribe_thread(queue, audio_buffer, optional_key_phrases):
    try:
      transcription = transcribe_voice(audio_buffer, optional_key_phrases)
      queue.put(transcription)
    except Exception as e:
      queue.put(e)

  jsp_log("Threading: Starting the thread for transcribing voice")
  jsp_log(f"Threading: Timeout: {timeout}, max retries: {max_retries}")

  # Initialize a queue to hold the transcription result
  q = queue.Queue()

  # Retry mechanism
  for count in range(max_retries):
    # Start a thread for transcription
    thread = threading.Thread(target=transcribe_thread, 
                              args=(q, audio_buffer, optional_key_phrases))
    thread.start()
    jsp_log(f"Threading: Starting the current thread: {count}")

    try:
      # Wait for the thread to complete with timeout
      result = q.get(block=True, timeout=timeout)
      # Check if the result is an exception and raise it
      if isinstance(result, Exception):
          raise result
      # If successful, return the transcription
      return result
    except queue.Empty:
      # Handle timeout, log if necessary
      jsp_log(f"Threading: Timed out after {timeout} seconds.")
    except Exception as e:
      # Handle other exceptions, log if necessary
      jsp_log(f"Threading: Error during transcription: {e}")
    finally:
      # Ensure the thread is terminated
      thread.join()

  # Return a placeholder if transcription fails after maximum retries
  return "..."


if __name__ == '__main__':
  # Path to the audio file
  audio_file_path = "agent_modules/user_119.wav"

  # Open the audio file and read it into a BytesIO buffer
  with open(audio_file_path, "rb") as audio_file:
      audio_buffer = io.BytesIO(audio_file.read())

  start_time = time.time()
  # Transcribe the audio file
  transcription = threaded_transcribe_voice(audio_buffer, 
                    ["my name is Joon"], 10, 3)
  
  end_time = time.time()
  elapsed_time = end_time - start_time

  # Output the transcription result
  print("Transcription Result:")
  print(transcription)
  print(f"Time elapsed: {elapsed_time} seconds")




















