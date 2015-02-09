from ctypes import *

class DigitalSwitch(object):
    def __init__(self, name, driver_name, default=False, update_on_init=False):
        self.name = name
        self.default = default
        self.driver = SwitchDriver(driver_name)
        
    def change_to(self, value):
        """ Toggle the switch """
        print 'Changing', self.name, 'switch to', value
        self.driver.change_to(value)
        
        
class SwitchDriver(object):
    
    def __init__(self, driver_name):
        self.devname = driver_name[:3]
        self.ch = driver_name[5:]
        
        child_dict = {  'Dev' : NiDriver, 
                        'nul' : FakeDriver
                     }
        try:
            self.__class__ = child_dict[ self.devname ]
            self.__init__()
        except KeyError:
            raise ValueError('No driver available for device '+devname)
        
class FakeDriver(SwitchDriver):
    def change_to(self, value):
        print 'Fake driver called to change switch'
     

class NiDriver(SwitchDriver):
    def __init__(self):
        pass
    
    try:
        daqmx = windll.nicaiu
        TaskHandle = c_void_p
        CreateTask = daqmx.DAQmxCreateTask
        StartTask = daqmx.DAQmxStartTask
        StopTask = daqmx.DAQmxStopTask
        ClearTask = daqmx.DAQmxClearTask
        ResetDevice = daqmx.DAQmxResetDevice
        CreateDOChan = daqmx.DAQmxCreateDOChan
        WriteDigitalU8 = daqmx.DAQmxWriteDigitalU8
        WaitUntilTaskDone = daqmx.DAQmxWaitUntilTaskDone

        #From NIDAQmx.h
        DAQmx_Val_ChanForAllLines = 1
        DAQmx_Val_GroupByScanNumber = 1
        DAQmx_Val_WaitInfinitely = c_double(-1.0)

        update_data_type = c_uint8 * 50  # declare space for a ctypes array of 50 unsigned ints for update data
        init_data = update_data_type( *([0]*50) )
        
        hDAC = TaskHandle(0)
        samples_written = c_int32(0)
        timeout = c_double( 10.0 )

    except NameError:
        print ("Unable to load windows dll for NI driver.")   

    def change_to(self, value):
        pass
