'''
Line related classes
Created on 25 Apr 2020

@author: simon
'''

from utils import make_ints, list_to_str
from sheetdb import get_data_range_as_dict, put_data_range_from_dict
# import sheetdb

import logging
import random
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


class Station:
    def __init__(self, name, line, pos):
        self.name = name
        self.line = line
        self.pos = pos

    def __str__(self):
        return f"{self.name} on {self.line}"


class Place:
    def __init__(self, name, line, pos, direction, dir_no, last_train_time,
                 wait, turnaround_percent):
        self.name = name
        self.line = line
        self.pos = pos
        self.direction = direction
        self.dir_no = dir_no  # 0=forward,1=backward
        self.last_train_time = last_train_time
        self.wait = wait
        self.turnaround_percent = turnaround_percent  # % of trains turnaround
        self.trains = []  # this is maintained by Train.move()

    def __str__(self):
        return f"{self.name}, {self.direction} on {self.line}"

    def next(self):
        """ next place on the line """
        next_pos = self.next_pos()
        if next_pos is None:
            return None
        return self.line.places[self.direction][next_pos]

    def next_pos(self):
        next_pos = self.pos + (1 if self.dir_no == 0 else -1)
        if 0 <= next_pos < len(self.line):
            return next_pos
        return None  # hit buffers

    def prev(self):
        """ previous place on the line """
        prev_pos = self.prev_pos()
        if prev_pos is None:
            return None
        return self.line.places[self.direction][prev_pos]

    def prev_pos(self):
        prev_pos = self.pos + (1 if self.dir_no == 1 else -1)
        if 0 <= prev_pos < len(self.line):
            return prev_pos
        return None  # hit buffers

    def is_depot(self):
        return self.pos == 0 or self.pos == len(self.line) - 1

    def is_start_of_line(self):
        return (self.dir_no == 0 and self.pos == 0) or \
            self.dir_no == 1 and self.pos == len(self.line) - 1

    def reverse_direction(self):
        """ return the place on the same line in the opposite direction """
        reverse_dir_no = 1 - self.dir_no  # swap 0 <-> 1
        reverse_dir = self.line.directions[reverse_dir_no]
        return self.line.places[reverse_dir][self.pos]


class Train:
    train_number = 0
    awaiting_turnaround = False

    def __init__(self, line, current_place):
        self.line = line
        self.location = current_place
        current_place.trains.append(self)
        self.number = self.__class__.allocate_train_number()
        self.incidents = []  # allow incidents to move with the train

    @classmethod
    def allocate_train_number(cls):
        cls.train_number += 1
        return cls.train_number

    def __str__(self):
        flag = '*' * len(self.incidents)
        return f"{flag}Train {self.number} at {self.location}"

    def move(self, new_location):
        """ move a train, unconditionally, and update last_train_time """
        # log.info("move(%s, -> %s.", self, new_location)
        # log.info("before move, %s has %s", self.location,
        #          list_to_str(str(t) for t in self.location.trains))
        # log.info("before move, %s has %s", new_location,
        #          list_to_str(str(t) for t in new_location.trains))
        # update last_train_time
        if not new_location.trains:
            # don't update if there's a train already waiting to go (depot)
            new_location.last_train_time = self.line.current_time
        # departure time, (depot)
        self.location.last_train_time = self.line.current_time

        # update location lists of trains
        self.location.trains.remove(self)
        new_location.trains.append(self)
        # update this train's location
        # old_location = self.location
        self.location = new_location
        # No need to update location of incidents - they move with the train

        # log.info(" after move: %s", self)
        # log.info(" after move, %s has %s", old_location,
        #          list_to_str(str(t) for t in old_location.trains))
        # log.info(" after move, %s has %s", new_location,
        #          list_to_str(str(t) for t in new_location.trains))

    def try_move(self):
        """ move if not at end of line, or line blocked, or counting down delay
        If blocked, add to line delays """
        # log.info("try_move for %s", self)
        next_place = self.location.next()
        if next_place is None:
            # log.info("try_move for %s: end of line", self)
            return  # end of line, can't move
        if next_place.trains and not next_place.is_depot():
            # log.info("try_move for %s: line blocked", self)
            # blocked.  count delay.
            self.line.delays += 1
            return False
        """ consider delays.   If no last-train_time recorded, or we've
           waited 'delay' time since the last train, we can move """
        # log.info("try_move for %s: considering delays. current_time=%d,"
        #          "last_train_time=%s, wait=%s", self, self.line.current_time,
        #          self.location.last_train_time, self.location.wait)
        if not next_place.last_train_time or (
                self.line.current_time >=
                self.location.last_train_time + self.location.wait):
            # log.info("try_move for %s -> Success! calling move", self)
            self.move(next_place)

    def try_turnaround(self):
        """ assess moving train to opposite direction on line -> True if OK
        If it's not a depot and it's blocked, delay & return False """
        if self.location.is_depot():
            # log.info("try_turnaround(%s) in depot: is_start_of_line=%s",
            #          self, self.location.is_start_of_line())
            return not self.location.is_start_of_line()
        if self.awaiting_turnaround or \
                random.random() * 100 < self.location.turnaround_percent:
            self.awaiting_turnaround = True
            blocked = self.turnaround_blocked()
            # log.info("want to turnaround(%s): blocked=%s", self, blocked)
            return not blocked
        # log.info("try_turnaround(%s): no turnaround", self)
        return False

    def turnaround_blocked(self):
        if self.location.reverse_direction().trains:
            self.line.delays += 1
            return True

    def turnaround(self):
        """ move the train to the reverse direction """
        reverse_direction = self.location.reverse_direction()
        self.move(reverse_direction)
        self.awaiting_turnaround = False


class Line():
    def __init__(self):
        self.info = get_data_range_as_dict("Line", 'Data')
        # log.info("Line():loaded info is %d rows of %d columns, keys=%s",
        #          len(self.info),
        #          len(self.info['Wait']) + 1, list(self.info))
        self.directions = [key[11:] for key in self.info  # e.g W-E
                           if key.startswith('Turnaround%')]
        assert 0 < len(self.directions) < 3, \
            f"Invalid number of Turnaround%...rows: {self.directions}"
        self.train_directions = [key for key in self.info
                                 if key.startswith('Trains')]
        self.last_train_times = [key for key in self.info
                                 if key.startswith('Last_Train_Time')]
        assert len(self.directions) == len(self.train_directions), \
            f"mismatch between Turnaround% directions {self.directions} and " \
            f" train_directions {self.train_directions}"
        assert len(self.train_directions) == len(self.last_train_times), \
            f"mismatch between train_directions {self.train_directions} and " \
            f"last_train_times {self.last_train_times}"
        self._length = len(self.info['Delays'])  # no of places along the line
        self.setup_places()  # setup self.places:{direction:[Place]}
        self.setup_stations()  # setup self.stations: [Station]

        make_ints(self.info,  # turn floats into ints & blanks into zeros
                  self.train_directions + self.last_train_times + ['Wait'] +
                  ['Turnaround%' + d for d in self.directions])
        self.setup_trains()  # setup self.trains: {direction: [[Trains]]}
        self.current_time = int(self.info['Current_Time'][0])
        self.delays = int(self.info['Delays'][0])
        self.name = self.info['Line_Name'][0]
        self.validate_turnarounds()

    def setup_places(self):
        """ setup dict of Places on the line, keyed by direction """
        self.place_names = self.info['Place']
        self.places = {direction: [
            Place(name=self.place_name(pos, dir_no), line=self, pos=pos,
                  direction=direction, dir_no=dir_no,
                  last_train_time=self.info['Last_Train_Time'+direction][pos],
                  wait=self.info['Wait'][pos],
                  turnaround_percent=self.info['Turnaround%'+direction][pos])
            for pos in range(len(self))
            ]
            for dir_no, direction in enumerate(self.directions)}

    def place_name(self, pos, dir_no):
        """ return the name of the place at pos.  If it's a station or
        depot, just return the name, else return 'Between x and y'
        (or Line between y and x if direction is 1)
        dir_no is the index of self_directions, i.e. 0 or 1
        """
        assert dir_no in (0, 1), \
            f"Invalid value {dir_no} for dir_no"
        place_name = self.place_names[pos]
        if place_name == 'Line':
            a, b = self.place_names[pos-1], self.place_names[pos+1]
            if dir_no:
                a, b = b, a  # switch direction
            place_name = f'Between {a} and {b}'
        return place_name

    def setup_trains(self):
        """ create a dict of Trains for this line by direction
        actually: dict by direction of dict by position of list of trains """
        train_qty = {direction: [
            (place, self.info['Trains'+direction][place.pos])
            for place in places]
            for direction, places in self.places.items()}
        self.trains = {direction: [[Train(self, place)
                                    for _i in range(qty)]
                                   for place, qty in qty_list]
                       for direction, qty_list in train_qty.items()}

    def setup_stations(self):
        """ create a list of stations and their positions """
        self.stations = [Station(name, self, pos=pos)
                         for pos, name in enumerate(self.place_names)
                         if name not in ('Line', 'Depot', 'Depot2')]

    def validate_turnarounds(self):
        z = zip(*(self.info['Turnaround%' + dirn]
                for dirn in self.directions))
        for pos, (t1, t2) in enumerate(z):
            if t1 and t2:
                raise ValueError("Line Turnaround% cannot be specified in both"
                                 f" directions at {self.info['Place'][pos]}")

    def __str__(self):
        return self.name

    def __len__(self):
        return self._length

    def dump_places(self):
        log.info("Stations for %s: %s", self.name,
                 list_to_str(self.stations))
        log.info("Places for %s: %s", self.name,
                 {k: list_to_str(v) for k, v in self.places.items()})
        self.dump_trains()

    def dump_trains(self):
        log.info("Trains for %s: %s", self.name,
                 {k: list_to_str(list_to_str(t) for t in v)
                  for k, v in self.trains.items()})

    def reset(self):
        size = len(self)
        for direction in self.directions:
            self.info["Trains" + direction] = size * [0]
            self.info['Last_Train_Time' + direction] = size * [0]
        # override turnaround at depots
        turnaround0 = self.info['Turnaround%'+self.directions[0]]
        turnaround0[0] = 0
        turnaround0[-1] = 100
        turnaround1 = self.info['Turnaround%'+self.directions[1]]
        turnaround1[0] = 100
        turnaround1[-1] = 0
        self.info[self.train_directions[0]] = self.info['Initial_Trains']
        self.info['Wait'][0] = self.info['Train_Freq'][0]
        self.info['Wait'][-1] = self.info['Train_Freq'][0]
        self.info['Current_Time'][0] = self.current_time = 0
        self.info['Delays'][0] = self.delays = 0
        # log.info("Reset: self.info=%s", self.info)
        put_data_range_from_dict("Line", "Data", self.info)

    def save(self):
        # NB don't do save after reset - overwrites reset!
        self.info['Current_Time'][0] = self.current_time
        self.info['Delays'][0] = self.delays
        # self.dump_trains()
        for direction in self.directions:
            for pos, place in enumerate(self.places[direction]):
                self.info['Trains' + direction][pos] = \
                    len(self.places[direction][pos].trains)
                self.info['Last_Train_Time'+direction][pos] = \
                    place.last_train_time
        put_data_range_from_dict("Line", "Data", self.info)

    def update_trains(self):
        """ update the status of all trains on the line """
        self.current_time += 1
        self.turnaround_trains()
        self.move_trains()

    def turnaround_trains(self):
        """train turnaround at depots and where turnaround specified
        move trains from end-of-line depots to start-of-line depots in
        opposite direction, and update last_train_time """
        if len(self.directions) < 2:
            return  # no turnarounds possible

        # create a list of trains which can turnaround first
        trains_to_turnaround = [
            train
            for direction in self.directions
            for trains_at_position in self.trains[direction]
            for train in trains_at_position
            if train.try_turnaround()]
        # and then turnaround, to prevent double turnarounds
        for train in trains_to_turnaround:
            train.turnaround()

    def move_trains(self):
        # move trains: run through places in reverse order
        for i, direction in enumerate(self.directions):
            places_orig = self.places[direction]
            # log.info("move_trains: i=%d, direction=%s, places_orig=%s"
            #          "type(places_orig)=%s", i, direction, places_orig,
            #          type(places_orig))
            # start at the end of the line and work back...
            if i:
                places = places_orig
            else:
                places = reversed(places_orig)  # preserve the underlying list
            for place in places:
                if place.trains:
                    place.trains[0].try_move()
