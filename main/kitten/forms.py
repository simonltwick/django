from django import forms
import logging

from .models import Game, TeamInvitation, Team

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


class GameForm(forms.ModelForm):

    class Meta:
        model = Game
        fields = ('name', 'teams')


class TeamInvitationForm(forms.ModelForm):

    class Meta:
        model = TeamInvitation
        fields = ('invitee_username', 'password')

    def clean(self):
        cleaned_data = super().clean()
        team = self.instance.team
        invitee = cleaned_data.get("invitee_username")
        if Team.objects.filter(id=team.id, members=invitee).exists():
            self.add_error('invitee_username', "Invitee is already a member.")
        elif TeamInvitation.objects.filter(team=team,
                                           invitee_username=invitee).exists():
            self.add_error('invitee_username',
                           "Invitee has already been invited")
        return cleaned_data


class InvitationAcceptanceForm(forms.ModelForm):

    class Meta:
        model = TeamInvitation
        fields = ('password',)
