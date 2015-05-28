#from multiprocessing import Process, Value, Array
import thread
import numpy as np
import time
import serial

class Driver(object):
    
    running = False
    
    def __new__(self, devname):
                
        self.devname = devname
        
        drivers = { 'nul' : FakeDriver,
                    'ser'  : SerialDriver } 
        try:
            return drivers[devname[:3]](devname)
            #self.__class__ = child_dict[ devname[:3] ]
            #self.__init__(devname)
        except KeyError:
            raise ValueError('No laser driver available for device '+devname)

class AbstractDriver(object):
    
    def __new__(cls, *args, **kwargs):
        # make class a singleton
        if not cls._instance:
            cls._instance = super(AbstractDriver, cls).__new__(cls, *args, **kwargs)
            #cls.max_positions = 10
            #cls._voltage_array = Array('d', [0]*cls.max_positions)
            #cls._num_voltages = Value('i', 0)
            #cls._cooling_time = Value('i', 100)
            #cls.devname = devname
        return cls._instance
    
    def __init__(self, devname):
        self.devname = devname
        self.clear_all()
    
    def set_solution(self, solution):
        print 'Laser pointing : set solution ', solution
        self.solution = solution
    
    def set_cooling_time(self, cooling_time):
        self._cooling_time = cooling_time
    
    def clear_all(self):
        self.regions = []
        self.positions = []
        self._update_voltage_list()
        
    def clear_last(self):
        self.regions = self.regions[0:-1]
        self.positions = self.positions[0:-1]
        self._update_voltage_list()
    
    def add_position(self, region, position):
        print 'Adding position', position, 'in region', region
        self.regions.append(region)
        self.positions.append(position)
        self._update_voltage_list()

    def _update_voltage_list(self):
        "After adding more positions, this will update a list calculating the actual voltages"       
        self._voltages = []
        for region, position in zip(self.regions, self.positions):
            self._voltages.append( self.solution.laser_voltage_at(region, position) )
        
        #self._num_voltages.value = len(self.positions)
        #for i in range(self.max_positions):
        #    try:
        #        self._voltage_array[i] = self._voltages[i]
        #    except IndexError:
        #        self._voltage_array[i] = 0.0
        
        print 'After update : Voltages : ', self._voltages
    
    def _set_voltage(voltage):
        print 'Driver setting voltage ', voltage

class FakeDriver(AbstractDriver):
    _instance = None
    p = None # Driver process
    
    def __init__(self, devname):
        super(FakeDriver, self).__init__(devname)

        self.terminate = False
        if self.p is None:
            self.p = thread.start_new_thread(self._cycle, () )
            Driver.running = True
    
    def _cycle(self):
        print 'Fake laser pointing driver thread started. Voltages = ', self._voltages

        while not self.terminate:
            for voltage in self._voltages:
                print 'Fake laser driver would write = v'+str(voltage)
                time.sleep(self._cooling_time/1000.0)

        print 'Fake laser pointing driver thread finished'

    def stop(self):
        print 'Terminating fake driver update thread'
        self.terminate = True
        Driver.running = False

class SerialDriver(AbstractDriver):
    _instance = None    
    p = None # Driver process
    serial_device = None
    
    def __init__(self, devname):
        super(SerialDriver, self).__init__(devname)
        
        print 'Serial Laser driver initialized'
        if self.serial_device is None:
            self.serial_device = serial.Serial(devname[4:])
        
        if self.p is None:
            self.p = Process(target=self._cycle)
            print 'starting laser driver process from class', str(self)
            self.p.start()
    
    def _cycle(self):
        while True:
            for i,voltage in enumerate(self._voltage_array):
                if i > self._num_voltages.value-1:
                    continue
                self.serial_device.write('s'+str(voltage)+'\n')
                time.sleep(self._cooling_time.value/1000.0)
    
    def __del__(self):
        self.stop()
    
    def stop(self):
        self.serial_device.close()
        print 'terminating', self.p.pid, 'from class', str(self)
        self.p.terminate()
        self.p = None
        Driver.running = False
