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

    def exposed_binary_image(self):
        print 'Returning camera image'
        background = (256*np.random.rand(1000, 1000)).astype(np.uint8)
        
        # need to make a copy in some way on the server side otherwise
        # it will be really slow as synchronizing object across socket
        # connection. This seems to be the fastest way. Could add compression
        # if network bandwidth an issue.        
        temp = StringIO.StringIO()
        np.save(temp, background)
        binary = temp.getvalue()
        temp.close()
        return binary
    
    def exposed_about(self):
        print "Client requested information about this service"
        return "Fake emccd camera server"
    
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
        
if __name__ == "__main__":
    
    print 'Starting fake camera service'

    CameraService.backend_init()
    t = ThreadedServer( CameraService, port = 18861, protocol_config = {"allow_public_attrs" : True, \
                                                                        "allow_pickle" : True})
    t.start()
    CameraService.backend_terminate()
