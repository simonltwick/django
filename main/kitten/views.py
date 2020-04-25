from django.shortcuts import render, get_object_or_404

from django.http import HttpResponse
from.models import Game, Team


def index(request):
    teams = Team.objects.all()
    return render(request, 'kitten/home.html', {'teams': teams})


def games(request, team_id=None):
    """ list games available to this team """
    if team_id is None:
        games = Game.objects.all()
        team = None
    else:
        team = get_object_or_404(Team, pk=team_id)
        games = Game.objects.filter(team__pk=team.pk)
    return render(request, 'kitten/games.html', {'games': games, 'team': team})


def game(request, game_id):
    """ load a specific game by pk """
    game = get_object_or_404(Game, pk=game_id)
    return render(request, 'kitten/game.html', {'game': game})


def game_new(request):
    """ start a new game """
    return HttpResponse("New game")


def team_new(request):
    return HttpResponse("New team")


def team_join(request):
    return HttpResponse("Join team")
