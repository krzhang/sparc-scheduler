import typing
import importlib
import markdown
import random
from collections.abc import Sequence
import csv
from ortools.sat.python import cp_model

STATUSES = ["RETURNER", "NEWCOMER"]
CLASS_STATUSES = ["TRACKED", "MIXED"]
SLOTS_PER_DAY = 3
CLASS_SIZE = 10
TIMES = ["9:30AM-10:20AM", "10:30AM-11:20AM", "11:30AM-12:20PM"]

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
    with open(filename, newline='') as csvfile:
      reader = csv.reader(csvfile, delimiter=',', quotechar='|')
      next(reader, None)
      for row in reader:
        students.append(cls(row[0], row[1]))
    random.shuffle(students)    
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
    # return self.name + " {}".format(self.class_status[0])
    return self.name

  @classmethod
  def get_id(cls):
    cls.index += 1
    return cls.index - 1
  
class Day:

  def __init__(self, date, classes = Sequence[ClassBundle]):
    """ 
    currently only supports 0, 1, or 3 tracked classes. (others being mixed)
    """
    self.date = date
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

class Schedule(object):

  def __init__(self, students, curriculum, solutions, guest_slots, post_curriculum_text):
    self.students = students
    self.curriculum = curriculum
    self.solutions = solutions # each a solution is a slots, solutions
    self.guest_slots = guest_slots
    self.post_curriculum_text = post_curriculum_text
    
  def student_view(self, student, html=False):
    output = "# {}({})'s Schedule\n\n".format(student, student.id)
    for i, day in enumerate(self.curriculum):
      output += "## Day {}: \n\n".format(day.date)
      _, sol_day = self.solutions[i]
      for j, slot in enumerate(sol_day):
        output += "* Slot {}: {}\n".format(j, slot[student])
      output += "\n"
    if html:
      return markdown.markdown(output)
    else:
      return output

  def class_view(self, day_index):
    day = self.curriculum[day_index]
    slots, solution = self.solutions[day_index]
    output = "## {} Schedule\n\n".format(day.date)
    output += "## 9:00AM - 9:30AM: Morning Meta (Sequoia Lounge)\n"
    for i, time in enumerate(slots):
      output += "## " + TIMES[i] + '\n\n'
      for cl in time:
        first = True
        print_str = '**{}**: '.format(cl.name)
        for s in self.students:
          if solution[i][s] == cl:
            if first:
              print_str += str(s.name)
              first = False
            else:
              print_str += ", " + str(s.name)
        print_str += "\n\n"
        output += print_str
    output += self.post_curriculum_text.format(self.guest_slots[day_index])
    return output
    
class Scheduler(object):
  """ 
  The main class. Given students and curriculum, make a schedule
  """

  def __init__(self, students: Sequence[Student], curriculum: Sequence[Day]):
    self.students = students
    self.cohorts = {"NEWCOMER": [s for s in students if s.status == "NEWCOMER"],
                    "RETURNER": [s for s in students if s.status == "RETURNER"]}
    self.curriculum = curriculum
  
  def make_schedule(self, guest_slots, post_curriculum_text):
    solutions = [self.make_schedule_day(day, printing=False) for day in self.curriculum]
    sched = Schedule(self.students, self.curriculum, solutions, guest_slots, post_curriculum_text)
    return sched
  
  def make_schedule_day(self, day, printing=True):
    students = self.students
    slots = list(day.make_slots())
    classes_matrix = list(zip(*slots))
    
    model = cp_model.CpModel()

    student_ids = [s.id for s in self.students]
    class_ids = sum([[t.id for t in time] for time in slots], []) # a list of all class ids
    # first, we need a variable for each (student, class) combo
    # example variable: 3_in_7 means studen 3 is in slot 7
    sc_variables = {(s, c):model.NewIntVar(0, 1, "{}_in_{}".format(s, c))
                    for s in student_ids for c in class_ids}
    if printing:
      print (f"{len(sc_variables)} variables made")

    # TODO: [ortools.sat.python.cp_model API documentation](https://google.github.io/or-tools/python/ortools/sat/python/cp_model.html)

    # create the constraints
    # 1. each student is in 1 class per time period:
    for s in student_ids:
      for time in slots:
        class_ids_for_time = [t.id for t in time]
        lin_expr = 0
        for i in class_ids_for_time:
          lin_expr += sc_variables[(s,i)]
        if printing:
          print("  constraint: " + str(lin_expr))
        model.Add(lin_expr == 1)

    # 2. class size constraints
    # TODO: change constraint to minimize difference in class sizes
    for i in class_ids:
      lin_expr = 0
      for s in student_ids:
        lin_expr += sc_variables[(s, i)]
      if printing:
        print("  constraint: " + str(lin_expr))
      model.Add(lin_expr <= CLASS_SIZE)

    # 3. each student goes to all the classes
    for s in student_ids:
      for cl in classes_matrix:
        lin_expr = 0
        for i in [x.id for x in cl]:
          lin_expr += sc_variables[(s, i)]
        if printing:
          print("  constraint: " + str(lin_expr))
        model.Add(lin_expr == 1)
      
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
      solution = []
      for i, time in enumerate(slots):
        solution.append({})
        if printing:
          print(f'time period {i}:\n')
        for cl in time:
          print_str = '  class {}: '.format(cl.name)
          first = True
          for s in students:
            if solver.Value(sc_variables[(s.id, cl.id)]):
              solution[i][s] = cl
          if printing:
            print (print_str + '\n')
      return slots, solution
    else:
      if printing:
        print("Impossible!\n")
      return None

def make_schedule(data, student_data_name):
  """
  Make the (full) schedule. 

  Testing example:
  # import scheduler; sched = scheduler.make_schedule("data_2025", students-2025); print (sched.class_view(1))
  """
  data = importlib.import_module(data)
  curriculum = [Day(date, [ClassBundle(b) for b in d]) for date, d, _ in data.curriculum]
  guest_slots = [x for _, _, x in data.curriculum]
  post_curriculum_text = data.post_curriculum_text
  students = Student.load_from_file(student_data_name)
  scheduler = Scheduler(students, curriculum)
  sched = scheduler.make_schedule(guest_slots, post_curriculum_text)
  return sched 

def write_schedule_day(data, student_data_name, day, output_file):
  """
  Make one day of the schedule

  Testing example:
  # import scheduler; scheduler.write_schedule_day("data_2025", "students-2025.csv", 0, "07-21-2025.md") 
  """
  sched = make_schedule(data, student_data_name)
  with open(output_file, 'w') as file:
    file.write(sched.class_view(day))
  return 

