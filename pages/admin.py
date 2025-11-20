from django.contrib import admin
from .models import *


class ParticipantAdmin(admin.ModelAdmin): 
  list_display = ('username',
                  'prolific_id',
                  'email',
                  'completed_modules',
                  'audio_calibration_float',
                  'behavioral_activated')
  list_filter = ()
admin.site.register(Participant, ParticipantAdmin)


class BehavioralStudyModuleAdmin(admin.ModelAdmin): 
  list_display = ('study_cond',
                  'study_rand_o_1', 
                  'study_rand_o_2')
  list_filter = ()
admin.site.register(BehavioralStudyModule, BehavioralStudyModuleAdmin)


class InterviewAdmin(admin.ModelAdmin):
  list_display = ('participant', 
                  'script_v',
                  'interviewer_summary', 
                  'curr_module_id', 
                  'question_id_count', 
                  'p_notes', 
                  'optional_key_phrases',
                  'completed',
                  'id')
  list_filter = ()
admin.site.register(Interview, InterviewAdmin)


class InterviewSegmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'audio', 'sequence_number', 'start_time', 'end_time', 'duration', 'word_count', 'created')
    list_filter = ('created',)
    search_fields = ('segment_text', 'audio__id')
    ordering = ('audio', 'sequence_number')
admin.site.register(InterviewSegment, InterviewSegmentAdmin)


class InterviewModuleAdmin(admin.ModelAdmin): 
  list_display = ('module_id', 
                  'curr_question_id', 
                  'interview', 
                  'completed')
  list_filter = ()
admin.site.register(InterviewModule, InterviewModuleAdmin)


class InterviewQuestionAdmin(admin.ModelAdmin): 
  list_display = ('question_id', 
                  'global_question_id', 
                  'interview', 
                  'module', 
                  'q_content',
                  'q_type',
                  'q_requirement',
                  'q_max_sec',
                  'convo',
                  'completed')
  list_filter = ()
admin.site.register(InterviewQuestion, InterviewQuestionAdmin)


class PerfMeasurementAdmin(admin.ModelAdmin): 
  list_display = ('participant', 
                  'details', 
                  'start_time', 
                  'end_time', 
                  'sec_passed')
  list_filter = ()
admin.site.register(PerfMeasurement, PerfMeasurementAdmin)


class TimeoutTimerAdmin(admin.ModelAdmin): 
  list_display = ('participant',
                  'created', 
                  'endtime',
                  'cause')
  list_filter = ()
admin.site.register(TimeoutTimer, TimeoutTimerAdmin)


class InterviewClipInline(admin.TabularInline):
    model = InterviewClip
    extra = 1

class InterviewRecommendationAdmin(admin.ModelAdmin):
    list_display = ('id', 
                    'recommendation',
                    'participant',
                    'created_at')
    list_filter = ('created_at',)
    inlines = [InterviewClipInline]

class ParticipantRecommendationSupportAdmin(admin.ModelAdmin):
    list_display = ('id', 'recommendation', 'get_participant_name', 'support_score', 'confidence_score', 'created_at')
    list_filter = ('created_at', 'support_score', 'confidence_score')
    search_fields = ('explanation', 'recommendation__recommendation')
    
    def get_participant_name(self, obj):
        return obj.interview.participant.get_full_name()
    get_participant_name.short_description = 'Participant'

admin.site.register(InterviewRecommendation, InterviewRecommendationAdmin)
admin.site.register(ParticipantRecommendationSupport, ParticipantRecommendationSupportAdmin)


class InterviewAudioAdmin(admin.ModelAdmin):
    list_display = ('question',
                   'user_speech',
                   'audio_file',
                   'created')
    list_filter = ('user_speech', 'created')
admin.site.register(InterviewAudio, InterviewAudioAdmin)


class InterviewUtteranceAdmin(admin.ModelAdmin):
    list_display = ('utterance_text', 'question', 'is_interviewer', 'sequence_number', 'created', 'audio_id')
    list_filter = ('is_interviewer', 'created')
admin.site.register(InterviewUtterance, InterviewUtteranceAdmin)

class RecommendationAdmin(admin.ModelAdmin):  
    list_display = ('rec_text',)
    list_filter = ('utterances',)
admin.site.register(Recommendation, RecommendationAdmin)

@admin.register(RecommendationParticipantSummary)
class RecommendationParticipantSummaryAdmin(admin.ModelAdmin):
    list_display = ('recommendation', 'participant', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('summary', 'participant__prolific_id', 'recommendation__rec_text')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('recommendation', 'participant')
        }),
        ('Summary', {
            'fields': ('summary',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
