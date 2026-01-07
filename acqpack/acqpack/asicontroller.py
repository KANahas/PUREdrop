import time
import serial as s
import yaml

from ctypes import*
import sys


class New_AsiController:
    'Trying to connect to the C DLL'
    def __init__(self, config_file, logger, logger_name='AsiController', init_xy=True) -> None:

        self.logger = logger
        self.logger_name = logger_name

        self.logger.log(f'Initializing AsiController...')
        self.logger.log(f'[{self.logger_name}] Using config file {config_file}.')
        self.logger.savefile(config_file)

        # load config file
        self.logger.log(f'[{self.logger_name}] Loading config file.')
        f = open(config_file, 'r')
        self.config = yaml.load(f, Loader=yaml.SafeLoader)
        f.close()

        # give location of dll
        # TODO relative path?? Put this into config file??
        self.dll_path = "tango/TangoDLL_64bit_V1414/Tango_DLL.dll"
        self.logger.log(f'[{self.logger_name}] Using dll file {self.dll_path}.')

        # load library
        self.logger.log(f'[{self.logger_name}] Loading dll library.')
        self.m_Tango = cdll.LoadLibrary(self.dll_path)
        if self.m_Tango == 0:
            print("Error: failed to load DLL")
            self.logger.log(f'[{self.logger_name}] Failed to load dll.')
            sys.exit(0)

        # get communication id from DLL
        print("Get communication id from dll.")
        if self.m_Tango.LSX_CreateLSID == 0:
            self.logger.log(f'[{self.logger_name}] unexpected error. required DLL function CreateLSID() missing.')
            print("unexpected error. required DLL function CreateLSID() missing.")
            sys.exit(0)
        self.LSID = c_int()
        error = int   
        error = self.m_Tango.LSX_CreateLSID(byref(self.LSID))
        if error > 0:
            print("Error: " + str(error))
            self.logger.log("[{self.logger_name}] Error: " + str(error))
            sys.exit(0)
            
        # connect
        self.logger.log(f'[{self.logger_name}] Connecting to controller.')
        if self.m_Tango.LSX_ConnectSimple == 0:
            print("unexpected error. required DLL function ConnectSimple() missing")
            self.logger.log("[{self.logger_name}] unexpected error. required DLL function ConnectSimple() missing")
            sys.exit(0)
        porttext = c_char_p(self.config['serial']['port'].encode("utf-8"))
        error = self.m_Tango.LSX_ConnectSimple(self.LSID,1,porttext,self.config['serial']['baudrate'],0)
        if error > 0:
            self.logger.log("[{self.logger_name}] Error: LSX_ConnectSimple " + str(error))
            print("Error: LSX_ConnectSimple " + str(error))
            sys.exit(0)

        print("[TANGO init] Successfully connected.")
        self.logger.log(f'[{self.logger_name}] Successfully connected.')

        
        # calibrate all available axes (should be x and y)
        print('[TANGO init] Calibrating xy axes')
        self.logger.log(f'[{self.logger_name}] Calibrating xy axes')
        error = self.m_Tango.LSX_Calibrate(self.LSID)
        if error > 0:
            print("Error: Calibrate " + str(error))
            self.logger.log(f'[{self.logger_name}] Error: Calibrate ' + str(error))
        else:
            print("[TANGO init] Calibration done")
            self.logger.log(f'[{self.logger_name}] Calibration done')

        # Should this be done??
        print("[TANGO init] Measuring maximum position of xy axes.")
        self.logger.log(f'[{self.logger_name}] Measuring maximum position of xy axes.')
        error = self.m_Tango.LSX_RMeasure(self.LSID)
        if error > 0:
            print("Error: Measuring " + str(error))
            self.logger.log(f'[{self.logger_name}] "Error: Measuring ' + str(error))
        else:
            print("[TANGO init] Measuring done")
            self.logger.log(f'[{self.logger_name}] Measuring done')

        if init_xy:
            print(f'[TANGO init] init_xy not implemented yet, ignoring!')
            self.logger.log(f'[{self.logger_name}] init_xy not implemented yet, ignoring!')

        

    def halt(self):
        """
        Sends halt command to all axes, interrupting execution of their current commands.
        Note that many commands are sent in 'blocking' mode, so this function will likely not be called until the
        axes finish executing their current command.
        """
        self.logger.log(f'[{self.logger_name}] Halting all axes.')
        error = self.m_Tango.LSX_StopAxes(self.LSID)
        if error > 0:
            print(f'[TANGO halt] Error: {error}')
            self.logger.log(f'[{self.logger_name}] Error: {error}')
        print(f'[TANGO halt] Halted.')

    def exit(self):
        """
        Closes the connection.
        """
        self.logger.log(f'[{self.logger_name}] Closing connection.')
        error = self.m_Tango.LSX_Disconnect(self.LSID)
        if error > 0:
            print(f'[TANGO exit] Error: {error}')
            self.logger.log(f'[{self.logger_name}] Error: {error}')
        print(f'[TANGO exit] Connection closed.')

    # XY ----------------------------------------------
    def is_busy_xy(self):
        """
        Determines if XY-axes are moving.
        :return: (bool) true if axes are moving
        """

        raise NotImplementedError(f'Let me know if needed. Proved to be a bit complicated to implement. ')
        # x_string = c_char_p()
        # error = self.m_Tango.LSX_GetStatusAxis(self.LSID, byref(x_string), 16)
        # if error > 0:
        #     print("Error: [TANGO is_busy_xy] GetStatusAxis " + str(error))
        # print(str(x_string.value))
        # return True
    
    def halt_xy(self):
        """
        Halt xy axes
        """
        self.logger.log(f'[{self.logger_name}] Halting xy axes.')
        error = self.m_Tango.LSX_StopAxesEx(self.LSID,3)
        if error > 0:
            print(f'[TANGO halt_xy] Error: {error}')
            self.logger.log(f'[{self.logger_name}] Error: {error}')
        print(f'[TANGO halt_xy] Halted.')

    def zero_xy(self, x_dir=1, y_dir=1):
        """
        Sets the origin (zeros) at current location. If 'x_dir' and 'y_dir' are specified, will seek hardware limit
        (hall-effect stops) before zeroing. 'x_dir' and 'y_dir' represent whether to max (+1) or min (-1) each axis.

        :param x_dir: (int) -1 to min, +1 to max
        :param y_dir: (int) -1 to min, +1 to max
        :return: (str) device response
        """
        raise NotImplementedError("This is not implemented as to me it seems for this controller it doesn't make sense. Please let me know if you need it")

    def home_xy(self):
        """
        Moves XY-axes to origin (0,0)
        """
        self.logger.log(f'[{self.logger_name}] Move to (0,0) in xy.')
        return self.goto_xy(0, 0)
    
    def where_xy(self):
        """
        Retrieves XY-axes' current position relative to zero point (w/ linear encoder).

        :return: (tup) current X and Y position [mm]
        """
        self.logger.log(f'[{self.logger_name}] Retrieve xy position relative to zero point.')

        dx = c_double()
        dy = c_double()
        error = self.m_Tango.LSX_GetPosSingleAxis(self.LSID, 1, byref(dx))
        if error > 0:
            print(f'[TANGO where_xy] LSX_GetPosSingleAxis Error: {error}')
            self.logger.log(f'[{self.logger_name}] LSX_GetPosSingleAxis Error: {error}')
        error = self.m_Tango.LSX_GetPosSingleAxis(self.LSID, 2, byref(dy))
        if error > 0:
            print(f'[TANGO where_xy] LSX_GetPosSingleAxis Error: {error}')
            self.logger.log(f'[{self.logger_name}] LSX_GetPosSingleAxis Error: {error}')
        self.logger.log(f'[{self.logger_name}] x={dx.value}, y={dy.value}')
        return (dx.value, dy.value)
    
    def goto_xy(self, x_mm, y_mm):
        """
        Moves XY-axes absolutely to the specified position.

        Currently implemented such that the function returns after the moving is done!

        :param x_mm: (float) desired absolute X position [mm]
        :param y_mm: (float) desired absolute Y position [mm]
        :return: (str) device response 
        """
        self.logger.log(f'[{self.logger_name}] Move to x={x_mm}mm, y={y_mm}mm')

        error = self.m_Tango.LSX_MoveAbsSingleAxis(self.LSID, 1, c_double(x_mm), True)
        if error > 0:
            print(f'[TANGO goto_xy] LSX_MoveAbsSingleAxis Error: {error}')
            self.logger.log(f'[{self.logger_name}] LSX_MoveAbsSingleAxis Error: {error}')
        error = self.m_Tango.LSX_MoveAbsSingleAxis(self.LSID, 2, c_double(y_mm), True)
        if error > 0:
            print(f'[TANGO goto_xy] LSX_MoveAbsSingleAxis Error: {error}')
            self.logger.log(f'[{self.logger_name}] LSX_MoveAbsSingleAxis Error: {error}')

        return None
    
    def move_relative_xy(self, x_mm, y_mm):
        """
        Moves XY-axes relatively by the specified number of mm.

        Currently implemented such that the function returns after the moving is done!

        :param x_mm: (float) desired relative movement [mm]
        :param y_mm: (float) desired relative movement [mm]
        :return: (str) device response
        """
        self.logger.log(f'[{self.logger_name}] Move relative for x={x_mm}mm, y={y_mm}mm')

        error = self.m_Tango.LSX_MoveRelSingleAxis(self.LSID, 1, c_double(x_mm), True)
        if error > 0:
            print(f'[TANGO goto_xy] LSX_MoveAbsSingleAxis Error: {error}')
            self.logger.log(f'[{self.logger_name}] LSX_MoveAbsSingleAxis Error: {error}')
        error = self.m_Tango.LSX_MoveRelSingleAxis(self.LSID, 2, c_double(y_mm), True)
        if error > 0:
            print(f'[TANGO goto_xy] LSX_MoveAbsSingleAxis Error: {error}')
            self.logger.log(f'[{self.logger_name}] LSX_MoveAbsSingleAxis Error: {error}')

        return None
    
    def get_velocity(self):
        """
        Get velocity for all axes
        """
        self.logger.log(f'[{self.logger_name}] Get velocity for all axes.')
        dx = c_double()
        dy = c_double()
        dz = c_double()
        da = c_double()
        error = self.m_Tango.LSX_GetVel(self.LSID, byref(dx), byref(dy), byref(dz), byref(da))
        if error > 0:
            print(f'[TANGO get_velocity] LSX_GetVel Error: {error}')
            self.logger.log(f'[{self.logger_name}] LSX_GetVel Error: {error}')
        self.logger.log(f'[{self.logger_name}] velocities (x,y,z,a): ({dx},{dy},{dz},{da})')
        return (dx, dy, dz, da)
    
    def set_velocity(self, x_vel, y_vel):
        """
        Set velocity for x and y axes (z and a are not used so ignored)
        """
        self.logger.log(f'[{self.logger_name}] Set xy velocities to x={x_vel}, y={y_vel}')
        error = self.m_Tango.LSX_SetVel(self.LSID, c_double(x_vel), c_double(y_vel), c_double(0), c_double(0))
        if error > 0:
            print(f'[TANGO set_velocity] LSX_SetVel Error: {error}')
            self.logger.log(f'[{self.logger_name}] LSX_SetVel Error: {error}')
        return None


        





class AsiController:
    """
    Low-level wrapper for the Applied Scientific Instrumentation (ASI) Controller.
    Config file must be defined.

    This class can control both an XY-axis (MS-2000 stage) and a Z-axis (LS-50 linear stage).
    Since this hardware was taken from an Illumina GaIIx, it assumes the controller's serial command-set requires an OEM
    prefix of 1h (Z-axis) or 2h (XY-axes). Both stages have a linear-encoder.

    Functions for Z-axis control are defined, but it is not initialized. If it is desired to be used, then a homing
    procedure needs to be defined in initialize().
    """
    def __init__(self, config_file, init_xy=True):
        self.serial = s.Serial()  # placeholder
        
        f = open(config_file, 'r')
        self.config = yaml.load(f, Loader=yaml.FullLoader)
        f.close()
        
        self.config['conv'] = float(self.config['conv'])
        self.serial = s.Serial(**self.config['serial'])  # open serial connection
        self.cmd_xy('MC x+ y+')  # enable motor control for xy
        self.cmd_z('MC z+')      # enable motor control for z

        if init_xy:
            self.zero_xy(**self.config['init_dir'])

    def cmd(self, cmd_string):
        """
        Wraps core cmd_string with terminator specified in config, writes to serial, and returns response.

        :param cmd_string: (str) core command (w/o prefix nor terminator)
        :return: (str) device response
        """
        full_string = self.config['prefix'] + cmd_string + self.config['terminator']
        self.serial.write(full_string)
        time.sleep(0.05)
        response = self.serial.read(self.serial.inWaiting())
        return response
    
    def halt(self):
        """
        Sends halt command to both axes, interrupting execution of their current commands.
        Note that many commands are sent in 'blocking' mode, so this function will likely not be called until the
        axes finish executing their current command.

        In the future, it may be nice to implement a 'waiting' scheme.
        """
        self.halt_xy()
        self.halt_z()

    def exit(self):
        """
        Closes the device's serial connection.
        """
        self.serial.close()
    
    # XY ----------------------------------------------
    def cmd_xy(self, cmd_string, block=True):
        """
        Wraps core cmd_string with axes prefix (2h), passes to the cmd() function, and returns response.
        Optionally blocks programmatic flow (default=True).

        :param cmd_string: (str) core command (w/o prefix nor terminator)
        :param block: (bool) whether the command blocks program flow until action is complete
        :return: (str) device response
        """
        full_string = '2h ' + cmd_string
        response = self.cmd(full_string)
        
        while block and self.is_busy_xy():
            time.sleep(0.05)
            pass
         
        return response

    def is_busy_xy(self):
        """
        Sends status command, then parses response to determine if XY-axes are busy.

        :return: (bool) true if axes are executing a command
        """
        status = self.cmd('2h STATUS')[0]
        return status == 'B'

    def halt_xy(self):
        """
        Sends halt command to the XY-axes (stage), interrupting execution of its current command.
        Note that many commands are sent in 'blocking' mode, so this function will likely not be called until the
        axes finish executing their current command.

        In the future, it may be nice to implement a 'waiting' scheme.
        """
        self.cmd_xy('HALT', False)

    def zero_xy(self, x_dir=1, y_dir=1):
        """
        Sets the origin (zeros) at current location. If 'x_dir' and 'y_dir' are specified, will seek hardware limit
        (hall-effect stops) before zeroing. 'x_dir' and 'y_dir' represent whether to max (+1) or min (-1) each axis.

        :param x_dir: (int) -1 to min, +1 to max
        :param y_dir: (int) -1 to min, +1 to max
        :return: (str) device response
        """
        if (x_dir is not None) and (y_dir is not None):
            assert(abs(x_dir)==1 and abs(y_dir)==1)
            OVERLOAD = 1000.0
            OFFSET = 0.2
            print("Seeking limits x:{} y:{}".format(x_dir, y_dir))
            self.goto_xy(x_dir*OVERLOAD, y_dir*OVERLOAD)  # move to hall-effect limits
            self.move_relative_xy(-x_dir*OFFSET, -y_dir*OFFSET)  # nudge off switch limits

        return self.cmd_xy('HERE x y') # establish current XY position as 0,0 (zero)

    def home_xy(self):
        """
        Moves XY-axes to origin (0,0)
        """
        return self.goto_xy(0, 0)
    
    def where_xy(self):
        """
        Retrieves XY-axes' current position relative to zero point (w/ linear encoder).

        :return: (tup) current X and Y position [mm]
        """
        conv = self.config['conv']
        response = self.cmd_xy('WHERE X Y')
        if response.find('A'):
            pos_xy = response.split()[1:3]
            pos_x = round(float(pos_xy[0])/conv, 4)
            pos_y = round(float(pos_xy[1])/conv, 4)
            return pos_x, pos_y
        else:
            return None, None

    def goto_xy(self, x_mm, y_mm):
        """
        Moves XY-axes absolutely to the specified position.

        :param x_mm: (float) desired absolute X position [mm]
        :param y_mm: (float) desired absolute Y position [mm]
        :return: (str) device response
        """
        conv = self.config['conv']
        x_str = 'x=' + str(float(x_mm) * conv)
        y_str = 'y=' + str(float(y_mm) * conv)
        return self.cmd_xy(' '.join(['m', x_str, y_str]))
    
    def move_relative_xy(self, x_mm, y_mm):
        """
        Moves XY-axes relatively by the specified number of mm.

        :param x_mm: (float) desired relative movement [mm]
        :param y_mm: (float) desired relative movement [mm]
        :return: (str) device response
        """
        conv = self.config['conv']
        x_str = 'x=' + str(float(x_mm) * conv)
        y_str = 'y=' + str(float(y_mm) * conv)
        return self.cmd_xy(' '.join(['r', x_str, y_str]))

    # Z -----------------------------------------------
    def cmd_z(self, cmd_string, block=True):
        """
        Wraps core cmd_string with axis prefix (1h), passes to the cmd() function, and returns response.
        Optionally blocks programmatic flow (default=True).

        :param cmd_string: (str) core command (w/o prefix nor terminator)
        :param block: (bool) whether the command blocks program flow until action is complete
        :return: (str) device response
        """
        while block and self.is_busy_z():
            time.sleep(0.3)
        full_string = '1h ' + cmd_string
        return self.cmd(full_string)
    
    def is_busy_z(self):
        """
        Sends status command, then parses response to determine if Z-axis is busy.

        :return: (bool) true if axis is executing a command
        """
        status = self.cmd('1h STATUS')
        return status[0] == 'B'

    def halt_z(self):
        """
        Sends halt command to the Z-axis (linear motor), interrupting execution of its current command.
        Note that many commands are sent in 'blocking' mode, so this function will likely not be called until the
        axes finish executing their current command.

        In the future, it may be nice to implement a 'waiting' scheme.
        """
        self.cmd_z('HALT', False)

    def home_z(self):
        """
        Moves Z-axis to 0.
        """
        return self.goto_z(0)
        
    def where_z(self):
        """
        Retrieves Z-axis' current position relative to zero point (w/ linear encoder).

        :return: (tup) current Z position [mm]
        """
        response = self.cmd_z('WHERE Z')
        if response.find('A'):
            pos_z = float(response.split()[1:2])
            return pos_z
        else:
            return None    
    
    def goto_z(self, z_mm):
        """
        Moves Z-axis absolutely to the specified position.

        :param z_mm: (float) desired absolute Z position [mm]
        :return: (str) device response
        """
        conv = self.config['conv']
        z_str = 'z=' + str(float(z_mm) * conv)
        return self.cmd_z(' '.join(['m', z_str]))
    
    def move_relative_z(self, z_mm):
        """
        Moves Z-axis relatively by the specified number of mm.

        :param z_mm: (float) desired relative movement [mm]
        :return: (str) device response
        """
        conv = self.config['conv']
        z_str = 'z=' + str(float(z_mm) * conv)
        return self.cmd_z(' '.join(['r', z_str]))
