import z3
from z3 import *
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
#
distance = ctrl.Antecedent(np.arange(0, 11, 0.1), 'distance')
smile = ctrl.Antecedent(np.arange(0, 2, 1), 'smile')       # 0 or 1
uv = ctrl.Antecedent(np.arange(0, 2, 1), 'uv')             # 0 or 1


NUM_TIMESLOTS = 50
NUM_ROOMS=2
NUM_ROBOTS=2
QUEUE_SIZE=6

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
    s = Solver()

    # initialise robots to charging
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


    # simulate at least one stop
    # s.add(emergency_stop[0][T -5] == True)
    # set up the time transitions
    for t in range(NUM_TIMESLOTS-1):
        s.add(queue[t] >= 0) # queue can't go negative
        # everytime a room is used reduce the queue (assuming 1 timeslot for op)
        s.add(queue[t + 1] == queue[t] - Sum([If(room_used[room][t], 1, 0) for room in range(NUM_ROOMS)]))


        for room in range(NUM_ROOMS):
            # if room was just used make it dirty (the room would have been clean if in use)
            s.add(Implies(room_used[room][t], Not(room_cleaned[room][t + 1])))
            # if room just cleaned use it.
            # s.add(room_used[room][t] == room_cleaned[room][t])
            s.add(room_used[room][t] == If(queue[t]>0,room_cleaned[room][t], False))
            # is any robot in the room with uv_on?
            any_robot_uv_this_room = Or([uv_on[room][robot][t] for robot in range(NUM_ROBOTS)])
            # if and only if there was then mark room as cleaned. If it was previous clean keep it that way.$$
            # s.add(Or((any_robot_uv_this_room == room_cleaned[room][t + 1]))) #,
                   # (room_cleaned[room][t] == room_cleaned[room][t + 1])))
            s.add(room_cleaned[room][t + 1] == Or(any_robot_uv_this_room, And(Not(room_used[room][t]), room_cleaned[room][t])))
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
            in_any_doorway = Or([in_doorway[room][robot][t] for room in range(NUM_ROOMS)])
            out_any_doorway = Or([out_doorway[room][robot][t] for room in range(NUM_ROOMS)])
            all_clean =  And([room_cleaned[room][t] for room in range(NUM_ROOMS)])
            # battery consumption
            s.add(
                battery[robot][t+1] == battery[robot][t]
                                    # normal move
                                    - If(Or(to_charge[robot][t],to_any_room), 6, 0)
                                    # uv light uses more power
                                    - If(cleaning_any_room, 16, 0) # 16
                                    # manoeuvring through doorway
                                    - If(in_any_doorway, 4, 0)
                                    - If(out_any_doorway, 4, 0)
                                    # charging adds 8 unless it needs less.
                                    + If(charging[robot][t], If(battery[robot][t] <= 92, 8, 100 - battery[robot][t]), 0)
                                    # + If(And(charging[robot][t], battery[robot][t] <= 92), 8, 100- battery[robot][t])
            )
            s.add(battery[robot][t] >= 0)
            s.add(battery[robot][t] <= 100)

            min_batt_for_door=10
            # don't go through a doorway on < x% battery in case of blockage
            # s.add(Implies(Or(in_any_doorway,out_any_doorway),battery[robot][t]>=min_batt_for_door))
            s.add(Implies(battery[robot][t] < min_batt_for_door, Not(to_any_room)))
            s.add(Implies(Or(in_any_doorway, out_any_doorway), battery[robot][t] >= min_batt_for_door))
            s.add(Implies(
                And(in_any_room, battery[robot][t] < min_batt_for_door),
                And(halted[robot][t + 1] , Not(in_any_room))
            ))


            # can only go to charging if previous was to_charge or already charging if not fully charged
            s.add(charging[robot][t+1] == Or( to_charge[robot][t], If(And(charging[robot][t], battery[robot][t] < 97), True, False)))
            # room specific
            s.add(AtMost(*[to_room[room][robot][t] for room in range(NUM_ROOMS)], 1))

            for room in range(NUM_ROOMS):
                s.add(cleaning[room][robot][t] == in_room[room][robot][t])
                s.add(And(Implies(uv_on[room][robot][t], cleaning[room][robot][t]),
                          Implies(cleaning[room][robot][t], uv_on[room][robot][t])))
                # only go to dirty rooms
                s.add(Implies(to_room[room][robot][t], Not(room_cleaned[room][t])))
                # go to the indoorway
                s.add(in_doorway[room][robot][t+1] == to_room[room][robot][t])
                # go into room from in doorway
                s.add(in_room[room][robot][t + 1] == in_doorway[room][robot][t])
                # when the room is cleaned and this robot was in the room - go out
                s.add(out_doorway[room][robot][t + 1] == And(cleaning[room][robot][t],in_room[room][robot][t]))

            # Smile inside rooms
            # s.add(And(pause_and_smile[robot][t],moving[robot][t]))
            s.add(pause_and_smile[robot][t]== human_detected[robot][t])

            # human detection stop clean/UV
            # s.add(human_detected[t]!=uv_on[t])
            s.add(Implies(human_detected[robot][t],And( Not(uv_on_any_room),Not(cleaning_any_room),Not(moving[robot][t]))))
            # emergency stop
            s.add(Implies(emergency_stop[robot][t],And(Not(uv_on_any_room),Not(cleaning_any_room),Not(moving[robot][t]))))
            # halt if emerg stop, previously halted or battery too low.

            s.add(emergency_stop[robot][t + 1] == Or(emergency_stop[robot][t],emergency_button[robot][t] ))
            s.add(halted[robot][t + 1] == Or(halted[robot][t], battery[robot][t] < 20))

            # moving if to_*
            s.add(moving[robot][t]==Or(to_any_room,to_charge[robot][t]))

            # states are 1 and only 1
            s.add(AtMost(in_any_room, charging[robot][t], in_any_doorway, emergency_stop[robot][t], out_any_doorway, to_any_room, to_charge[robot][t], halted[robot][t],1))
            s.add(Or(in_any_room, charging[robot][t],  in_any_doorway, emergency_stop[robot][t],  out_any_doorway, to_any_room, to_charge[robot][t], halted[robot][t]))

            #  robot cannot move while cleaning
            s.add(Implies(cleaning_any_room, Not(moving[robot][t])))

            s.add(Implies(And(all_unused_clean, battery[robot][t] < 80),
                          to_charge[robot][t]))
            # low battery go charge
            s.add(Implies( Or(battery[robot][t] < 20),    to_charge[robot][t] ))
            # s.add(Implies(to_charge[robot][t], Or( battery[robot][t] < 30)))
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

