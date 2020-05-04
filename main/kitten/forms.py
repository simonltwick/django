from django import forms
import logging

from .models import Game, TeamInvitation, Team, GameInvitation, User

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


class GameForm(forms.ModelForm):

    class Meta:
        model = Game
        fields = ('name',)


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


class GameInvitationForm(forms.ModelForm):

    class Meta:
        model = GameInvitation
        fields = ('invited_team', 'password')

    def clean(self):
        cleaned_data = super().clean()
        invitee = cleaned_data.get("invited_team")
        game = self.instance.game
        if invitee == self.instance.inviting_team:
            self.add_error('invited_team',
                           f"{invitee.name} is already a participant.")
        elif GameInvitation.objects.filter(game=self.instance.game,
                                           invited_team=invitee).exists():
                self.add_error('invited_team',
                               f"{invitee.name} has already been invited.")
        else:
            # users in invitee team already in other game teams?
            joint_users = User.objects.filter(
                teams=invitee).filter(teams__games=game)
            if joint_users.exists():
                usernames = ', '.join(user.username
                                      for user in joint_users.all())
                self.add_error('invited_team',
                               f"{usernames} in {invitee.name} are already in "
                               "other participating teams.")
        return cleaned_data


class GameInvitationAcceptanceForm(forms.ModelForm):

    class Meta:
        model = GameInvitation
        fields = ('password',)
