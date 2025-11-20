import json
import random
import ast
import re
import sys
sys.path.append('../')

from global_methods import *

from interviewer_agent.interviewer_utils.settings import * 
from interviewer_agent.prompt_template.gpt_structure import *
from interviewer_agent.prompt_template.print_prompt import *

prompt_dir = f"interviewer_agent/prompt_template/prompts"


def run_gpt_generate_conditional(character, 
                                 p_notes, 
                                 q, 
                                 convo_str, 
                                 test_input=None, 
                                 verbose=False): 
  def create_prompt_input(character, p_notes, q, convo_str, test_input=None):
    prompt_input = [character["name"], 
                    character["characteristics"], 
                    p_notes, 
                    character["name"], 
                    q.q_content, 
                    convo_str, 
                    q.q_condition]
    return prompt_input

  def __chat_func_clean_up(gpt_response, prompt=""): 
    gpt_response = json.loads(gpt_response) 
    ret = {}
    ret["assessment"] = gpt_response["assessment"]
    ret["determination"] = gpt_response["determination"]
    return ret

  def __chat_func_validate(gpt_response, prompt=""): 
    try: 
      response = __chat_func_clean_up(gpt_response)
      return True
    except:
      return False 

  def get_fail_safe():
    ret = {}
    ret["assessment"] = "..."
    ret["objective accomplished"] = True
    ret = json.dumps(ret)
    return ret

  prompt_template = f"{prompt_dir}/conditional_v2.txt" 
  prompt_input = create_prompt_input(character, p_notes, q, convo_str) 
  prompt = generate_prompt(prompt_input, prompt_template)
  fail_safe = get_fail_safe() 
  output = threaded_chat_safe_generate(prompt, 
                                       "ChatGPT", 
                                       3, 
                                       fail_safe, 
                                       __chat_func_validate, 
                                       __chat_func_clean_up, 
                                       verbose)
  if DEBUG or verbose: 
    print_run_prompts(prompt_template, prompt_input, prompt, output)
  return output, [output, prompt, prompt_input, fail_safe]



def run_gpt_generate_factual_next_interview_step(character, 
                                                 p_notes, 
                                                 q, 
                                                 convo_str, 
                                                 test_input=None, 
                                                 verbose=False): 
  def create_prompt_input(character, p_notes, q, convo_str, test_input=None):
    prompt_input = [character["name"], 
                    character["characteristics"], 
                    p_notes, 
                    character["name"], 
                    q.q_content, 
                    convo_str, 
                    q.q_requirement]
    return prompt_input

  def __chat_func_clean_up(gpt_response, prompt=""): 
    gpt_response = json.loads(gpt_response) 
    ret = {}
    ret["assessment"] = gpt_response["assessment"]
    ret["completed"] = gpt_response["objective accomplished"]
    ret["next_utt"] = gpt_response["interviewer next utterance"]

    if ret["completed"]: 
      ret["skip_user_utt"] = True
    return ret

  def __chat_func_validate(gpt_response, prompt=""): 
    try: 
      response = __chat_func_clean_up(gpt_response)
      return True
    except:
      return False 

  def get_fail_safe():
    ret = {}
    ret["assessment"] = "..."
    ret["objective accomplished"] = "true"
    ret["interviewer next utterance"] = "hmm ..."
    ret = json.dumps(ret)
    return ret

  prompt_template = f"{prompt_dir}/factualq_next_interview_step_v2.txt" 
  prompt_input = create_prompt_input(character, p_notes, q, convo_str) 
  prompt = generate_prompt(prompt_input, prompt_template)
  fail_safe = get_fail_safe() 
  output = threaded_chat_safe_generate(prompt, 
                                       "ChatGPT", 
                                       3, 
                                       fail_safe, 
                                       __chat_func_validate, 
                                       __chat_func_clean_up, 
                                       verbose)
  if DEBUG or verbose: 
    print_run_prompts(prompt_template, prompt_input, prompt, output)
  return output, [output, prompt, prompt_input, fail_safe]


def run_gpt_generate_qualitative_next_interview_step(character, 
                                                     p_notes, 
                                                     q, 
                                                     convo_str,
                                                     test_input=None, 
                                                     verbose=False,
                                                     prompt_template_file="qualitativeq_next_interview_step_v2"): 
  def create_prompt_input(character, p_notes, q, convo_str, test_input=None):
    prompt_input = [character["name"], 
                    character["characteristics"], 
                    p_notes, 
                    character["name"], 
                    q.q_content, 
                    convo_str, 
                    q.q_requirement]
    return prompt_input

  def __chat_func_clean_up(gpt_response, prompt=""): 
    gpt_response = json.loads(gpt_response) 
    ret = {}
    if prompt_template_file == "qualitativeq_next_interview_step_v2": 
      ret["assessment"] = gpt_response["assessment"]
    ret["completed"] = False
    if "completed" in gpt_response: 
      ret["completed"] = gpt_response["completed"]
    ret["next_utt"] = gpt_response["interviewer next utterance"]
    ret["skip_user_utt"] = False
    return ret

  def __chat_func_validate(gpt_response, prompt=""): 
    try: 
      response = __chat_func_clean_up(gpt_response)
      return True
    except:
      return False 

  def get_fail_safe():
    ret = {}
    ret["assessment"] = "..."
    ret["completed"] = "true"
    ret["interviewer next utterance"] = "hmm ..."
    ret = json.dumps(ret)
    return ret

  prompt_template = f"{prompt_dir}/{prompt_template_file}.txt"
  prompt_input = create_prompt_input(character, p_notes, q, convo_str) 
  prompt = generate_prompt(prompt_input, prompt_template)
  fail_safe = get_fail_safe() 
  output = threaded_chat_safe_generate(prompt, 
                                       "ChatGPT", 
                                       3, 
                                       fail_safe, 
                                       __chat_func_validate,
                                       __chat_func_clean_up, verbose)
  if DEBUG or verbose: 
    print_run_prompts(prompt_template, prompt_input, prompt, output)
  return output, [output, prompt, prompt_input, fail_safe]


def run_gpt_generate_q_end_thankyou(character, 
                                    q, 
                                    p_notes, 
                                    convo_str,
                                    test_input=None, 
                                    verbose=False): 
  def create_prompt_input(character, p_notes, q, convo_str, test_input=None):
    prompt_input = [character["name"], 
                    character["characteristics"], 
                    p_notes, 
                    character["name"], 
                    q.q_content, 
                    convo_str]
    return prompt_input

  def __chat_func_clean_up(gpt_response, prompt=""): 
    gpt_response = json.loads(gpt_response) 
    ret = {}
    ret["completed"] = True
    ret["skip_user_utt"] = True
    ret["next_utt"] = gpt_response["interviewer's thank you"]
    return ret

  def __chat_func_validate(gpt_response, prompt=""): 
    try: 
      response = __chat_func_clean_up(gpt_response)
      return True
    except:
      return False 

  def get_fail_safe():
    ret = {}
    ret["interviewer's thank you"] = "hmm ..."
    ret = json.dumps(ret)
    return ret

  prompt_template = f"{prompt_dir}/q_end_thankyou_v1.txt" 
  prompt_input = create_prompt_input(character, p_notes, q, convo_str) 
  prompt = generate_prompt(prompt_input, prompt_template)
  fail_safe = get_fail_safe() 
  output = threaded_chat_safe_generate(prompt, 
                                       "ChatGPT", 
                                       3, 
                                       fail_safe, 
                                       __chat_func_validate, 
                                       __chat_func_clean_up, verbose)
  if DEBUG or verbose: 
    print_run_prompts(prompt_template, prompt_input, prompt, output)
  return output, [output, prompt, prompt_input, fail_safe]


def run_gpt_generate_module_notes(convo_str, test_input=None, verbose=False):
  def create_prompt_input(convo_str, test_input=None):
    prompt_input = [convo_str]
    return prompt_input

  def __chat_func_clean_up(gpt_response, prompt=""): 
    gpt_response = json.loads(gpt_response) 
    return gpt_response

  def __chat_func_validate(gpt_response, prompt=""): 
    try: 
      response = __chat_func_clean_up(gpt_response)
      return True
    except:
      return False 

  def get_fail_safe():
    return {}

  prompt_template = f"{prompt_dir}/module_notes_v1.txt" 
  prompt_input = create_prompt_input(convo_str) 
  prompt = generate_prompt(prompt_input, prompt_template)
  fail_safe = get_fail_safe() 
  output = threaded_chat_safe_generate(prompt, 
                                       "ChatGPT", 
                                       3, 
                                       fail_safe, 
                                       __chat_func_validate, 
                                       __chat_func_clean_up, verbose)
  if DEBUG or verbose: 
    print_run_prompts(prompt_template, prompt_input, prompt, output)
  return output, [output, prompt, prompt_input, fail_safe]







