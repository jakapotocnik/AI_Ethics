import z3
from z3 import *
import numpy as np

# TEAM F - Z3 Validation of Disinfection Robot, PWB and JP

NUM_TIMESLOTS = 50 #Number of timeslots to test
NUM_ROOMS=2 # Number of rooms to model
NUM_ROBOTS=2 # Number of robots to model
QUEUE_SIZE=6 # Number of patients/workload in the queue - keep small to min timeslots
BATT_USE_CLEANING = 16 # How much battery is used cleaning
BATT_USE_DOORWAY = 4 # How much battery is used going through a door carefully
BATT_CHARGE_INCREMENT = 8 #  How much battery charged is added during charging
BATT_MOVING = 6 #  How much battery is used moving to rooms or to the charged
BATT_MIN_FOR_DOOR = 25 #  Minimum battery to be allow go through door
BATT_CRITICAL = 10 #  HALT battery level
BATT_LOW = 20 # mandatory recharge level

# Initialise all the variables for each timeslot.
battery = [[Real(f"battery_{robot}_{t}") for t in range(NUM_TIMESLOTS)] for robot in range(NUM_ROBOTS)]
queue = [Int(f"queue_{t}") for t in range(NUM_TIMESLOTS)]
human_detected = [[Bool(f"human_{robot}_{t}") for t in range(NUM_TIMESLOTS)] for robot in range(NUM_ROBOTS)]
pause_and_smile = [[Bool(f"pause_and_smile_{robot}_{t}") for t in range(NUM_TIMESLOTS)] for robot in range(NUM_ROBOTS)]
halted = [[Bool(f"halted_{robot}_{t}") for t in range(NUM_TIMESLOTS)] for robot in range(NUM_ROBOTS)]
uv_on = [[[Bool(f"uv_{room}_{robot}_{t}") for t in range(NUM_TIMESLOTS)]
          for robot in range(NUM_ROBOTS)] for room in range(NUM_ROOMS)]
cleaning = [[[Bool(f"cleaning{room}_{robot}_{t}") for t in range(NUM_TIMESLOTS)] for robot in range(NUM_ROBOTS)] for room in
            range(NUM_ROOMS)]
moving = [[Bool(f"moving_{robot}_{t}") for t in range(NUM_TIMESLOTS)] for robot in range(NUM_ROBOTS)]
to_room = [[[Bool(f"to_room_{room}_{robot}_{t}") for t in range(NUM_TIMESLOTS)] for robot in range(NUM_ROBOTS)] for room in
           range(NUM_ROOMS)]
to_charge = [[Bool(f"to_charge_{robot}_{t}") for t in range(NUM_TIMESLOTS)] for robot in range(NUM_ROBOTS)]
charging = [[Bool(f"charging_{robot}_{t}") for t in range(NUM_TIMESLOTS)] for robot in range(NUM_ROBOTS)]
emergency_button = [[Bool(f"emergency_button_{robot}_{t}") for t in range(NUM_TIMESLOTS)] for robot in range(NUM_ROBOTS)]
emergency_stop = [[Bool(f"emergency_stop_{robot}_{t}") for t in range(NUM_TIMESLOTS)] for robot in range(NUM_ROBOTS)]

in_room = [[[Bool(f"in_room_{room}_{robot}_{t}") for t in range(NUM_TIMESLOTS)] for robot in range(NUM_ROBOTS)] for room in
           range(NUM_ROOMS)]
in_doorway = [[[Bool(f"in_doorway_{room}_{robot}_{t}") for t in range(NUM_TIMESLOTS)] for robot in range(NUM_ROBOTS)] for room in
           range(NUM_ROOMS)]
out_doorway = [[[Bool(f"out_doorway_{room}_{robot}_{t}") for t in range(NUM_TIMESLOTS)] for robot in range(NUM_ROBOTS)] for room in
           range(NUM_ROOMS)]
room_used = [[Bool(f"room_used_{room}_{t}") for t in range(NUM_TIMESLOTS)] for room in range(NUM_ROOMS)]
room_cleaned = [[Bool(f"room_cleaned_{room}_{t}") for t in range(NUM_TIMESLOTS)] for room in range(NUM_ROOMS)]


def build_solver(add_violations=False,functional_goals=True,force_one_stop=False):
    '''
    Method to build a z3 solver for the robot.
    :param add_violations: Flag to enable the violation search. Should return unsat if enabled.
    :param functional_goals: Enable the end goals, queue=0, rooms all clean.
    :param force_one_stop: Force an emergency stop in the simulation - 5 TIME SLOTS FROM END
    :return: the solver object.
    '''
    s = Solver()

    # initialise robots and rooms
    for robot in range(NUM_ROBOTS):
        s.add(battery[robot][0] == 100)
        s.add(human_detected[robot][0] == False)
        s.add(pause_and_smile[robot][0] == False)
        s.add(moving[robot][0] == False)
        s.add(charging[robot][0] == True)
        s.add(to_charge[robot][0] == False)
        s.add(halted[robot][0] == False)
        s.add(emergency_stop[robot][0] == False)
        s.add(emergency_button[robot][0] == False)

        for room in range(NUM_ROOMS):
            s.add(uv_on[room][robot][0] == False)
            s.add(cleaning[room][robot][0] == False)
            s.add(in_room[room][robot][0] == False)
            s.add(to_room[room][robot][0] == False)
            s.add(in_doorway[room][robot][0] == False)
            s.add(out_doorway[room][robot][0] == False)
    # init rooms to not in use and dirty
    for room in range(NUM_ROOMS):
        s.add(room_used[room][0] == False)
        s.add(room_cleaned[room][0] == False)

    # init the patient queue
    s.add(queue[0] == QUEUE_SIZE)

    # s.add(emergency_stop[0][T -5] == True)
    # set up the time transitions
    for t in range(NUM_TIMESLOTS-1):
        s.add(queue[t] >= 0) # queue can't go negative
        # everytime a room is used reduce the queue (assuming 1 timeslot for op)
        s.add(queue[t + 1] == queue[t] - Sum([If(room_used[room][t], 1, 0) for room in range(NUM_ROOMS)]))


        for room in range(NUM_ROOMS):
            # if room was just used make it dirty
            s.add(Implies(room_used[room][t], Not(room_cleaned[room][t + 1])))
            # if room just cleaned use it.
            s.add(room_used[room][t] == If(queue[t]>0,room_cleaned[room][t], False))
            # is any robot in the room with uv_on?
            any_robot_uv_this_room = Or([uv_on[room][robot][t] for robot in range(NUM_ROBOTS)])
            # if and only if there was then mark room as cleaned. If it was previous clean keep it that way.$$
            s.add(room_cleaned[room][t + 1] == Or(any_robot_uv_this_room, And(Not(room_used[room][t]), room_cleaned[room][t])))
        # global to see if all rooms not in use are clean
        all_unused_clean = And([And(room_cleaned[room][t], Not(room_used[room][t])) for room in range(NUM_ROOMS)])
        for robot in range(NUM_ROBOTS):
            if force_one_stop and t == NUM_TIMESLOTS - 5:
               # force the 5th last timeslot to be a stop
                force_one_stop=False
                s.add(emergency_stop[robot][t] == True)
            else:
                s.add(emergency_stop[robot][t] == False)
            # Any Rooms states
            uv_on_any_room = Or([uv_on[room][robot][t] for room in range(NUM_ROOMS)]) # the robot has uv on somewhere
            cleaning_any_room = Or([cleaning[room][robot][t] for room in range(NUM_ROOMS)]) # the robot is cleaning some room
            in_any_room = Or([in_room[room][robot][t] for room in range(NUM_ROOMS)]) # the robot is in a room
            to_any_room = Or([to_room[room][robot][t] for room in range(NUM_ROOMS)]) # the robot is on the way to a room
            # the robot is going in/out of room
            # in any IN doorway
            in_any_doorway = Or([in_doorway[room][robot][t] for room in range(NUM_ROOMS)])
            # in any OUT doorway
            out_any_doorway = Or([out_doorway[room][robot][t] for room in range(NUM_ROOMS)])

            # battery consumption - capture the change to the previous level based on activity
            s.add(
                battery[robot][t+1] == battery[robot][t]
                                    # normal move
                                    - If(Or(to_charge[robot][t],to_any_room), BATT_MOVING, 0)
                                    # uv light uses more power
                                    - If(cleaning_any_room, BATT_USE_CLEANING, 0) # 16
                                    # manoeuvring through doorway
                                    - If(in_any_doorway, BATT_USE_DOORWAY, 0)
                                    - If(out_any_doorway, BATT_USE_DOORWAY, 0)
                                    # charging adds 8 unless it needs less.
                                    + If(charging[robot][t], If(battery[robot][t] <= 100 - BATT_CHARGE_INCREMENT, BATT_CHARGE_INCREMENT, 100 - battery[robot][t]), 0)
            )
            s.add(battery[robot][t] >= 0)
            s.add(battery[robot][t] <= 100)


            # don't go through a doorway on < x% battery in case of blockage
            s.add(Implies(battery[robot][t] < BATT_MIN_FOR_DOOR, Not(to_any_room)))
            s.add(Implies(Or(in_any_doorway, out_any_doorway), battery[robot][t] >= BATT_MIN_FOR_DOOR))
            s.add(Implies(
                And(in_any_room, battery[robot][t] < BATT_MIN_FOR_DOOR),
                And(halted[robot][t + 1] , Not(in_any_room))
            ))


            # can only go to charging if previous was to_charge or already charging if not fully charged
            s.add(charging[robot][t+1] == Or( to_charge[robot][t], If(And(charging[robot][t], battery[robot][t] <= 97), True, False)))

            # robot can only be sent to one room
            s.add(AtMost(*[to_room[room][robot][t] for room in range(NUM_ROOMS)], 1))

            for room in range(NUM_ROOMS):
                # if in a room it should be cleaning
                s.add(cleaning[room][robot][t] == in_room[room][robot][t])
                # uv_on if and only if cleaning
                s.add(And(Implies(uv_on[room][robot][t], cleaning[room][robot][t]),
                          Implies(cleaning[room][robot][t], uv_on[room][robot][t])))
                # only go to dirty rooms
                s.add(Implies(to_room[room][robot][t], Not(room_cleaned[room][t])))
                # go to the room through the in doorway
                s.add(in_doorway[room][robot][t+1] == to_room[room][robot][t])
                # go into room from in doorway # stage is to enable checking if we should go through door
                s.add(in_room[room][robot][t + 1] == in_doorway[room][robot][t])
                # when the room is cleaned and this robot was in the room - go out
                s.add(out_doorway[room][robot][t + 1] == And(cleaning[room][robot][t],in_room[room][robot][t]))

            # Smile inside rooms
            s.add(pause_and_smile[robot][t]== human_detected[robot][t])

            # human detection stop clean/UV
            s.add(Implies(human_detected[robot][t],And( Not(uv_on_any_room),Not(cleaning_any_room),Not(moving[robot][t]))))
            # emergency stop
            s.add(Implies(emergency_stop[robot][t],And(Not(uv_on_any_room),Not(cleaning_any_room),Not(moving[robot][t]))))
            # halt if emerg stop, previously halted or battery too low.

            # if button pressed go to emergency stop stage
            s.add(emergency_stop[robot][t + 1] == Or(emergency_stop[robot][t],emergency_button[robot][t] ))
            # if battery critical HALT
            s.add(halted[robot][t + 1] == Or(halted[robot][t], battery[robot][t] < BATT_CRITICAL))

            # moving if to_room or to_charge
            s.add(moving[robot][t]==Or(to_any_room,to_charge[robot][t]))

            # states are 1 and only 1
            s.add(AtMost(in_any_room, charging[robot][t], in_any_doorway, emergency_stop[robot][t], out_any_doorway, to_any_room, to_charge[robot][t], halted[robot][t],1))
            s.add(Or(in_any_room, charging[robot][t],  in_any_doorway, emergency_stop[robot][t],  out_any_doorway, to_any_room, to_charge[robot][t], halted[robot][t]))

            #  robot cannot move while cleaning
            s.add(Implies(cleaning_any_room, Not(moving[robot][t])))
            # if all the rooms are clean go charge if needed
            s.add(Implies(And(all_unused_clean, battery[robot][t] < 100),
                          to_charge[robot][t]))
            # low battery go charge
            s.add(Implies( Or(battery[robot][t] < BATT_LOW),    to_charge[robot][t] ))

    #  patient queue drained at end

    if functional_goals:
        # Set up the desired target states
        # rooms all clean at end
        for room in range(NUM_ROOMS):
            s.add(room_cleaned[room][NUM_TIMESLOTS - 1] == True)

        s.add(queue[NUM_TIMESLOTS - 1] == 0)
    # add violations (states not safe) we want to test for happening.
    if add_violations:
        violations = []
        for t in range(NUM_TIMESLOTS-1):
            for robot in range(NUM_ROBOTS):
                for room in range(NUM_ROOMS):
                    violations.append(And(human_detected[robot][t], uv_on[room][robot][t]))
                    violations.append(And(halted[robot][t], Or(in_doorway[room][robot][t]),out_doorway[room][robot][t]))
        for robot in range(NUM_ROBOTS):
            violations.append(halted[robot][NUM_TIMESLOTS-1])
        s.add(Or(violations))
    return s

def print_timeline(s):
    model = s.model()
    robot_vars = [
        ("battery", battery),
        ("moving", moving),
        ("to_charge", to_charge),
        ("charging", charging),
        ("pause_and_smile", pause_and_smile),
        ("human_detected", human_detected),
        ("emergency_button",emergency_button),
        ("emergency_stop", emergency_stop),
        ("halted", halted),
    ]

    room_robot_vars = [
        ("to_room", to_room),
        ("in_doorway", in_doorway),

        ("in_room", in_room),
        ("uv_on", uv_on),
        ("cleaning", cleaning),
        ("out_doorway", out_doorway),
    ]

    room_vars = [
        ("room_cleaned", room_cleaned),
        ("room_used", room_used)]

    global_vars = [
        ("queue", queue)
    ]

    def clean_val(val):
        if is_bool(val):
            val = "1" if is_true(val) else "."
        else:
            if name == 'battery':
                # val = model.evaluate(var[t], model_completion=True)
                val = val.numerator_as_long() / val.denominator_as_long()
                val = f"{val:3.0f}"
                # val = str(int(val.numerator_as_long() / val.denominator_as_long() / 100 * 9)) + "|"
            else:
                val = str(val)
        return val

    print("GLOBAL")
    for name, var in global_vars:
        timeline = []
        timeline2 = []
        timeline.append(name + " " * (23 - len(name)))
        timeline2.append(" " * (23))
        for t in range(NUM_TIMESLOTS):
            val = model.evaluate(var[t], model_completion=True).as_long()
            val = f"{val:2d}"
            timeline.append(str(val)[0] + "|")
            timeline2.append(str(val)[1] + "|")
        print("".join(timeline))
        print("".join(timeline2))

    for robot in range(NUM_ROBOTS):
        print("\nROBOT %s" % (robot + 1))
        for name, var in robot_vars:
            timeline = []
            timeline2=[]
            timeline3 = []
            timeline.append(name + "(%s)" % (robot + 1) + " " * (20 - len(name)))
            if name == 'battery':
                timeline2.append(" " * (23))
                timeline3.append(" " * (23))
            for t in range(NUM_TIMESLOTS):
                val = clean_val(model.evaluate(var[robot][t], model_completion=True))

                if name == 'battery':
                    timeline.append(val[0] + "|")
                    timeline2.append(val[1]+"|")
                    timeline3.append(val[2]+"|")
                else:
                    timeline.append(val + "|")
            print("".join(timeline))
            if name == 'battery':
                print("".join(timeline2))
                print("".join(timeline3))
                print(" "*23+"-+"*(NUM_TIMESLOTS))

    for room in range(NUM_ROOMS):
        for robot in range(NUM_ROBOTS):
            print("\nROOM %s and ROBOT %s" % (room + 1, robot + 1))
            for name, var in room_robot_vars:
                timeline = []
                timeline.append(name + "(%s, %s)" % (room + 1, robot + 1) + " " * (17 - len(name)))
                for t in range(NUM_TIMESLOTS):
                    val = clean_val(model.evaluate(var[room][robot][t], model_completion=True))
                    timeline.append(val+"|")
                print("".join(timeline))

    for room in range(NUM_ROOMS):
        print("\nROOM %s" % (room + 1))
        for name, var in room_vars:
            timeline = []
            timeline.append(name + "(%s)" % (room + 1) + " " * (20 - len(name)))
            for t in range(NUM_TIMESLOTS):
                val = clean_val(model.evaluate(var[room][t], model_completion=True))
                timeline.append(val+"|")
            print("".join(timeline))

print("STEP 1. Timeline (without violations or functional checks)!")
print("----------------------------------------------------------")
s=build_solver(add_violations=False,functional_goals=False)
result = s.check()
print("Result:", result)
if result == sat:
    print_timeline(s)
else:
    print(s.check())
print()

print("STEP 2. Timeline (without violations with functional checks)!")
print("------------------------------------------------------------")
s=build_solver(add_violations=False,functional_goals=True)
result = s.check()
print("Result:", result)
if result == sat:
    print_timeline(s)

print()
print("STEP 3. Timeline (with violations AND with functional checks)!")
print("-------------------------------------------------------------")
s=build_solver(add_violations=True,functional_goals=True)
result = s.check()
print("Result:", result)
if result == sat:
    print("\nViolation found!\n")
    print_timeline(s)
else:

    print("\nHumans never saw UV. Robot didn't halt in doorway - so safe for", NUM_TIMESLOTS, "steps")

