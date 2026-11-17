from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Profile
AVATARS = [('fox','🦊 Fox'),('panda','🐼 Panda'),('frog','🐸 Frog'),('cat','🐱 Cat'),('lion','🦁 Lion'),('owl','🦉 Owl'),('koala','🐨 Koala'),('dragon','🐲 Dragon')]
DECKS = [('cosmic','Cosmic purple'),('candy','Candy coral'),('lagoon','Electric teal')]
class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True)
    class Meta:
        model=User
        fields=('username','email','password1','password2')
class ProfileForm(forms.ModelForm):
    avatar=forms.ChoiceField(choices=AVATARS)
    deck=forms.ChoiceField(choices=DECKS)
    class Meta:
        model=Profile
        fields=('nickname','avatar','deck')
