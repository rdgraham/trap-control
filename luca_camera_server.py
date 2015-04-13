import rpyc
import numpy as np
import cStringIO as StringIO
import time
from ctypes import *
from ctypes.wintypes import HANDLE
import win32event

from threading import Thread
from rpyc.utils.server import ThreadedServer

class CameraService(rpyc.Service):       

    all_roi = {}
    image = None
    luca = None
    scale_min = None
    scale_max = None

    @classmethod
    def backend_init(cls):
        cls.image = np.zeros((1000, 1000))
        print 'Starting Andor LUCA camera driver ...'
        cls.luca = Luca()
        print '[Initilized OK]'
        cls.luca.start_acquiring(callback = CameraService.got_image)
        print '[Acquiring OK]'
    
    @classmethod
    def backend_terminate(cls):
        print 'Terminating Andor LUCA camera driver ...'
        cls.luca.shutdown()
        print '[OK]'
    
    @classmethod
    def got_image(cls, image_data):
        print 'Got image'
        cls.image = image_data.astype('f')

    def exposed_autoscale(self):
        self.autoscale()
        print 'Client requested autoscale. Now max', self.scale_max, 'min', self.scale_min
        
    def autoscale(self):
        try:
            self.scale_min = np.min(self.image)
            self.scale_max = np.max(self.image)        
        except TypeError:
            self.scale_min = 0
            self.scale_max = 100
        
    def exposed_setbg(self):
        pass
    
    def exposed_scaled_image(self):
        if self.scale_min is None or self.scale_max is None:
            # Auto scale never set, determine automatically
            self.autoscale()
        
        image_to_send = (256* (self.image-self.scale_min)/(self.scale_max-self.scale_min)).astype(np.uint8)
        
        # need to make a copy in some way on the server side otherwise
        # it will be really slow as synchronizing object across socket
        # connection. This seems to be the fastest way. Could add compression
        # if network bandwidth an issue.        
        temp = StringIO.StringIO()
        np.save(temp, image_to_send)
        binary = temp.getvalue()
        temp.close()
        
        #print 'Original image : mean', np.average(self.image), 'shape', np.shape(self.image)
        print 'Returning scaled image to client ', np.min(image_to_send), np.max(image_to_send), np.min(self.image), np.max(self.image)
        
        return binary
    
    def exposed_about(self):
        print "Client requested information about this service"
        return "Basic windows server for Andor LUCA EMCCD"
    
    def exposed_image_stats(self):
        return None
   
    def circular_mask(self, index, radius, array):
        a,b = index
        nx,ny = array.shape
        y,x = np.ogrid[-a:nx-a,-b:ny-b]
        mask = x*x + y*y <= radius*radius
        return mask
        
    def exposed_roi_stats(self, roi_name):
        image = (256*np.random.rand(1000, 1000)).astype(np.uint8)
        
        roi = self.all_roi[roi_name]
        mask = self.circular_mask( (roi[0], roi[1]), roi[2], image )
        mean = np.sum( image * mask ) / np.sum(mask)
        return {'mean' : mean}
        
    #return(sum(array[mask]))
    def exposed_clear_roi(self):
        self.all_roi = {}
    
    def exposed_delete_roi(self, name):
        try:
            del self.all_roi[name]
        except KeyError:
            pass
        
    def exposed_set_roi(self, roi_name, x, y, r):
        print 'Adding or changing roi named : ', roi_name
        self.all_roi[roi_name] = (x,y,r)
    
    def exposed_roi_list(self):
        return self.all_roi.values()
    
    def exposed_roi_names(self):
        return self.all_roi.keys()
    
    def exposed_get_roi(self,name):
        return self.all_roi[name]
    
    def exposed_camera_setting(self, setting, value):
        """Change a camera setting to given value. Automatically stops the acqusition if required.
           'frame_rate' and 'em_gain' currently supported.
        """
        
        was_acquiring = self.luca.acquiring
        if self.luca.acquiring:
            print 'Client requested change of ', setting, ' to ', value, ' : must stop acquisition'
            self.luca.stop_acquiring(join=True)

        if setting == 'frame_rate' and value == 0.0 : 
            self.luca.stop_acquiring(join=True)
            was_acquiring = False
        if setting == 'frame_rate' and value > 0.0 :
            self.luca.set_exposure(1.0/value)
            was_acquiring = True
        
        if setting == 'em_gain' : self.luca.set_gain(value)
        
        if was_acquiring : 
            print 'Restarted acquisition'
            self.luca.start_acquiring()
    
class Luca( object ):
    
    atmcd = windll.atmcd32d
    
    AC_ACQMODE_SINGLESCAN = 1
    AC_ACQMODE_RUNTILABORT = 5    
    AC_READMODE_IMAGE = 4
    AC_TRIGGERMODE_INTERNAL = 0
    AC_TRIGGERMODE_EXTERNAL = 1
    
    image = None
    
    def __init__(self):

        self.acquiring = False
        self.event = None
        
        he = self._handle_error
        
        self.bin_size = 1
        self.exposure_time = 1
        self.callback = None
    
        try:
            camera_handle, ncameras = c_long( 0 ), c_long( 0 )
            he( self.atmcd.GetAvailableCameras( byref(ncameras) ), "GetAvailableCameras" )
            print "Andor SDK has {0} camera(s) available, choosing first available".format( ncameras.value )
            
            for i in range( ncameras.value ):
                he( self.atmcd.GetCameraHandle( c_long(i), byref(camera_handle) ), "GetCameraHandle" )
                he( self.atmcd.SetCurrentCamera( camera_handle ), "SetCurrentCamera" )
                self.handle = camera_handle
                
                try:
                    print "Initializing Andor software, this will take a few moments"
                    he( self.atmcd.Initialize( c_char_p( "" ) ), "Initialize" )
            
                    serial = c_int( 0 )
                    he( self.atmcd.GetCameraSerialNumber( byref(serial) ), "GetCameraSerialNumber" )
                    print "Initialized camera {0} with serial {1}".format( i, serial.value )
                    break
                    
                except ValueError:
                    print "Failed to initialize camera {0}.".format( i )
                    self.atmcd.ShutDown()

            he( self.atmcd.SetAcquisitionMode( self.AC_ACQMODE_RUNTILABORT ), "SetAcquisitionMode" )
            he( self.atmcd.SetReadMode( self.AC_READMODE_IMAGE ), "SetReadMode" )
            he( self.atmcd.SetFrameTransferMode( c_long(1) ), "SetFrameTransferMode" )
            he( self.atmcd.SetTriggerMode( self.AC_TRIGGERMODE_INTERNAL ), "SetTriggerMode" )
            he( self.atmcd.SetShutter( c_int(0), c_int(0), c_int(0), c_int(0) ), "SetShutter" )
            
            self.set_image_and_binning()            
            
            num_vs_speeds = c_long( 0 )
            he( self.atmcd.SetHSSpeed( c_long(0), c_long(0) ), "SetHSSpeed" )
            he( self.atmcd.GetNumberVSSpeeds( byref( num_vs_speeds ) ), "GetNumberVSSpeeds" )
            he( self.atmcd.SetVSSpeed( c_long( num_vs_speeds.value-1 ) ), "SetVSSpeed" )
            
            he( self.atmcd.SetKineticCycleTime( c_float(0.) ), "SetKineticCycleTime" )
            self.set_gain(1)
            self.set_exposure(1)
            
        except ValueError as exc:
            print exc
                        
    def set_gain( self, gain ):
        if self.acquiring:
            return False
            
        he = self._handle_error
        try:
            #print 'Trying to set EMCCDGain to', gain
            he( self.atmcd.SetEMCCDGain( c_int(int(gain)) ), "SetEMCCDGain" )
        except ValueError as exc:
            print 'Error setting gain : ', exc
            return False
        return True
    
    def set_exposure( self, exposure_time ):
        if self.acquiring: 
            return False
            
        he = self._handle_error
        try:
            he( self.atmcd.SetExposureTime( c_float(exposure_time) ), "SetExposureTime" )
        except ValueError as exc:
            print exc
            return False
        
        self.exposure_time = exposure_time
        
        return True
        
    def set_image_and_binning( self ):
        if self.acquiring: 
            return False
            
        he = self._handle_error
        try:
            width, height = c_int(0), c_int(0)
            he( self.atmcd.GetDetector( byref(width), byref(height) ), "GetDetector" )
            
            bin = self.bin_size
            width, height = c_int( (width.value / bin)*bin ), c_int( (height.value / bin)*bin )
            he( self.atmcd.SetImage( c_long(bin), c_long(bin), c_long(1), width, c_long(1), height ), "SetImage" )
            
            self.width, self.height = width.value / bin, height.value / bin
            print width.value, height.value, self.width, self.height
            self.image = np.zeros( (self.height, self.width), np.uint16 )
        except ValueError as exc:
            print exc
            return False

        return True
        
    def _acquire( self, callback ):
        he = self._handle_error
        
        try:
            self.acquiring = True
            self.event = win32event.CreateEvent( None, 0, 0, None )
            
            he( self.atmcd.StartAcquisition(), "StartAcquisition" )
            he( self.atmcd.SetDriverEvent( self.event.handle ), "SetDriverEvent" )
            
            npixels = self.width*self.height
            image = self.image.ctypes.data_as( POINTER(c_uint16) )
            while self.acquiring:
                win32event.WaitForSingleObject( self.event, 5000 )
                he( self.atmcd.GetMostRecentImage16( image, c_long(npixels) ), "GetMostRecentImage16" )
                if callback:    callback( self.image )
                
            he( self.atmcd.AbortAcquisition(), "AbortAcquisition" )
            
        except ValueError as exc:
            self.acquiring = False
            print exc
            
        finally:
            self.atmcd.SetDriverEvent( None )
            self.event.Close()
            self.event = None
            
    def start_acquiring( self, callback = None ):
        if callback is None:
            callback = self.callback
        else:
            self.callback = callback
        
        if self.acquiring or self.event:
            print 'Not able to start acqusition thread'
            return
        
        self.thread = Thread(target=self._acquire, args=(callback,))
        self.thread.start()
        print 'Started acqusition thread'
            
    def stop_acquiring( self, join = False ):
        self.acquiring = False
        if join:
            self.thread.join()
        time.sleep(self.exposure_time)
        print 'Stopped acqusition'
        
    def shutdown( self ):
        self.acquiring = False
        he = self._handle_error
        try:                
            print "Shutting down Andor."
            he( self.atmcd.FreeInternalMemory(), "FreeInternalMemory" )
            he( self.atmcd.ShutDown(), "ShutDown" )
            
        except ValueError as exc:
            print "Error shutting down"
            print exc
        
    def _handle_error( self, err_code, fn_name = "<unknown function>" ):
        if err_code != 20002:
            msg = "Error in Andor SDK: {0} returned {1}".format( fn_name, err_code )
            raise ValueError( msg )
            
        
if __name__ == "__main__":
    port = 18861
    
    print 'Starting Andor LUCA camera rpyc service on port ' + str(port)
    
    CameraService.backend_init()
    t = ThreadedServer( CameraService, port = port, protocol_config = {"allow_public_attrs" : True, \
                                                                       "allow_pickle" : True})
    t.start()
    CameraService.backend_terminate()
