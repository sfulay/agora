from django import forms
from allauth.account.forms import SignupForm, LoginForm
import logging
from django.db.models import Q
from pages.views import jsp_log
from .models import Participant

from .interview_settings import *

logger = logging.getLogger(__name__)

class SpriteSheetForm(forms.Form):
  front = forms.ImageField()
  spritesheet = forms.ImageField()
  right_gif = forms.FileField()
  back_gif = forms.FileField()
  left_gif = forms.FileField()
  front_gif = forms.FileField()

class ConsentForm(forms.Form):
    consent = forms.BooleanField(
        label='I confirm that I have read the information and consent to participate in this study.',
        required=True,
        error_messages={'required': 'You must confirm your consent to continue.'}
    )

class CustomSignupForm(SignupForm):
  prolific_id = forms.CharField(
      label='Email Address',
      required=True,
      widget=forms.TextInput(attrs={'placeholder': 'Enter your email address'}),
      error_messages={
          'required': 'Please enter your email address to continue.'
      }
  )

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    # Remove username and email fields completely
    del self.fields['username']
    del self.fields['email']
    self.fields['password1'].required = False
    self.fields['password1'].widget = forms.HiddenInput()
    self.fields['password2'].required = False
    self.fields['password2'].widget = forms.HiddenInput()

  def clean_prolific_id(self):
    prolific_id = self.cleaned_data.get('prolific_id')
    if prolific_id:
      # Check if a user with this Prolific ID already exists
      if Participant.objects.filter(
          Q(prolific_id=prolific_id) | Q(username=prolific_id)
      ).exists():
          raise forms.ValidationError(
              'This Prolific ID is already registered. Please use a different ID or sign in if this is your account.'
          )
      if ' ' in prolific_id:
        raise forms.ValidationError('Prolific ID must not contain spaces.')
      if any(c.isupper() for c in prolific_id):
        raise forms.ValidationError('Prolific ID must be all lowercase (no uppercase letters).')
    return prolific_id

  def clean(self):
    cleaned_data = super().clean()
    prolific_id = cleaned_data.get('prolific_id')
    
    if prolific_id:  # Only proceed if prolific_id is valid
      # Generate a random password since we don't need it
      cleaned_data['password1'] = 'random_password_123'
      cleaned_data['password2'] = 'random_password_123'
      # Set email to a placeholder since it's required by the model
      cleaned_data['email'] = f"{prolific_id}@placeholder.com"
    
    return cleaned_data

  def save(self, request):
    try:
      user = super(CustomSignupForm, self).save(request)
      user.prolific_id = self.cleaned_data['prolific_id']
      user.username = self.cleaned_data['prolific_id']
      user.email = f"{self.cleaned_data['prolific_id']}@placeholder.com"
      user.set_password('random_password_123')  # Set a random password
      user.save()
      logger.info(f"[SIGNUP] User created successfully with Prolific ID: {user.prolific_id}")
      return user
    except Exception as e:
      logger.error(f"[SIGNUP] Error saving user: {str(e)}")
      raise

  def is_valid(self):
    jsp_log("🔍 FORM: Starting validation")
    try:
      result = super().is_valid()
      jsp_log(f"✅ FORM: Validation result: {result}")
      return result
    except Exception as e:
      jsp_log(f"❌ FORM: Error in validation: {str(e)}")
      raise


class SurveyCompletionForm(forms.Form):
  survey_code_pt1 = forms.CharField(label='Enter the completion code from "Survey Part 1":', 
    error_messages={
            'required': 'This field is required.',
            'invalid': 'Enter a valid value.'
        })
  survey_code_pt2 = forms.CharField(label='Enter the completion code from "Survey Part 2":', 
    error_messages={
            'required': 'This field is required.',
            'invalid': 'Enter a valid value.'
        })
  survey_part = forms.CharField(widget=forms.HiddenInput(), initial='1')


  def clean_survey_code(self):
    survey_code = self.cleaned_data['survey_code']
    # Your validation logic here
    if (survey_code != first_survey_code 
      and survey_code != second_survey_code):
      raise forms.ValidationError(f'Enter a valid survey code (it starts with {first_survey_code[:3]}).')
    return survey_code


class ExperimentCodeForm(forms.Form):
  code = forms.CharField(label='Enter the code')


class CustomLoginForm(LoginForm):
    prolific_id = forms.CharField(
        label='Email Address',
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Enter your email address'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Keep login field but make it hidden
        self.fields['login'].required = False
        self.fields['login'].widget = forms.HiddenInput()
        self.fields['password'].required = False
        self.fields['password'].widget = forms.HiddenInput()

    def clean_prolific_id(self):
        prolific_id = self.cleaned_data.get('prolific_id')
        if prolific_id:
            try:
                user = Participant.objects.get(prolific_id=prolific_id)
                # Set the login field to the user's username
                self.cleaned_data['login'] = user.username
                self.cleaned_data['password'] = 'random_password_123'
            except Participant.DoesNotExist:
                raise forms.ValidationError('Invalid email address')
        return prolific_id

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data

    def user_credentials(self, form = None, login_field = None, password_field = None):
        return {
            'username': self.cleaned_data['login'],  # Use the username we set in clean_prolific_id
            'password': 'random_password_123'
        }

class EditableRecommendationForm(forms.Form):
    rec_text = forms.CharField(
        label='Edit Recommendation',
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        max_length=2000,
        required=True
    )



































