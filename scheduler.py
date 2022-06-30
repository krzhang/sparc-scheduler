import typing
from collections.abc import Sequence

SLOTS_PER_DAY = 3

class Student:

  def __init__(self, name, status):
    self.name = name
    self.status = status # "RETURNER", "NEWCOMER"

class Class:

  def __init__(self, name, target):
    self.name = name
    self.target = target # "TRACKED", "MIXED"
    self.status = None # only if tracked

  def __hash__(self):
    return hash((self.name, self.target))
    
class Day:

  def __init__(self, classes = Sequence[Class]):
    """ 
    currently only supports 3 mixed classes or 3 tracked classes. Note we can have 1 tracked
    class for returners and 2 tracked classes for 
    """
    self.classes = classes
    
  def make_slots(self):
    target = self.classes[0].target
    assert all([c.target == target for c in self.classes])
    if target == "TRACKED":
      assert len(classes)
    
    
class Scheduler(object):

  def __init__(self, students: Sequence[Student], curriculum: Sequence[Day]):
    self.students = students
    self.cohorts = {"NEWCOMER": [s for s in students if s.status == "NEWCOMER"],
                    "RETURNER": [s for s in students in s.status == "RETURNER"]}
    self.curriculum = curriculum

  def make_schedule(self):
    return [self.make_schedule_day(day) for day in self.curriculum]

  def make_slots(self, day):
    """
    suppose we have a single tracked class, then 
    """
  
  def make_schedule_day(self, day):
    students = self.students
    slots = self.make_slots(day)
    
