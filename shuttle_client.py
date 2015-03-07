import rpyc
import sys

try:
    conn = rpyc.connect("localhost", 18861, config = {"allow_public_attrs" : True})
except:
    print 'Server not running'
    sys.exit(0)

# get remote objects

solution = conn.root.solution()(None)
dac_controller = conn.root.dac_controller()

# Do shuttle

class Region:
    def __init__(self, center, width, sym_scale, asym_scale):
        self.region_name = 'Q'
        self.sub_electrode = True
        self.width = width
        self.center = center
        self.sym_scale = sym_scale
        self.asym_scale = asym_scale
        self.solution = solution

start_region = Region(9,0,1,0)
end_region = Region(10,0,1,0)
steps = 20

##c = dac_control.DacController(dac_driver, mapping)
print type(dac_controller)
sequence = dac_controller.build_sequence( start_region, end_region, steps, 
                             return_to_start = True,
                             print_output = False )
dac_controller.driver.write_frames(sequence)
