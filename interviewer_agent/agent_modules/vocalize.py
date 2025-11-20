import threading
import queue
import json
import openai

from global_methods import *
from interviewer_agent.interviewer_utils.settings import * 

openai.api_key = get_open_api_keyset()["key"]


def jsp_log(message): 
  from datetime import datetime
  formatted_time = datetime.now().strftime("%H:%M:%S")
  print (f'[vocalize.py] {formatted_time} -- {message}')


def generate_voice(curr_input="Hello there!", voice="nova"): 
  """
  Generates synthetic speech audio from text using OpenAI's text-to-speech 
  model.

  This function converts a given text input to speech using a specified voice 
  model. It utilizes OpenAI's text-to-speech (TTS) API to create the speech 
  audio.

  Args:
    curr_input (str, optional): The text to be converted into speech. Defaults
      to "Hello there!".
    voice (str, optional): The identifier for the voice model to be used for 
      speech generation. Defaults to "nova".

  Returns:
      bytes: The generated audio data as a byte stream.
  """
  jsp_log(f'Creating a voice for the following text: "{curr_input}"')
  response = openai.audio.speech.create(
    model="tts-1",
    voice=voice,
    input=curr_input,
  )
  audio_data = response.content 
  return audio_data


def threaded_generate_voice(curr_input="Hello there!",  
                            voice="nova", 
                            timeout=50, 
                            max_retries=4):
  """
  Generates synthetic speech audio from text using a threaded approach with 
  retries and timeout handling.

  This function creates a thread to handle the voice generation process using 
  the `generate_voice` function. It retries the voice generation up to a 
  specified number of times if it fails or times out.

  Args:
    curr_input (str, optional): The text to be converted into speech. 
      Defaults to "Hello there!".
    voice (str, optional): The identifier for the voice model to be used for 
      speech generation. Defaults to "nova".
    timeout (int, optional): The maximum number of seconds to wait for voice 
      generation to complete before timing out. Defaults to 30 seconds.
    max_retries (int, optional): The maximum number of times to retry the 
      voice generation in case of failure or timeout. Defaults to 3 retries.

  Returns:
    bytes: The generated audio data as a byte stream, or None if voice 
      generation fails after maximum retries.
  """
  # Function to be executed in a thread
  def generate_voice_thread(queue, curr_input, voice):
    try:
      audio_data = generate_voice(curr_input, voice)
      queue.put(audio_data)
    except Exception as e:
      queue.put(e)

  jsp_log("Threading: Starting the thread for vocalizing the script")
  jsp_log(f"Threading: Timeout: {timeout}, max retries: {max_retries}")

  jsp_log(f"Threading: Current input len: {len(curr_input)}")
  if len(curr_input) > 4095: 
    jsp_log(f"Threading: Curr len too long (max is 4096). Truncating.")
    curr_input = curr_input[:4095]

  # Initialize a queue to hold the audio data
  q = queue.Queue()
  jsp_log(f"Max retries: {max_retries}")
  # Retry mechanism
  for count in range(max_retries):
      jsp_log(f"Threading: Starting the current thread: {count}")
      # Start a thread for voice generation
      thread = threading.Thread(target=generate_voice_thread, args=(q, curr_input, voice))
      thread.start()
      jsp_log(f"Threading: Starting the current thread: {count}")

      try:
          # Wait for the thread to complete with timeout
          result = q.get(block=True, timeout=timeout)
          # Check if the result is an exception and raise it
          if isinstance(result, Exception):
              raise result
          # If successful, return the audio data
          return result
      except queue.Empty:
          # Handle timeout, log if necessary
          jsp_log(f"Threading: Timed out after {timeout} seconds.")
      except Exception as e:
          # Handle other exceptions, log if necessary
          jsp_log(f"Threading: Error during transcription: {e}")
      finally:
          # Ensure the thread is terminated
          jsp_log(f"Threading: Joining the thread: {count}")
          thread.join(timeout=1)
          jsp_log(f"Threading: Joined the thread: {count}")

  # Return None if voice generation fails after maximum retries
  return None










