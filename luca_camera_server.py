import rpyc
import numpy as np
import cStringIO as StringIO

from ctypes import *
from ctypes.wintypes import HANDLE
import win32event

from threading import Thread
from rpyc.utils.server import ThreadedServer

class CameraService(rpyc.Service):       

    all_roi = {}
    image = None
    luca = None

    @classmethod
    def backend_init(cls):
        print 'Starting Andor LUCA camera driver ...'
        self.luca = Luca()
        self.luca.start_acquiring(callback = CameraService().got_image)
        print '[OK]'
    
    @classmethod
    def backend_terminate(cls):
        print 'Terminating Andor LUCA camera driver ...'
        self.luca.shutdown()
        print '[OK]'

    def got_image(self, image_data):
        image = image_data.astype('f')

    def exposed_terminate(self):
        self.luca.stop_acquiring()
        self.luca.shutdown()

    def exposed_autoscale(self):
        pass
        
    def exposed_setbg(self):
        pass
    
    def exposed_binary_image(self):
        print 'Returning camera image'
        
        image_to_send = (256*self.image).astype(np.uint8)
        
        # need to make a copy in some way on the server side otherwise
        # it will be really slow as synchronizing object across socket
        # connection. This seems to be the fastest way. Could add compression
        # if network bandwidth an issue.        
        temp = StringIO.StringIO()
        np.save(temp, image_to_send)
        binary = temp.getvalue()
        temp.close()
        return binary
    
    def exposed_about(self):
        print "Client requested information about this service"
        return "Basic windows server for Andor LUCA EMCCD"
    
    def exposed_image_stats(self):
        return None
    
    def circular_mask(index,radius,array):
        a,b = index
        nx,ny = array.shape
        y,x = np.ogrid[-a:nx-a,-b:ny-b]
        mask = x*x + y*y <= radius*radius
        return mask
    
    def exposed_roi_stats(self, roi_name):
        image = (256*np.random.rand(1000, 1000)).astype(np.uint8)
        
        roi = self.all_roi[roi_name]
        mean = np.mean( image * circular_mask( (roi[0], roi[1]), roi[2], image ) )
        return {'mean' : mean}
        
    #return(sum(array[mask]))
    def exposed_clear_roi(self):
        self.all_roi = {}
        
    def exposed_set_roi(self, roi_name, x, y, r):
        print 'Adding or changing roi named : ', roi_name
        self.all_roi[roi_name] = (x,y,r)
    
    def exposed_roi_list(self):
        return self.all_roi.values()

    def exposed_set_gain(self, gain):
        self.luca.set_gain(gain)
        
    def exposed_set_exposure(self, exposure):
        self.luca.set_exposure(exposure)

class Luca( object ):
    
    atmcd = windll.atmcd32d
    
    AC_ACQMODE_SINGLESCAN = 1
    AC_ACQMODE_RUNTILABORT = 5    
    AC_READMODE_IMAGE = 4
    AC_TRIGGERMODE_INTERNAL = 0
    AC_TRIGGERMODE_EXTERNAL = 1
    
    image = None
    
    def __init__(self):

        he = self._handle_error
        
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
            self.set_gain_and_exposure()
        except ValueError as exc:
            print exc
            
        self.acquiring = False
        self.event = None
        
        self.exposure_time = 0.2
        self.EMCCD_gain = 1
        self.bin_size = 1
                        
    def set_gain( self, gain ):
        self.gain = gain
        
        if self.acquiring: 
            return False
            
        he = self._handle_error
        try:
            he( self.atmcd.SetEMCCDGain( c_long(gain) ), "SetEMCCDGain" )
        except ValueError as exc:
            print exc
            return False
        return True
    
    def set_exposure( self, exposure_time ):
        self.exposure_time = exposure_time
        
        if self.acquiring: 
            return False
            
        he = self._handle_error
        try:
            he( self.atmcd.SetExposureTime( c_float(exposure_time) ), "SetExposureTime" )
        except ValueError as exc:
            print exc
            return False
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
                win32event.WaitForSingleObject( self.event, 1000 )
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
        if self.acquiring or self.event:
            return
        self.thread = Thread(target=self._acquire, args=(callback,))
        self.thread.start()
            
    def stop_acquiring( self, join = False ):
        self.acquiring = False
        if join:
            self.thread.join()
        
    def shutdown( self ):
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

    t = ThreadedServer( CameraService, port = port, protocol_config = {"allow_public_attrs" : True, \
                                                                       "allow_pickle" : True})
    t.start()
