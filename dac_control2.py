#!/usr/bin/env python

from ctypes import *
#from collections import defaultdict
from itertools import izip_longest
import sys, argparse, re, time, struct, socket
import trap_mapper
import solutions
from repoze.lru import lru_cache  #for python2, if update to python3 use functools
try:
    import parallel
except ImportError:
    print ("Parallel port support not installed.")

DEBUG=False

class Driver(object):
    """Abstract driver class for an output device driver.
       Deligates automatically to concrete device depending on device name prefix.
    """
    # Specify which of output ports to use for each function.
    # Can override in subclass if necessary
    frame_bit = 1 << 4
    clock_bit = 1 << 3
    data3_bit = 1 << 2
    data2_bit = 1 << 1
    data1_bit = 1 << 0

    dt = -1.0 # average output rate
    
    def __init__(self, devname):
        self.devname = devname
        
        child_dict = {  'Dev' : NiDriver, 
                        'LPT' : LptDriver,
                        'UDP' : FPGADriver,
                        'nul' : FakeDriver
                     }
        try:
            self.__class__ = child_dict[ devname[:3] ]
            self.__init__(devname)
        except KeyError:
            raise ValueError('No driver available for device '+devname)

    def _build_frame( self, data1, data2, data3 ):
        """ Return the 24 bits of data at the falling clock cycles 
            with frame boundary signals.
        """
        # Initialize output with frame boundary signal
        out = [0] * 50
        out[0] = out[-1] = self.frame_bit
        
        data = [ data1, data2, data3 ]
        dbits = [ self.data1_bit, self.data2_bit, self.data3_bit ]
        or_fn = lambda x, y: x | y

        for i in range( 24 ):
            # Set data bit in val is corresponding bit in data set
            vals = (b if d>>i & 1 else 0 for b, d in zip( dbits, data ))
            val = reduce( or_fn, vals )
            # While outputing val output a clock pulse
            out[ 48 - i*2 ] |= val
            out[ 48 - i*2 - 1 ] |= val | self.clock_bit
        
        return out
        
    def write_frames(self, frames):
        " Writes out a list of frames "
        num_frames = len(frames)
        for i,f in enumerate(frames):
            final = i == num_frames-1
            self.write_frame(f, final_update_frame = final)

class FakeDriver(Driver):
    
    def __init__(self, devname):
        print "Fake driver initilized"
    
    def write_frame(self, data, final_update_frame = False):
        print "Fake driver writing frames " + str(data)
        #for d in self._build_frame(*data):
        #    print "bit = ", d
        
    def __del__(self):
        pass

class NiDriver(Driver):
    
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
    
    def __init__(self, devname):
        
        # Create NI digital out task
        self.CreateTask( c_char_p("DAC"), byref(self.hDAC) )
        self.CreateDOChan( self.hDAC, devname, None, self.DAQmx_Val_ChanForAllLines )
        self.StartTask( self.hDAC )
        
        # Write some initial data (maybe unnecessary?)
        self.WriteDigitalU8( self.hDAC, 50, c_int32(True), self.timeout, 
            self.DAQmx_Val_GroupByScanNumber, self.init_data, 
            byref(self.samples_written), None )
        self.StopTask( self.hDAC );
        
        print( "NI Driver Initilized" )
    
    def write_frame( self, data, final_update_frame = False ):
        "Write data to NIDaqmx channel"
        
        # DAQmxWriteDigitalU8 arguments: 
        # 		channel, nsamp, autostart, timeout, 
        # 		grouping, data, output samples written, reserved
        #print 'Writing : '+str(data)
        
        self.WriteDigitalU8( 
            self.hDAC, 
            c_int32(50), 
            c_int32(True), 
            self.timeout, 
            self.DAQmx_Val_GroupByScanNumber, 
            self.update_data_type(*self._build_frame(*data)), 
            byref(self.samples_written), 
            None )
        self.WaitUntilTaskDone( self.hDAC, c_double(5.0) )
        
    def __del__( self ):
        self.ClearTask( self.hDAC )
        self.ResetDevice( self.devname[:3] )

class LptDriver(Driver):

    def __init__(self, devname):
        
        dataRegAdr = int( devname[4:], 16 )
        
        self.parport = parallel.Parallel() #parallel.Parallel( int( devname[4:], 16 ) )
        
        # pyParallel is stupid in that it does not allow non standard port numbers
        # so this does what the constructor should do ..
        self.parport.dataRegAdr = dataRegAdr
        self.parport.statusRegAdr = dataRegAdr + 1
        self.parport.ctrlRegAdr   = dataRegAdr + 2
        self.parport.ctrlReg = windll.simpleio.inp(self.parport.ctrlRegAdr)
        
    
    def __del__(self):
        # may need to zero everything ?
        del self.parport
    
    def write_frame(self, data, final_update_frame = False):        
        for d in self._build_frame(*data):
            before = time.clock()
            self.parport.setData(d)
            self.dt = time.clock() - before
        
class FPGADriver(Driver):
    def __init__( self, devname, start_address = 0 ):
        addr = devname[4:]
        self.ip, self.port = addr.split( ':' )
        self.port = int(self.port)
        print (self.ip, self.port)

        self.fpga = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
        #self.fpga.setsockopt( socket.SOL_SOCKET, socket.SO_REUSEADDR, 1 )
        self.fpga.settimeout( 1.0 )
        self.fpga.bind( ('', self.port) )

        self.address = start_address

    def write_frame( self, data, final_update_frame = False  ):
        flags = 2 if final_update_frame else 0
        if data[0] == data[1] and data[1] == data[2]:
            # FPGA interprets chip 3 as write to all chips
            self.upload( flags, 3, data[0] )
            return

        last_update = 2 if data[2] else 1 if data[1] else 0
        for i, d in enumerate( data ):
            if d != 0:
                flags = 2 if final_update_frame and i == last_update else 0
                self.upload( flags, i, d )

    def upload( self, flags, chip, voltage_data ):
        d = struct.pack( '>HHBBBB', 
            self.address >> 16,
            self.address & ((1<<16)-1), 
            flags << 2 | chip,
            voltage_data >> 16,
            (voltage_data >> 8) & 255,
            voltage_data & 255 )
        #print repr(d), len(d)
        
        response, tries = None, 0
        while response != d and tries < 5:
            try:
                self.fpga.sendto( d, 0, (self.ip, self.port) )
                while True:
                    response = self.fpga.recvfrom( 1024 )[0]
                    if response != d:   print "Bad response", repr(response)
                    else: break
            except socket.error:
                tries += 1
        if tries == 5:
            if DEBUG: print "Response", response
            raise ValueError( "Could not connect to fpga." )

        # FPGA uses two addresses to store each update, so increment by 2
        self.address += 2

    def __del__( self ):
        # Upload sentinel to mark end of sequence
        self.upload( 1, 0, 0 )
        self.upload( 4, 0, 0 ) # Trigger sequence
        del self.fpga

class DataFile(object):
    "DEPRICATED : Represents the trapping solution" 
    
    comments = ""
    dt = 1.0  # default time step in ms
    potentials = []
    
    def __init__(self, filename):
        "Load the specified file. *Should* work with both GTRI and Sandia files."
        self.filename = filename
        self.dt = -1

        col_offset = None
        with open(filename) as f:
            for line in f:               
                if line.startswith('#') : self.comments += line.replace('#','').strip()
                if line.startswith('dt=') : self.dt = float(line[3:])
                if line.startswith('e0') : col_offset = 0
                if line.startswith('e1') : col_offset = 1
                if line[0].isupper() and line[1:2].isdigit(): #we have a line of electrode names
                    electrode_names = line.split()
                    col_offset = 0
                    #if DEBUG: print 'Electrode names:',electrode_names
                    
                if line[0].isdigit() : # we have a line of voltages
                    # check we know how the columns match up to the electrodes
                    if col_offset == None:
                        #print( 'Warning : electrode header info not found. Assuming starts with electrode number 1' )
                        col_offset = 1
                    # split up the rows by tab or comma and make into list of floats
                    rawdata = [float(i) for i in re.split('\t| |\n|,', line) if i != '']
                    # make into a list of tuples (electrode, voltage), ignoring last col
                    #potential_row = [(i + col_offset, d) for i, d in enumerate(rawdata) if i < 90]
                    
                    self.potentials.append( dict(zip(electrode_names, rawdata)) )
            
        print( 'Loaded '+str(self) )
        if DEBUG: print self.potentials
    
    def __str__(self):
        return 'File %s : %s. Timestep = %3.2f ms, %i rows or %3.2f s.' % \
            (self.filename, self.comments, self.dt, len(self.potentials), self.dt*len(self.potentials)/1000)

    def __iter__(self):
        return iter(self.potentials)

    def apply_override(self, s):
        """Overrides electrode potentials. Potentials to override are specified
           as a string with a comma seperated list of channel_number=voltage.
           Does nothing if s is None.
        """
        if s==None: return
        for tok in s.split(','):
            # check no weird characters
            if len(re.sub('[0-9]|=|-|\.', '', tok)) > 0: raise ValueError('Illegal character in override string')
            electrode, voltage = tok.split('=')
            electrode, voltage = ( int(electrode) , float(voltage) )
            override_fn = lambda e : (e[0], voltage) if e[0] == electrode else e
            defined_fn = lambda e : e[0]==electrode
            for i,p in enumerate(self.potentials):
                # apply override to existing potentials
                self.potentials[i] = map(override_fn, p)
                # if electrode is not defined already, must add it
                if len( filter(defined_fn, p) ) == 0:
                    self.potentials[i].append( (electrode, voltage) )   

    def scale(self, s):
        #self.potentials = [ [(e,v*s) for e, v in row] for row in self.potentials]
        self.potentials = [dict(zip(p.keys(), [s*i for i in p.values()] )) for p in self.potentials]

@lru_cache(maxsize=1)
class DacController(object):
    """Setup a DAC Controller. Driver is automatically selected based on device.
       If map_source is a string, it should be the filename of the mapping spreadsheet file and trap_name should be specified
       If map_source is a trap_mapper.TrapMapping object 
    """

    _device = None
    _map_source = None
    _trap_name = None

    driver = None
    trap = None
    offset = None
    a_voltages = dict()
    b_voltages = dict()
    output_a = True

    # Specify DAC voltage range
    min_voltage = -10
    max_voltage = 20 + min_voltage
    precision = 1 << 16

    def __init__( self, device, map_source, clear_dac, trap_name = None):

        print 'Initilizing DAC controller'

        if type(map_source) == type(''):
            self.trap = trap_mapper.TrapMapping(trap_name, map_source)
        elif isinstance(map_source, trap_mapper.TrapMapping):
            self.trap = map_source
        
        self.driver = Driver(device)

        self.offset( 0x2000 )		    # Set range to center about 0
        if clear_dac:
            print 'Driver is clearing DACs'
            self.input_register( True )
            self.voltage( None, 0. )	    # Set all voltages to 0 initially
            self.driver.write_frame( [0]*3, True )
            self.driver.write_frame( [0]*3, True )
            self.input_register( False )
            self.voltage( None, 0. )
            self.driver.write_frame( [0]*3, True )
            self.driver.write_frame( [0]*3, True )
            
        self.a_voltages = dict()
        self.b_voltages = dict()

        self.output_a = True
        self.input_register( not self.output_a )
        self.output_register( self.output_a )
        
    def _voltage_data( self, channel, v ):
        """Generate voltage data setting channel to v in volts, 
        sets all channels if channel is None."""
        if channel is not None and (channel < 0 or channel >= 32):
            return 0

        # Map voltage to digital value using min/max voltage
        r = self.max_voltage - self.min_voltage
        val = int( (v - self.min_voltage) / r * self.precision )
        val = max( 0, min( val, self.precision-1 ) )

        # target is 0 to update all channels, or as described below
        target = 0
        if channel is not None:
            group, channel = channel / 8, channel % 8
            target = (group+1) << 19 | channel << 16

        # Set first two bits to indicate we're writing to DAC register
        update_data_mode = 1 << 23 | 1 << 22
        data = update_data_mode | target | val
        return data

    def voltage( self, electrode, v , write=True):
        """Set electrode to v in volts. 
        If electrode is None, set all channels"""
        if electrode is not None:
            if electrode not in self.trap.electrode_map:
                return
            # Get chip and channel from map and generate data
            chip, channel = self.trap.electrode_map[ electrode ]
            vdata = self._voltage_data( channel, v )

            # Update given chip, send 0 (NOP) to others
            data = [0, 0, 0]
            data[ chip ] = vdata
            self.voltages[ electrode ] = v
        else:
            # Generate voltage data and send to all chips
            vdata = self._voltage_data( None, v )
            data = [vdata]*3
            self.voltages = [v]*(len(self.trap.electrode_map)+1)
        
        if write:
            self.driver.write_frame( data )
        else:
            return data
        
    def offset( self, off ):
        "Set offset registers to raw offset value given by off."
        off = max( 0, min( off, 1<<14 -1 ) )
        
        # Write offset to all OFS0 and OFS1 registers
        self.driver.write_frame( [2<<16 | off]*3 )
        self.driver.write_frame( [3<<16 | off]*3 )

    def input_register( self, a=True , write=True):
        bit = 1 if not a else 0
        if write: self.driver.write_frame( [1<<16 | bit<<2 | 1<<1]*3 )
        return [1<<16 | bit<<2 | 1<<1]*3

    def output_register( self, a=True , write=True):
        data = 255 if not a else 0
        if write: self.driver.write_frame( [11<<16 | data]*3 )
        return [11<<16 | data]*3

    def build_single( self, region, interpolate=True, print_output=False ):
        """ Returns a list of frames to setup a trapping potential at a given physical position.
        
            This does the conversion from physical positions along the x axis of the trap region to the relevant
            electrodes. Internally uses Solution.interpolated_voltage_at() or voltage_at depending on if interpolate parameter set.
        
            region is the TrapRegion object describing the center and other parameters of the trap to make
            base_solution is the (string) description identifying the solution to use
        """
        # get all electrodes in the region
        
        #solution = solutions.get_from_description( region.solution )(None)
        
        potentials = {}
        for electrode, x, y in self.trap.get_electrode_locations( region.name ):
            if interpolate :
                voltage = region.solution.interpolated_voltage_at( (x,y), region)
            else:
                voltage = region.solution.voltage_at( (x,y), region)
            potentials[electrode] = voltage
            if DEBUG : print 'Will set electrode '+electrode+' = '+str(voltage)

        frames_to_write = []
        frames_to_write = self.update(potentials, print_output=print_output)
        frames_to_write = frames_to_write + frames_to_write
        return frames_to_write
        
    def build_sequence( self, start, end, steps, return_to_start = False, print_output=False):
        """ Returns a list of frames for a sequence operation from start to end in a given number of steps.
            
            This does the conversion from physical positions along the x axis of the trap region to the relevant
            electrodes and internally uses Solution.interpolated_voltage_at().
            
            start/end are TrapRegion objects which define the trap created at the start and end of the sequence.
            TrapRegions will be created in betwen these points by interpolation of the center and width parameters.
            
            return_to_start, if True will write frames for a sequence from end back to start after to move the potential
            back to the starting position.

            Note : currently only supports sequences along one region. The region, scale factors and solutions should
                   be the same in both the start and end regions
        """
        
        frames_to_write = []
        
        #solution_class = solutions.get_from_description( base_solution.solution )
        #if solution_class is None:
        #    print "No known trapping solution. Can't update display"
        #    return
        #solution = solution_class(None) ## TODO: pass in trap parameters somehow
        
        delta_center = (end.center - start.center) / float(steps)
        delta_width = (end.width - start.width) / float(steps)
        for step in range(steps):
            if print_output: print 'Building potentials step', step, 'in a sequence of', steps
            
            # at each position, build an object confirming to the TrapRegion specification
            # that can be passed in to the solution to get the voltage
            trap_region = lambda : None
            trap_region.name = start.region_name  ## TODO: support multiple regions somehow
            trap_region.center = start.center + step * delta_center
            trap_region.width = start.width + step * delta_width
            trap_region.sym_scale = start.sym_scale
            trap_region.asym_scale = start.asym_scale
            trap_region.solution = start.solution
            trap_region.sub_electrode = True
            
            # get dict of potentials at each electrode
            potentials = {}
            #for electrode, x, y in mappings.get_electrode_locations( Chip().trap, trap_region.name ):
            for electrode, x, y in self.trap.get_electrode_locations( trap_region.name ):
                voltage = trap_region.solution.interpolated_voltage_at( (x,y), trap_region)
                potentials[electrode] = voltage
                
            # get the raw data required to update previous solution to current
            new_frames = self.update(potentials, write = False, print_output=print_output)
            frames_to_write = frames_to_write + new_frames + new_frames #need to write twice
        
        if return_to_start:
            frames_to_write = frames_to_write + self.build_sequence( end, start, steps, return_to_start = False )
        
        return frames_to_write
        
    def update( self, raw_updates, write = True, print_output = False ):
        """Returns the sequence of data frames to write in order to update the DAC given raw_updates.
           raw_updates is a dictionary with the keys the electrodes and values the voltages.
           
           If write is True, will write out to the DAC device at this time as the updates are calculated.
           
           Note:    Each frame consists of a tuple of 3 24-bit values, used for updating each chip. Can be
                    written out with driver.write_frames
           Note:    This will probably need to be called twice in order to rotate the data into the working
                    registers of the DACs.
        """
        to_write = []
        updates = []
        if DEBUG: print 'raw updates', raw_updates
        for electrode, v in raw_updates.iteritems():
            try:
                if not electrode in self.trap.electrode_info:
                    print "Warning: no known electrode information for "+str(electrode)+". Ignoring"
                    continue
                
                # Update voltage state and remove redundant updates
                volts = self.a_voltages if not self.output_a else self.b_voltages
                if (not electrode in volts) or volts[electrode] != v:
                    if DEBUG or print_output:
                        print( 'Updating electrode %s %s to %f V' % (electrode, self.trap.electrode_info[electrode]  ,  v) )
                    volts[ electrode ] = v
                    updates.append( (electrode, v) )
            except IndexError as e:
                print( volts, e )
                print( 'Error : could not apply voltage to electrode %s' % (electrode) )

        # Get chip and channel including repeats
        tupled = lambda i: i if isinstance( i[0], tuple ) else ( i, )
        updates = sorted( (emap, v)
                                  for e, v in updates
                                  for emap in tupled(self.trap.electrode_map[e]) )
        
        # Iterate through 1 update per chip
        chips = [ filter( lambda v: v[0][0] == i, updates ) for i in range(3) ]
        for updates in izip_longest( *chips, fillvalue = (None,0) ):
            if DEBUG: print( updates )

            # Build data or NOP if no more updates for this chip
            f = lambda ch, v: self._voltage_data( ch[1], v )
            data = [ (f(ch, v) if ch is not None else 0) for ch, v in updates ]
            
            # Write data
            if write:
                self.driver.write_frame( data )		
            else:
                to_write.append(data)
        
        if DEBUG: print( 'Update rate %f kHz' % (1.0 / self.driver.dt / 1000) )

        # Indicate to driver that this is the last frame of the update
        # The way synchronization is implemented the driver should wait
        # after the frame this flag was set until dt time has passed
        # So, in order to have updates occur synchronized we need to
        # change the output register at the START of the next sync point
        
        self.output_a = not self.output_a
        
        if write:
            self.driver.write_frame( [0]*3, True )
            self.input_register( not self.output_a )
            self.output_register( self.output_a )
        else:
            to_write.append( [0]*3 )
            to_write.append( self.input_register( not self.output_a , write=False) ) 
            to_write.append( self.output_register( self.output_a    , write=False) )
        
        return to_write
    
    def multiple_update( self , df ):
        "DEPRICATED : Updates all the rows in the data file in succession. Tries to maintain the timing specified in the file."
        last_update = None
        for update in iter(df):
            last_update = update
            self.update( update )

        # Always end outputting data from register a
        # So we don't clear current waveform next time program is run
        if not self.output_a:
            self.update( last_update )
        
    def __del__(self):
        del self.driver
        del self.trap

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description = 'Controls a 96 channel analog output device')
    parser.add_argument('trap',
                        help="""Specifies the electrode mapping for a given trap to use.
                                Corresponds to the name of the sheet in the mapping file (see below).
                             """
                        )
    parser.add_argument('file', help="File name of control data to use.")
    parser.add_argument('driver', 
                        help="""The name of the output device (and subdevice if necessary) to use.
                                For example, for a NI device : 'Dev1/port0/line0:4'.
                                For a parallel port device : 'LPT/0x378' where 0x378 is the hex address of the port to use.
                             """
                        )
    parser.add_argument('--mapfile', default='trap_mappings.ods', metavar='FILE',
                        help="""A spreadsheet file containing the map of electrodes to DAC channel.
                                Defaults to trap_mappings.ods.
                                Sheets must have columns with headers 'Electrode', 
                                'DAC Chip' and 'DAC Ch'.
                             """
                        )
    parser.add_argument('--output', default='0', metavar='N',
                        help="""Specifies what to output from the given file. Can be either:
                                 - a row rumber, e.g. 0 (default)
                                 - a row range, e.g. 0-4
                                 - text 'all' which outputs the whole file in succession, trying to maintain the time step specified in the file.  
                             """
                        )
    parser.add_argument('--override', metavar='MAP',
                        help="""Allows voltages specified for given channels to be overridden.
                                Formatted as a comma seperated list of channel_number=voltage, e.g.
                                '5=.2,6=0'. No spaces. Does not require that the electrode already has a defined voltage.
                             """
                        )
    parser.add_argument('-s', '--scale', default=1., metavar = 'S',
                        help="""Rescales all voltages in control file by S."""
                        )
    parser.add_argument('-c', '--clear', default=False, action='store_true',
                        help="""Reset all voltages to zero before beginning updates.  Only voltages which are nonzero in the 
                                data file will be updated."""
                        )
    parser.add_argument('-r', '--reverse', default=False, action='store_true',
                        help="""If outputing a range of rows or an entire data file, reverse the order of the output."""
                        )
    parser.add_argument('-t', '--roundtrip', default=False, action='store_true',
                        help="""After outputting a range of rows reverse it."""
                        )
    parser.add_argument('--debug', action='store_true', help="Turns on debugging")
    
    args = vars(parser.parse_args())
    DEBUG = args['debug']   

    c = DacController( args['trap'], args['driver'], args['mapfile'], args['clear'] )
    
    df = DataFile( args['file'] )
    df.scale( float(args['scale']) )
    
    df.apply_override(args['override'])
    if args['output'].isdigit():
        #try:
            #print df.potentials[ int(args['output']) ]
        c.update( df.potentials[ int(args['output']) ] )
        c.update( df.potentials[ int(args['output']) ] )
        #except IndexError:
        #    print 'Error : Data file has no row number %s' % args['output']
    elif args['output'] == 'all':
        i = list(df)
        if args['reverse']:  i = list(reversed( list(i) ))
        c.multiple_update( i )
        if args['roundtrip']:
            i = list(reversed( list(i) ))
            c.multiple_update( i )
    else:
        s = args['output'].split('-')
        if len(s) != 2 or any( not i.isdigit() for i in s ):
            print( 'Error %s is not a valid output description.' % args['output'] )
        else:
            start, end = int( s[0] ), int( s[1] )
            i = df.potentials[ start: end ]
            if args['reverse']:   i = list(reversed( list(i) ))
            c.multiple_update( i )

            if args['roundtrip']:
                i = list(reversed( list(i) ))
                c.multiple_update( i )
    del c
