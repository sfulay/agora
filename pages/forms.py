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
  email = forms.EmailField(
      label='Email Address',
      required=True,
      widget=forms.EmailInput(attrs={'placeholder': 'Enter your email address'}),
      error_messages={
          'required': 'Please enter your email address to continue.',
          'invalid': 'Please enter a valid email address.'
      }
  )

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    # Remove username field - we'll use email instead
    if 'username' in self.fields:
      del self.fields['username']
    # Make password fields visible and required
    self.fields['password1'].required = True
    self.fields['password1'].widget = forms.PasswordInput(attrs={'placeholder': 'Enter your password'})
    self.fields['password2'].required = True
    self.fields['password2'].widget = forms.PasswordInput(attrs={'placeholder': 'Confirm your password'})

  def clean_email(self):
    email = self.cleaned_data.get('email')
    if email:
      # Check if a user with this email already exists
      if Participant.objects.filter(email=email).exists():
          raise forms.ValidationError(
              'This email address is already registered. Please use a different email or sign in if this is your account.'
          )
    return email

  def save(self, request):
    try:
      user = super(CustomSignupForm, self).save(request)
      # Set username to email (required by Django's User model)
      user.username = self.cleaned_data['email']
      user.email = self.cleaned_data['email']
      # Leave prolific_id as None for new users
      user.prolific_id = None
      user.save()
      logger.info(f"[SIGNUP] User created successfully with email: {user.email}")
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Update login field to be email
        self.fields['login'].label = 'Email Address'
        self.fields['login'].widget.attrs.update({'placeholder': 'Enter your email address'})
        # Make password field visible and required
        self.fields['password'].required = True
        self.fields['password'].widget = forms.PasswordInput(attrs={'placeholder': 'Enter your password'})

    def clean(self):
        cleaned_data = super().clean()
        login = cleaned_data.get('login')

        # Support backward compatibility: if user enters prolific_id, try to find by that
        if login and '@' not in login:
            try:
                user = Participant.objects.get(prolific_id=login)
                # If found, update login to use their username for authentication
                cleaned_data['login'] = user.username
            except Participant.DoesNotExist:
                # Not a prolific_id, will fail authentication normally
                pass

        return cleaned_data

    def user_credentials(self, form = None, login_field = None, password_field = None):
        # Use email as username for authentication
        login = self.cleaned_data.get('login')
        password = self.cleaned_data.get('password')

        # Try to find user by email first
        try:
            user = Participant.objects.get(email=login)
            username = user.username
        except Participant.DoesNotExist:
            # Use login as-is (might be username or prolific_id from backward compat)
            username = login

        return {
            'username': username,
            'password': password
        }

class EditableRecommendationForm(forms.Form):
    rec_text = forms.CharField(
        label='Edit Recommendation',
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        max_length=2000,
        required=True
    )



































