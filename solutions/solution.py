import numpy as np
from scipy.interpolate import interp1d
from scipy.interpolate import pchip

class Solution(object):
    for_traps = None
    description = ''    
    
    def __init__(self, p):
        self.trap_parameters = p
        self._regions = []
        self._positions = []
        self._voltages = []
        self._offsets = []
        
        self._laser_positions = []
        self._laser_regions = []
        self._laser_voltages = []
        
        self.add_negatives = False  #if true, automatically add opposite solution to any given offset
    
    def __str__(self):
        return 'Solution Class : '+self.description
    
    def laser(self, region, position, voltages):
        "Shortcut function to specify laser voltage required for given position and region"
        self._laser_positions.append(position)
        self._laser_voltages.append(voltages)
        self._laser_regions.append(region)
    
    def voltage(self, region, position, sym, asym1, asym2=None, offset=0):
        "Shortcut function to set the voltage for a given position"
        if asym2 == None: asym2 = -1*asym1
        
        self._regions.append(region)
        self._positions.append(position)
        self._offsets.append(offset)
        self._voltages.append( (sym, asym1, asym2) )
        
        if self.add_negatives and offset > 0:
            self._regions.append(region)
            self._positions.append( position*-1 )
            self._offsets.append( -1.0 * offset)
            self._voltages.append( (sym, asym1, asym2) )
            
    def laser_voltage_at(self, region_name, position):
        if not region_name in self._laser_regions:
            print 'Required laser voltage unknown at this position'
            return 0
        
        # TODO: support multiple dimensions
        indices = [i for i in range(len(self._laser_positions)) if self._laser_regions[i] == region_name]
        positions = np.array([self._laser_positions[i] for i in indices])
        voltages = np.array([self._laser_voltages[i][0] for i in indices])
        order = np.argsort(positions)
        
        interpolator = interp1d( positions[order], voltages[order], kind='linear')
        return float(interpolator(position))
    
    def interpolated_voltage_at(self, (x,y), region):
        "Returns voltage at (x,y) with given sub-electrode offset, interpolated as necessary"
        available_offsets = sorted(set(self._offsets))
        
        if available_offsets > 2 and region.sub_electrode:
            voltages = [self.voltage_at( (x,y), region, electrode_offset = offset) for offset in available_offsets]
            interpolator = interp1d( available_offsets, voltages, kind='cubic' ) 
            
            #print 'at x=', x
            #print 'offsets', available_offsets
            #print 'voltages', voltages
            #print 'interped', interpolator(available_offsets), '\n'
            try:
                return interpolator(region.center - round(region.center))
            except ValueError:
                print 'Offset outside interpolation range'
                return 0
        else:
            #print 'Sub-electrode offsets not specified for this solution'
            return self.voltage_at( (x,y), region )
    
    def voltage_at(self, (x,y) , region , electrode_offset=0):

        # find the index of the entry with correct offset & region closest 
        # to the actual position of trap center.
        min_delta = float('inf')
        closest = None
        for i in range(len(self._regions)):
            if (self._regions[i] == region.name and self._offsets[i] == electrode_offset):
                delta = abs( self._positions[i] - (x-round(region.center)) )
                if delta < min_delta:
                    min_delta = delta
                    closest = i
        
        #print 'Indices matching offset ', electrode_offset, indices
        
        # find closest x position
        #deltas = [abs( self._positions[i] - (x-round(region.center)) ) for i in indices]
        #closest = deltas.index(min(deltas))
        #print 'deltas ', deltas, closest
        
        sym   = self._voltages[closest][0]
        asym1 = self._voltages[closest][1]
        asym2 = self._voltages[closest][2]
        
        if y <= 0 : return sym * region.sym_scale + asym1 * region.asym_scale
        if y > 0 : return sym * region.sym_scale + asym2 * region.asym_scale
    
    def old_voltage_at(self, (x,y) , region , electrode_offset=0):
        """DEPRICATED
           Returns the voltage at a given point x,y,region point
        """
        # make interpolator if necessary
        if self.interpolators == None:
            matching_region_indices = [i for i,r in enumerate(self._regions) if r == region.name]
            matching_offset_indices = [i for i,o in enumerate(self._offsets) if o == electrode_offset]
            indices = matching_region_indices and matching_offset_indices
            #indices = matching_region_indices
            #print matching_offset_indices
            
            positions = np.array(self._positions)[indices]
            syms = np.array([v[0] for v in self._voltages])[indices]
            asyms1 = np.array([v[1] for v in self._voltages])[indices]
            asyms2 = np.array([v[2] for v in self._voltages])[indices]
            self.interpolators = (  interp1d( positions, syms, kind='linear'), \
                                    interp1d( positions, asyms1, kind='linear'), \
                                    interp1d( positions, asyms2, kind='linear') )
            #self.interpolators = (  pchip( positions, syms  ) ,\
            #                        pchip( positions, asyms ) )
        try:
            sym = self.interpolators[0](x - region.center)
            asym1 = self.interpolators[1](x - region.center)
            asym2 = self.interpolators[2](x - region.center)
        except ValueError:
            return None
        ## original scheme
        ##if y < 0 : asym = asym * -1
        ##return sym * region.sym_scale + asym * region.asym_scale
        
        if y < 0 : return sym * region.sym_scale + asym1 * region.asym_scale
        if y > 0 : return sym * region.sym_scale + asym2 * region.asym_scale
        
    def solution_info(self, region):
        return {}
        
    def wells(self, trap_region):
        "Returns a list of tuples giving the region name and position of any potential wells in the solution"
        # Default version, for single well, returns center
        return [(trap_region.region_name, trap_region.center)]

class CopyRegion(object):
    """ This is a convenience class. It will make a copy of a TrapRegion,
        preserving only the basic parameters : center, scalefactor, etc.
        The solution will not be copied.
    """
    def __init__(self, original):
        self.sym_scale = original.sym_scale
        self.asym_scale = original.asym_scale
        self.center = original.center
        self.width = original.width
        self.axial_compensation = original.axial_compensation
        self.vertical_compensation = original.vertical_compensation
        self.horizontal_compensation = original.horizontal_compensation
        self.sub_electrode = original.sub_electrode
        self.name = str(original.name)

        
