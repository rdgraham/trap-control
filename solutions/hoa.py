from solution import Solution
from scipy.interpolate import interp1d
import numpy as np

class SandiaHoaRotation(Solution):
    for_traps = ('hoa')
    description = 'Sandia asym434'
    uses_regions = ('Q')
    adjustable = ('Sym scale', 'Asym scale')

    rot = ([0.0892857, 0.216837, 0.382653, 0.535714, 0.727041, 0.956633, 1.21173, 1.47959, 1.79847, 2.09184, 2.3852, 2.67857, 3.02296, 3.31633, 3.62245, 4.01786, 4.375, 4.66837, 4.89796, 5] , \
           [28.4483, 25.0862, 21.9828, 19.5259, 16.9397, 14.7414, 12.6724, 11.25, 9.69828, 8.7931, 8.01724, 7.24138, 6.59483, 6.07759, 5.81897, 5.43103, 4.91379, 4.65517, 4.52586, 4.52586 ] )
    rot_interpolator = interp1d( rot[0], rot[1], kind='linear')
    
    f0 = ([0.115979,  0.257732, 0.773196, 1.27577, 1.79124,   2.35825,  2.91237,  3.45361,  4.21392,  5.00] , \
          [0.0149077, 0.102454, 0.198388, 0.255865, 0.306927, 0.351556, 0.389781, 0.423738, 0.470421, 0.510684] )              
    f1 = ([0.0700494, 0.076433, 0.082817, 4.00638, 4.00675 ] , \
          [2.58197,   2.59563,  2.60929,  2.6571,  2.6571 ])
    f2 = ([0.0700494, 0.076433, 0.082817, 4.00638, 4.00675 ] , \
          [2.59576,   2.59563,  2.5955,   2.51366, 2.51365])
    freq_interpolators = [interp1d( data[0], data[1], kind='linear') for data in (f0, f1, f2)]


    def __init__(self, p):
        Solution.__init__(self, p)
        #voltage = self._voltage
        voltage = self.voltage
        
        voltage('Q', -5, .981, 1.0)
        voltage('Q', -4, .981, 1.0)
        voltage('Q', -3, .981, 1.0)
        voltage('Q', -2, .981, 1.0)
        voltage('Q', -1, -.857, .378)
        voltage('Q',  0,  -1,  .378)
        voltage('Q',  1, -.857, 1.0)
        voltage('Q',  2, .981, 1.0)
        voltage('Q',  3, .981, 1.0)
        voltage('Q',  4, .981, 1.0)
        voltage('Q',  5, .981, 1.0)

    def solution_info(self, region):
        freq = '('
        for x in self.trap_frequencies(region):
            if x is None: 
                freq = freq + 'unknown, '
            else:
                freq = freq + "{:.2f}".format(x) + ', '
        freq = freq[0:-2]+') MHz'
        
        rot = self.rotation(region)
        if rot is None:
            rot = 'unknown'
        else:
            rot = "{:.3f}".format(rot)
        return {'Axial trap depth' : "{:.3f}".format(self.axial_depth(region)) + ' eV',
                'Frequency' : freq,
                'Rotation' : rot + ' deg'}

    def axial_depth(self, region):
        scale = 5.93 * self.trap_parameters.rf_voltage**2 / (self.trap_parameters.ion_mass * self.trap_parameters.rf_frequency**2)
        return region.sym_scale * .07616 * scale

    def trap_frequencies(self, region):
        v = region.sym_scale
        
        try:
            frequencies = [float(i(v)) for i in self.freq_interpolators]
        except IndexError:
            return [None, None, None]
        except ValueError:
            return [None, None, None]
        scale = (32.04*self.trap_parameters.rf_voltage)/(self.trap_parameters.ion_mass*self.trap_parameters.rf_frequency)
        return [f*scale for f in frequencies]
    
    def rotation(self, region):
        try:
            r = float(self.rot_interpolator(region.sym_scale) * region.asym_scale/5.0)
        except ValueError:
            return None
        return r

if __name__ == "__main__":
    solution = SandiaHoaRotation(None)
    class Region():
        sym_scale = 1
        asym_scale = .1
        center = 2
        name = 'Q'
    region = Region()
    for x in np.linspace(-10, 10, num = 20):
        print x, solution.voltage_at( (x,-1), region)
    
    print '---'
    
    for x in np.linspace(0,10, num=20):
        print x, solution.solution_info(region)
    
    print '---'
    
    for s in Solution.children:
        print s.__class__.__name__
