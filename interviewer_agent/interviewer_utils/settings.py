import sys
import os
import random

def get_open_api_keyset(): 
  open_api_keyset = [{"key": "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",
                       "owner": "Suyash",
                       "id": 1,
                       "weight": 12}]
  # open_api_keyset += [{"key": "",
  #                      "owner": "",
  #                      "id": 1,
  #                      "weight": 12}]

  # Extracting weights
  weights = [api["weight"] for api in open_api_keyset]
  # Selecting one dictionary considering the weights
  selected_api_key = random.choices(open_api_keyset, weights=weights, k=1)[0]
  print (f"========== USING THE FOLLOWING: ", selected_api_key)
  return selected_api_key


# DEBUG = False
DEBUG = True

STORAGE_DIR = "storage"

GOOGLE_CRED_PATH = ""

INTERVIEW_AGENT_PATH = "interviewer_agent"



get_open_api_keyset()