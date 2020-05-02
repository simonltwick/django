from django import forms

from .models import Game, Team


class GameForm(forms.ModelForm):

    class Meta:
        model = Game
        fields = ('name', 'teams')


class TeamForm(forms.ModelForm):

    class Meta:
        model = Team
        fields = ('name', 'description')