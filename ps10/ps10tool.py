# -*- coding: utf-8 -*-
"""
Created on Wed Aug 17 17:16:45 2016

@author: as
"""

#ps10tool This is a demo application for the PS 10 controller.
#   retval = ps10tool( COM_port, velocity, distance, params_export ) moves the attached axis...
#   function parameters 
#   parameter 1 - COM port
#   parameter 2 - positioning velocity in Hz
#   parameter 3 - distance for positioning in mm, distance=0 - reference run
#   parameter 4 - mode for data export: 0 - nothing to do, 1 - save, 2 - load

import ctypes
#from ctypes import *
from ctypes import windll, c_double
#from ctypes import windll, c_double, create_string_buffer
import sys

nComPort=5 
nAxis=1
nPosF=50000
dDistance=10.0
nExport=0

if (len(sys.argv) != 5):  
    print("ps10tool.py <COM port> <velocity> <distance> <params_export>")
    print("e.g. ps10tool.py 5 50000 10 0")
    sys.exit(0)
else:
    # set parameters *************
    nComPort=int(sys.argv[1])
    nPosF=int(sys.argv[2])
    dDistance=float(sys.argv[3])
    nExport=int(sys.argv[4])
    # ****************************

# load library
# give location of dll
mydll = windll.LoadLibrary("C:/Users/user/Documents/CLA/ps10/ps10.dll")

# open virtual serial interface (or serial interface via tcp/ip socket)
if nComPort==0: # find first connected control unit
    result1=mydll.PS10_SimpleConnect(1, b"") # ANSI/Unicode !!
elif nComPort==-1: # find the first connected control unit via tcp/ip socket (localhost, port=1200)
    result1=mydll.PS10_SimpleConnect(1, b"net") # ANSI/Unicode !!
else: # connect control unit with defined COM port
    result1=mydll.PS10_Connect(1, 0, nComPort, 9600,0,0,0,0)

# define slaves
#result1=mydll.PS10_SetCanOpenSlave(101, 1) # axis 2 (SlaveID=1)
#result1=mydll.PS10_SetCanOpenSlave(102, 2) # axis 3 (SlaveID=2)

# define constants for calculation Inc -> mm
#result1=mydll.PS10_SetStageAttributes(1, nAxis, c_double(1.0), 200, c_double(1.0))

"""
# get firmware version (string test)
str_data = create_string_buffer(20) # ANSI/Unicode !!
result1=mydll.PS10_GetBoardVersion(1, str_data, 20)
print( "Version=%s" %(str_data.value.decode("utf-8")) )
"""

# load param file
if nExport==2:
    result1=mydll.PS10_LoadTextFile(1, nAxis, b"ps10_params_export.txt") # ANSI/Unicode !!

# initialize axis
result1=mydll.PS10_MotorInit(1, nAxis)

# save param file
if nExport==1:
    result1=mydll.PS10_SaveTextFile(1, nAxis, b"ps10_params_export.txt") # ANSI/Unicode !!

# set target mode (0 - relative)
result1=mydll.PS10_SetTargetMode(1, nAxis, 0)

# set velocity 
if nPosF > 0:
    result1=mydll.PS10_SetPosF(1, nAxis, nPosF)

# check position
PS10_GetPositionEx=mydll.PS10_GetPositionEx
PS10_GetPositionEx.restype = ctypes.c_double
result2=PS10_GetPositionEx(1, nAxis)
print( "Position=%.3f" %(result2) )

# start positioning
if dDistance==0.0: # go home (to start position)
	result1=mydll.PS10_GoRef(1, nAxis, 4)
else: # move to target position (+ positive direction, - negative direction)
	result1=mydll.PS10_MoveEx(1, nAxis, c_double(dDistance), 1)

# check move state of the axis
print("Axis is moving...")
state = mydll.PS10_GetMoveState(1, nAxis)
while state > 0: 
    state = mydll.PS10_GetMoveState(1, nAxis)
    
print("Axis is in position.")

# check position
result2=PS10_GetPositionEx(1, nAxis)
print( "Position=%.3f" %(result2) )

# close interface
result1=mydll.PS10_Disconnect(1)
