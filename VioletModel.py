
from z3 import *
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib
matplotlib.use("TkAgg")
import random

NUM_ROBOTS = 1
NUM_ROOMS = 4
NUM_HUMANS = 3

rooms_x, rooms_y= [1,1,8,1], [1,5,1,3]
charger_x, charger_y= 8,8
ROOM_OPERATION_TYPES = [1 ,1 , 2,1] # what type is each room
OPERATION_DURATION = {1:4,2:6} # how long is a room type used.
CLEAN_DURATION = {1:2,2:15} # how long does it take to clean a room type

BATTERY_PER_DIST=.3
BATTERY_PER_CLEAN=1
BATTERY_PER_WAIT=.1
BATTERY_PER_CHARGE=3
OPERATION_TYPE_QUEUE = {1:20,2:20}

pending_clean_queue=[]
operation_queue={}
for op_type in OPERATION_TYPE_QUEUE.keys():
    operation_queue[op_type]=[(1000*op_type) + x for x in range(OPERATION_TYPE_QUEUE[op_type])]


class Room:
    def __init__(self, id):
        self.id = id
        self.is_in_use = False
        self.is_being_cleaned=False
        self.status=0
        self.downtime=0
        self.is_clean = True
        self.is_dirty = False

class Human:
    def __init__(self,id):
        self.id = id
        self.loc=(1,random.randint(1, 8))
        self.speed = random.randint(10, 50)

class Robot:
   def __init__(self,id):
       self.id=id
       self.battery=100 # battery level
       self.is_in_transit_to_room=False # on the way to a room
       self.is_paused_transit_to_room = False
       self.is_in_transit_to_charge= False # on the way to charger
       self.is_in_paused_transit_to_charge = False
       self.distance_to_travel=0 # how far to go
       self.at_destination = False
       self.human_detected=False # detected
       self.emergency_stop = False # emergency button prossed
       self.is_cleaning=False
       self.is_paused_cleaning = False
       self.is_charging=False
       self.is_in_park = False # safely park
       self.is_in_panic=False
       self.location = None # where is it now/or was last
       self.in_room=False # in the room or not
       self.room_destination = None # what room to travel to
       self.is_available_for_allocation=True # robot freed up
       self.is_critical_battery = False
       self.is_low_battery = False
       self.is_smiling=False
       self.UV_ON=False # UV on or off
       self.x=charger_x # x,y position for graphing only
       self.y=charger_y
   def __repr__(self):
        return f"{self.id}:  BAT:{self.battery:0.2f}, loc:{self.location if self.location else 'CHRG'}, dst:{self.room_destination if self.room_destination else 'NONE'}) {'CLEANING' if self.is_cleaning else ''} {'GO CLN' if self.is_in_transit_to_room else ''} {'UV' if self.UV_ON else ''}    {'GO CHR' if self.is_in_transit_to_charge else ''}  {'PANIC' if self.is_in_panic else ''} {'HUMAN' if self.human_detected else ''}"


rooms=dict()
for room_no in range(NUM_ROOMS):
    # rooms.append(Room(room_no))
    rooms[room_no]=Room(room_no)

import math

def dist(x1, y1, x2, y2,move_step_size):
    dx = x2 - x1
    dy = y2 - y1
    dist = math.sqrt(dx*dx + dy*dy)
    if abs(dist) <  move_step_size:
        dist = 0
    return dist

def move_step(x1, y1, x2, y2, step=0.1):
    dx = x2 - x1
    dy = y2 - y1
    the_dist =  dist(x1, y1, x2, y2,move_step_size)

    if the_dist == 0:
        return x2, y2
    ux = dx / the_dist
    uy = dy / the_dist
    new_x = x1 + step * ux
    new_y = y1 + step * uy
    return new_x, new_y

move_step_size = 1
robots=[]
for robot_no in range(NUM_ROBOTS):
    robots.append(Robot(robot_no))

humans=[]
for i in range(NUM_HUMANS):
    humans.append(Human(i))

def do_time(t):
    print(f"Time: {t},",end="")
    for op_type in operation_queue.keys():
        print(f"Queue for {op_type}:{len(operation_queue[op_type])}, ",end="")
    print(f" Pending Clean{pending_clean_queue}, ", end='')
    for human in humans:
        x,y = human.loc
        if x == 1 and y != 1:
            human.loc = move_step(x, y, 1, 1, step=move_step_size/human.speed)
        if x == 8 and y != 8:
            human.loc = move_step(x, y, 8, 8, step=move_step_size/human.speed)
        if x != 1 and y == 8:
            human.loc = move_step(x, y, 1, 8, step=move_step_size/human.speed)
        if x != 8 and y == 1:
            human.loc = move_step(x, y, 8, 1, step=move_step_size/human.speed)

    # Room allocation
    for room_no in range(NUM_ROOMS):
        print(f"Room: {room_no}:{rooms[room_no].status}, ", end="")
        op_type = ROOM_OPERATION_TYPES[room_no]
        # room was in use and now ready for cleaning
        if rooms[room_no].status == 0 and rooms[room_no].is_in_use:
            rooms[room_no].is_in_use=False
            if room_no in pending_clean_queue:
                print('block')
            rooms[room_no].status = CLEAN_DURATION[op_type]*-1
            pending_clean_queue.append(room_no)
            rooms[room_no].is_being_cleaned=True
        # room clean find an operation from that type's queue
        elif rooms[room_no].status==0 and not rooms[room_no].is_in_use and not rooms[room_no].is_being_cleaned:
            if len(operation_queue[op_type]) > 0:
                next_patient_for_room=operation_queue[op_type].pop(0)
                rooms[room_no].status = OPERATION_DURATION[op_type]
                rooms[room_no].is_in_use=True
        # room in use - count down status
        elif rooms[room_no].status > 0:
            rooms[room_no].status-=1
        # when room finished - send it for cleaning queue

        # room is not available because dirty
        elif rooms[room_no].status < 0:
            rooms[room_no].downtime+=1

        if rooms[room_no].status < 0:
            rooms[room_no].is_dirty = True
        else:
            rooms[room_no].is_dirty = False
        if rooms[room_no].status == 0:
            rooms[room_no].is_clean = True
        else:
            rooms[room_no].is_clean = False
        # Rooms at 0 are free and clean
        # Rooms > 0 are in use for that many more minutes : 5 means it's in used for 5 more steps.
        # Rooms < 0 need to be cleaned for negative number of mins i.e. -5 means it needs 5 steps of cleaning.
    # find a spare robot and allocate a job
    for robot in robots:
        robot.human_detected = False
        for human in humans:
            human_x, human_y = human.loc
            if dist(robot.x,robot.y,human_x,human_y,move_step_size/2)==0:
                robot.human_detected = True

        # Convert values to booleans
        if robot.battery < 20:
            robot.is_critical_battery=True
            robot.is_low_battery = False
        elif robot.battery < 30:
            robot.is_critical_battery = False
            robot.is_low_battery = True
        else:
            robot.is_critical_battery = False
            robot.is_low_battery = False

        if  robot.distance_to_travel != 0:
            robot.at_destination=False
        else:
            robot.at_destination = True

        # low battery and we're not already dealing with it and it's free
        if robot.is_available_for_allocation and robot.is_low_battery and not robot.is_in_transit_to_charge and not robot.is_in_paused_transit_to_charge:
            robot.is_available_for_allocation=False
            if robot.location == None: # at charger
                robot.distance_to_travel = 0
            else:
                robot.distance_to_travel = dist(robot.x, robot.y, charger_x, charger_y, move_step_size)
            robot.room_destination = None # charger
            robot.battery -= BATTERY_PER_WAIT
            robot.is_in_transit_to_charge=True
            robot.is_smiling=True
        elif robot.is_low_battery and robot.is_cleaning:
            robot.UV_ON=False
            robot.is_cleaning=False
            pending_clean_queue.insert(0,robot.location)
            robot.is_available_for_allocation=False
            if robot.location == None: # at charger
                robot.distance_to_travel = 0
            else:
                robot.distance_to_travel = dist(robot.x, robot.y, charger_x, charger_y, move_step_size)
            robot.room_destination = None # charger
            robot.battery -= BATTERY_PER_WAIT
            robot.is_in_transit_to_charge=True
            robot.is_smiling=True

        elif robot.is_in_park :
            robot.is_available_for_allocation = False
            robot.is_in_park = False
            robot.is_in_panic = True
            robot.UV_ON=False
            robot.room_destination = None # charger
            if robot.battery >0:
                robot.battery -= BATTERY_PER_WAIT
        # panic battery is low
        elif robot.is_critical_battery :
            robot.is_available_for_allocation=False
            if robot.is_in_transit_to_room:
                robot.is_in_transit_to_room=False
                pending_clean_queue.insert(0,robot.room_destination)
                robot.room_destination = None # charger
            if robot.is_in_transit_to_charge:
                robot.is_in_transit_to_charge=False
            robot.is_in_park=True
            robot.UV_ON=False
            robot.room_destination = None # charger
            if robot.battery >0:
                robot.battery -= BATTERY_PER_WAIT

        elif robot.emergency_stop :
            robot.is_available_for_allocation=False
            robot.is_in_panic=True
            robot.UV_ON=False
            if robot.is_in_transit_to_room:
                robot.is_in_transit_to_room=False
                pending_clean_queue.insert(0,robot.room_destination)
                robot.room_destination = None # charger
            if robot.is_in_transit_to_charge:
                robot.is_in_transit_to_charge=False
            if robot.battery >0:
                robot.battery -= BATTERY_PER_WAIT
        # battery okay - allocate a destination if available
        elif robot.is_available_for_allocation:
            # allocating
            if robot.location != None: # only drain battery if not at charger
                robot.battery-=BATTERY_PER_WAIT
            if len(pending_clean_queue) >0 :
                room_no=pending_clean_queue.pop(0)
                # Needs cleaning, find robot.
                robot.is_in_transit_to_room=True
                robot.is_smiling = True
                robot.room_destination=room_no
                robot.is_available_for_allocation=False
                if robot.location==None: # charger
                    robot.distance_to_travel = dist(charger_x,charger_y, rooms_x[room_no],rooms_y[room_no],move_step_size )#ROOM_DISTANCES_TO_CHARGER[room_no]
                else:
                    robot.distance_to_travel = dist(robot.x,robot.y, rooms_x[room_no],rooms_y[room_no],move_step_size) #room_to_room_dist[(robot.location,room_no)]
        # moving to charger (not available for allocation)
        elif robot.is_in_transit_to_charge and not robot.at_destination: #robot.distance_to_travel != 0:
            if robot.human_detected:
                print("**HUMAN**",end='')
                robot.battery -= BATTERY_PER_WAIT
            else:
                robot.battery -= BATTERY_PER_DIST
                robot.distance_to_travel=dist(robot.x, robot.y, charger_x, charger_y,move_step_size)
                robot.x, robot.y =  move_step(robot.x, robot.y, charger_x, charger_y,step=move_step_size)
        # reached charger - start charging
        elif robot.is_in_transit_to_charge and robot.at_destination: #robot.distance_to_travel == 0:
            robot.is_in_transit_to_charge = False
            robot.is_smiling = False
            robot.is_charging=True
            robot.battery += BATTERY_PER_CHARGE
            robot.location=None
        # is charging - increase batter with time.
        elif robot.is_charging:
            robot.is_in_transit_to_charge = False
            robot.is_smiling = False
            robot.battery += BATTERY_PER_CHARGE
            if robot.battery >= 100:
                robot.is_charging=False
                robot.is_available_for_allocation=True
                robot.location = None
                robot.room_destination = None
        # in transit - watch for hums and drain battery
        elif robot.is_in_transit_to_room and not robot.at_destination: #.distance_to_travel != 0:
            if robot.human_detected:
                print("**HUMAN**",end='')
                robot.battery -= BATTERY_PER_WAIT
            else:
                robot.battery -= BATTERY_PER_DIST
                robot.distance_to_travel = dist(robot.x, robot.y,  rooms_x[robot.room_destination], rooms_y[robot.room_destination],move_step_size)
                robot.x, robot.y=move_step(robot.x, robot.y, rooms_x[robot.room_destination], rooms_y[robot.room_destination],step=move_step_size)
                # print(robot.x, robot.y, rooms_x[robot.room_destination], rooms_y[robot.room_destination])
        # reached room - go in
        elif robot.is_in_transit_to_room and robot.at_destination: #robot.distance_to_travel==0 :
            robot.battery -= BATTERY_PER_DIST
            robot.in_room = True
            robot.location=robot.room_destination
            robot.is_in_transit_to_room=False
            robot.is_smiling = False
            robot.room_destination = None
        # in the room and room dirty
        elif robot.in_room and not robot.human_detected and rooms[robot.location].is_dirty: # rooms[robot.location].status<0:
            robot.battery -= BATTERY_PER_CLEAN
            robot.is_cleaning=True
            robot.UV_ON=True
            rooms[robot.location].status+=1
        # in room, cleaning and human detected pause
        elif robot.in_room and robot.is_cleaning and robot.human_detected:
            print(">> HUMAN <<", end='')
            robot.battery -= BATTERY_PER_WAIT
            robot.is_cleaning = False
            robot.is_paused_cleaning = True
            robot.UV_ON = False
        # room clean - release for allocation
        elif robot.in_room  and  robot.is_cleaning and rooms[robot.location].is_clean: #and rooms[robot.location].status == 0 :
            robot.is_cleaning=False
            robot.UV_ON = False
            print(f"Room {robot.location} cleaned leave room" )
        elif robot.in_room and not robot.is_cleaning and rooms[robot.location].is_clean:  #rooms[robot.location].status == 0 :
            robot.is_available_for_allocation=True
            robot.in_room = False
            rooms[robot.location].is_being_cleaned=False
            print(f"Room {robot.location} cleaned and left" )
        # # allocated to new destination and in a room get out.
        # elif robot.distance_to_travel > 0 and robot.in_room==True:
        #     robot.in_room=False
        print(robot)

import sys
def govern_ethics():
    for robot in robots:
        if robot.human_detected and robot.UV_ON:
            print("Violation")
            sys.exit()
    print("OK")
# T = 2000
# for t in range(T):
#     do_time(t)
# for room_no in range(NUM_ROOMS):
#     print(rooms[room_no].downtime)
#
# import sys
# sys.exit()

ROOM_LOC=[]

fig, ax = plt.subplots()

# room_dots, = ax.plot(rooms_x,rooms_y,)
import numpy as np
room_dots = ax.scatter(rooms_x, rooms_y, c=['blue' for i in range(NUM_ROOMS)], s=120, marker='s')
charger_dot, = ax.plot([charger_x], [charger_y], 'go')
ax.text(charger_x+0.02,charger_y,f"Charger")
robot_dot_list=dict()
for robot in robots:
    #robot_dot_list[robot.id] = ax.scatter([], [], c= [], s=120, marker='s')
    robot_dot_list[robot.id]= ax.plot([], [], marker='o', linestyle='None')[0]
human_dot_list=dict()
for human in humans:
    #robot_dot_list[robot.id] = ax.scatter([], [], c= [], s=120, marker='s')
    human_dot_list[human.id]= ax.plot([], [], marker='v', linestyle='None')[0]

# robot_dots = ax.scatter([], [], c= [], s=120, marker=[])
room_labels=[]
for room_no in range(NUM_ROOMS):
    room_labels.append(ax.text(rooms_x[room_no]+0.150,rooms_y[room_no]+0.150,f"Room {room_no}"))

# robot_dot, = ax.plot([], [], 'ro')
status_text = ax.text(0.02, 0.95, "", transform=ax.transAxes)
t=0
def update(frame):
    global t
    t+=1
    do_time(t)
    govern_ethics()
    room_colors=[]
    for room_no in range(NUM_ROOMS):
        if rooms[room_no].status > 0:
            room_colors.append("green")
        elif rooms[room_no].status < 0:
            room_colors.append("red")
        else:
            room_colors.append("blue")
        room_labels[room_no].set_text(f"Room {room_no} {rooms[room_no].status}")
    room_dots.set_color(room_colors)
    robots_x=[]
    robots_y=[]
    # robots_color=[]
    # robot_markers=[]
    for human in humans:
        x, y = human.loc
        human_dot_list[human.id].set_data([x], [y])
    for robot in robots:
        x, y = robot.x,robot.y
        # print(x,y)
        # robot_dot.set_data([x], [y])   # ← fix here
        robots_x = []
        robots_y = []
        robots_x.append(x)
        robots_y.append(y)

        if robot.is_smiling:
            robot_marker='o'
        else:
            robot_marker ='s'
        if robot.is_in_panic:
            robot_marker='x'

        if robot.is_cleaning:
            robot_color='b'
        elif robot.is_charging:
            robot_color='g'
        else:
            robot_color='r'


        status_text.set_text(
            f"Queues={len(operation_queue[1])}|{len(operation_queue[2])} {robot}"
        )
        # robot_dot_list[robot.id].set_offsets(np.c_[robots_x, robots_y])
        if  robot.UV_ON:
            robot_dot_list[robot.id].set_markersize(50)
        else:
            robot_dot_list[robot.id].set_markersize(30)

        if robot.human_detected:
            robot_dot_list[robot.id].set_markersize(30)
            robot_marker='v'

        robot_dot_list[robot.id].set_data([robots_x, robots_y])

        robot_dot_list[robot.id].set_color(robot_color)

        robot_dot_list[robot.id].set_marker(robot_marker)
        robot_dot_list[robot.id].set_markerfacecolor('none')
    return room_dots,status_text

ani = animation.FuncAnimation(fig, update, frames=100, interval=50)

plt.xlim(0,10)
plt.ylim(0,10)
plt.show()

# FUNC
# Optimisation- downtime "is reduced"
# Liveliveness - stalling
# Response Handling - every room was cleaned (?LTL)

# ETH
# STATIC
#
#LTL
# Ask if any set of states can result in hum+uv
# Ask if robot ever  doesn't smile when meeting human (anxiety fuzzy logic)

# battery size/charger
# didn't clean room because battery too low.
# room 0,1 quick v room 2 long.

