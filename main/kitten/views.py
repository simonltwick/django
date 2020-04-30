from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

from .models import Game, Team, GameTemplate, Line, LineLocation, Train, \
    GameInterval, Incident
from .forms import GameForm
import logging
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


@login_required
def index(request):
    teams = Team.objects.all()
    return render(request, 'kitten/home.html', {'teams': teams})


@login_required
def team(request, team_id):
    """ list games available to this team """
    team = get_object_or_404(Team, pk=team_id)
    games = Game.objects.filter(teams__pk=team.pk)
    return render(request, 'kitten/team.html', {'games': games, 'team': team})


@login_required
def game_new(request, team_id):
    """ start a new game.
    Prompt for game template and teams, then create game """
    if request.method == 'POST':
        # handle form here .. create the game and then go to edit game
        # to further customise
        selected_template = request.POST.get('template')
        name = request.POST.get('name')
        if selected_template == "NONE":
            errors = "ERROR: You must select a network to base your game upon"
        elif selected_template is None:
            errors = "template field not included in POST data"
        else:
            errors = f"You selected {selected_template}"
            template = get_object_or_404(GameTemplate, pk=selected_template)
            team = get_object_or_404(Team, pk=team_id)
            game = Game.new_from_template(teams=[team], template=template,
                                          name=name)
            game.save()
            form = GameForm(instance=game)
            return render(request, 'kitten/game.html',
                          {'form': form, 'game': game, 'team_id': team.id})
    else:  # initial call with only team_id
        errors = ""
    team = get_object_or_404(Team, pk=team_id)
    game_templates = GameTemplate.objects.filter(level__lte=team.level)
    return render(request, 'kitten/game_new.html',
                  {'team': team, 'templates': game_templates,
                   'errors': errors})


@login_required
def game(request, game_id, team_id):
    """ load a specific game by pk """
    if not Team.objects.filter(id=team_id, members=request.user).exists():
        return HttpResponse('Unauthorised team', status=401)
    if not Game.objects.filter(id=game_id, teams=team_id).exists():
        return HttpResponse('Unauthorized game', status=401)
    game = get_object_or_404(Game, pk=game_id)
    if request.method == 'POST':  # handle incoming form
        form = GameForm(request.POST, instance=game)
        if form.is_valid():
            game = form.save()
    else:
        form = GameForm(instance=game)
    return render(request, 'kitten/game.html',
                  {'form': form, 'game': game, "team_id": team_id})


@login_required
def game_delete(request, game_id, team_id):
    return HttpResponse("Delete game not yet implemented.")


@login_required
def game_tick(request, game_id, team_id):
    return game_operations(request, game_id, team_id,
                           tick_interval=GameInterval.TICK_SINGLE)


@login_required
def game_operations(request, game_id, team_id, tick_interval=None):
    if not Team.objects.filter(id=team_id, members=request.user).exists():
        return HttpResponse('Unauthorised team', status=401)
    if not Game.objects.filter(id=game_id, teams=team_id).exists():
        return HttpResponse('Unauthorized game', status=401)
    team = get_object_or_404(Team, pk=team_id)
    game = get_object_or_404(Game, pk=game_id)
    if tick_interval is not None:
        game.run(tick_interval)
    lines = Line.objects.filter(game=game, operator=team)

    # details is {line([(trains_up, loc, trains_down)], [incidents])}
    details = {line: ([(trains_dir1, location, trains_dir2)
                      for location, (trains_dir1, trains_dir2)
                      in line.details().items()],
                      line.incidents.all())
               for line in lines
               }
    lines_other_op = Line.objects.filter(game=game).exclude(
        operator=team).order_by('operator')
    return render(request, 'kitten/game_operations.html',
                  {'game': game, 'team': team,
                   'details': details,
                   'lines_other_op': lines_other_op
                   })


@login_required
def game_stage(request, game_id, team_id):
    return game_operations(request, game_id, team_id,
                           tick_interval=GameInterval.TICK_STAGE)


@login_required
def incident(request, team_id, incident_id):
    if not Team.objects.filter(id=team_id, members=request.user).exists():
        return HttpResponse('Unauthorised team', status=401)
    try:
        incident = Incident.objects.get(id=incident_id,
                                        line__game__teams=team_id)
    except Incident.DoesNotExist:
        return HttpResponse('Unauthorised team', status=401)
    log.info("views.incident: incident.impacts.all=%s", incident.impacts.all())
    return render(request, 'kitten/incident.html',
                  {'game': incident.line.game,
                   'team_id': team_id,
                   'incident': incident,
                   'response': incident.response})


@login_required
def game_incidents_clear(request, game_id, team_id):
    if not Team.objects.filter(id=team_id, members=request.user).exists():
        return HttpResponse('Unauthorised team', status=401)
    if not Game.objects.filter(id=game_id, teams=team_id).exists():
        return HttpResponse('Unauthorized game', status=401)
    log.info("Deleting incidents for game id %s", game_id)
    Incident.objects.filter(line__game_id=game_id).delete()
    return game_operations(request, game_id, team_id)


@login_required
def team_new(request):
    return HttpResponse("New team not yet written. Please ask Simon")


@login_required
def team_join(request):
    return HttpResponse("Join team net yet written. Please ask Simon")