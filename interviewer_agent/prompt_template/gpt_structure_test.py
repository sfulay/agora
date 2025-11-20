import json
import random
import openai
import time 
import threading
import queue

import sys
import os

OPENAI_API_KEY = "" # Michael
KEY_OWNER = ""

# DEBUG = False
DEBUG = True

STORAGE_DIR = "storage"

GOOGLE_CRED_PATH = ""

INTERVIEW_AGENT_PATH = "interviewer_agent"
openai.api_key = OPENAI_API_KEY


def jsp_log(message): 
  from datetime import datetime
  formatted_time = datetime.now().strftime("%H:%M:%S")
  print (f'[gpt_structure.py] {formatted_time} -- {message}')


# ============================================================================
# #######################[SECTION 0: HELPER FUNCTIONS] #######################
# ============================================================================

def generate_prompt(curr_input, prompt_lib_file): 
  """
  Takes in the current input (e.g. comment that you want to classifiy) and 
  the path to a prompt file. The prompt file contains the raw str prompt that
  will be used, which contains the following substr: !<INPUT>! -- this 
  function replaces this substr with the actual curr_input to produce the 
  final promopt that will be sent to the GPT3 server. 
  ARGS:
    curr_input: the input we want to feed in (IF THERE ARE MORE THAN ONE
                INPUT, THIS CAN BE A LIST.)
    prompt_lib_file: the path to the promopt file. 
  RETURNS: 
    a str prompt that will be sent to OpenAI's GPT server.  
  """
  if type(curr_input) == type("string"): 
    curr_input = [curr_input]
  curr_input = [str(i) for i in curr_input]

  f = open(prompt_lib_file, "r")
  prompt = f.read()
  f.close()
  for count, i in enumerate(curr_input):   
    prompt = prompt.replace(f"!<INPUT {count}>!", i)
  if "<commentblockmarker>###</commentblockmarker>" in prompt: 
    prompt = prompt.split("<commentblockmarker>###</commentblockmarker>")[1]
  return prompt.strip()


def truncate_prompt_content(prompt, 
                            trunc_char_threshold=10000, 
                            content_sig="=*=*="):
    if len(prompt) <= trunc_char_threshold: 
      return prompt

    # Check if content_sig is in prompt
    if content_sig not in prompt:
        return prompt

    # Split the prompt into two parts
    parts = prompt.split(content_sig)
    before_content = parts[0]
    after_content = content_sig.join(parts[1:])

    # Truncate the first part to the specified threshold
    truncated_before_content = before_content[-trunc_char_threshold:]
    truncated_before_content = "[... Truncated] " + truncated_before_content

    # Rejoin the two parts
    return f"{truncated_before_content} \n {content_sig} \n {after_content}"


# ============================================================================
# ################## [SECTION 1: SAFE GENERATE (Threading)] ##################
# ============================================================================

def ChatGPT_simple_request(prompt, system_prompt=""): 
  try: 
    if system_prompt: 
      completion = openai.chat.completions.create(
        model="gpt-3.5-turbo", 
        messages=[
          {"role": "system", "content": system_prompt},
          {"role": "user", "content": prompt}
        ]
      )
    else: 
      completion = openai.chat.completions.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt}])
    output = completion.choices[0].message.content
    return output
  except Exception as e:
    return "GENERATION ERROR"


def threaded_ChatGPT_simple_request(prompt, 
                                    system_prompt="", 
                                    timeout=60, 
                                    max_retries=3):
  """
  Sends a prompt to OpenAI's ChatGPT and retrieves a response using a threaded
  approach with retries.

  This function creates a thread to send a prompt to the ChatGPT model and 
  waits for a response. It retries the request up to a maximum number of times 
  if it fails to get a response within a specified timeout.

  Args:
    prompt (str): The user's prompt to send to the ChatGPT model.
    system_prompt (str, optional): An additional system-level prompt to 
      provide context or instructions to the model. Useful for setting up a 
      specific scenario or providing guidelines for the response.
      Defaults to an empty string.
    timeout (int, optional): The maximum number of seconds to wait for a 
      transcription to complete before timing out. Defaults to 8 seconds.
    max_retries (int, optional): The maximum number of times to retry the 
      transcription in case of failure or timeout. Defaults to 3 retries.

  Returns:
    str: The response from ChatGPT, or an error message if the request 
      fails or the thread hangs.
  """
  # Function to be executed in a thread
  def chatgpt_request_thread(queue, prompt, system_prompt):
    try:
      response = ChatGPT_simple_request(prompt, system_prompt)
      queue.put(response)
    except Exception as e:
      queue.put(e)

  jsp_log("Threading: Starting the thread for ChatGPT generation")
  jsp_log(f"Threading: Timeout: {timeout}, max retries: {max_retries}")

  # Initialize a queue to hold the response
  q = queue.Queue()

  # Retry mechanism
  for count in range(max_retries):
    # Start a thread for the ChatGPT request
    thread = threading.Thread(target=chatgpt_request_thread, 
                              args=(q, prompt, system_prompt))
    thread.start()
    jsp_log(f"Threading: Starting the current thread: {count}")

    try:
      # Wait for the thread to complete with timeout
      result = q.get(block=True, timeout=timeout)
      # Check if the result is an exception and raise it
      if isinstance(result, Exception):
          raise result
      # If successful, return the response
      return result
    except queue.Empty:
      # Handle timeout, log if necessary
      jsp_log(f"Threading: Timed out after {timeout} seconds.")
    except Exception as e:
      # Handle other exceptions, log if necessary
      jsp_log(f"Threading: Error during ChatGPT request: {e}")
    finally:
      # Ensure the thread is terminated
      thread.join()

  # Return an error message if the request fails after maximum retries
  return "THREAD HANGING"


def threaded_chat_safe_generate(prompt, 
                                gpt_version="ChatGPT",
                                repeat=3,
                                fail_safe_response="error",
                                func_validate=None,
                                func_clean_up=None,
                                verbose=False): 
  """
  Generates responses to a prompt using ChatGPT with safety and validation 
  checks, retrying if necessary.

  This function sends a prompt to ChatGPT and retrieves a response. It 
  includes additional mechanisms for validation and cleanup of the generated 
  response. The function retries the generation process a specified number of 
  times if the initial attempts are not successful or do not pass validation.

  Args:
    prompt (str): The prompt to be sent to the ChatGPT model.
    gpt_version (str, optional): The version of the GPT model to use. 
      Defaults to "ChatGPT".
    repeat (int, optional): The number of times to retry generating a 
      response if validation fails. Defaults to 3.
    fail_safe_response (str, optional): The response to return if all 
      retries fail or an error occurs. Defaults to "error".
    func_validate (callable, optional): A function to validate the generated 
      response. It should take two arguments: the response and the original 
      prompt, and return a boolean.
    func_clean_up (callable, optional): A function to clean up or modify the 
      generated response before returning it. It should take two arguments: 
      the response and the original prompt, and return a modified response.
    verbose (bool, optional): If True, enables additional logging for 
      debugging. Defaults to False.

  Returns:
    str: The generated and processed response from ChatGPT, or the fail-safe 
      response if generation fails.
  """
  print (f"LENGTH::: {len(prompt)}")
  print (f"PROMPT: {prompt}")
  prompt = truncate_prompt_content(prompt)
  print (f"TRUNC PROMPT: {prompt}")

  if verbose: 
    jsp_log(f"Current prompt:\n {prompt}")

  for i in range(repeat): 
    try:
      curr_gpt_response = threaded_ChatGPT_simple_request(prompt).strip()
      print (curr_gpt_response)

      if curr_gpt_response == "GENERATION ERROR": 
        print ("GENERATION ERROR")
        time.sleep(2**i)

      if curr_gpt_response == "THREAD HANGING": 
        print ("THREAD HANGING")
        break
        
      print ("???")
      print ("???", func_validate(curr_gpt_response, prompt=prompt))
      if func_validate(curr_gpt_response, prompt=prompt): 
        return func_clean_up(curr_gpt_response, prompt=prompt)

      jsp_log(f"Error occurred in generating.")
      jsp_log(f"Current repeat count is {i}.")
      jsp_log(f"Current erred response is {curr_gpt_response}.")

    except:
      pass

  jsp_log(f"We failed to generate: {curr_gpt_response}")
  jsp_log(f"Following failsafe is triggered: {fail_safe_response}")
  return fail_safe_response


# ============================================================================
# #################### [SECTION 2: OTHER API FUNCTIONS] ######################
# ============================================================================

def get_embedding(text, model="text-embedding-ada-002"):
  """
  Generates an embedding for a given text using OpenAI's specified embedding 
  model.

  This function creates a numerical representation (embedding) of the provided 
  text. It is useful for various natural language processing tasks like 
  semantic analysis, similarity comparison, etc. The function uses OpenAI's 
  Embedding API to generate the embedding.

  Args:
    text (str): The text for which the embedding is to be generated.
    model (str, optional): The model to be used for generating the embedding. 
      Defaults to "text-embedding-ada-002".

  Returns:
    list: A list of numerical values representing the embedding of the given 
      text.
  """
  text = text.replace("\n", " ")
  if not text: 
    text = "this is blank"
  return openai.Embedding.create(
    input=[text], model=model)['data'][0]['embedding']






if __name__ == '__main__':
  import json
  def __chat_func_clean_up(gpt_response, prompt=""): 
    gpt_response = json.loads(gpt_response) 
    return gpt_response

  def __chat_func_validate(gpt_response, prompt=""): 
    try: 
      response = __chat_func_clean_up(gpt_response)
      return True
    except:
      return False 
  testp = """Here is a conversation between an interviewer and an interviewee. 
Interviewer: Let's start with an icebreaker -- I am going to ask you a few simple questions. First, what is your personality?
Interviewee: 
Interviewer: That's alright. Take your time to think about it. When you're ready, I would love to hear your thoughts on your personality.
Interviewee: 
Interviewer: That's alright. Take your time to think about it. When you're ready, I would love to hear your thoughts on your personality.
Interviewee: And I'm here to talk to you about how to make sure which ideas will succeed. And in any case, if your idea succeeds, it has as much to do with how well you execute as your initial idea anyway. But certain ideas are much more likely to succeed than others. And so my goal here is to help you stack the deck in your favor by starting with a promising idea. The advice in this talk came from several places. First, I analyzed the top 100 YC companies by valuation, and I looked at how they all got their idea. So I started with some hard quantitative data on how recent billion-dollar companies actually came up with their idea. It also draws on a classic essay by Paul Graham that I really recommend. It's called How to Get Startup Ideas. It also comes from helping YC companies that pivot in the middle of the batch and learning over the years what advice helps them to find a new good startup idea. And then finally, it comes from reading thousands of YC applications that we rejected and looking at the mistakes that caused good founders to come up with bad ideas. Those are the mistakes I'm going to help you all avoid. This talk's got three parts. First, I'm going to tell you the most common mistakes founders make with startup ideas. Then I'm going to talk about how to know if your idea is good. And then about how to come up with new ones. Okay, the four most common mistakes with startup ideas. So the most common mistake is just building something that doesn't solve a real problem for your users. Typically, you can articulate the problem that you're solving. You can put it in words. But when you actually go and talk to the users, it's just not something that they really care about. We call it a solution in search of a problem or a SISP. Let's go through an example. So a lot of founders come up with an idea with this kind of thought process. They go, hmm, AI is cool. What can I apply AI to? And then they go look for a problem that they could solve with AI. That's a solution in search of a problem. And the reason it's dangerous is that if you do that, you'll probably find a problem. But it will be a superficially plausible problem. It'll be a made-up problem that people don't really care about rather than a real problem that people actually care about. And if people don't really care about the problem, they won't really care about your solution. So instead, you want to fall in love with a problem. The best way to find a startup idea is to start with a high-quality problem. Now, sometimes founders hear this, and they decide to interpret that as guidance to work on some, like, huge societal problem. Like, I don't know, global poverty or something. No doubt, those are real problems, but they're too abstract to make good starting points for startup ideas. You need something that's more specific, something that's tractable with a startup. The next mistake is getting stuck on what we call tar pit ideas. What's a tar pit idea? So there's this certain set of common startup ideas that have been around for forever. They have been applying in droves to YC batch after batch for years. And when founders start working on these ideas, it's like they've gotten stuck in tar. They never seem to go anywhere. So we call them tar pit ideas. Here's what causes tar pit ideas. They all form around some, like, widespread problem that lots of potential founders encounter. And it's a problem that seems like it could be easily solved with a startup, but it's an illusion. There's actually a structural reason why it's very hard or impossible to solve, which is why, after all these years, no one has solved it. And you can see why ideas like this would be so dangerous, why they will cause so many founders to waste months of their life stuck in a tar pit. Like, they're very tantalizing from a distance because they're so superficially plausible as startup ideas. Here's a concrete example. This is a very common tar pit idea that's been applying to YC for, like, 20 years. This is, like, the stereotypical college student idea, and it goes like this. You think, man, every Friday or Saturday night when I'm making plans to meet up with my friends, it's so inefficient. I'm in all these different text threads and chat groups, and we're, like, trying to make plans to meet up. I'm just going to make an app to make it more efficient. Well, it turns out that there are some structural reasons why this idea is hard, which is why, in, like, 20 years of people applying to YC with this idea, nobody has actually pulled it off. You can see why so many people have been attracted to it. It's, like, it's a problem that almost everyone encounters at some point, and it seems, like, maybe so easy to solve. Like, you can just imagine the app. It's just got, like, a list of events, and you invite friends to it. Like, it seems so simple. The thing about tar pit ideas is that they are not necessarily impossible. Like, I'm even open-minded that somebody will eventually make the, like, app to meet up with your friends idea work. It's more accurate to think of them as common ideas that are much harder than they seem. So if you want to work on one, here's my advice. First, Google it. It's amazing how many founders skip the step of just, like, Googling for their own startup idea to see who has worked on it in the past. You should find who's worked on this in the past and actually talk to them if you can. Try to figure out what the hard part of this idea is that has caused other people to not be able to solve it yet. The next mistake is simple. It is amazing how many founders will basically just, like, jump into the first idea they have without even...
Interviewer: Thank you for sharing your insights on startup ideas, Joon.

Interviewer: And what is your favorite painting?
Interviewee: I'm a founder of the company, and I'm here to talk about the importance of having a good business. So, the first thing to consider is whether it would actually make a good business. But more dangerous is the founders on the opposite side of the spectrum who sit around waiting for the perfect startup idea. And of course, there is no such thing, so these people just never actually start a company. So, if you imagine that there's like a spectrum between picking the first idea that comes to mind and waiting for the perfect idea, and you know, somewhere in the middle, there's this like happy place, which is the place that you want to be, right? And the way that Paul Graham put this is that you should think of your idea as a good starting point. No startup idea is perfect, and no matter what you start with, it's probably going to morph anyway. So, you just want to have an initial idea that has enough interesting qualities that can morph in the right direction. So, now suppose you have a startup idea, and you want to know if it's good. I'm going to give you a framework for this, and the format of the framework is 10 key questions to ask about any startup idea. So, the first one is, do you have founder market fit? If I had to pick like one most important criteria, it'd probably be this one. And what I mean by founder market fit is just, are you the right team to be working on this idea? And a great example of what good founder market fit looks like is PlanGrid. So, PlanGrid makes an iPad app to view construction blueprints. And two of the founders of PlanGrid were Tracy and Ralph. Tracy had worked in the construction industry, and she knew a lot about construction. And Ralph was an awesome developer who was like the perfect person to build this iPad. If you were going to imagine a team to start PlanGrid, the team that you would imagine would look, you know, something like that. And that's what good founder market fit looks like. It's like this team is obviously the right team to work on the idea. In fact, founder market fit is so important that I would recast your search for a startup idea. When people go to pick a startup idea, they try to look for a good startup idea, like in the abstract. And instead, I would think about this exercise as an exercise to pick a good idea for your team. Are you with me? It doesn't matter if something is a good startup idea for someone else if it's not a good idea for your team. So, you may as well just look for ideas that you would actually be good at executing. Okay, number two, how big is the market? Obviously you need a big market, which for startups typically means a billion-dollar market. But actually, less obviously, there are two kinds of markets for startups that are good. Ones that are big now and ones that are small but rapidly grow. And an example of the second one is Coinbase. So when Coinbase got started in 2012, the Bitcoin trading market was minuscule. But even at that time, it was pretty obvious that if Bitcoin succeeded the way people hoped that it would, that this would eventually be a billion-dollar market. Number three, how acute is this problem? So as I said earlier, the most common mistake is just like working on something that just isn't really a problem or it's just not a problem that people care enough about. Here's an example of the opposite. Here's an example of what a good problem looks like. Brex. So, Brex from winter 2017 makes a credit card for startups. Before Brex, if a startup in YC wanted a corporate credit card, they literally could not get one because no bank would give a credit card to a startup. That's a good problem. Like if the alternative to your solution is literally nothing, that's what a good problem looks like. Okay, next. Do you have competition? Now, most founders think that if you have competition, that that's bad. But counterintuitively, it is the opposite. Idea is a good starting point. No startup idea is perfect and no matter what you start with, it's probably going to morph anyway. So you just want to have an initial idea that has enough interesting qualities that can morph in the right direction. So now suppose you have a startup idea and you want to know if it's good. I'm going to give you a framework for this and the format of the framework is 10 key questions to ask about any startup. So the first one is, do you have founder market fit? If I had to pick like one most important criteria, it would probably be this one. And what I mean by founder market fit is just, are you the right team to be working on this idea? And a great example of a good founder market fit looks like is PlanGrid. So PlanGrid makes an iPad app to view construction blueprints. And two of the founders of PlanGrid were Tracy and Ralph. And Tracy had worked in the construction industry and she knew a lot about construction. And Ralph was an awesome developer who was like the perfect person to build this iPad. If you were going to imagine a team to start PlanGrid, the team that you would imagine would look, you know, something like that. And that's what good founder market fit looks like. It's like this team is obviously the right team to work on the idea. In fact, founder market fit is so important that I would recast your search for a startup idea. When most people go to pick a startup idea, they try to look for a good startup idea in the app style. But instead, I would think about this exercise as an exercise to pick a good idea for your team. Are you with me? It doesn't matter if something is a good startup idea for someone else if it's not a good idea for your team. So you may as well just look for ideas that you would actually be good at executing. Okay, number two, how big is the market? Obviously you need a big market, which for startups typically means a billion dollar market. But actually, less obviously, there are two kinds of markets for startups that are good. Ones that are big now and ones that are small but rapidly grow. And an example of the second one is Coinbase. So when Coinbase got started in 2012, the Bitcoin trading market was minuscule. But even at that time, it was pretty obvious that if Bitcoin succeeded the way people hoped it would, that this would eventually be a billion dollar market. Number three, how acute is this problem? So as I said earlier, the most common mistake is just like working on something that just isn't really a problem or it's just not a problem that people care enough about. Here's an example of the opposite. Here's an example of what a good problem looks like. Brex. So Brex from winter 2017 makes a credit card for startups. Before Brex, if a startup in YC wanted a corporate credit card, they literally could not get one because no bank would give a credit card to a startup. That's a good problem. If the alternative to your solution is literally nothing, that's what a good problem looks like. And next, do you have competition? Now most founders think that if you have competition, that that's bad. But counterintuitively, it is the opposite. Most good startup ideas have competition. But if you are going up against especially entrenched competition, you typically need a new insight. Next one is like, do you want this personally? Do you know people personally who want this? It's amazing how often people start companies where the answer to both these questions is no. If that's the case, you definitely got to worry that, you know, maybe nobody wants this. So definitely time to go talk to some users. Did this only recently become possible or only recently become necessary? So something has recently changed in the world, like a new technology, regulatory change, or a new problem. That is often what creates a new opportunity. And a great example of this is a company called Checkr, which does background checks via an API. It's an API for doing background checks on people. And roughly the story of Checkr is delivery services like DoorDash and Instacart and Uber started to take off. And they were all hiring huge pools of delivery people and workers. And they needed to run background checks on all of these people. And there were at the time already a bunch of large existing companies that run background checks, but they weren't well suited for this very new use case. And that is like exactly the kind of change in the world that creates a new opportunity. Let's talk about proxies. So a proxy is a large company that does something similar to your startup, but it is not a direct competitor. And so a good example of this in practice is a company called Rappi, which does food delivery in Latin America. And when Rappi got started, there were already food delivery companies in other parts of the world like DoorDash that were doing very well. They just hadn't caught on in Latin America yet. And so DoorDash was a great proxy to show that this idea of doing food delivery in Latin America would probably work. Is this an idea you'd want to work on for years? But this is a tricky one. Sure, if the answer to this question is yes, that's a good sign. But often it's not. Often an idea grows on founders over time as it starts to work. As I'm going to talk about in a moment, a lot of the best startup ideas are in boring spaces like tax accounting software or something like that. No one is particularly passionate about that. Nobody starts off being passionate about tax accounting software. But tax accounting software is probably a good business. And if you're actually running a successful business, you tend to become passionate about it over time. Is this a scalable business? So if you're building pure software, the answer is yes, because software scales infinitely and you can just like check this one off. The place where founders most often get into trouble here is with services businesses like agencies or dev shops, anything that requires like high skill human labor in order to serve your customers. Okay, my last question is, is this a good idea space? Which of course means I need to tell you what an idea space is. This is a concept from my colleague Dalton, who you'll hear from later in this course. An idea space is like one level of abstraction out from a particular startup idea. It is a class of closely related startup ideas.


=*=*=
Task: Very succinctly summarize the facts about the interviewee based on the conversation above in a few bullet points -- again, think short, concise, bullet points.
Output format: Json dictionaries of 1~3 key-value pair(s) where the keys are a keyword describing the bullet point, and values are a phrase or a one sentence description of that keyword: 
{"<key>": "<val>"}
(Example json output: {"name": "Jane Doe", "age": "21", "favorite food": "pasta"}) 
  """
  ret = threaded_chat_safe_generate(testp, 
                                    gpt_version="ChatGPT",
                                    repeat=2,
                                    fail_safe_response="error",
                                    func_validate=__chat_func_validate,
                                    func_clean_up=__chat_func_clean_up,
                                    verbose=False)

  print ("=== fin")
  print (ret)






























