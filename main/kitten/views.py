from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect

from .models import Game, Team, GameTemplate
from .forms import GameForm


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
                          {'form': form, 'game': game})
    else:  # initial call with only team_id
        errors = ""
    team = get_object_or_404(Team, pk=team_id)
    game_templates = GameTemplate.objects.filter(level__lte=team.level)
    return render(request, 'kitten/game_new.html',
                  {'team': team, 'templates': game_templates,
                   'errors': errors})


@login_required
def team_new(request):
    return HttpResponse("New team")


def team_join(request):
    return HttpResponse("Join team")


def game(request, game_id):
    """ load a specific game by pk """
    if game_id not in (game.pk for game in request.user.teams.games):
        return redirect('/login/?next=%s' % request.path)
    game = get_object_or_404(Game, pk=game_id)
    return render(request, 'kitten/game.html', {'game': game})
