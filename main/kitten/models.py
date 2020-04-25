from django.db import models
from enum import IntEnum


class Network(models.Model):
    # map
    # font
    # logo
    name = models.CharField(max_length=40)
    description = models.CharField(max_length=300)
    created = models.DateField(auto_now_add=True)
    last_saved = models.DateField(auto_now=True)
    # owner = models.ForeignKey(User, on_delete=models.WARN)
    # settings
    # min. level to play & success criteria & completion score
    # last use

    def __str__(self):
        return self.name


class Team(models.Model):
    name = models.CharField(max_length=40)
    # -> users
    # levels_unlocked (some kind of score)

    def __str__(self):
        return self.name


class Game(models.Model):
    # level
    name = models.CharField(max_length=40, null=True)
    started = models.DateField(auto_now_add=True)
    last_played = models.DateField(auto_now=True)
    team = models.ManyToManyField(Team, related_name='games')
    network = models.ForeignKey(Network, on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.name if self.name else ''} started {self.started}, "\
            f"last played {self.last_played}"


class Line(models.Model):
    network = models.ForeignKey(Network)
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
    network = models.ForeignKey(Network, null=True)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, null=True)
    name = models.CharField(max_length=40)
    trains_dir1 = models.IntegerField(default=3)
    trains_dir2 = models.IntegerField(default=3)
    train_frequency = models.IntegerField(default=10)
    reputation = models.IntegerField(default=100)

    def __str__(self):
        return str(self.name)

    class Meta:
        verbose_name_plural = "Game Line Parameters"


class LineLocation(models.Model):
    """ a place on the line: a station, a depot or a line  """
    game = models.ForeignKey(GameLineParameters, on_delete=models.CASCADE)
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
