from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, AccessMixin
# from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse_lazy, reverse
from django.views.generic.edit import CreateView, DeleteView, UpdateView

from .models import Game, Team, GameTemplate, Line, Network, \
    GameInterval, Incident, TeamInvitation, GameInvitation, LineTemplate, \
    GameTemplate, PlaceTemplate, GamePlayStatus
from .forms import GameForm, TeamInvitationForm, InvitationAcceptanceForm, \
    GameInvitationForm, GameInvitationAcceptanceForm, NewGameForm, \
    LineTemplateForm, PlaceTemplateFormSet
import logging
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


class TeamAccessMixin(AccessMixin):
    permission_denied_message = 'Unauthorised Team'

    def handle_no_permission(self):
        return HttpResponse(self.get_permission_denied_message())


class IsTeamMemberMixin(TeamAccessMixin):
    """Verify that the current user is a member of team_id.
    Only works for ModelForms (update, delete) with model=Team """

    def dispatch(self, request, *args, **kwargs):
        team_id = kwargs.get('team_id', None) or kwargs.get('pk', None)
        if request.user and team_id and is_team_member(request, team_id):
            return super().dispatch(request, *args, **kwargs)
        return self.handle_no_permission()


def is_user_in_team_in_game(request, team_id, game_id):
    return Team.objects.filter(id=team_id, members=request.user,
                               games=game_id).exists()


def is_team_member(request, team_id):
    return Team.objects.filter(id=team_id, members=request.user).exists()


def game_has_team(team_id, game_id):
    return Game.objects.filter(id=game_id, teams=team_id).exists()


@login_required
def home(request):
    teams = request.user.teams.all()
    TeamInvitation.remove_expired()
    return render(request, 'kitten/home.html', {'teams': teams})


@login_required
def team_games(request, team_id):
    """ list games available to this team """
    if not is_team_member(request, team_id):
        return HttpResponse("Unauthorised team", status=401)
    team = get_object_or_404(Team, pk=team_id)
    TeamInvitation.remove_expired()
    GameInvitation.remove_expired()
    games = Game.objects.filter(teams__pk=team.pk)
    return render(request, 'kitten/team_games.html',
                  {'games': games, 'team': team})


class TeamNew(LoginRequiredMixin, CreateView):
    model = Team
    fields = ('name', 'description')

    def form_valid(self, form):
        form.save()
        form.instance.members.add(self.request.user)
        return super().form_valid(form)


class TeamUpdate(IsTeamMemberMixin, UpdateView):
    model = Team
    fields = ('name', 'description')


class TeamDelete(IsTeamMemberMixin, DeleteView):
    model = Team
    fields = ('name', 'description', 'games')
    success_url = reverse_lazy('home')


# TODO: validate that request.user owns this network / linetemplate / gametemp.
class NetworkNew(LoginRequiredMixin, CreateView):
    model = Network
    fields = ('name', 'description', 'day_start_time', 'day_end_time',
              'game_round_duration')

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.owner = self.request.user
        return super(NetworkNew, self).form_valid(form)


class NetworkUpdate(LoginRequiredMixin, UpdateView):
    model = Network
    fields = ('name', 'description', 'day_start_time', 'day_end_time',
              'game_round_duration')


class NetworkDelete(LoginRequiredMixin, DeleteView):
    model = Network
    success_url = reverse_lazy('home')


@login_required
def linetemplate(request, network_id, linetemplate_id=None):
    if not Network.objects.filter(
            owner=request.user, pk=network_id).exists():
        return HttpResponse("Unauthorised network.", status=401)

    if linetemplate_id is not None:
        linetemplate = get_object_or_404(LineTemplate, pk=linetemplate_id)
    else:
        linetemplate = None

    # 4 options: Post or Get with/without existing line template
    if request.method == 'POST':
        if network_id != request.POST.get('network_id'):
            return HttpResponse("Invalid network.", status=401)

        if linetemplate_id is None:
            # linetemplate_id is None: returning a new LineTemplate
            form = LineTemplateForm(request.POST)
            formset = PlaceTemplateFormSet(request.POST)
            if form.is_valid():
                form.instance.network_id = network_id
                linetemplate = form.save(commit=False)  # get id assigned

        else:  # returning an existing linetemplate
            if linetemplate_id != request.POST.get('linetemplate_id'):
                log.error("views.linetemplate(network_id=%r, linetemplate_id"
                          "=%r) retrieved POST[linetemplate_id]=%r",
                          network_id, linetemplate_id,
                          request.POST.get('linetemplate_id'))
                return HttpResponse("Invalid line template.", status=401)

            form = LineTemplateForm(request.POST, instance=linetemplate)
            formset = PlaceTemplateFormSet(request.POST)

        formset.is_valid()  # force clean of data, prior to validating order
        positions = []
        for place_form in formset:
            if place_form.cleaned_data:
                try:
                    pos = int(place_form.cleaned_data['ORDER'])
                except (ValueError, TypeError):
                    place_form.add_error('ORDER', 'Order must be a number')
                    continue
                if pos in positions:
                    place_form.add_error('ORDER', 'Duplicate value for Order')
                else:
                    positions.append(pos)

        if form.is_valid() and formset.is_valid():
            form.save()
            for place_form in formset:
                if place_form.cleaned_data:  # keyerror if blank form
                    place_form.instance.line_id = linetemplate.id
                    place_form.instance.position = place_form.cleaned_data[
                        'ORDER']
            if len(formset):
                # decided not to ensure turnaround at end of line, confusing
                # to user: leave it to Line.new_from_template
                r = formset.save()
            next_url = request.GET.get('next', None)
            if next_url:
                return HttpResponseRedirect(next_url)
                # refresh formset to action deletions & reordering
            formset = PlaceTemplateFormSet(
                queryset=PlaceTemplate.objects.filter(line=linetemplate))

    elif linetemplate_id is None:
        # Get with no linetemplate id - new linelocation
        form = LineTemplateForm()
        formset = PlaceTemplateFormSet(
            queryset=PlaceTemplate.objects.none(),
            initial=[{'name': f"Depot{i}", 'type': PlaceTemplate.DEPOT}
                     for i in range(1, 3)])
    else:  # get (for update) with linetemplate_id
        if linetemplate.network_id != int(network_id):
            log.error("views.linetemplate(network_id=%r, linetemplate_id=%s)"
                      "retrieved linetemplate.network_id=%r", network_id,
                      linetemplate_id, linetemplate.network_id)
            return HttpResponse("Invalid network.", status=401)
        form = LineTemplateForm(instance=linetemplate)
        formset = PlaceTemplateFormSet(
            queryset=PlaceTemplate.objects.filter(line=linetemplate))

    return render(request, 'kitten/linetemplate_form.html',
                  context={'form': form, 'formset': formset,
                           'network_id': network_id,
                           'linetemplate': linetemplate})


class LineTemplateDelete(LoginRequiredMixin, DeleteView):
    model = LineTemplate

    def get_success_url(self):
        return reverse_lazy('network',
                            kwargs={'pk': self.object.network.id})


def linelocation(request, linetemplate_id, linelocation_id=None):
    """ handle a linelocation request """
    return HttpResponse("Not yet written.")


class GameTemplateNew(LoginRequiredMixin, CreateView):
    model = GameTemplate
    fields = ('level', 'incident_rate')

    def dispatch(self, request, *args, **kwargs):
        if not Network.objects.filter(pk=kwargs['network_id'],
                                      owner=request.user).exists():
            return HttpResponse("Unauthorised network", status=401)
        if 'gametemplate_id' in kwargs:
            if not Network.objects.filter(games=kwargs['gametemplate_id'],
                                          pk=kwargs['network_id']).exists():
                return HttpResponse("Unauthorised game template", status=401)
        return super(CreateView, self).dispatch(request, *args, *kwargs)

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.network_id = self.kwargs['network_id']
        return super(GameTemplateNew, self).form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['network_id'] = self.kwargs['network_id']
        return context


class GameTemplateUpdate(LoginRequiredMixin, UpdateView):
    model = GameTemplate
    fields = ('level', 'incident_rate')

    def dispatch(self, request, *args, **kwargs):
        if not Network.objects.filter(pk=kwargs['network_id'],
                                      owner=request.user).exists():
            return HttpResponse("Unauthorised network", status=401)
        if 'gametemplate_id' in kwargs:
            if not Network.objects.filter(games=kwargs['gametemplate_id'],
                                          pk=kwargs['network_id']).exists():
                return HttpResponse("Unauthorised game template", status=401)
        return super(UpdateView, self).dispatch(request, *args, *kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['network_id'] = self.kwargs['network_id']
        return context

    def get_success_url(self):
        return reverse('network',
                       kwargs={'pk': self.object.network_id})


class GameTemplateDelete(LoginRequiredMixin, DeleteView):
    model = GameTemplate

    def get_success_url(self):
        return reverse_lazy('network',
                            kwargs={'pk': self.object.network.id})


@login_required
def invitation_delete(request, team_id, invitation_id):

    if not is_team_member(request, team_id):
        return HttpResponse("Unauthorised team", status=401)
    if not TeamInvitation.objects.filter(id=invitation_id,
                                         team=team_id).exists:
        return HttpResponse("Unauthorised invitation", status=401)
    TeamInvitation.objects.filter(id=invitation_id).delete()
    return TeamUpdate.as_view()(request, pk=team_id)


@login_required
def invitation_accept(request, invitation_id):
    invitation = get_object_or_404(TeamInvitation, pk=invitation_id)
    if invitation.invitee_username != request.user:
        return HttpResponse("Unauthorised invitation", status=401)
    if request.method == 'POST':
        form = InvitationAcceptanceForm(request.POST)
        if form.is_valid():
            if form.cleaned_data['password'] == invitation.password:
                invitation.accept(request.user)
                return HttpResponseRedirect(reverse(
                    'team_games', kwargs={'team_id': invitation.team.id}))

            invitation.failed_attempts += 1
            if invitation.failed_attempts > invitation.MAX_PASSWORD_FAILURES:
                log.error("Too many failed attempts for %s. Invitation "
                          "deleted.", invitation)
                invitation.delete()
                return HttpResponse(
                    "Too many failed attempts. Please ask the team"
                    " to re-issue the invitation.", status=429)

            form.add_error('password', 'The password is incorrect.  Please'
                           ' check and try again')
            invitation.save()
    else:
        form = InvitationAcceptanceForm()
    return render(request, 'kitten/invitation_accept.html',
                  {'form': form,
                   'invitation': invitation})


@login_required
def team_invitation_new(request, team_id):
    if not is_team_member(request, team_id):
        return HttpResponse("Unauthorised team", status=401)
    team = get_object_or_404(Team, id=team_id)
    if request.method == 'POST':
        form = TeamInvitationForm(request.POST)
        form.instance.team = team
        if form.is_valid():
            form.instance.invited_by = request.user
            form.save()
            return team_games(request, team_id)
    else:
        form = TeamInvitationForm(initial={"invited_by": request.user,
                                           "team": team})
    return render(request, 'kitten/team_invitation.html',
                  {'form': form, 'team': team})


@login_required
def team_member_remove(request, team_id, user_id):
    if not is_team_member(request, team_id):
        return HttpResponse("Unauthorised team", status=401)
    team = Team.objects.get(id=team_id)
    if team.members.count() <= 1:
        return HttpResponse("Cannot remove the only team member: delete team"
                            " instead.", status=403)
    if not Team.objects.filter(id=team_id, members=user_id).exists():
        return HttpResponse(f"User is not a member of {team.name}.",
                            status=400)
    team.members.remove(user_id)
    log.info("team_member_remove: user_id=%s, request.user.id=%s",
             user_id, request.user.id)
    if user_id == str(request.user.id):  # removed yourself
        return HttpResponseRedirect(reverse('home'))
    return TeamUpdate.as_view()(request, pk=team_id)


@login_required
def game_new(request, team_id):
    """ start a new game.
    Prompt for game template and teams, then create game """
    if not is_team_member(request, team_id):
        return HttpResponse("Unauthorised team", status=401)
    team = Team.objects.get(pk=team_id)
    if request.method == 'POST':
        # handle form here .. create the game and then go to edit game
        # to further customise
        form = NewGameForm(request.POST)
        form.fields['game_template'].queryset = GameTemplate.objects.filter(
            level__lte=team.level)
        if form.is_valid():
            game_template = form.cleaned_data.get('game_template', None)
            name = form.cleaned_data['name']
            game = Game.new_from_template(teams=[team], template=game_template,
                                          name=name)
            game.save()
            form = GameForm(instance=game)
            return HttpResponseRedirect(reverse(
                'game', kwargs={'game_id': game.id, 'team_id': team.id}))

    else:  # initial call with only team_id
        form = NewGameForm()
        form.fields['game_template'].queryset = GameTemplate.objects.filter(
            level__lte=team.level)
    return render(request, 'kitten/game_new.html',
                  {'form': form,
                   'team': team})


@login_required
def game(request, game_id, team_id):
    """ load a specific game by pk """
    if not is_team_member(request, team_id):
        return HttpResponse("Unauthorised team", status=401)
    if not game_has_team(team_id, game_id):
        return HttpResponse('Unauthorized game', status=401)
    game = get_object_or_404(Game, pk=game_id)
    if request.method == 'POST':  # handle incoming form
        form = GameForm(request.POST, instance=game)
        if form.is_valid():
            game = form.save()
    else:
        form = GameForm(instance=game)
    GameInvitation.remove_expired()
    return render(request, 'kitten/game.html',
                  {'form': form, 'game': game, "team_id": team_id,
                   'GamePlayStatus': GamePlayStatus})


@login_required
def game_debug(request, game_id, team_id, code):
    """ various debug options for game """
    if not is_team_member(request, team_id):
        return HttpResponse("Unauthorised team", status=401)
    if not game_has_team(team_id, game_id):
        return HttpResponse('Unauthorized game', status=401)
    # log.info("game.debug(%r)", code)
    code = int(code)
    game = get_object_or_404(Game, pk=game_id)
    game.debug(code)
    return HttpResponseRedirect(reverse(
        'game_operations', kwargs={'team_id': team_id, 'game_id': game_id}))


@login_required
def game_invitation_new(request, game_id, team_id):
    """ invite another team to join game """
    if not is_team_member(request, team_id):
        return HttpResponse("Unauthorised team", status=401)
    if not game_has_team(team_id, game_id):
        return HttpResponse('Unauthorized game', status=401)
    game_inst = get_object_or_404(Game, pk=game_id)
    team = get_object_or_404(Team, pk=team_id)
    if request.method == 'POST':
        form = GameInvitationForm(request.POST)
        form.instance.game = game_inst
        form.instance.inviting_team = team
        if form.is_valid():  # is_valid requires team and game to be set
            form.save()
            return HttpResponseRedirect(reverse(
                'game', kwargs={'game_id': game_id, 'team_id': team_id}))
    else:
        form = GameInvitationForm(initial={"game": game_inst})
    return render(request, 'kitten/game_invitation_new.html',
                  {'form': form, 'team': team, 'game': game_inst})


@login_required
def game_invitation_accept(request, team_id, invitation_id):
    log.info("game_invitation_accept(team_id=%d, invitation_id=%d",
             team_id, invitation_id)
    if not is_team_member(request, team_id):
        return HttpResponse("Unauthorised team", status=401)
    invitation = get_object_or_404(GameInvitation, pk=invitation_id,
                                   invited_team=team_id)
    if request.method == 'POST':
        form = GameInvitationAcceptanceForm(request.POST)
        if form.is_valid():
            if form.cleaned_data['password'] == invitation.password:
                invitation.accept(team_id)
                return HttpResponseRedirect(reverse(
                    'game', kwargs={'game_id': invitation.game.id,
                                    'team_id': team_id}))

            invitation.failed_attempts += 1
            if invitation.failed_attempts > invitation.MAX_PASSWORD_FAILURES:
                log.error("Too many failed attempts for %s. Deleted.",
                          invitation)
                invitation.delete()
                return HttpResponse(
                    "Too many failed attempts. Please ask the team"
                    " to re-issue the invitation.", status=429)

            form.add_error('password', 'The password is incorrect.  Please'
                           ' check and try again')
            invitation.save()
    else:
        form = GameInvitationAcceptanceForm()
    return render(request, 'kitten/game_invitation_accept.html',
                  {'form': form,
                   'invitation': invitation,
                   'team_id': team_id})


@login_required
def game_team_remove(request, game_id, team_id, remove_team_id):
    if not Team.objects.filter(games=game_id, members=request.user).exists():
        return HttpResponse('Unauthorized game', status=403)
    game_inst = get_object_or_404(Game, id=game_id)
    if not Game.objects.filter(id=game_id, teams=remove_team_id).exists():
        return HttpResponse(f'Team is not a participant in {game_inst.name}',
                            status=400)
    if game_inst.teams.count() <= 1:
        return HttpResponse("Cannot remove the only participant: delete game"
                            " instead.", status=403)
    game_inst.teams.remove(remove_team_id)
    if team_id == remove_team_id:
        return HttpResponseRedirect(
            reverse('team_games', kwargs={'team_id': team_id}))
    else:
        return HttpResponseRedirect(reverse(
                'game', kwargs={'game_id': game_id, 'team_id': team_id}))


@login_required
def game_delete(request, game_id, team_id):
    if not is_team_member(request, team_id):
        return HttpResponse("Unauthorised team", status=403)
    if not game_has_team(team_id, game_id):
        return HttpResponse('Unauthorized game', status=403)
    return HttpResponse("Delete game not yet implemented.")


@login_required
def game_play(request, game_id, team_id):
    if not is_team_member(request, team_id):
        return HttpResponse("Unauthorised team", status=403)
    if not game_has_team(team_id, game_id):
        return HttpResponse('Unauthorized game', status=403)
    game = get_object_or_404(Game, pk=game_id)
    game.play_status = GamePlayStatus.RUNNING
    game.save()
    if 'next' in request.GET:
        return HttpResponseRedirect(request.GET['next'])
    return HttpResponse("Play game not yet implemented.  Go to Operations"
                        " and press Tick to get an idea...")


@login_required
def game_pause(request, game_id, team_id):
    if not is_team_member(request, team_id):
        return HttpResponse("Unauthorised team", status=403)
    if not game_has_team(team_id, game_id):
        return HttpResponse('Unauthorized game', status=403)
    game = get_object_or_404(Game, pk=game_id)
    game.play_status = GamePlayStatus.PAUSED
    game.save()
    if 'next' in request.GET:
        return HttpResponseRedirect(request.GET['next'])
    return HttpResponse("Play/pause game not yet implemented.  Go to "
                        "Operations and press Tick to get an idea...")


@login_required
def game_tick(request, game_id, team_id):
    if not is_team_member(request, team_id):
        return HttpResponse("Unauthorised team", status=401)
    if not game_has_team(team_id, game_id):
        return HttpResponse('Unauthorized game', status=401)
    game = get_object_or_404(Game, pk=game_id)
    game.run(GameInterval.TICK_SINGLE)
    return HttpResponseRedirect(reverse(
        'game_operations', kwargs={'team_id': team_id, 'game_id': game_id}))


@login_required
def game_status(request, game_id, team_id, status=None):
    """ query or change game play status.
    returns a Json response {"status": a string with status,
                             "teams": an optional list of teams relevant to the
                             status above}   """
    if not is_team_member(request, team_id):
        return HttpResponse("Unauthorised team", status=403)
    if not game_has_team(team_id, game_id):
        return HttpResponse('Unauthorized game', status=403)
    game = get_object_or_404(Game, pk=game_id)
    try:
        status = game.request_play_status(team_id, status)
    except (ValueError, KeyError) as e:
            return HttpResponse(e.args[0], status=400)
    return JsonResponse(status)


@login_required
def game_operations(request, game_id, team_id, tick_interval=None):
    if not is_user_in_team_in_game(request, team_id, game_id):
        if not is_team_member(request, team_id):
            return HttpResponse("Unauthorised team", status=403)
        if not game_has_team(team_id, game_id):
            return HttpResponse('Unauthorized game', status=403)
    team = get_object_or_404(Team, pk=team_id)
    game = get_object_or_404(Game, pk=game_id)
    if tick_interval is not None:
        game.run(tick_interval)
    lines = Line.objects.filter(game=game_id, operator=team_id)

    # details is {line([(trains_up, loc, trains_down)], [incidents])}
    details = {line: ([(trains_dir1, location, trains_dir2)
                      for location, (trains_dir1, trains_dir2)
                      in line.details().items()],
                      line.incidents)
               for line in lines
               }
    lines_other_op = Line.objects.filter(game=game).exclude(
        operator=team).order_by('operator')
    return render(request, 'kitten/operations.html',
                  {'game': game, 'team': team,
                   'details': details,
                   'lines_other_op': lines_other_op
                   })


@login_required
def game_scheduling(request, game_id, team_id):
    if not is_team_member(request, team_id):
        return HttpResponse("Unauthorised team", status=401)
    if not game_has_team(team_id, game_id):
        return HttpResponse('Unauthorized game', status=401)
    game = get_object_or_404(Game, pk=game_id)
    return render(request, 'kitten/scheduling.html',
                  {'game': game, 'team_id': team_id})


@login_required
def game_boardroom(request, game_id, team_id):
    if not is_team_member(request, team_id):
        return HttpResponse("Unauthorised team", status=401)
    if not game_has_team(team_id, game_id):
        return HttpResponse('Unauthorized game', status=401)
    game = get_object_or_404(Game, pk=game_id)
    return render(request, 'kitten/boardroom.html',
                  {'game': game, 'team_id': team_id})


@login_required
def game_hr(request, game_id, team_id):
    if not is_team_member(request, team_id):
        return HttpResponse("Unauthorised team", status=401)
    if not game_has_team(team_id, game_id):
        return HttpResponse('Unauthorized game', status=401)
    game = get_object_or_404(Game, pk=game_id)
    return render(request, 'kitten/hr.html',
                  {'game': game, 'team_id': team_id})


@login_required
def game_engineering(request, game_id, team_id):
    if not is_team_member(request, team_id):
        return HttpResponse("Unauthorised team", status=401)
    if not game_has_team(team_id, game_id):
        return HttpResponse('Unauthorized game', status=401)
    game = get_object_or_404(Game, pk=game_id)
    return render(request, 'kitten/engineering.html',
                  {'game': game, 'team_id': team_id})


@login_required
def game_marketing(request, game_id, team_id):
    if not is_team_member(request, team_id):
        return HttpResponse("Unauthorised team", status=401)
    if not game_has_team(team_id, game_id):
        return HttpResponse('Unauthorized game', status=401)
    game = get_object_or_404(Game, pk=game_id)
    return render(request, 'kitten/marketing.html',
                  {'game': game, 'team_id': team_id})


@login_required
def game_stage(request, game_id, team_id):
    return game_operations(request, game_id, team_id,
                           tick_interval=GameInterval.TICK_STAGE)


@login_required
def incident(request, team_id, game_id, incident_id):
    if not is_team_member(request, team_id):
        return HttpResponse("Unauthorised team", status=401)
    try:
        game = Game.objects.get(id=game_id, teams=team_id)
    except Game.DoesNotExist:
        return HttpResponse('Unauthorised game', status=401)
    incident = get_object_or_404(Incident, id=incident_id, line__game=game)

    errors = None
    if request.method == "POST":
        # start new response
        response_id = request.POST.get("option")
        if not response_id:
            errors = "You must choose a response"
        else:
            incident.start_response(response_id)
            return HttpResponseRedirect(
                reverse('game_operations',
                        kwargs={'team_id': team_id, 'game_id': game_id}))
    return render(request, 'kitten/incident.html',
                  {'game': game,
                   'team_id': team_id,
                   'incident': incident,
                   'response': incident.response,
                   'errors': errors})


@login_required
def incident_debug(request, team_id, game_id, incident_id, code):
    """ various debug actions for an incident """
    if not is_team_member(request, team_id):
        return HttpResponse("Unauthorised team", status=401)
    try:
        game = Game.objects.get(id=game_id, teams=team_id)
    except Game.DoesNotExist:
        return HttpResponse('Unauthorised game', status=401)
    incident = get_object_or_404(Incident, id=incident_id, line__game=game)

    log.info("incident_debug(code=%r)", code)
    code = int(code)
    if code == 1:
        impacts = [(impact.name,
                    impact.impact_now(game.current_time))
                   for impact in incident.impacts.all()]
        impacts = [(name, str(impact)) for name, impact in impacts]
        log.info("incident.impacts=%s", impacts)
        impact_types = {impact.type for impact in incident.impacts.all()}
        impacts_by_type = [
            (impact_type, incident.impact_now(impact_type, game.current_time))
            for impact_type in impact_types]
        impacts_by_type = [(t, str(impact)) for t, impact in impacts_by_type]
        log.info("incident.impact_now()=%s", impacts_by_type)
    else:
        raise ValueError(f"incident_debug: invalid code {code!r}")
    return HttpResponseRedirect(reverse(
        'incident', kwargs={'team_id': team_id, 'game_id': game_id,
                            'incident_id': incident_id}))


@login_required
def game_incidents_clear(request, game_id, team_id):
    if not is_team_member(request, team_id):
        return HttpResponse("Unauthorised team", status=401)
    if not game_has_team(team_id, game_id):
        return HttpResponse('Unauthorized game', status=401)
    log.info("Deleting incidents for game id %s", game_id)
    Incident.objects.filter(line__game_id=game_id).delete()
    return game_operations(request, game_id, team_id)
