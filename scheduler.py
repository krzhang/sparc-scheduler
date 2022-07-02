import typing
from collections.abc import Sequence
import csv
from ortools.sat.python import cp_model

STATUSES = ["RETURNER", "NEWCOMER"]
CLASS_STATUSES = ["TRACKED", "MIXED"]
SLOTS_PER_DAY = 3
CLASS_SIZE = 14

class Student:

  index = 0
  
  def __init__(self, name, status):
    self.name = name
    self.status = status # "RETURNER", "NEWCOMER"
    self.id = Student.get_id()
    
  def __repr__(self):
    return self.name + "({})".format(self.status[0])

  def __str__(self):
    return repr(self)
  
  @classmethod
  def load_from_file(cls, filename):
    students = []
    with open("students.csv", newline='') as csvfile:
      reader = csv.reader(csvfile, delimiter=',', quotechar='|')
      for row in reader:
        students.append(cls(row[0], row[1]))
    print ("{} students loaded".format(len(students)))
    return students

  @classmethod
  def get_id(cls):
    tid = cls.index
    cls.index += 1
    return tid
  
class ClassBundle:
  """ 
  Classes come 'packaged' together. Each class is either a mixed class or a TRACKED
  class (where returners and newcomers are split)
  """
  
  def __init__(self, bundle_dict):
    """
    [names]: different formats for different targets:
    TRACKED: {"RETURNER":"Statistical Street Fighting 2", 
              "NEWCOMER":"Statistical Street Fighting 1"} 
    MIXED: {'MIXED':'Statistical Street Fighting'}
    """
    if len(bundle_dict) == 1:
      self.bundle_status = "MIXED"
      self.names = {s:bundle_dict["MIXED"] for s in STATUSES}
    else:
      self.bundle_status = "TRACKED"
      self.names = bundle_dict
      
  def __hash__(self):
    return hash((self.name, self.target))

  def make_classes(self, returner_index):
    """ 
    make a list of classes where the returner index is in the [returner_index] slot, if 
    it is tracked. This allows us to space out where the returners are so they don't clash.
    """
    if self.bundle_status == "MIXED":
      return [Class("MIXED", self.names["NEWCOMER"]) for i in range(SLOTS_PER_DAY)]
    else:
      lis = [Class("NEWCOMER", self.names["NEWCOMER"]) for i in range(SLOTS_PER_DAY-1)]
      return lis[:returner_index] + [Class("RETURNER", self.names["RETURNER"])] + lis[returner_index:]

class Class:

  index = 0
  
  def __init__(self, class_status, name):
    """
    [class_status]: 
    "MIXED", 'RETURNER', 'NEWCOMER'
    """
    self.class_status = class_status
    self.name = name
    self.id = Class.get_id()

  def __repr__(self):
    return self.name + " {}".format(self.class_status[0])

  @classmethod
  def get_id(cls):
    cls.index += 1
    return cls.index - 1
  
class Day:

  def __init__(self, classes = Sequence[ClassBundle]):
    """ 
    currently only supports 0, 1, or 3 tracked classes. (others being mixed)
    """
    self.class_bundles = classes
    assert len(classes) == SLOTS_PER_DAY
    
  def make_slots(self):
    class_slots = []
    for i in range(SLOTS_PER_DAY):
      class_slots.append(self.class_bundles[i].make_classes(i))
    # now we have a 2-d array, where each row is the classes offered during one period of time,
    # we can think of the corresponding columns as room numbers
    # we need to transpose since right now we have the iterations of a class as rows instead of
    # columns, and we want the rows to correspond to different time periods    
    return zip(*class_slots)
    
class Scheduler(object):
  """ 
  The main class. Given students and curriculum, make a schedule
  """

  def __init__(self, students: Sequence[Student], curriculum: Sequence[Day]):
    self.students = students
    self.cohorts = {"NEWCOMER": [s for s in students if s.status == "NEWCOMER"],
                    "RETURNER": [s for s in students if s.status == "RETURNER"]}
    self.curriculum = curriculum
  
  def make_schedule(self):
    return [self.make_schedule_day(day) for day in self.curriculum]
  
  def make_schedule_day(self, day):
    students = self.students
    slots = list(day.make_slots())
    
    print("slots made")
    for s in slots:
      print("  " + str(s))

    model = cp_model.CpModel()
    
    student_ids = [s.id for s in self.students]
    class_ids = sum([[t.id for t in time] for time in slots], []) # a list of all class ids
    # first, we need a variable for each (student, class) combo
    # example variable: 3_in_7 means studen 3 is in slot 7
    sc_variables = {(s, c):model.NewIntVar(0, 1, "{}_in_{}".format(s, c))
                    for s in student_ids for c in class_ids}

    print (f"{len(sc_variables)} variables made")

    # TODO: [ortools.sat.python.cp_model API documentation](https://google.github.io/or-tools/python/ortools/sat/python/cp_model.html)
    
    # creat the constraints
    # 1. each student is in 1 class per time period:
    for s in student_ids:
      for time in slots:
        class_ids_for_time = [t.id for t in time]
        lin_expr = 0
        for i in class_ids_for_time:
          lin_expr += sc_variables[(s,i)]
        # print("  constraint: " + str(lin_expr))
        model.Add(lin_expr == 1)

    # 2. class size constraints
    for i in class_ids:
      lin_expr = 0
      for s in student_ids:
        lin_expr += sc_variables[(s, i)]
      # print("  constraint: " + str(lin_expr))
      model.Add(lin_expr <= CLASS_SIZE)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)


    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
      for i, time in enumerate(slots):
        print(f'time period {i}:\n')
        for cl in time:
          print(f'  class {cl.name}: ')
          for s in students:
            if solver.Value(sc_variables[(s.id, cl.id)]):
              print(f'{s.name}, ')
          print('\n')
    else:
      print("Impossible!\n")

def test():
  import data
  curriculum = [Day([ClassBundle(b) for b in d]) for d in data.curriculum]
  students = Student.load_from_file("students.csv")
  scheduler = Scheduler(students, curriculum)
  scheduler.make_schedule()
