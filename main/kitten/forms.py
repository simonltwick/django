from django import forms
from django.forms import modelformset_factory
import logging

from .models import Game, TeamInvitation, Team, GameInvitation, User, \
    Network, Line, LineTemplate, PlaceTemplate, PassengerTrafficProfile

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


PlaceTemplateFormSet = modelformset_factory(
    PlaceTemplate,
    fields=("name", 'type', 'transit_delay',
            'turnaround_percent_direction1', 'turnaround_percent_direction2'),
    min_num=3, validate_min=True,
    can_order=True, can_delete=True,
    widgets={
        'turnaround_percent_direction1': forms.NumberInput(
            attrs={'class': 'small-int'}),
        'turnaround_percent_direction2': forms.NumberInput(
            attrs={'class': 'small-int'}),
        'transit_delay': forms.NumberInput(attrs={'class': 'small-int'}),
        'ORDER': forms.NumberInput(attrs={'class': 'small-int'})
        })


StationTemplateTrafficFormSet = modelformset_factory(
    PlaceTemplate,
    fields=('name', 'passenger_traffic_dir1', 'passenger_traffic_dir2'),
    widgets={
        'passenger_traffic_dir1': forms.NumberInput(
            attrs={'class': 'small-int'}),
        'passenger_traffic_dir2': forms.NumberInput(
            attrs={'class': 'small-int'}),
        },
    extra=0,
    )


class NetworkForm(forms.ModelForm):

    class Meta:
        model = Network
        fields = ('name', 'description',
                  'game_tick_interval',
                  'game_round_duration',
                  'day_start_time',
                  'peak_morning_end', 'peak_evening_start',
                  'day_end_time',
                  'peak_morning_traffic', 'peak_evening_traffic',
                  'night_traffic',
                  )
