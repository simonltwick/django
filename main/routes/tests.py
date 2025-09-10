""" These tests cannot be run
because of problems with the routes migration history
- cannot build the test database """

from django.test import TestCase
from .views import (
    SearchQ, AndSearchQ, OrSearchQ, BoundarySearchQ, NearbySearchQ)

class TestSearchQ(TestCase):
    """ test we can translate to JSON and back """
    def test_searchq(self):
        sq = SearchQ(key1="value1")
        sq_json = sq.json()
        sq2 = SearchQ.from_json("user", sq_json)
        self.assertEqual(sq2, sq)
