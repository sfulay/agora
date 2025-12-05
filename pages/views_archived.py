"""
ARCHIVED VIEWS - pages/views_archived.py

This file contains deprecated views that have been removed from the main views.py file
during the Habermas game (recommendation_editor.html) cleanup.

These views are preserved for historical reference but are no longer actively used:
- Old recommendation system (replaced by recommendation_editor)
- Old participant selection algorithms (replaced by generating_v2)
- Old AB testing system
- Deprecated social features
- Obsolete API endpoints

Archived on: 2025-12-05
Reason: Cleanup to focus codebase on recommendation_editor.html functionality
"""

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
from django.template.loader import render_to_string
from django.template import RequestContext

import openai
from interviewer_agent.interviewer_utils.settings import get_open_api_keyset
from global_methods import *
from datetime import datetime, timedelta
from django.utils import timezone
from io import BytesIO
from PIL import Image, ImageSequence
from pydub import AudioSegment

from pages.forms import *
from pages.models import *

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt


# ============================================================================
# ARCHIVED VIEWS - These functions are no longer in active use
# ============================================================================
#
# IMPORTANT: The actual code for these functions has been removed from views.py
# They can be recovered from git history if needed (commit before 2025-12-05)
#
# FUNCTIONS REMOVED:
#
# OLD RECOMMENDATION SYSTEM (Templates Deleted):
# - view_recommendations() - line 693
# - view_recommendation_voting() - line 892
# - habermas_game() - line 924 (replaced by recommendation_editor)
# - edit_editable_recommendation() - line 1002
# - submit_recommendation_vote() - line 1139
# - get_participant_prediction() - line 1301
# - get_participant_modal_content() - line 1326
#
# OLD PARTICIPANT SELECTION SYSTEM:
# - get_top_n_relevant_participants() - line 744
# - get_similarity_based_participants() - line 1609
# - has_module_responses() - line 1672
# - get_module_responses() - line 1697
# - get_participant_buckets() - line 1720
# - create_similarity_prompt() - line 1747
# - call_gpt() - line 1787 (local version, shadowed views_exp_summaries version)
# - get_llm_selection_with_retry() - line 1807
# - select_similar_participants() - line 1833
#
# OLD AB TESTING SYSTEM:
# - get_or_create_user_recommendation_order() - line 850
# - get_current_recommendation() - line 872
# - advance_to_next_recommendation() - line 879
# - set_condition() - line 1040
#
# SOCIAL FEATURES (Removed):
# - send_connection_request() - line 1569
# - submit_reflection() - line 1482
# - submit_feedback() - line 1534
#
# MISC DEPRECATED:
# - submit_decision_feedback() - line 2573
# - check_participant() - line 710
# - get_completion_details() - line 729
#
# STATUS: 18 of 26 functions removed from views.py (see below for remaining 8)
#
# REMAINING 8 FUNCTIONS TO REMOVE (still in views.py):
# - get_or_create_user_recommendation_order() - line ~730
# - get_current_recommendation() - line ~752
# - advance_to_next_recommendation() - line ~759
# - view_recommendation_voting() - line ~772
# - habermas_game() - line ~804
# - edit_editable_recommendation() - line ~882
# - set_condition() - line ~920
# - submit_recommendation_vote() - line ~1019
#
# These are all old AB testing and recommendation voting functions that can be
# safely removed. Search for each function name in views.py and delete it.
#
# NOTE: To recover any of these functions, use:
#   git log --all --full-history -- pages/views.py
#   git show <commit-hash>:pages/views.py
#
# ============================================================================

