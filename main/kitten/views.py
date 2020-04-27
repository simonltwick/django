from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

from .models import Game, Team, GameTemplate
from .forms import GameForm


@login_required
def index(request):
    teams = Team.objects.all()
    return render(request, 'kitten/home.html', {'teams': teams})


@login_required
def games(request, team_id=None):
    """ list games available to this team """
    if team_id is None:
        games = Game.objects.all()
        team = None
    else:
        team = get_object_or_404(Team, pk=team_id)
        games = Game.objects.filter(teams__pk=team.pk)
    return render(request, 'kitten/games.html', {'games': games, 'team': team})


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
def team_new(request):
    return HttpResponse("New team not yet written. Please ask Simon")


@login_required
def team_join(request):
    return HttpResponse("Join team net yet written. Please ask Simon")
