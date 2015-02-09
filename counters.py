from multiprocessing import Process, Value, Array
from random import random, randint, gauss
import numpy as np
import time
import ctypes

class Driver(object):
    
    running = False
        
    def __new__(self, name):

        drivers = { 'nul' : FakeDriver,
                    'ni'  : FakeDriver
                } 
        try:
            return drivers[name]()
        except KeyError:
            raise ValueError('No driver available for device '+devname)

class Buffer(object):
    def __init__(self, size=1000, data_type='int32'):
        self.data_type = data_type
        self.head = Value('i', 0)
        self.ring_buffer = Array(data_type[0], range(size)) 
        self.size = size
        for i in range(size): self.ring_buffer[i] = 0 #probably really slow but not done often

    def get_head_value(self):
        return self.ring_buffer[self.head.value]
    
    def get_buffer(self):    
        buf = np.frombuffer(self.ring_buffer.get_obj(), dtype=self.data_type)
        return np.concatenate( (buf[self.head.value+1 :] , buf[0:self.head.value]) )

    def push(self, v):
        self.head.value = self.head.value+1
        if self.head.value == self.size: self.head.value = 0
        self.ring_buffer[self.head.value] = v #randint(0,10)

class FakeDriver(object):
    _instance = None
    p = None
    def __new__(cls, *args, **kwargs):
        # make class a singelton
        if not cls._instance:
            cls._instance = super(FakeDriver, cls).__new__(
                                cls, *args, **kwargs)
        return cls._instance
        
    def __init__(self):
        # start process generating numbers which go in a ring buffer
        if self.p is None:
            self.count_buffer = Buffer()
            self.moving_avg_buffer = Buffer(data_type='float32')
            self.shelved = False
            self.p = Process(target=self._acquire)
            print 'starting counter process from class', str(self)
            self.p.start()
            Driver.running = True

    def get_counts(self):
        return self.count_buffer.get_head_value()
    
    def get_moving_avg_buffer(self):
        return self.moving_avg_buffer.get_buffer()
    
    def get_buffer(self):
        return self.count_buffer.get_buffer()

        
    def stop(self):
        print 'terminating', self.p.pid, 'from class', str(self)
        self.p.terminate()
        self.p = None
        Driver.running = False
    
    def _acquire(self):
        while True:
            if random() < .01 : self.shelved = not self.shelved
            
            r = int(gauss(10,3))
            if self.shelved: r = r + 25
            time.sleep(.02)
            self.count_buffer.push( r )
            ma = np.average(self.count_buffer.get_buffer()[-100:-1] )
            self.moving_avg_buffer.push( ma )


