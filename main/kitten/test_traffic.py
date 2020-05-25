'''
Pilot programme exploring passenger traffic loading on&off trains
No train delays.   Train at every station to start with.

5 stations, one train in each direction per station for the initial simulation

Created on 25 May 2020

@author: simon
'''
from itertools import accumulate
import logging

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)


TRAIN_CAPACITY = 100
# station traffic is pairs of in/out of station
STATION_TRAFFIC = ((120, 30), (100, 100), (30, 150), (100, 100), (120, 30))


class Station:
    platform_capacity = 500
    p_waiting_left = 0  # waiting to travel left
    p_waiting_right = 0  # waiting to travel right
    # me as proportion of remaining left-bound stations
    proportion_of_left = None
    proportion_of_right = None  # ditto, right-bound stations
    params_as_str_header = "name       in out bdl bdr  al_l  al_r"

    @classmethod
    def init_stations(cls, station_traffic):
        stations = [Station(f'Station {i}', p_board, p_alight)
                    for i, (p_board, p_alight) in enumerate(station_traffic)]
        # cum_p_alight is total p_alight to left of this station,
        #     including this one.
        cum_p_alight = list(accumulate(
            p_alight for _p_board, p_alight in STATION_TRAFFIC))
        total_p_alight = cum_p_alight[-1]

        for station, p_alight_left in zip(stations, cum_p_alight):
            station.init_passenger_ratios(p_alight_left, total_p_alight)
        return stations

    def __init__(self, name, passengers_in, passengers_alighting):
        self.name = name
        self.p_board = passengers_in
        self.p_alight = passengers_alighting
        self.trains = []

    def __str__(self):
        return self.name

    def init_passenger_ratios(self, p_alight_left, total_p_alight):
        """ calc numbers of passengers boarding trains left and right,
        and fraction of passengers who get off trains travelling left and right
        p_alight_left is px alighting HERE or at stations to the left
        """
        # total px alighting on stations to left
        alight_left = (p_alight_left - self.p_alight)
        alight_right = (total_p_alight - p_alight_left)
        # numbers of passengers boarding trains travelling left and right
        self.num_boarding_left = self.p_board * alight_right / (
            alight_left + alight_right)
        self.num_boarding_right = self.p_board * alight_left / (
            alight_left + alight_right)
        # fraction of passengers alighting here from trains left & right
        p_alight_right = total_p_alight - p_alight_left + self.p_alight
        self.fraction_alighting_left = self.p_alight / p_alight_right
        self.fraction_alighting_right = self.p_alight / p_alight_left

    def params_as_str(self):
        """ return a string of p_board, p_alight, boarding_left, boarding_right,
        alighting_left, alighting_right """
        pattern = '{:9}' + 4*'{:4.0f}' + 2*'{:6.3f}'
        return pattern.format(self.name, self.p_board, self.p_alight,
                              self.num_boarding_left, self.num_boarding_right,
                              self.fraction_alighting_left,
                              self.fraction_alighting_right)

    def add_waiting_passengers(self):
        """ add x new passengers and direct them left or right """
        self.p_waiting_left += self.num_boarding_left
        self.p_waiting_right += self.num_boarding_right
        if self.p_waiting_left > self.platform_capacity:
            log.warn("%s-> overcrowded: %0.0fpx", self, self.p_waiting_left)
        if self.p_waiting_right > self.platform_capacity:
            log.warn("%s<- overcrowded: %0.0fpx", self, self.p_waiting_right)

    def board(self, train, direction, limit):
        num_boarding = (self.p_waiting_left if direction > 0
                        else self.p_waiting_right)
        # log.debug('board(%s, dir=%d): num_boarding=%s', self, direction,
        #           num_boarding)
        if limit:
            if num_boarding > limit:
                log.warn("Passengers unable to board overcrowded %s", train)
            num_boarding = max(num_boarding, limit)
        if direction > 0:
            self.p_waiting_left -= num_boarding
        else:
            self.p_waiting_right -= num_boarding
        return num_boarding

    def alight(self, _train, direction, passengers):
        fraction_alighting = (self.fraction_alighting_left
                              if direction > 0
                              else self.fraction_alighting_right)
        num_alighting = round(fraction_alighting * passengers)
        # passengers just vanish at present: could calculate stn overloading
        return num_alighting


class Train:
    capacity = 500
    passengers = 0

    def __init__(self, name, pos, direction):
        self.name = name
        self.pos = pos
        self.direction = direction
        self.location.trains.append(self)

    def __str__(self):
        return f"{self.name} at {self.location}{self.direction_name}"

    def move(self):
        self.depart()
        # if end of line: turnaround
        if self.pos == 0 and self.direction == -1:
            self.direction = 1
        elif self.direction == 1 and self.pos >= len(stations) - 1:
            self.direction = -1
        else:
            self.pos += self.direction
        self.arrive()

    def depart(self):
        self.location.trains.remove(self)

    def arrive(self):
        """ handle alighting & boarding """
        # log.debug('%s.arrive()', self)
        station = self.location
        station.trains.append(self)
        num_alighting = station.alight(self, self.direction, self.passengers)
        num_boarding = station.board(self, self.direction, 0)
        log.debug("%s had %d px -%d, +%d", self, self.passengers,
                  num_alighting, num_boarding)
        self.passengers += num_boarding - num_alighting
        if self.passengers > self.capacity:
            log.warning("%s: overloaded with %0.0fpx", self, self.passengers)

    @property
    def direction_name(self):
        return "->" if self.direction > 0 else "<-"

    @property
    def location(self):
        return stations[self.pos]


def dump_stations():
    names = [station.name for station in stations]
    max_length = max(len(name) for name in names)
    print(' '.join(f'{name:{max_length}}' for name in names))
    print(' '.join(f'{station.p_waiting_left:{max_length}.0f}'
                   for station in stations))
    print(' '.join(f'{station.p_waiting_right:{max_length}.0f}'
                   for station in stations))


def dump_trains():
    for train in trains:
        print(f"{train}: {train.passengers:.0f} px")


def tick():
    for station in stations:
        station.add_waiting_passengers()
    dump_stations()
    for train in trains:
        train.move()
    dump_trains()
    dump_stations()


def main():
    global stations, trains
    stations = Station.init_stations(STATION_TRAFFIC)
    print(Station.params_as_str_header)
    for station in stations:
        print(station.params_as_str())
    trains = [Train('Train 1', pos=0, direction=-1),
              Train('Train 2', pos=len(stations)-1, direction=1)]
    dump_stations()
    dump_trains()
    while input('Tick or Quit? (T/q): ').upper()[:1] != 'Q':
        tick()


if __name__ == '__main__':
    main()
