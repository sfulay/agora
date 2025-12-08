"""
URL configuration for gabm_infra project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import include, re_path, path
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.http import HttpResponse, FileResponse
from django.shortcuts import render
import logging
import sys
import traceback
import os

from pages import views as pages_views
from pages.views import jsp_log
from allauth.account.views import SignupView


pages_urlpatterns = [
  re_path(r'^$', pages_views.home, name='home'),
  re_path(r'^login$', pages_views.login, name='login'),
  re_path(r'^create_avatar$', pages_views.create_avatar, name='create_avatar'),
  re_path(r'^interview/(?P<script_v>[^/]+)/$', pages_views.interview, name='interview'),
  re_path(r'^download_p_data/(?P<participant_username>[^/]+)/(?P<script_v>[^/]+)/$', pages_views.download_p_data, name='download_p_data'),
  re_path(r'^download_p_audio_data/(?P<participant_username>[^/]+)/(?P<script_v>[^/]+)/$', pages_views.download_p_audio_data, name='download_p_audio_data'),
  re_path(r'^download_p_list_of_fin_interview/$', pages_views.download_p_list_of_fin_interview, name='download_p_list_of_fin_interview'),
  re_path(r'^handler_consent$', pages_views.handler_consent, name='handler_consent'),
  re_path(r'^handler_calibration$', pages_views.handler_calibration, name='handler_calibration'),
  re_path(r'^handler_take_one_step$', pages_views.handler_take_one_step, name='handler_take_one_step'),
  re_path(r'^handler_upload_spritesheet$', pages_views.handler_upload_spritesheet, name='handler_upload_spritesheet'),
  re_path(r'^handler_upload_surveycode$', pages_views.handler_upload_surveycode, name='handler_upload_surveycode'),
  re_path(r'^handler_upload_experiment_code$', pages_views.handler_upload_experiment_code, name='handler_upload_experiment_code'),
  re_path(r'^handler_download_summaries/(?P<starting_index>[^/]+)/(?P<desired_count>[^/]+)/$', pages_views.handler_download_summaries, name='handler_download_summaries'),
  re_path(r'^handler_phase_one_complete/$', pages_views.handler_phase_one_complete, name='handler_phase_one_complete'),

  re_path(r'^zipped_reset_check/(?P<participant_username>[^/]+)/(?P<script_v>[^/]+)/$', pages_views.zipped_reset_check, name='zipped_reset_check'),

  # Telemetry endpoints
  re_path(r'^api/telemetry/recommendation/start/$', pages_views.start_recommendation_tracking, name='start_recommendation_tracking'),
  re_path(r'^api/telemetry/recommendation/end/$', pages_views.end_recommendation_tracking, name='end_recommendation_tracking'),
  re_path(r'^api/telemetry/avatar/click/$', pages_views.track_avatar_click, name='track_avatar_click'),
  re_path(r'^api/telemetry/meta-medley/click/$', pages_views.track_meta_medley_click, name='track_meta_medley_click'),
  re_path(r'^api/telemetry/profile/start/$', pages_views.start_profile_tracking, name='start_profile_tracking'),
  re_path(r'^api/telemetry/profile/end/$', pages_views.end_profile_tracking, name='end_profile_tracking'),
  re_path(r'^api/telemetry/audio/start/$', pages_views.start_audio_tracking, name='start_audio_tracking'),
  re_path(r'^api/telemetry/audio/update/$', pages_views.update_audio_tracking, name='update_audio_tracking'),
  re_path(r'^api/telemetry/audio/end/$', pages_views.end_audio_tracking, name='end_audio_tracking'),
  re_path(r'^api/telemetry/voting/start/$', pages_views.start_voting_tracking, name='start_voting_tracking'),
  re_path(r'^api/telemetry/voting/end/$', pages_views.end_voting_tracking, name='end_voting_tracking'),
  re_path(r'^api/telemetry/summary/$', pages_views.get_telemetry_summary, name='get_telemetry_summary'),
  re_path(r'^api/telemetry/export/$', pages_views.export_telemetry_data, name='export_telemetry_data'),
  
  # Dynamic recommendation editor - standalone
  re_path(r'^editor/(?P<recommendation_id>\d+)/$', pages_views.recommendation_editor, name='recommendation_editor'),
  re_path(r'^api/editor/(?P<recommendation_id>\d+)/recompute-stream/$', pages_views.recompute_recommendation_stream, name='recompute_recommendation_stream'),
  re_path(r'^api/medley/(?P<recommendation_id>\d+)/participant/(?P<participant_username>[^/]+)/$', pages_views.get_medley_participant_modal, name='get_medley_participant_modal'),
  re_path(r'^api/meta-medley/(?P<recommendation_id>\d+)/(?P<medley_type>bottom|middle|top)/$', pages_views.get_meta_medley_panel, name='get_meta_medley_panel'),
  re_path(r'^api/editor/(?P<recommendation_id>\d+)/leaderboard/$', pages_views.get_leaderboard, name='get_leaderboard'),

  # AgoraChat
  re_path(r'^chat/$', pages_views.chat_interface, name='chat_interface'),
  re_path(r'^api/chat/query/$', pages_views.api_chat_query, name='api_chat_query'),
  re_path(r'^api/chat/medley/(?P<message_id>\d+)/$', pages_views.api_chat_medley, name='api_chat_medley'),
]

# Serve JavaScript files from templates directory
def serve_template_js(request, path):
    """Serve JavaScript files from templates/pages/"""
    # Try recommendation_editor path first (for /js/recommendation_editor/...)
    file_path = os.path.join(settings.BASE_DIR, 'templates', 'pages', 'recommendations', 'js', path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(open(file_path, 'rb'), content_type='application/javascript')

    # Try under templates/pages/js/ directly (for /js/chat/chat.js -> templates/pages/chat/js/chat.js)
    # The pattern is: /js/MODULE/FILE.js -> templates/pages/MODULE/js/FILE.js
    parts = path.split('/', 1)  # Split into [module, rest]
    if len(parts) == 2:
        module, filename = parts
        file_path = os.path.join(settings.BASE_DIR, 'templates', 'pages', module, 'js', filename)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(open(file_path, 'rb'), content_type='application/javascript')

    return HttpResponse(f'File not found: {path}', status=404)

# Add this temporary debug view
def debug_view(request):
    jsp_log("Debug view hit!")
    if request.method == 'GET':
        jsp_log(f"GET params: {request.GET}")
    elif request.method == 'POST':
        jsp_log(f"POST params: {request.POST}")
    from allauth.account.forms import SignupForm
    form = SignupForm()
    jsp_log("Form created")
    return HttpResponse("Debug view")

# Add this debug view
def debug_signup(request):
    print("DEBUG: Starting debug_signup view", file=sys.stderr)  # This will show up in web.stdout.log
    try:
        print("DEBUG: About to create SignupView", file=sys.stderr)
        from allauth.account.views import SignupView
        print("DEBUG: Successfully imported SignupView", file=sys.stderr)
        
        view = SignupView()
        print("DEBUG: Created SignupView instance", file=sys.stderr)
        
        # Return a simple response instead of trying to render
        return HttpResponse("Debug view reached successfully!")
        
    except Exception as e:
        print(f"DEBUG: Exception occurred: {str(e)}", file=sys.stderr)
        print("DEBUG: Traceback:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return HttpResponse(f"Error: {str(e)}")

urlpatterns = [
  path('admin/', admin.site.urls),
  path('accounts/', include('allauth.urls')),
  path('debug/', debug_view, name='debug'),
  path('debug-signup/', debug_signup),
  # Serve JS files from templates/pages/recommendations/js/
  re_path(r'^js/(?P<path>.+)$', serve_template_js, name='serve_template_js'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += pages_urlpatterns



