from collections import defaultdict
import datetime
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from enum import IntEnum
import logging
import random
from typing import Dict, List, Optional, Union, Tuple
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


def hhmm(dt: Union[datetime.time, datetime.datetime]) -> str:
    """ accepts a datetime or time object & returns just hh:mm as a string """
    if dt is None:
        return None

    if isinstance(dt, datetime.timedelta):
        mins = dt.seconds // 60
        hh, mm = divmod(mins, 60)
        return(f"{hh}h{mm:02d}")

    if isinstance(dt, datetime.time):
        return dt.isoformat(timespec='minutes')

    return dt.strftime('%H:%M')


def escape(s):
    """ escape html < character in user strings so it won't be treated as html
    """
    return None if s is None else s.replace('<', '&lt.')


# TODO: change IntegerFields to PositiveIntegerFields for validation
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
    description = models.CharField(max_length=300, null=True, blank=True)
    members = models.ManyToManyField(User, related_name='teams')
    invitees = models.ManyToManyField(
        User, through='TeamInvitation',
        through_fields=['team', 'invitee_username'])
    level = models.IntegerField(choices=GameLevel.CHOICES,
                                default=GameLevel.BASIC)
    # games = reverse FK

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('team', args=[str(self.id)])


class TeamInvitation(models.Model):
    EXPIRY_LIMIT = datetime.timedelta(days=14)
    MAX_PASSWORD_FAILURES = 5
    team = models.ForeignKey(Team, on_delete=models.CASCADE,
                             related_name='invitations')
    invitee_username = models.ForeignKey(User, on_delete=models.CASCADE,
                                         related_name='invitations')
    password = models.CharField(max_length=20)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return (f"{self.team.name} invitation to "
                f"{self.invitee_username.username}")

    def accept(self, user: User):
        self.team.members.add(user)
        self.delete()

    @classmethod
    def remove_expired(cls):
        """ expire (delete) invitation where expiry is > expiry_limit """
        n, _d = cls.objects.filter(
            date__lt=(timezone.now() - cls.EXPIRY_LIMIT)).delete()
        # _d is a dict of number of objects deleted by object class
        if n:
            log.info("Expiring %d TeamInvitations", n)


# ------ network and game templating classes
class Network(models.Model):
    # map
    # font
    # logo
    TICK_STAGE = datetime.timedelta(minutes=30)
    TICK_SINGLE = datetime.timedelta(seconds=60)
    name = models.CharField(max_length=40)
    description = models.CharField(max_length=300)
    created = models.DateField(auto_now_add=True)
    last_updated = models.DateField(auto_now=True)
    owner = models.ForeignKey(User, on_delete=models.PROTECT,
                              null=True)
    day_start_time = models.TimeField(default=datetime.time(hour=6))
    day_end_time = models.TimeField(default=datetime.time(hour=22))
    game_round_duration = models.DurationField(default=TICK_STAGE)
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
    incident_rate = models.PositiveSmallIntegerField(
        default=100, help_text="average rate of incidents, with 100 generating"
        "1 incident per tick of the clock")

    class Meta:
        unique_together = (('network', 'level'))

    def __str__(self):
        return f'{self.get_level_display()} game on {self.network}'


# ----- Incident Types and responses -----
class Impact(models.Model):
    name = models.CharField(max_length=40, default='?')
    blocking = models.BooleanField(default=False)
    network = models.ForeignKey(Network, related_name='impacts',
                                on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Response(models.Model):
    name = models.CharField(max_length=40, default='?')
    developer_description = models.CharField(max_length=100, null=True,
                                             blank=True)
    network = models.ForeignKey(Network, null=True, on_delete=models.CASCADE)
    effectiveness_percent = models.PositiveSmallIntegerField(default=100)
    impacts = models.ManyToManyField(Impact)
    time_to_fix = models.DurationField(default=datetime.timedelta(0))

    def __str__(self):
        return self.name

    def fix_duration_hhmm(self):
        return hhmm(self.time_to_fix)

    def worked(self):
        """ return True in effectiveness_percent% of cases """
        return random.random() * 100 < self.effectiveness_percent


class IncidentFamily:
    LINE = 1
    TRAIN = 2
    STATION = 3
    CHOICES = ((1, 'Line'), (2, 'Train'), (3, 'Station'))


class IncidentType(models.Model):
    network = models.ForeignKey(Network, related_name='incident_types',
                                on_delete=models.CASCADE)
    name = models.CharField(max_length=40, default='?')
    type = models.IntegerField(choices=IncidentFamily.CHOICES)
    description = models.CharField(max_length=100, null=True, blank=True)
    likelihood = models.PositiveSmallIntegerField(
        default=10, help_text="0-100: likelihood of this incident type "
        "occuring compared to other incident types")
    responses = models.ManyToManyField(Response)
    impacts = models.ManyToManyField(Impact)

    def __str__(self):
        return self.name


# ----- Game related models ------
class GameInterval(IntEnum):
    TICK_SINGLE = 1
    TICK_STAGE = 2
    MAX_TICKS_PER_ROUND = 20


class Game(models.Model, GameLevel):
    INCIDENT_LIMIT = 1  # per place
    INCIDENT_SEVERITY_VARIATION = 0.5  # in range  +/- variation
    INCIDENT_RATE = 50
    name = models.CharField(max_length=40)
    started = models.DateField(auto_now_add=True)
    last_played = models.DateField(auto_now=True)
    teams = models.ManyToManyField(Team, related_name='games')
    network_name = models.CharField(max_length=40)
    incident_types = models.ManyToManyField(IncidentType)
    incident_rate = models.PositiveSmallIntegerField(
        default=INCIDENT_RATE, help_text="average rate of incidents, with 100"
        " generating1 incident per tick of the clock")
    level = models.IntegerField(choices=GameLevel.CHOICES)
    day_start_time = models.TimeField(default=datetime.time(hour=6))
    day_end_time = models.TimeField(default=datetime.time(hour=22))
    current_time = models.DateTimeField(auto_now_add=True, null=True)
    game_round_duration = models.DurationField(default=Network.TICK_STAGE)
    tick_interval = models.DurationField(default=Network.TICK_SINGLE)
    delay = models.PositiveIntegerField(default=0)

    class meta:
        unique_together = [['name', 'team']]

    def __str__(self):
        return self.name if self.name else f'[untitled#{self.id}]'

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
        game = Game.objects.create(
            network_name=network_name, level=level,
            day_start_time=template.network.day_start_time,
            day_end_time=template.network.day_end_time,
            game_round_duration=template.network.game_round_duration,
            current_time=datetime.datetime.combine(
                datetime.date.today(), template.network.day_start_time),
            incident_rate=template.incident_rate,
            **kwargs)
        game.teams.add(*teams)
        game.incident_types.add(*template.network.incident_types.all())
        line_templates = LineTemplate.objects.filter(network=template.network)
        operator = teams[0] if level <= GameLevel.BASIC else None
        for line_template in line_templates:
            Line.new_from_template(template=line_template, game=game,
                                   operator=operator)
            # lines then create the Station, LineLocations and Trains
        return game

    def run(self, save=False, interval=GameInterval.TICK_SINGLE):
        """ do a series of ticks up to stage_duration, and save afterwards """
        if interval is GameInterval.TICK_SINGLE:
            num_ticks = 1
        else:
            # arbitrary max ticks per round, prevent "infinite" rounds
            # prevent zero ticks per round
            num_ticks = max(min(self.game_round_duration // self.tick_interval,
                                GameInterval.MAX_TICKS_PER_ROUND),
                            1)
        # log.info("Game.run called for %d ticks with save=%s", num_ticks,
        #          save)
        for _t in range(num_ticks - 1):
            self.tick(save=False)
        self.tick(save=save)

    def tick(self, save=False):
        """ run the game for one tick of the clock """
        # log.info("Game.Tick at %s", hhmm(self.current_time))
        # self.sprinkle_incidents()
        for line in self.lines.all():
            line.resolve_incidents()
            # line.update_trains(self.current_time)
        self.current_time += self.tick_interval
        self.save()
        # sprinkle_incidents
        # update scoreboard

    # ----- incident generation ------
    def sprinkle_incidents(self):
        """ generate a random number of incidents at random locations """
        for incident in self.generate_incidents():
            if incident is None:  # if no incident types defined
                return

            for _i in range(10):  # try 10 times for an incident-free place
                incident.location = self.random_place(
                    incident.type.type)
                if self.can_place_incident(incident):
                    break
            else:
                log.warning("Unable to find available location for incident: "
                            f"discarding it")
                return

            # severity in range 0.5-1.5
            # TODO: make incident variability (more) customisable
            incident.severity = 0.5 + random.uniform(
                1-self.INCIDENT_SEVERITY_VARIATION,
                1+self.INCIDENT_SEVERITY_VARIATION)
            incident.occur()

    def can_place_incident(self, incident):
        """ update the incident location so it knows it has an incident
        Return False if there is already an incident there
        Currently only limits number of Incidents on Trains"""
        if isinstance(incident.location, Train):
            if incident.location.incidents.count() >= self.INCIDENT_LIMIT:
                return False  # already has an incident
        return True

    @cached_property
    def incident_type_likelihoods(self) -> Tuple[
            List[IncidentType], List[int]]:
        """ return (list(IncidentTypes), list(incident_type_percent_chance))
        """
        pairs = ((incident_type, incident_type.likelihood)
                 for incident_type in self.incident_types.all())
        # and transpose into a pair of lists
        return tuple(zip(*pairs))

    def random_incident(self):
        """ return a random incident based on all incidentType likelihoods
        The incident doesn't have a start time or place specified yet """
        incident_types, weights = self.incident_type_likelihoods
        if not incident_types or not sum(weights):
            return None
        incident_type = random.choices(incident_types, weights, k=1)[0]
        return Incident(type=incident_type, start_time=self.current_time)

    def random_place(self, place_type):
        """ find a place at random.  Place type could be station, line or train
        """
        return random.choice(self.places[place_type])

    @cached_property
    def places(self):
        places = {IncidentFamily.LINE: [],
                  IncidentFamily.STATION: [],
                  IncidentFamily.TRAIN: []
                  }
        for line in self.lines.all():
            for place_type, place_list in line.places.items():
                places[place_type].extend(place_list)
        # log.info("Places for %s:", self)
        # for k, v in self._places.items():
        #     log.info('%s: [%s]', k, ', '.join(str(e) for e in v))
        return places

    def generate_incidents(self):
        """ yield a random number of new incidents up to twice the average
        incident frequency.
        The new incidents need a place, start time and severity allocating
        (done by caller)
        and they need to added to the GameIncidents by GameIncidents.record

        generates up to 2*freq/100 incidents per call, with an average
        event frequency of freq/100 """
        num = random.randrange(200 * self.incident_rate + 10000) // 10000

        for _i in range(num):
            yield self.random_incident()


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


class GameInvitation(models.Model):
    EXPIRY_LIMIT = datetime.timedelta(days=14)
    MAX_PASSWORD_FAILURES = 5
    game = models.ForeignKey(Game, on_delete=models.CASCADE,
                             related_name='invitations')
    invited_team = models.ForeignKey(Team, on_delete=models.CASCADE,
                                     related_name='game_invitations')
    password = models.CharField(max_length=20)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)
    inviting_team = models.ForeignKey(Team, on_delete=models.CASCADE)

    def __str__(self):
        return (f"{self.game.name} invitation to "
                f"{self.invited_team.name}")

    def accept(self, team: Team):
        self.game.teams.add(team)
        self.delete()

    @classmethod
    def remove_expired(cls):
        """ expire (delete) invitation where expiry is > expiry_limit """
        n, _d = cls.objects.filter(
            date__lt=(timezone.now() - cls.EXPIRY_LIMIT)).delete()
        # _d is a dict of number of objects deleted by object class
        if n:
            log.info("Expiring %d %ss", n, cls.__name__)


# ----- Line related models -----
class Line(models.Model):
    # name, direction1, direction2, trains_dir1, trains_dir2, train_interval
    # train_type = all from LineParameters
    game = models.ForeignKey(Game, on_delete=models.CASCADE, null=True,
                             related_name='lines')
    operator = models.ForeignKey(Team, null=True,
                                 on_delete=models.SET_NULL)
    line_reputation = models.IntegerField(default=100)
    name = models.CharField(max_length=40, default='')
    # direction fields must be read-only or locations become orphans
    direction1 = models.CharField(max_length=20, default='Up',
                                  editable=False)
    direction2 = models.CharField(max_length=20, default='Down',
                                  editable=False)
    trains_dir1 = models.IntegerField(default=3)
    trains_dir2 = models.IntegerField(default=3)
    train_interval = models.IntegerField(default=10)
    train_type = models.CharField(max_length=20, default='Train')
    total_arrivals = models.PositiveIntegerField(default=0)
    total_delay = models.DurationField(default=datetime.timedelta(0))
    on_time_arrivals = models.PositiveIntegerField(default=0)
    # num_trains local variable for assigning train serial numbers
    # line style / colour
    # train icon
    # mapping? (line path)

    @cached_property
    def line_locations(self):
        """ return a list of line locations, ordered by position """
        return LineLocation.objects.filter(
            line=self).order_by('position').all()

    @cached_property
    def trains(self):
        return Train.objects.filter(location__line=self).all()

    @cached_property
    def stations(self):
        return Station.objects.filter(line=self).all()

    @property  # cached_property with append/pop functions
    def incidents(self):
        try:
            return self._incidents
        except AttributeError:
            self._incidents = [incident
                               for incident in
                               Incident.objects.filter(line=self).all()]
        return self._incidents

    def report_incident(self, incident: 'Incident'):
        self.incidents.append(incident)

    def close_incident(self, incident: 'Incident',
                       _closure_time: datetime.datetime):
        self._incidents.pop(incident)

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
        LineLocations in turn create Stations and Trains
        called from Line.new_from template."""
        places = [p for p in template.places.order_by('position').all()]
        line_length = len(places)

        self.num_trains = 0  # used to allocate Train serial numbers
        is_forward = True
        for direction in (template.direction1, template.direction2):
            # re-enumerate in case place.position isn't consecutive
            for pos, place in enumerate(places):
                lls = [LineLocation.new_from_template(
                        self, line_length, place, pos, direction, is_forward)]
            is_forward = False

            # set any blank LineLocation names e.g. Between x and y
            for line_location in lls:
                if line_location.update_name():
                    line_location.save()
            self._line_locations.extend(lls)

    def details(self):
        """ return a pair of dicts of locations along the line with trains,
            one for dir1, and one for dir2 """
        """ return a dict of locations along the line with trains
        ... details of incidents to be added """
        trains_by_loc = self.trains_by_loc()
        return {location: (trains_by_loc[location.id],
                           trains_by_loc[reverse_loc.id])
                for location, reverse_loc in self.location_pairs()}

    def trains_by_loc(self) -> Dict[int, List['Train']]:
        """ return a dict of trains by loc.id
        Use location_id to avoid DB calls """
        trains_by_loc = defaultdict(list)
        for train in self.trains:
            trains_by_loc[train.location_id].append(train)
        return trains_by_loc

    def locations_dir1(self):
        """ return a list of 'forward' LineLocations, ordered by position """
        return [fwd for fwd, _bwd in self.location_pairs]

    def location_pairs(self):
        """ return a tuple of pairs (dir1, dir2) ordered by position """
        # loop over 2 at a time to get pairs in posn order: (forward, backward)
        iter_locs = iter(self.line_locations)
        pairs = tuple((l1, next(iter_locs))
                      if l1.direction_is_forward
                      else (next(iter_locs), l1)
                      for l1 in iter_locs)
        return pairs

    @property
    def places(self):
        """ returns a dict of places """
        return {IncidentFamily.LINE: self.line_locations,
                IncidentFamily.STATION: self.stations,
                IncidentFamily.TRAIN: self.trains
                }

    def __str__(self):
        return self.name

    def punctuality_display(self):
        if self.total_arrivals == 0:
            return '(no punctuality stats)'
        punctuality_percent = self.on_time_arrivals/self.total_arrivals*100
        s = f"{punctuality_percent:0.1f}% punctuality."
        if self.total_arrivals != self.on_time_arrivals:
            av_delay = self.total_delay / (
                self.total_arrivals - self.on_time_arrivals)
            s += f" Average delay={hhmm(av_delay)}."
        return s

    def update_trains(self, current_time):
        # log.info("Line.update_trains(%s)", self)
        # ### HACK get start of line in 1st direction & turnaround a train ###
        # loc0=LineLocation.objects.get(position=0, direction=self.direction1)
        # trains_loc0 = Train.objects.filter(location=loc0).all()
        # assert len(trains_loc0) == 3,f"Wrong number of trains at start, " \
        #    f"len={len(trains_loc0)}"
        # trains_loc0[0].turnaround(current_time)
        # trains_loc0b = Train.objects.filter(location=loc0).all()
        # assert len(trains_loc0b) == 2,f"Move didn't happen, " \
        #    f"len={len(trains_loc0b)}"

        self.turnaround_trains(current_time)

        # trains_loc0c = Train.objects.filter(location=loc0).all()
        # assert len(trains_loc0c) == 3, f"Turnaround_trains didn't work, " \
        #    f"len={len(trains_loc0c)}"
        # log.info("Turnaround test worked")

        self.try_move_trains(current_time)

    def turnaround_trains(self, current_time):
        """train turnaround at depots and where turnaround specified
        move trains from end-of-line depots to start-of-line depots in
        opposite direction, and update last_train_time """
        # TODO: ensure can't set turnaround% in both directions for a posn
        # on a line - it would create a deadlock

        # create a list of trains which can turnaround first
        trains_on_line = Train.objects.filter(location__line=self).all()
        trains_to_turnaround = [train for train in trains_on_line
                                if train.will_turnaround()]

        # and then turnaround, to prevent double turnarounds
        for train in trains_to_turnaround:
            train.turnaround(current_time)

    def try_move_trains(self, current_time):
        # move trains: run through places in reverse order
        trains_direction1 = Train.objects.filter(
            location__line=self,
            location__direction_is_forward=True).order_by(
                '-location__position').all()
        # handle trains in reverse order, from end of line to start
        for train in trains_direction1:
            # this results in trying ALL trains in a depot...
            train.try_move(current_time)

        trains_direction1 = Train.objects.filter(
            location__line=self,
            location__direction_is_forward=False).order_by(
                'location__position').all()
        for train in trains_direction1:
            train.try_move(current_time)

    def report_punctuality(self, delay: datetime.timedelta):
        """ record train arrival punctuality """
        self.total_arrivals += 1
        self.total_delay += delay
        if not delay:
            self.on_time_arrivals += 1
        self.save()

    def resolve_incidents(self):
        """ try to resolve incidents """
        for incident in self.incidents:
            if incident.response_id:
                incident.try_close()


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
                               default=LocationType.TRACK)
    position = models.IntegerField()
    line = models.ForeignKey(LineTemplate, related_name='places',
                             on_delete=models.CASCADE)
    transit_delay = models.IntegerField(
        default=1, help_text='Wait time at stations or depots')
    turnaround_percent_direction1 = models.PositiveSmallIntegerField(
        default=0)
    turnaround_percent_direction2 = models.PositiveSmallIntegerField(
        default=0)

    class Meta:
        unique_together = (('line', 'position'))

    def display_type(self):
        return (self.name if self.name else
                f'[{self.get_type_display()}]')

    def __str__(self):
        return f'{self.name} ({self.display_type()})'


class LineLocation(models.Model, LocationType):
    """ a place on the line: a station, a depot or a line  """
    line = models.ForeignKey(Line, on_delete=models.CASCADE, null=True)
    name = models.CharField(max_length=40, default='', blank=True)
    type = models.IntegerField(choices=LocationType.CHOICES,
                               default=LocationType.DEPOT)
    position = models.IntegerField()
    transit_delay = models.IntegerField(default=1)
    direction = models.CharField(max_length=20, default='direction?')
    direction_is_forward = models.BooleanField(default=True)
    is_start_of_line = models.BooleanField(default=False)
    is_end_of_line = models.BooleanField(default=False)
    turnaround_percent = models.PositiveSmallIntegerField(default=0)
    last_train_time = models.DateTimeField(null=True)
    # trains = fk Trains
    # incidents= fk
    # type (from LocationType abc)

    @classmethod
    def new_from_template(cls, line, line_length, template: PlaceTemplate,
                          position, direction, is_forward):
        """ create and return a new LineLocation, and also create Stations
        and Trains, according to the PlaceTemplate
        NB position may not == template.position, as
        position of LineLocation needs to be consecutive """
        assert isinstance(line, Line)
        start_of_line = position == 0
        end_of_line = position == line_length-1
        train_type = line.train_type
        if (start_of_line or end_of_line) and not is_forward:
            start_of_line, end_of_line = end_of_line, start_of_line
        if end_of_line:
            turnaround_percent = 100
        else:
            turnaround_percent = (template.turnaround_percent_direction1
                                  if is_forward
                                  else template.turnaround_percent_direction2)

        ll = LineLocation(
            name=template.name, type=template.type,
            line=line.id, position=position,
            transit_delay=template.transit_delay,
            turnaround_percent=turnaround_percent,
            direction=direction, direction_is_forward=is_forward,
            is_start_of_line=start_of_line, is_end_of_line=end_of_line)
        ll.save()
        # create stations and trains in depots
        if ll.is_station() and ll.direction_is_forward:
            # apply calculated station name if not set
            ss = Station(line=line.id, name=ll.name or ll.calculate_name())
            ss.save()
        if ll.is_start_of_line:
            ll.create_trains(train_type,
                             line.trains_dir1
                             if ll.direction_is_forward
                             else line.trains_dir2)
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
                return f"[Station at {self.position}]"

        else:  # Track
            try:
                return f'Between {self.prev().display_name()} and' \
                    f'{self.next_loc.display_name()}'
            except self.DoesNotExist:  # not created yet
                return f"Track{self.position}"

    def create_trains(self, train_type, num_trains):
        train_serial = self.line.num_trains
        for _i in range(num_trains):
            train_serial += 1
            train = Train(location=self, type=train_type,
                          serial=train_serial,
                          direction_is_forward=self.direction_is_forward)
        self.line.num_trains = train_serial

    def __str__(self):
        return f'{self.name}, {self.direction}'

    def html(self):
        """ return description for display, including <span> classes """
        # TODO: escape user-provided names in .html methods:replace < with &lt.
        classes = ['location']
        if self.is_station():
            classes.append('station')
        classes = ' '.join(classes)
        name = escape(self.name) or '[Track]'
        # TODO: add turnaround indicator
        return ('<div class="location">'  # allows transit-delay -> right
                f'<span class="{classes}">{name}</span>'
                f'<span class="transit-delay">{self.transit_delay}</span>'
                f'<span class="turnaround">{self.display_turnaround()}</span>'
                '</div>')

    def display_turnaround(self):
        """ return a string describing turnaround % in both directions """
        if self.is_depot():
            return ""
        turnaround = (self.turnaround_percent or
                      self.reverse.turnaround_percent)
        if not turnaround:
            return ""
        char = "⮍" if self.turnaround_percent else "⮏"
        return f", {char}{turnaround}%"

    def display_type(self):
        return (self.name if self.name else
                f'[{self.get_location_type_display()}]')

    def is_station(self):
        return self.type == LocationType.STATION

    def is_depot(self):
        return self.type == LocationType.DEPOT

    def get_next(self) -> Optional['LineLocation']:
        """ return the next Linelocation in direction of travel, or None
        Raises LineLocation.DoesNotExist if next hasn't been created"""
        if self.is_end_of_line:
            return None

        increment = 1 if self.direction_is_forward else -1
        return LineLocation.objects.get(
            line=self.line.id, position=self.position + increment,
            direction_is_forward=self.direction_is_forward)
    next_loc = cached_property(get_next, name='next')

    @cached_property
    def prev(self):
        """ return the previous LineLocation for direction of travel, or None.
        Raises LineLocation.DoesNotExist if prev hasn't been created """
        if self.is_start_of_line:
            return None

        increment = -1 if self.direction_is_forward else 1
        return LineLocation.objects.get(
            line=self.line, position=self.position + increment,
            direction_is_forward=self.direction_is_forward)

    @cached_property
    def reverse(self) -> 'LineLocation':
        """ return the 'twin' location in the reverse direction """
        return LineLocation.objects.get(
            line=self.line_id, position=self.position,
            direction_is_forward=not self.direction_is_forward)


class Train(models.Model):
    # passengers
    # attractiveness
    type = models.CharField(max_length=20, default='Train')
    location = models.ForeignKey(LineLocation, on_delete=models.CASCADE,
                                 related_name='trains')
    serial = models.PositiveIntegerField(default=1)
    awaiting_turnaround = models.BooleanField(default=False)
    blocked = models.BooleanField(default=False)
    delay = models.DurationField(default=datetime.timedelta(0))
    # this is kept in step with LineLocation.direction_is_forward,(performance)
    direction_is_forward = models.BooleanField(default=True)

    @property
    def line(self):
        """ used when recording incidents, to allocate to the correct line """
        return self.location.line

    def __str__(self):
        return f"{self.type} #{self.serial} at {self.location}"

    def html(self):
        classes = ['train']
        if self.blocked:  # this overrides train-delayed in the css
            classes.append('train-blocked')
        elif self.delay:
            classes.append('train-delayed')
        classes = ' '.join(classes)
        return (f'<span class="{classes}">{escape(self.type)} {self.serial}'
                '</span>')

    def move(self, new_location, current_time):
        """ move a train, unconditionally, and update last_train_time """
        # log.info("%s, -> %s", self, new_location)
        # update last_train_time
        if not new_location.trains.exists():
            # don't update if there's a train already waiting to go (depot)
            new_location.last_train_time = current_time
        # departure time, (depot)
        self.location.last_train_time = current_time
        self.location.save()

        if new_location.is_station():
            self.location.line.report_puncuality(self.delay)

        self.location = new_location

        self.blocked = False
        # No need to update location of incidents - they move with the train
        self.save()

    def try_move(self, current_time):
        """ move if possible, i.e. not at end of line, or line blocked, or
        counting down delay
        If blocked, add to line delays """
        # log.info("try_move for %s", self)
        if self.location.is_end_of_line:
            log.warning("%s stuck at end of line?", self)
            return  # end of line, can't move

        if self.awaiting_turnaround:
            return  # already logged in turnaround_clear()

        next_place = self.location.next_loc
        """ consider transit_time.   If no last-train_time recorded, or we've
           waited transit_time since we arrived,
           (or the last train departed from a depot) we can move """

        if self.location.last_train_time is not None and (
            current_time < self.location.last_train_time + (
                self.location.transit_delay *
                self.location.line.game.tick_interval)):
            # log.info("%s in transit at %s "
            #          "(last train=%s, transit_delay=%s)",
            #          self, hhmm(current_time),
            #          hhmm(self.location.last_train_time),
            #          hhmm(self.location.transit_delay *
            #               self.location.line.game.tick_interval))
            return

        # log.info("%s ready to move at %s (last train=%s, transit_delay=%s)",
        #          self, hhmm(current_time),
        #          hhmm(self.location.last_train_time),
        #          hhmm(self.location.transit_delay *
        #               self.location.line.game.tick_interval))
        if next_place.trains.exists() and not next_place.is_depot():
            log.warning("%s is blocked (train ahead)", self)
            self.blocked = True
            self.delay += self.location.line.game.tick_interval
            self.save()
            return False

        self.move(next_place, current_time)

    def will_turnaround(self):
        """ assess moving train to opposite direction on line -> True if OK
        If it's not a depot and it's blocked, delay & return False.
        In this case, it will turnaround later."""
        if self.location.is_depot():
            # always turnaround at end of line
            # log.info("will_turnaround: %s: is_depot=True", self)
            return self.location.is_end_of_line
        if self.location.turnaround_percent == 0:
            return False
        rand = random.random() * 100
        # log.info("Considering turnaround for %s, random#=%d, chance %s%%",
        #          self, rand, self.location.turnaround_percent)
        if self.awaiting_turnaround or \
                rand < self.location.turnaround_percent:
            return self.attempt_turnaround()
            turnaround_ok = self.turnaround_clear()
            return turnaround_ok
        # log.info("will_turnaround(%s): no turnaround", self)
        return False

    def attempt_turnaround(self):
        """ the train is for turning.  Can it be done this time? """
        if not self.location.reverse.trains.exists():
            # log.info("%s will turnaround", self,)
            return True
        log.warning("%s turnaround is blocked (train on reverse track)", self)
        self.blocked = True
        self.delay += self.location.line.game.tick_interval
        self.awaiting_turnaround = True
        self.save()
        return False

    def turnaround(self, current_time):
        """ move the train to the reverse direction """
        # log.info("%s -> %s (turnaround)", self, self.location.reverse)
        self.awaiting_turnaround = False
        reverse_loc = self.location.reverse
        if reverse_loc.trains.exists():
            # clear delays if there's already a train in the depot
            self.delay = datetime.timedelta(0)
        self.direction_is_forward = reverse_loc.direction_is_forward
        self.move(reverse_loc, current_time)


class Station(models.Model):
    line = models.ForeignKey(Line, on_delete=models.CASCADE)
    name = models.CharField(max_length=40)

    def __str__(self):
        return f"{self.name}"


class Incident(models.Model):
    line = models.ForeignKey(Line, on_delete=models.CASCADE)
    type = models.ForeignKey(IncidentType, on_delete=models.CASCADE)
    response = models.ForeignKey(Response, null=True, blank=True,
                                 on_delete=models.SET_NULL)
    # severity
    start_time = models.DateTimeField(null=True)
    response_start_time = models.DateTimeField(null=True, blank=True)
    # exactly one of these location fields should be completed
    location_line = models.ForeignKey(LineLocation, null=True, blank=True,
                                      related_name="incidents",
                                      on_delete=models.CASCADE)
    location_station = models.ForeignKey(Station, null=True, blank=True,
                                         related_name="incidents",
                                         on_delete=models.CASCADE)
    location_train = models.ForeignKey(Train, null=True, blank=True,
                                       related_name="incidents",
                                       on_delete=models.CASCADE)
    impacts = models.ManyToManyField(Impact)
    previous_response_status = models.CharField(null=True, blank=True,
                                                max_length=60)

    @property
    def location(self):
        try:
            return self._location
        except AttributeError:
            pass
        self._location = (
            self.location_line if self.location_line is not None else
            self.location_train if self.location_train is not None else
            self.location_station)
        if self._location is None:
            raise ValueError(f"Incident %s location not set")
        return self._location

    @location.setter
    def location(self, loc):
        self._location = loc
        if isinstance(loc, LineLocation):
            self.location_line = loc
        elif isinstance(loc, Train):
            self.location_train = loc
        elif isinstance(loc, Station):
            self.location_station = loc
        else:
            raise TypeError(f"Unrecognised location type {loc!r}")

    def __str__(self):
        return str(self.type)

    def html(self):
        """ return html version """
        classes = 'incident'
        if self.response is None:
            classes += ' incident-open'
        else:
            classes += ' incident-responding'
        return (f'<span class="{classes}">{hhmm(self.start_time)} '
                f'{self.type.name}, {self.location}</span>')

    def occur(self):
        """ record a new incident """
        if not all((self.start_time, self.location, self.severity),):
            raise ValueError("Incident start_time, location or severity not "
                             f"specified in {self}")
        self.line = self.location.line
        self.line.report_incident(self)
        self.save()
        self.impacts.add(*self.type.impacts.all())
        log.warning("%s: %s at %s", hhmm(self.start_time), self, self.location)

    def start_response(self, response_id):
        response = Response.objects.get(id=response_id)
        self.response = response
        self.response_start_time = self.line.game.current_time
        self.save()

    def try_close(self):
        """ try the response to see if we can close the incident """
        assert self.response, f"trying to close {self} with no response set"
        current_time = self.line.game.current_time
        # log.info("%s: Considering times for %s: response_start=%s, "
        #          "fix_time=%s",
        #          hhmm(current_time), self, self.response_start_time.time(),
        #          self.response.time_to_fix)
        # log.info("response end time=%s",
        #          hhmm(self.response_start_time + self.response.time_to_fix))
        if (self.response_start_time + self.response.time_to_fix >
                current_time):
            # log.info(
            #     "%s: Resolution ongoing for %s at %s", hhmm(current_time),
            #     self, self.location)
            return  # not yet...

        if not self.response.worked():  # based on fix chance
            log.warning("%s: Resolution failed for %s at %s",
                        hhmm(current_time), self, self.location)
            self.previous_response_status = f"{self.response} failed to fix " \
                f"at {hhmm(current_time)}"
            self.response = None
            self.save()
            return
        self.resolve(current_time)

    def resolve(self, current_time):
        log.info("%s: Resolved %s at %s", hhmm(current_time),
                 self, self.location)
        self.line.close_incident(self, current_time)
        self.delete()
        # bye bye!
