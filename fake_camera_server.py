import rpyc
import numpy as np
import math
import cStringIO as StringIO
from rpyc.utils.server import ThreadedServer
#from scipy.optimize import fmin_powell as fmin
from scipy.optimize import fmin

class CameraService(rpyc.Service):

    all_roi = {}
    backend = None
    
    _instance = None
    def __new__(cls, *args, **kwargs): #make it a singleton
        if not cls._instance:
            cls._instance = super(CameraService, cls).__new__(
                                cls, *args, **kwargs)
        return cls._instance

    #def __init__(self):
    #    print 'New camera service'
    @classmethod
    def backend_init(cls):
        print 'Initilizing backend'
    
    @classmethod
    def backend_terminate(cls):
        print 'Terminating backend'
    
    def exposed_scaled_image(self):
        print 'Returning camera image'
        image = (255*np.random.rand(1000, 1000)).astype(np.uint8)
        image = (image*.5) + image*self.circular_mask( (500,500), 30, image )
        self.image = image
        #image[500:600,500:600] = 255*np.ones([100,100])
        # need to make a copy in some way on the server side otherwise
        # it will be really slow as synchronizing object across socket
        # connection. This seems to be the fastest way. Could add compression
        # if network bandwidth an issue.        
        temp = StringIO.StringIO()
        np.save(temp, image)
        binary = temp.getvalue()
        temp.close()
        return binary
    
    def exposed_about(self):
        print "Client requested information about this service"
        return "Fake emccd camera server"

    def circular_mask(self, index,radius,array):
        a,b = index
        nx,ny = array.shape
        y,x = np.ogrid[-a:nx-a,-b:ny-b]
        mask = x*x + y*y <= radius*radius
        return mask
    
    def exposed_image_stats(self):
        image = (65535*np.random.rand(1000, 1000)).astype('int32')
        
        image_max = 65535
        saturation = float(np.sum(np.nonzero(image >= image_max-1))) / image.size
        
        return { 'saturation' : saturation ,
                 'min' : float(np.min(image)) / image_max ,
                 'max' : float(np.max(image)) / image_max ,
                 'mean' : float(np.average(image)) / image_max,
                 'stdev' : float(np.std(image)) / image_max }
    
    def exposed_roi_stats(self, roi_name):
        #image = (256*np.random.rand(1000, 1000)).astype(np.uint8)
        image = self.image
        
        roi = self.all_roi[roi_name]
        mask = self.circular_mask( (roi[0], roi[1]), roi[2], image )
        mean = np.sum( self.image * mask ) / np.sum(mask)
        print 'image : ', np.min(image), np.max(image), np.mean(image)
        print 'mask : ', np.min(mask), np.max(mask), np.mean(mask)
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
    
    def exposed_set_roi(self, name, x, y, r):
        #print 'Adding or changing roi named : ', name, ' : New settings ', x,y,r
        self.all_roi[name] = (x,y,r)
        
    def exposed_set_rois(self, name, number, x, y, r, spacing, axis_angle, spring):
        self.exposed_delete_rois(name)
        
        spacingX = spacing * math.cos( math.radians(axis_angle) )
        spacingY = spacing * math.sin( math.radians(axis_angle) )
        
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
 
        #if number % 2 : # odd numbers
            #for n in range(0, int(math.ceil(number/2.0))):
                #self.exposed_set_roi(name+str(n)+'l', x+n*spacingX , y+n*spacingY, r)
                #if number > 0 : self.exposed_set_roi(name+str(n)+'r', x-n*spacingX , y-n*spacingY, r)
        #else: # even numbers
            #for n in range(0, number/2):
                #self.exposed_set_roi(name+str(n)+'l', x+n*spacingX+.5*spacingX , y+n*spacingY+.5*spacingY, r)
                #self.exposed_set_roi(name+str(n)+'r', x-n*spacingX-.5*spacingX , y-n*spacingY-.5*spacingY, r)
        
        #print 'Final roi list', self.all_roi, ' of ', str(self)
    
    def exposed_roi_list(self):
        return self.all_roi.values()
    
    def exposed_roi_names(self):
        return self.all_roi.keys()
    
    def exposed_get_roi(self,name):
        return self.all_roi[name]
    
    
    def exposed_optimize_roi(self, number, x, y, r, spacing, axis_angle, spring):
        print "Optimize rois"

        def roi_optimize(p, number, r, axis_angle):            
            print "Trying : ", p
            
            x, y, spacing, spring = p[0], p[1], p[2], p[3]
            
            self.exposed_set_rois('manual', number, x, y, r, spacing, axis_angle, spring)
            #print 'all roi keys ', self.all_roi.keys()
            #print 'mean[0] ', self.exposed_roi_stats(self.all_roi.keys()[0])['mean']
            means = [self.exposed_roi_stats(roi)['mean'] for roi in self.all_roi.keys()]
            score = 1.0/np.sum(means)
            print 'Score : ', score 
            return score
        
        x0   = [ x, y, spacing, spring ]
        args = ( number, r, axis_angle )
        opt  = fmin(roi_optimize, x0, args=args, maxiter=1000)
        
        print 'Final result ', opt
        return opt
        
if __name__ == "__main__":
    
    print 'Starting fake camera service'

    #service = CameraService()
    CameraService.backend_init()
    t = ThreadedServer( CameraService, port = 18861, protocol_config = {"allow_public_attrs" : True, \
                                                                        "allow_pickle" : True})
    t.start()
    CameraService.backend_terminate()
