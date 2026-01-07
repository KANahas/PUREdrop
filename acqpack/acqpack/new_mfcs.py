from . import utils as ut

import os
import time
import yaml
from ctypes import *
import ctypes

### NEW ##
from Fluigent.SDK import fgt_detect, fgt_init, fgt_close
from Fluigent.SDK import fgt_get_controllersInfo
from Fluigent.SDK import fgt_get_pressureChannelCount, fgt_get_pressureChannelsInfo
from Fluigent.SDK import fgt_get_sensorChannelCount, fgt_get_sensorChannelsInfo
from Fluigent.SDK import fgt_get_TtlChannelCount, fgt_get_TtlChannelsInfo
from Fluigent.SDK import fgt_get_valveChannelCount, fgt_get_valveChannelsInfo
from Fluigent.SDK import fgt_get_valveRange, fgt_get_valvePosition, fgt_set_valvePosition #KAN imported
from Fluigent.SDK import fgt_set_pressureResponse
from Fluigent.SDK.low_level import fgt_get_pressureStatus
from Fluigent.SDK import fgt_set_pressure, fgt_get_pressure
from Fluigent.SDK import fgt_get_valveChannelsInfo
from Fluigent.SDK import fgt_get_sensorValue, fgt_set_sensorRegulation
### END ###

DLL_FILENAME = 'mfcs_64.dll'  # dll packaged with acqpack (todo: 'package resources')
DLL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), DLL_FILENAME)

class New_Mfcs:
    """
    Class to control the MFCS-EZ. 
    Adaptd to work with fluigentSDK, added logger
    """
    def __init__(self, config_file, chanmap_path, logger):

        self.logger = logger

        self.logger.log(f'Initializing MFCS...')
        self.logger.log(f'[MFCS] Using config file {config_file}.')
        self.logger.savefile(config_file)
        self.logger.log(f'[MFCS] Using chanmap file {chanmap_path}.')
        self.logger.savefile(chanmap_path)

        self.logger.log(f'[MFCS] Loading config file.')
        with open(config_file) as file:
            self.config = yaml.full_load(file)
        	# Variable types definition 
        self.config['conversion_to_mbar'] = float(self.config['conversion_to_mbar'])  # ensure conversion factor is float
        self.dll = cdll.LoadLibrary(DLL_PATH)  # load dll (i.e. MFCS API)
        self.c_status = c_char()  # placeholder for status
        self.c_serial = c_ushort(0)  # placeholder for serial number
        
        # Checking which devices are connected. 
        self.logger.log(f'[MFCS] Searching connected devices.')
        self.SNs = self.detect()
        print(f'Found {len(self.SNs)} MFCS devices. Serial numbers: {self.SNs}')
        self.logger.log(f'[MFCS] Found {len(self.SNs)} MFCS devices. Serial numbers: {self.SNs}')
        self.all_SNs = self.config['serial_number']
        
        # connecting to all devices
        self.logger.log(f'[MFCS] Connecting to devices.')
        self.connect()

        self.logger.log(f'[MFCS] Loading chanmaps.')
        self.load_chanmap(chanmap_path)

        self.logger.log(f'[MFCS] MFCS initialization done.')

    def __del__(self):
        self.exit()
    
    
    def detect(self):
        """
        Detects connected MFCS devices; returns serial numbers of connected devices.
        
        :return: (list) detected MFCS serial numbers as ints
        """
        SNs, types = fgt_detect() # doesn't store this anywhere
        return SNs

    
    def connect(self):
        """
        Initializes the MFCS.
        Makes connection, checks status, and sets the PID alpha parameter of all channels to 2.
        """

        print(f'Connecting to MFCS device(s) {self.all_SNs}...')
        self.logger.log(f'[MFCS] Connecting to MFCS device(s) {self.all_SNs}...')
        try:
            if not isinstance(self.all_SNs, list):
                fgt_init([self.all_SNs])
            else:
                fgt_init(self.all_SNs)
            print('Total number of pressure channels: {}'.format(fgt_get_pressureChannelCount()))
            print('Total number of sensor channels: {}'.format(fgt_get_sensorChannelCount()))
            print('Total number of TTL channels: {}'.format(fgt_get_TtlChannelCount()))
            print('Total number of valve channels: {}'.format(fgt_get_valveChannelCount()))
            self.logger.log('[MFCS] Total number of pressure channels: {}'.format(fgt_get_pressureChannelCount()))
            self.logger.log('[MFCS] Total number of sensor channels: {}'.format(fgt_get_sensorChannelCount()))
            self.logger.log('[MFCS] Total number of TTL channels: {}'.format(fgt_get_TtlChannelCount()))
            self.logger.log('[MFCS] Total number of valve channels: {}'.format(fgt_get_valveChannelCount()))

            # Set pressure controller response (PID alpha) 
            pressureInfoArray = fgt_get_pressureChannelsInfo()
            for i, pressureInfo in enumerate(pressureInfoArray):
                print(f'Set pressure controller response for Channel {i} to {self.config["alpha_default"]}.')
                self.logger.log(f'Set pressure controller response for Channel {i} to {self.config["alpha_default"]}.')
                self.pid(i, self.config['alpha_default']) 
            print('Pressure units: {}'.format(self.config['pressure_unit']))
            self.logger.log('[MFCS] Pressure units: {}'.format(self.config['pressure_unit']))
            
            s, status = self.status()
            time.sleep(0.1)
            if s != 1:
                print('Warning: Connected to MFCS, but status not normal. Status {}: {}'.format(s, status))
                self.logger.log('[MFCS] Warning: Connected to MFCS, but status not normal. Status {}: {}'.format(s, status))

        except: 
            print('Error: Could not connect to MFCS')
            self.logger.log('[MFCS] Error: Could not connect to MFCS')
            self.exit()

    
    def status(self):
        """
        Gets and returns status of the MFCS.
        0: dropped. (old: 'MFCS is reset - press "Play"')
        1: 'normal'
        2: 'PressureStatus Error' (old: 'overpressure')
        3: dropped. (old: 'need to rearm')

        :return: (tup) status int [0-3], status string
        """        
        status_number = 1
        status_description = 'normal'
        for i in fgt_get_pressureChannelsInfo():
            # check pressure status (case 2)
            pressure_status = fgt_get_pressureStatus(i.indexID)
            if pressure_status[0] != 0:
                return 2, pressure_status[-1]
        return 1, 'normal'
    
    
    def pid(self, chan, a):
        """
        Sets alpha parameter of the PID controller for the given channel.
        Lower values of alpha (1-2) are typically more stable at lower pressures, but take slightly
        longer to equilibrate. 
        
        For some reason, the python kernel would crash when 'channel' and 'alpha' were used
        as keywords. C-types...

        :param chan: (int) channel [1-4] to set; 0 sets for all channels
        :param a: (int) desired alpha value for PID
        """
        fgt_set_pressureResponse(chan, a)
        self.logger.log(f'[MFCS] Alpha parameter of PID controller for channel {chan} set to {a}')


    
    def load_chanmap(self, chanmap_path):
        """
        Stores channel map.

        :param chanmap_path: (str) path to chanmap
        """
        self.chanmap = ut.read_delim_pd(chanmap_path)

        
    def exit(self):
        """
        Safely closes the MFCS. 
        First closes device connection, then releases the DLL.
        """
        fgt_close()
        self.logger.log(f'[MFCS] Deconnected from MFCS.')
    
    
    def set(self, lookup_cols, lookup_vals, pressure=0.0):
        """
        Sets pressure of specified channel.
        
        :param lookup_cols: (str | list) column(s) to search in chanmap
        :param lookup_vals: (val | list) value(s) to find in lookup_cols
        :param pressure: (float) desired pressure; units specified in config file
        """
        channel = ut.lookup(self.chanmap, lookup_cols, lookup_vals)[['channel']].iloc[0]
        #channel = int(channel)
        channel = int(channel.iloc[0])
        mbar = pressure * self.config['conversion_to_mbar']
        fgt_set_pressure(channel, mbar)
        self.logger.log(f'[MFCS] Pressure in channel {channel} ({lookup_cols}={lookup_vals}) set to {mbar}.')

    
    def read(self, lookup_cols, lookup_vals):
        """
        Reads current pressure of the channel.
        
        :param lookup_cols: (str | list) column(s) to search in chanmap
        :param lookup_vals: (val | list) value(s) to find in lookup_cols
        :return: (float) current pressure; units specified in config file
        """
        channel = ut.lookup(self.chanmap, lookup_cols, lookup_vals)[['channel']].iloc[0]
        #channel = int(channel)
        channel = int(channel.iloc[0])
        mbar = fgt_get_pressure(channel)
        return mbar/self.config['conversion_to_mbar']
    
    # switching
    def get_switch_options(self):
        """
        Informs which switch (valve) options are available 
        """
        print(fgt_get_valveChannelsInfo())

    def set_switch_position(self, switch_index, position):
        """
        Set position of switch (valve) at index <switch_index> to <position>
        """
        fgt_set_valvePosition(switch_index, position, 0, 1)
        self.logger.log(f'[MFCS] Position of switch {switch_index} set to {position}.')

    def get_switch_position(self, switch_index):
        """
        Returns current position of switch (valve) at index <switch_index>
        """
        return fgt_get_valvePosition(switch_index)
    

    # sensing
    def get_sensor_options(self):
        """
        Informs whitch sensor options are available
        """
        print(fgt_get_sensorChannelsInfo())

    def get_sensor_Value(self, sensor_index):
        """
        Returns current value of sensor at index <sensor_index>
        """
        return fgt_get_sensorValue(sensor_index)
    
    def set_sensor_regulation(self, sensor_index, pressure_index, setpoint):
        """
        Make a closed-loop regulation between sensor and pressure unit. 
        The value of the sensor at <sensor_index> is controlled by changing 
        the pressure of pressure unit at <pressure_index>. The target value
        is <setpoint>. 
        """

        fgt_set_sensorRegulation(sensor_index, pressure_index, setpoint)
        self.logger.log(f'[MFCS] Started closed-loop regulation. Sensor: {sensor_index}, Pressure unit: {pressure_index}, Target Value: {setpoint}')


    def set_sensor_regulation_lookup(self, sensor_index, lookup_cols, lookup_vals, setpoint):
        """
        Make a closed-loop regulation between sensor and pressure unit. 
        The value of the sensor at <sensor_index> is controlled by changing 
        the pressure of pressure unit at <lookup_vals> in <lookup_cols> (e.g., "name" and "IAsampler"). 
        The target value         is <setpoint>. 
        """
        channel = ut.lookup(self.chanmap, lookup_cols, lookup_vals)[['channel']].iloc[0]
        channel = int(channel.iloc[0])

        fgt_set_sensorRegulation(sensor_index, channel, setpoint)
        self.logger.log(f'[MFCS] Started closed-loop regulation. Sensor: {sensor_index}, Pressure unit: {channel}, Target Value: {setpoint}')

    

    
