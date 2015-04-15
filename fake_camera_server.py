import rpyc
import numpy as np
import cStringIO as StringIO
from rpyc.utils.server import ThreadedServer

class CameraService(rpyc.Service):

    all_roi = {}
    
    backend = None
    
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
        image = (256*np.random.rand(1000, 1000)).astype(np.uint8)
        
        roi = self.all_roi[roi_name]
        mean = np.mean( image * self.circular_mask( (roi[0], roi[1]), roi[2], image ) )
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
        
if __name__ == "__main__":
    
    print 'Starting fake camera service'

    CameraService.backend_init()
    t = ThreadedServer( CameraService, port = 18861, protocol_config = {"allow_public_attrs" : True, \
                                                                        "allow_pickle" : True})
    t.start()
    CameraService.backend_terminate()
