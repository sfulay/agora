from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
  def populate_user(self, request, sociallogin, data):
    user = super().populate_user(request, sociallogin, data)
    email = data.get('email')
    if email:
      user.username = email
    return user