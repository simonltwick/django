from django.db import models
from django.contrib.auth.models import User
from enum import IntEnum
from typing import List


class Team(models.Model):
    LEVELS = ((10, 'Basic'), (20, 'Intermediate'),
              (30, 'Advanced'), (40, 'Expert'))
    name = models.CharField(max_length=40)
    members = models.ManyToManyField(User, related_name='teams')
    owner = models.ForeignKey(User, on_delete=models.PROTECT,
                              related_name='teams_owned')
    # games = reverse FK
    level = models.IntegerField(choices=LEVELS)

    def __str__(self):
        return self.name


# ------ network and game templating classes
class Network(models.Model):
    # map
    # font
    # logo
    name = models.CharField(max_length=40)
    description = models.CharField(max_length=300)
    created = models.DateField(auto_now_add=True)
    last_saved = models.DateField(auto_now=True)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, null=True)
    # lines = reverse FK (to LineTemplate)
    # game templates= reverse FK
    # incident_types= reverse FK
    # response_types= reverse FK
    # response_options= reverse FK
    # impacts = reverse FK
    # impact_types = reverse FK
    # passenter_profile
    # settings
    # min. level to play & success criteria & completion score
    # last use

    def __str__(self):
        return self.name


class LineTemplate(models.Model):
    name = models.CharField(max_length=40)
    network = models.ForeignKey(Network, related_name='lines',
                                on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.name} in {self.network}'


class PlaceTemplate(models.Model):
    name = models.CharField(
        max_length=40, help_text="A name is only required for stations",
        null=True, verbose_name="Name (if station)", blank=True)
    position = models.IntegerField()
    line = models.ForeignKey(LineTemplate, related_name='places',
                             on_delete=models.CASCADE)
    transit_delay = models.IntegerField(
        default=1, help_text='Wait time at stations or depots')
    # TODO: validate that station names are non-blank

    class LocationType(IntEnum):
        # NB must tie up with LocationType in Places, below
        DEPOT = 0
        TRACK = 1
        STATION = 2

    location_type = models.IntegerField(
        default=1, choices=[(0, 'Depot'), (1, 'Track'), (2, 'Station')])

    class Meta:
        unique_together = (('line', 'position'))

    def display_name(self):
        return (self.name if self.name else
                f'[{self.get_location_type_display()}]')

    def __str__(self):
        return self.display_name()


class GameTemplate(models.Model):
    level = models.IntegerField(choices=Team.LEVELS)
    network = models.ForeignKey(Network, related_name='levels',
                                on_delete=models.CASCADE)

    class Meta:
        unique_together = (('network', 'level'))

    def __str__(self):
        return f'{self.get_level_display()} game on {self.network}'


# ----- Game related models ------
class Game(models.Model):
    # level
    name = models.CharField(max_length=40, null=True, blank=True)
    started = models.DateField(auto_now_add=True)
    last_played = models.DateField(auto_now=True)
    teams = models.ManyToManyField(Team, related_name='games')
    network_name = models.CharField(max_length=40)
    level = models.IntegerField(choices=Team.LEVELS)

    def __str__(self):
        return f"{self.name if self.name else ''} started {self.started}, "\
            f"last played {self.last_played}"

    @classmethod
    def new_from_template(cls, template: GameTemplate, teams: List[Team],
                          **kwargs):
        """ make a new game from GameTemplate, including
        Lines from game_template.line.line_templates
        LineLocations and Tracks from line_templates.place_templates
        Trains from LineTemplates
        Only one team is required to start a game"""
        network_name = template.network.name
        level = template.level
        game = Game.objects.create(network_name=network_name, level=level,
                                   **kwargs)
        for team in teams:
            game.teams.add(team)
        return game


# ----- Line related models -----
class Line(models.Model):
    name = models.CharField(max_length=40)
    direction1 = models.CharField(max_length=20)
    direction2 = models.CharField(max_length=20)
    trains_dir1 = models.IntegerField(default=3)
    trains_dir2 = models.IntegerField(default=3)
    train_interval = models.IntegerField(default=10)
    # line style / colour
    # train icon
    # mapping? (line path)

    def __str__(self):
        return str(self.name)


class GameLineParameters(models.Model):
    """ operational line parameter overrides within a game """
    game = models.ForeignKey(Game, on_delete=models.CASCADE, null=True)
    team = models.ForeignKey(Team, null=True)
    trains_dir1 = models.IntegerField(default=3)
    trains_dir2 = models.IntegerField(default=3)
    train_frequency = models.IntegerField(default=10)
    line_reputation = models.IntegerField(default=100)

    def __str__(self):
        return str(self.name)

    class Meta:
        verbose_name_plural = "Game Line Parameters"


class LineLocation(models.Model):
    """ a place on the line: a station, a depot or a line  """
    game = models.ForeignKey(GameLineParameters, on_delete=models.CASCADE,
                             null=True)
    line = models.ForeignKey(Line, on_delete=models.CASCADE, null=True,
                             related_name='locations')
    name = models.CharField(max_length=40)
    sequence = models.IntegerField()
    transit_time = models.IntegerField(default=1)

    class LocationType(IntEnum):
        DEPOT = 0
        TRACK = 1
        STATION = 2
    location_type = models.IntegerField(
        default=1, choices=[(0, 'Depot'), (1, 'Track'), (2, 'Station')])

    def __str__(self):
        return str(self.name)


class Train(models.Model):
    # passengers
    # attractiveness
    location = models.ForeignKey(LineLocation, on_delete=models.CASCADE)

    def __str__(self):
        return str(self.name)
