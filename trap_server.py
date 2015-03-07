import switches
import solutions
import trap_mapper
import dac_control2 as dac_control
#import counters
#import lasers

import rpyc
import argparse

MAP_FILE = 'trap_mappings.ods'

mapping = None
dac_controller = None

class TrapService(rpyc.Service):       

    def exposed_solution(self):
        return solutions.get_from_description('UW Quantum Region Solution')
        
    def exposed_dac_controller(self):
        return dac_controller
    
if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description='Start a server providing a dac controller for remote use')
    parser.add_argument('trap_name', help='Name of the trap (eg. hoa2)')
    parser.add_argument('dac_driver', help='Name of the driver')
    args = vars(parser.parse_args())
    
    mapping = trap_mapper.TrapMapping(args['trap_name'], MAP_FILE)
    dac_controller = dac_control.DacController(args['dac_driver'], mapping)

    from rpyc.utils.server import ThreadedServer
    t = ThreadedServer( TrapService, port = 18861, protocol_config = {"allow_public_attrs" : True})
    t.start()
    
