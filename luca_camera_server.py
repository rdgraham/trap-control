import rpyc
import numpy as np
import cStringIO as StringIO
import time
import math
from ctypes import *
from ctypes.wintypes import HANDLE
import win32event

from threading import Thread
from rpyc.utils.server import ThreadedServer

saturation_level = 16383

class CameraService(rpyc.Service):       

    all_roi = {}
    image = None
    luca = None
    scale_min = None
    scale_max = None
    
    auto_min = 0
    auto_max = 100
    zoom = 1
    
    _instance = None
    def __new__(cls, *args, **kwargs): #make it a singleton
        if not cls._instance:
            cls._instance = super(CameraService, cls).__new__(
                                cls, *args, **kwargs)
        return cls._instance

    @classmethod
    def backend_init(cls):
        cls.image = np.zeros((1002, 1004))
        print 'Starting Andor LUCA camera driver ...'
        cls.luca = Luca()
        print '[Initilized OK]'
        cls.luca.start_acquiring(callback = cls.got_image)
        print '[Acquiring OK]'

    @classmethod
    def backend_terminate(cls):
        print 'Terminating Andor LUCA camera driver ...'
        cls.luca.shutdown()
        print '[OK]'

    @classmethod
    def got_image(cls, image_data):
        cls.image = image_data.astype('f')
        
        #apply zoom
        if cls.zoom > 1:
            width = np.shape(cls.image)[0]
            height = np.shape(cls.image)[1]
            newx = (width/2 - width/(2*cls.zoom)   , width/2 + width/(2*cls.zoom) )
            newy = (height/2 - height/(2*cls.zoom) , height/2 + height/(2*cls.zoom) )
            
            cls.image = cls.image[ newx[0]:newx[1] , newy[0]:newy[1] ]
            #print 'dimensions = ', width, height
            #print 'Originl was ', width, 'x' , height, ' new is ', np.shape(self.image)
        
        print 'Got image. Intensity from ', np.min(cls.image)/saturation_level, ' to ', np.max(cls.image)/saturation_level

    def exposed_limit_autoscale(self, auto_min, auto_max):
        self.auto_min = auto_min
        self.auto_max = auto_max
        print 'Client changed autoscale limits to ', self.auto_min, '...', self.auto_max
    
    def exposed_autoscale(self):
        try:
            # desaturate image to remove bright outliers, use this to produce the histogram
            #image_desaturated = self.image[ self.image < (saturation_level-1) ]
            
            #hist, bin_edges = np.histogram(image_desaturated, bins=50 )
            #hist, bin_edges = np.histogram(self.image, bins=128, range=(0, saturation_level) )

            #hist = hist / float(np.max(hist))
            #self.scale_min = bin_edges[ np.nonzero(hist > self.auto_min )[0][0] ]
            #self.scale_max = bin_edges[ np.nonzero(hist > self.auto_max )[0][-1]]

            print 'Scaling between', self.auto_min, '...', self.auto_max
            self.scale_min = np.percentile(self.image, self.auto_min)
            self.scale_max = np.percentile(self.image, self.auto_max)

            # In case of a single peak, ensure max > min
            #try:
            #    if self.scale_max == self.scale_min : self.scale_max = bin_edges[ np.nonzero(hist > self.auto_min)[0][1] ]
            #except IndexError:
            #    print 'Unable to auto scale. Default to 0..max'
            #    self.scale_min = 0.0
            #    self.scale_max = np.max(self.image)

            #print hist
            #print bin_edges
            print 'Auto scale min : original = ', np.min(self.image), ' final = ', self.scale_min
            print 'Auto scale max : original = ', np.max(self.image), ' final = ', self.scale_max
            #self.scale_min = np.min(self.image)
            #self.scale_max = np.max(self.image)
        except TypeError:
            print 'Unable to autoscale, using default 0..100'
            self.scale_min = 0
            self.scale_max = 100
        
    def exposed_setbg(self):
        pass

    def exposed_image_stats(self):
        
        saturation = float(np.sum(np.nonzero(self.image >= saturation_level-1))) / self.image.size
        
        return { 'saturation' : saturation ,
                 'min' : float(np.min(self.image)) / saturation_level ,
                 'max' : float(np.max(self.image)) / saturation_level ,
                 'mean' : float(np.average(self.image)) / saturation_level,
                 'stdev' : float(np.std(self.image)) / saturation_level }
    
    def exposed_scaled_image(self):
        if self.scale_min is None or self.scale_max is None:
            # Auto scale never set, determine automatically
            self.exposed_autoscale()
        
        image_to_send = (255* np.clip((self.image-self.scale_min)/(self.scale_max-self.scale_min),0,1.0)).astype(np.uint8)
        
        # need to make a copy in some way on the server side otherwise
        # it will be really slow as synchronizing object across socket
        # connection. This seems to be the fastest way. Could add compression
        # if network bandwidth an issue.        
        temp = StringIO.StringIO()
        np.save(temp, image_to_send)
        binary = temp.getvalue()
        temp.close()
        
        #print 'Original image : mean', np.average(self.image), 'shape', np.shape(self.image)
        print 'Returning scaled image to client. Scaled range : ', np.min(image_to_send), ' ... ', np.max(image_to_send), 'raw : ', np.min(self.image), ' ... ', np.max(self.image)
        
        return binary
    
    def exposed_about(self):
        print "Client requested information about this service"
        return "Basic windows server for Andor LUCA EMCCD"

    def circular_mask(self, index, radius, array):
        a,b = index
        nx,ny = array.shape
        y,x = np.ogrid[-a:nx-a,-b:ny-b]
        mask = x*x + y*y <= radius*radius
        return mask
        
    def exposed_roi_stats(self, roi_name):
        
        width, height = (1002, 1004) #of the original image (roi coordinates are relative to original image)
        
        transformX = lambda x : x - (width/2.0)  + (width/(2*CameraService.zoom))
        transformY = lambda y : y - (height/2.0) + (height/(2*CameraService.zoom))
                
        roi = self.all_roi[roi_name]
        mask = self.circular_mask( (transformX(roi[1]), transformY(roi[0])), roi[2], self.image )
        mean = np.sum( self.image * mask ) / np.sum(mask)
        return {'mean' : mean}
        
    #return(sum(array[mask]))
    def exposed_clear_roi(self):
        self.all_roi = {}
    
    def exposed_delete_roi(self, name):
        try:
            del self.all_roi[name]
        except KeyError:
            pass
            
    def exposed_delete_rois(self, prefix):
        "Remove all ROIs that have a name starting with given prefix"
        self.all_roi = dict( filter( lambda x : not x.startswith(prefix), self.all_roi ) )
        
    def exposed_set_roi(self, roi_name, x, y, r):
        print 'Adding or changing roi named : ', roi_name
        self.all_roi[roi_name] = (x,y,r)
        
    def exposed_set_rois(self, name, number, x, y, r, spacing, axis_angle, spring):
        self.exposed_delete_rois(name)

        if number % 2 : # odd numbers
            for n in range(0, int(math.ceil(number/2.0))):
                spacingX = (spacing + spring * n) * math.cos( math.radians(axis_angle) )
                spacingY = (spacing + spring * n) * math.sin( math.radians(axis_angle) )
                self.exposed_set_roi(name+str(n)+'l', x+n*spacingX, y+n*spacingY, r)
                if n > 0 : self.exposed_set_roi(name+str(n)+'r', x-n*spacingX, y-n*spacingY, r)
        else: # even numbers
            for n in range(0, number/2):
                spacingX = (spacing + spring*n) * math.cos( math.radians(axis_angle) )
                spacingY = (spacing + spring*n) * math.sin( math.radians(axis_angle) )
                self.exposed_set_roi(name+str(n)+'l', x+n*spacingX+.5*spacingX, y+n*spacingY+.5*spacingY, r)
                self.exposed_set_roi(name+str(n)+'r', x-n*spacingX-.5*spacingX, y-n*spacingY-.5*spacingY, r)
        
        print 'Final roi list', self.all_roi, ' of ', str(self)
    
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
        # These settings can be changed without restart of acqusition
        if setting == 'zoom':
            CameraService.zoom = int(value)
            return
        
        # These settings will require a restart of acqusition
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
            print 'Not able to start acquisition thread'
            return
        
        self.thread = Thread(target=self._acquire, args=(callback,))
        self.thread.start()
        print 'Started acquisition thread'
            
    def stop_acquiring( self, join = False ):
        self.acquiring = False
        if join:
            self.thread.join()
        time.sleep(self.exposure_time)
        print 'Stopped acquisition'
        
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
