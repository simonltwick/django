from django.db import models
from django.contrib.auth.models import User
from typing import List, Optional


class GameLevel:
    BASIC = 10
    INTERMEDIATE = 20
    ADVANCED = 30
    EXPERT = 40
    CHOICES = ((BASIC, 'Basic'),
              (INTERMEDIATE, 'Intermediate'),
              (ADVANCED, 'Advanced'),
              (EXPERT, 'Expert'))


class Team(models.Model, GameLevel):
    name = models.CharField(max_length=40, unique=True)
    members = models.ManyToManyField(User, related_name='teams')
    owner = models.ForeignKey(User, on_delete=models.PROTECT,
                              related_name='teams_owned')
    level = models.IntegerField(choices=GameLevel.CHOICES)
    # games = reverse FK

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
    owner = models.ForeignKey(User, on_delete=models.PROTECT,
                              null=True)
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


class GameTemplate(models.Model, GameLevel):
    network = models.ForeignKey(Network, related_name='levels',
                                on_delete=models.CASCADE)
    level = models.IntegerField(choices=GameLevel.CHOICES)

    class Meta:
        unique_together = (('network', 'level'))

    def __str__(self):
        return f'{self.get_level_display()} game on {self.network}'


# ----- Game related models ------
class Game(models.Model, GameLevel):
    name = models.CharField(max_length=40, null=True, blank=True)
    started = models.DateField(auto_now_add=True)
    last_played = models.DateField(auto_now=True)
    teams = models.ManyToManyField(Team, related_name='games')
    network_name = models.CharField(max_length=40)
    level = models.IntegerField(choices=GameLevel.CHOICES)

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
        game.teams.add(*teams)
        line_templates = LineTemplate.objects.filter(network=template.network)
        for line_template in line_templates:
            Line.new_from_template(template=line_template, game=game)
            # lines then create the Station, LineLocations and Trains
        return game


class LineTemplate(models.Model):
    # TODO: validate that ends of the line are depots
    network = models.ForeignKey(Network, related_name='lines',
                                on_delete=models.CASCADE)
    name = models.CharField(max_length=40, default='')
    direction1 = models.CharField(max_length=20, default='Up')
    direction2 = models.CharField(max_length=20, default='Down')
    trains_dir1 = models.IntegerField(default=3)
    trains_dir2 = models.IntegerField(default=3)
    train_interval = models.IntegerField(default=10)
    train_type = models.CharField(max_length=20, default='Train')
    # line style / colour
    # train icon
    # mapping? (line path)
    # places = fk to PlaceTemplate

    def __str__(self):
        return f'{self.name} in {self.network}'


# ----- Line related models -----
class Line(models.Model):
    # name, direction1, direction2, trains_dir1, trains_dir2, train_interval
    # train_type = all from LineParameters
    game = models.ForeignKey(Game, on_delete=models.CASCADE, null=True)
    operator = models.ForeignKey(Team, null=True,
                                 on_delete=models.SET_NULL)
    line_reputation = models.IntegerField(default=100)
    name = models.CharField(max_length=40, default='')
    direction1 = models.CharField(max_length=20, default='Up')
    direction2 = models.CharField(max_length=20, default='Down')
    trains_dir1 = models.IntegerField(default=3)
    trains_dir2 = models.IntegerField(default=3)
    train_interval = models.IntegerField(default=10)
    train_type = models.CharField(max_length=20, default='Train')
    # num_trains local variable for assigning train serial numbers
    # line style / colour
    # train icon
    # mapping? (line path)
    # stations fk
    # locations fk
    # trains fk

    def __str__(self):
        return self.name

    @classmethod
    def new_from_template(cls, template: LineTemplate, game: Game,
                          operator: Team=None):
        """ make a new line from a LineTemplate, including all the subsidiary
        Trains, Stations and LineLocations """
        line = Line(
            name=template.name, game=game, operator=operator,
            direction1=template.direction1, direction2=template.direction2,
            trains_dir1=template.trains_dir1, trains_dir2=template.trains_dir2,
            train_interval=template.train_interval,
            train_type=template.train_type)
        line.save()
        line.create_locations(template)
        return line

    def create_locations(self, template: LineTemplate):
        """ create LineLocations from PlaceTemplates
        LineLocations in turn create Stations and Trains """
        places = [(p, p.position) for p in template.places.all()]
        line_length = len(places)
        # sort and re-enumerate in case place.position isn't consecutive
        places.sort(key=lambda item: item[1])  # sort by position

        self.num_trains = 0  # used to allocate Train serial numbers
        is_forward = True
        for direction in (template.direction1, template.direction2):
            for pos, (place, _pos) in enumerate(places):
                lls = [LineLocation.new_from_template(
                        self, line_length, place, pos, direction, is_forward)]
            is_forward = False

            # set any blank LineLocation names e.g. Between x and y
            for line_location in lls:
                if line_location.update_name():
                    line_location.save()


class LocationType:
    DEPOT = 0
    TRACK = 1
    STATION = 2
    CHOICES = ((DEPOT, 'Depot'), (TRACK, 'Track'), (STATION, 'Station'))


class PlaceTemplate(models.Model, LocationType):
    # TODO: validate that station names are non-blank
    name = models.CharField(
        max_length=40, help_text="A name is only required for stations",
        default='', verbose_name="Name (if station)", blank=True)
    type = models.IntegerField(choices=LocationType.CHOICES,
                               default=LocationType.DEPOT)
    position = models.IntegerField()
    line = models.ForeignKey(LineTemplate, related_name='places',
                             on_delete=models.CASCADE)
    transit_delay = models.IntegerField(
        default=1, help_text='Wait time at stations or depots')
    # type (from LocationType abc)

    class Meta:
        unique_together = (('line', 'position'))

    def display_type(self):
        return (self.name if self.name else
                f'[{self.get_type_display()}]')

    def __str__(self):
        return f'{self.name} ({self.display_type()})'


class LineLocation(models.Model, LocationType):
    """ a place on the line: a station, a depot or a line  """
    line = models.ForeignKey(Line, on_delete=models.CASCADE, null=True,
                             related_name='locations')
    name = models.CharField(max_length=40, default='', blank=True)
    type = models.IntegerField(choices=LocationType.CHOICES,
                               default=LocationType.DEPOT)
    sequence = models.IntegerField()
    transit_delay = models.IntegerField(default=1)
    direction = models.CharField(max_length=20, default='direction?')
    direction_is_forward = models.BooleanField(default=True)
    is_start_of_line = models.BooleanField(default=False)
    is_end_of_line = models.BooleanField(default=False)
    # trains = fk Trains
    # incidents= fk
    # type (from LocationType abc)

    @classmethod
    def new_from_template(cls, line, line_length, template: PlaceTemplate,
                          position, direction, is_forward):
        """ create and return a new LineLocation, and also create Stations
        and Trains, according to the PlaceTemplate """
        assert isinstance(line, Line)
        start_of_line = position == 0
        end_of_line = position == line_length-1
        if start_of_line or end_of_line and not is_forward:
            start_of_line, end_of_line = end_of_line, start_of_line

        ll = LineLocation(
            name=template.name, type=template.type,
            line=line, sequence=position,
            transit_delay=template.transit_delay,
            direction_is_forward=is_forward, direction=direction,
            is_start_of_line=start_of_line, is_end_of_line=end_of_line)
        ll.save()
        # create stations and trains in depots
        if ll.is_station() and ll.direction_is_forward:
            # apply calculated station name if not set
            ss = Station(line=line, name=ll.name or ll.calculate_name())
            ss.save()
        elif ll.is_start_of_line and ll.direction_is_forward:
            ll.create_trains(line.trains_dir1)
        elif ll.is_end_of_line and not ll.direction_is_forward:
            ll.create_trains(line.trains_dir2)
        return ll

    def update_name(self):
        """  Calculate and update self.name (and return True) if not set.
         name for track segments is computed as "Between x and y" """
        if self.name:
            return False
        self.name = self.calculate_name()
        return True

    def calculate_name(self):
        if self.is_start_of_line or self.is_end_of_line:
            # should be depot
            depot_number = 1 if self.direction_is_forward else 2
            return f"Depot{depot_number}"

        elif self.get_location_type_display() == "Station":
                return f"[Station at {self.sequence}]"

        else:  # Track
            try:
                return f'Between {self.prev().display_name()} and' \
                    f'{self.next().display_name()}'
            except self.DoesNotExist:  # not created yet
                return f"Track{self.sequence}"

    def create_trains(self, num_trains):
        self.line.num_trains += 1
        for _i in range(num_trains):
            train = Train(location=self, type=self.line.train_type,
                          serial=self.line.num_trains)
            train.save()

    def __str__(self):
        return f'{self.name}, {self.direction}'

    def display_type(self):
        return (self.name if self.name else
                f'[{self.get_location_type_display()}]')

    def is_station(self):
        return self.type == LocationType.STATION

    def is_depot(self):
        return self.type == LocationType.DEPOT

    def next(self) -> Optional['LineLocation']:
        """ return the next Linelocation in direction of travel, or None
        Raises LineLocation.DoesNotExist if next hasn't been created"""
        if self.is_end_of_line:
            return None

        increment = 1 if self.is_forward else -1
        return LineLocation.objects.get(
            line=self.line, sequence=self.sequence + increment,
            is_forward=self.is_forward)

    def prev(self):
        """ return the previous LineLocation for direction of travel, or None.
        Raises LineLocation.DoesNotExist if prev hasn't been created """
        if self.is_start_of_line:
            return None

        increment = -1 if self.is_forward else 1
        return LineLocation.objects.get(
            line=self.line, sequence=self.sequence + increment,
            is_forward=self.is_forward)

    def reverse(self) -> 'LineLocation':
        """ return the 'twin' location in the reverse direction """
        return LineLocation.objects.filter(
            line=self.line, sequence=self.sequence,
            is_forward=not self.is_forward)


class Train(models.Model):
    # passengers
    # attractiveness
    type = models.CharField(max_length=20, default='Train')
    location = models.ForeignKey(LineLocation, on_delete=models.CASCADE)
    serial = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.type} #{self.serial} at {self.location}"


class Station(models.Model):
    line = models.ForeignKey(Line, related_name='stations',
                             on_delete=models.CASCADE)
    name = models.CharField(max_length=40)

    def __str__(self):
        return f"{self.name} on {self.line}"
