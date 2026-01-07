import time
import serial as s
import yaml

# imports for ps10
import ctypes
from ctypes import windll, c_double


class New_Motor:
    '''
    Low level wrapper for the ps10
    '''

    def __init__(self, config_file, logger, home=True) -> None:

        self.logger = logger

        self.logger.log(f'Initializing Motor...')
        self.logger.log(f'[Motor] Using config file {config_file}.')
        self.logger.savefile(config_file)

        self.logger.log(f'[Motor] Loading config file.')
        # load config file
        f = open(config_file, 'r')
        self.config = yaml.load(f, Loader=yaml.SafeLoader)
        f.close()

        # define serial port 
        nComPort = self.config['serial']['port']

        # give location of dll
        # TODO relative path?? Put this into config file??
        dll_path = "ps10/ps10.dll"

        # load library
        self.logger.log(f'[Motor] Loading dll library.')
        self.mydll = windll.LoadLibrary(dll_path)

        # open virtual serial interface (or serial interface via tcp/ip socket)
        self.logger.log(f'[Motor] Connecting to control unit.')
        if nComPort==0: # find first connected control unit
            result_str=self.check_result_string(self.mydll.PS10_SimpleConnect(1, b"")) # ANSI/Unicode !!
        elif nComPort==-1: # find the first connected control unit via tcp/ip socket (localhost, port=1200)
            result_str=self.check_result_string(self.mydll.PS10_SimpleConnect(1, b"net")) # ANSI/Unicode !!
        else: # connect control unit with defined COM port
            result_str=self.check_result_string(self.mydll.PS10_Connect(1, 0, nComPort, 9600,0,0,0,0))    
        
        # initialize axis
        self.logger.log(f'[Motor] Initialize z-axis.')
        self.nAxis = 1 # TODO put into config?? But should always be the same I guess
        self.logger.log(f'[Motor] z-axis = {self.nAxis}')
        result_str=self.check_result_string(self.mydll.PS10_MotorInit(1, self.nAxis))
        print(f'MotorInit: {result_str}')

        # set velocity
        result_str = self.check_result_string(self.set_velocity(self.config['velocity_limit']))

        # reset zero position
        if home:
            self.logger.log(f'[Motor] Reset z-axis Zero position.')
            self.home()

    def is_busy(self) -> bool:
        '''
        Checks if axis is moving. 
        # TODO check other occupations, not only moving??
        '''
        state = self.mydll.PS10_GetMoveState(1, self.nAxis)
        if state > 0:
            return True
        else: 
            return False

    def set_velocity(self, velocity) -> str:
        '''
        Sets motor velocity in usteps/sec. TODO UNITS?????

        :param velocity: (int) velocity
        :return: (str) device response
        '''
        # set velocity 
        if velocity > 0:
            self.logger.log(f'[Motor] Set velocity to {velocity} for z-axis')
            return self.check_result_string(self.mydll.PS10_SetPosF(1, self.nAxis, velocity))
        else:
            raise ValueError(f'Velocity must be >0! Velocity provided: {velocity}')

    def halt(self) -> None:
        '''
        Stop Movement
        '''
        self.logger.log(f'[Motor] Stop Movement of z-axis')
        return self.check_result_string(self.mydll.PS10_Stop(1, self.nAxis))
    
    def home(self) -> str:
        '''
        Reset Z position to reference position. 
        '''
        self.logger.log(f'[Motor] Go to z-axis reference position')
        return self.check_result_string(self.mydll.PS10_GoRef(1, self.nAxis, 1))

    def goto(self, mm, block=True) -> str:

        self.logger.log(f'[Motor] Move z-axis to absolute position {mm}mm.')

        # set target mode (1 -> absolute)
        result_str=self.check_result_string(self.mydll.PS10_SetTargetMode(1, self.nAxis, 1))

        # move command
        result_str = self.check_result_string(self.mydll.PS10_MoveEx(1, self.nAxis, c_double(mm), 1))

        # block until done
        if block:
            is_moving = self.is_busy()
            while is_moving:
                is_moving = self.is_busy()

        return result_str

    def move_relative(self, mm) -> str:
        '''
        Move relative to current position. Unit is [mm]. + or - for relative movement. 
        # TODO testing
        '''

        self.logger.log(f'[Motor] Move z-axis relative for {mm}mm.')

        # set target mode (0 -> relative)
        result_str=self.check_result_string(self.mydll.PS10_SetTargetMode(1, self.nAxis, 0))

        # move command
        result_str = self.check_result_string(self.mydll.PS10_MoveEx(1, self.nAxis, c_double(mm), 1))

        # block until done
        is_moving = self.is_busy()
        while is_moving:
            is_moving = self.is_busy()

        return result_str


    def where(self) -> tuple:
        '''
        Get position relative to home position (I believe this SDK also could provide absolute position, but to be consistent with the original class I only implement this)
        '''

        # set target mode (0 -> relative)
        result_str=self.mydll.PS10_SetTargetMode(1, self.nAxis, 0)

        # check position
        PS10_GetPositionEx=self.mydll.PS10_GetPositionEx
        PS10_GetPositionEx.restype = ctypes.c_double
        result_str=PS10_GetPositionEx(1, self.nAxis)

        return (float(result_str))

    def exit(self) -> None:
        '''
        Shut down motor, close interface
        '''
        self.logger.log(f'[Motor] Switch off.')
        result_str = self.check_result_string(self.mydll.PS10_MotorOff(1, self.nAxis))
        self.logger.log(f'[Motor] Disconnect.')
        return self.check_result_string(self.mydll.PS10_Disconnect(1))

    def check_result_string(self, result_string):
        '''
        check if result string is 0, if not log it.
        '''
        if result_string != 0:
            self.logger.log(f'[Motor] Unexpected result string: "{result_string}"') 
        return result_string



class Motor:
    """
    Low-level wrapper for the Lin Engineering (LE) CO-4118S-09.
    Config file must be defined.

    The LE CO-4118S-09 has an integrated controller with a documented serial command-set. It lacks an encoder, and so
    relies on dead-reckoning for position. It does have an optical sensor that allows it to get a positional fix (home).
    """
    def __init__(self, config_file, home=True):
        self.serial = s.Serial()  # placeholder

        f = open(config_file, 'r')
        self.config = yaml.load(f, Loader=yaml.SafeLoader)
        f.close()

        self.config['conv'] = float(self.config['conv'])

        self.serial = s.Serial(**self.config['serial'])  # open serial connection
        self.set_velocity(self.config['velocity_limit'])  # set velocity
        # TODO set moving current
        # TODO set holding current

        if home:
            self.home()

    def cmd(self, cmd_string, block=True):
        """
        Wraps core cmd_string with prefix and terminator specified in config, writes to serial, and returns response.
        Optionally blocks programmatic flow (default=True).

        :param cmd_string: (str) core command (w/o prefix nor terminator)
        :param block: (bool) whether the command blocks program flow until action is complete
        :return: (str) device response
        """
        full_string = self.config['prefix'] + cmd_string + self.config['terminator']
        self.serial.write(full_string)

        time.sleep(0.1)  # TODO: monitor for response?
        response = self.serial.read(self.serial.inWaiting()).decode('utf8', 'ignore')

        while block and self.is_busy():
            pass

        return response

    def is_busy(self):
        """
        Sends query command, then parses response to determine if motor is busy.

        :return: (bool) true if motor is executing a command
        """
        cmd_string = 'Q'
        time.sleep(0.05)
        response = self.cmd(cmd_string, False)
        return response.rfind('`') == -1

    def set_velocity(self, velocity):
        """
        Checks requested velocity against the velocity limit, then sets motor velocity in usteps/sec.

        :param velocity: (int) velocity
        :return: (str) device response
        """
        if velocity > self.config['velocity_limit']:
            velocity = self.config['velocity_limit']
            print('ERR: Desired velocity exceeds velocity_limit; velocity now set to velocity_limit')

        cmd_string = 'V{}R'.format(velocity)
        return self.cmd(cmd_string.encode('utf-8'))

    def halt(self):
        """
        Sends halt command to motor, which stops it from executing its current command.
        Note that many commands are sent in 'blocking' mode, so this function will likely not be called until the
        motor finishes executing its current command.

        In the future, it may be nice to implement a 'waiting' scheme.
        """
        cmd_string = 'T'
        self.cmd(cmd_string)

    def home(self):
        """
        Homes the motor until the optical sensor is triggered. Zero position is reset (motor gets positional fix).

        :return: (str) device response
        """
        cmd_string = 'Z{}R'.format(self.config['ustep_max'])
        return self.cmd(cmd_string)

    def goto(self, mm, block=True):
        """
        Moves motor absolutely to the specified position.

        :param mm: (float) desired absolute position [mm]
        :param block: (bool) whether the command blocks program flow until action is complete
        :return: (str) device response
        """
        ustep = int(self.config['conv'] * mm)

        if ustep > self.config['ustep_max']:
            ustep = self.config['ustep_max']
            print('ERR: Desired move to {} mm exceeds max of {} mm; moving to max instead'.format(mm, self.config[
                'ustep_max'] / self.config['conv']))
        if ustep < self.config['ustep_min']:
            ustep = self.config['ustep_min']
            print('ERR: Desired move to {} mm exceeds min of {} mm; moving to min instead'.format(mm, self.config[
                'ustep_min'] / self.config['conv']))

        cmd_string = 'A{}R'.format(ustep)

        return self.cmd(cmd_string, block)

    def move_relative(self, mm):
        """
        Moves motor relatively by the specified number of mm.

        :param mm: (float) desired relative movement [mm]
        :return: (str) device response
        """
        mm_current = self.where()[0]
        
        return self.goto(mm_current + mm)

    def where(self):
        """
        Retrieves motor's current position relative to zero-position (by dead reckoning).

        :return: (tup) current position of the motor [mm]
        """
        cmd_string = '?0'
        response = str(self.cmd(cmd_string))
        strt = response.rfind('`') + 1
        for end, c in enumerate(response[strt:]):
            if c not in str(list(range(0, 11))):
                break
        ustep = response[strt:strt + end]
        return round(float(ustep) / self.config['conv'], 4),  # tuple

    def exit(self):
        """
        Closes the device's serial connection.
        """
        self.serial.close()
