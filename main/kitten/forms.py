from django import forms
from django.forms import modelformset_factory
import logging

from .models import Game, TeamInvitation, Team, GameInvitation, User, \
    Network, Line, LineTemplate, LineLocation

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


class GameForm(forms.ModelForm):

    class Meta:
        model = Game
        fields = ('name',)


class NewGameForm(forms.ModelForm):

    class Meta:
        model = Game
        fields = ('name',)

    game_template = forms.ModelChoiceField(
        queryset=None, empty_label='-- select a game template --',
        help_text='The template provides a pre-defined set of lines, stations,'
        ' trains and incidents to base the game upon.')


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


class LineTemplateForm(forms.ModelForm):

    class Meta:
        model = LineTemplate
        fields = ('name', 'direction1', 'direction2', 'trains_dir1',
                  'trains_dir2', 'train_interval', 'train_type')


LineLocationFormSet = modelformset_factory(LineLocation,
                                           fields=("name",))
