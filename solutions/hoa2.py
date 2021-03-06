from solution import Solution, CopyRegion
import os

class SandiaHoa2(Solution):
    for_traps = ('hoa2')
    description = 'Sandia Q19 1MHz'
    uses_regions = ('Q')
    adjustable = ('Sym scale', 'Asym scale')  #other controls disabled [todo]

    def __init__(self, p):
        Solution.__init__(self, p)
        voltage = self.voltage
        
        # correct scale factor at 250V, 17 MHz should be about .19
        voltage('Q', -9	, 0.004	, 0)
        voltage('Q', -8	, 0.006	, 0)
        voltage('Q', -7	, 0.010	, 0)
        voltage('Q', -6	, 0.019	, 0)
        voltage('Q', -5	, 0.037	, 0)
        voltage('Q', -4	, 0.089	, 0)
        voltage('Q', -3	, 0.266	, .001)
        voltage('Q', -2	, 0.928	, .005)
        voltage('Q', -1	, 1.587	, .01)
        voltage('Q', 0	, -2.109, -.014)
        voltage('Q', 1	, 1.588	, .009)
        voltage('Q', 2	, 0.930	, .003)
        voltage('Q', 3	, 0.266	, .001)
        voltage('Q', 4	, 0.090	, 0)
        voltage('Q', 5	, 0.037	, 0)
        voltage('Q', 6	, 0.019	, 0)
        voltage('Q', 7	, 0.010	, 0)
        voltage('Q', 8	, 0.007	, 0)
        voltage('Q', 9	, 0.004	, 0)
        
class SandiaRot45(Solution):
    for_traps = ('hoa2')
    description = 'Sandia Q19 rotate 45'
    uses_regions = ('Q')
    adjustable = ('Sym scale', 'Asym scale')  #other controls disabled [todo]

    def __init__(self, p):
        Solution.__init__(self, p)
        voltage = self.voltage
        
        # correct scale factor at 250V, 17 MHz should be about .19
        voltage('Q', -9	, 0.004	, -.19, .85)
        voltage('Q', -8	, 0.006	, -.19, .85)
        voltage('Q', -7	, 0.010	, -.19, .85)
        voltage('Q', -6	, 0.019	, -.19, .85)
        voltage('Q', -5	, 0.037	, -.19, .85)
        voltage('Q', -4	, 0.089	, -.19, .85)
        voltage('Q', -3	, 0.266	, -.19, .85)
        voltage('Q', -2	, 0.928	, -.19, .85)
        voltage('Q', -1	, 1.587	, -.19, .85)
        voltage('Q', 0	, -2.109, -.19, .85)
        voltage('Q', 1	, 1.588	, -.19, .85)
        voltage('Q', 2	, 0.930	, -.19, .85)
        voltage('Q', 3	, 0.266	, -.19, .85)
        voltage('Q', 4	, 0.090	, -.19, .85)
        voltage('Q', 5	, 0.037	, -.19, .85)
        voltage('Q', 6	, 0.019	, -.19, .85)
        voltage('Q', 7	, 0.010	, -.19, .85)
        voltage('Q', 8	, 0.007	, -.19, .85)
        voltage('Q', 9	, 0.004	, -.19, .85)

class Wide(Solution):
    for_traps = ('hoa2')
    description = 'Wide solution'
    uses_regions = ('Q')
    adjustable = ('Sym scale', 'Asym scale', 'width', 'vertical_compensation', 'horizontal_compensation', 'axial_compensation')  #other controls disabled [todo]

    def __init__(self, p):
        Solution.__init__(self, p)

        self.base_solution = GlobalCompensatedUW(p)

        #voltage = self.voltage
        
        # correct scale factor at 250V, 17 MHz should be about .19
        #voltage('Q', -9	, 0.004	, -.19, .85)
        #voltage('Q', -8	, 0.006	, -.19, .85)
        #voltage('Q', -7	, 0.010	, -.19, .85)
        #voltage('Q', -6	, 0.019	, -.19, .85)
        #voltage('Q', -5	, 0.037	, -.19, .85)
        #voltage('Q', -4	, 0.089	, -.19, .85)
        #voltage('Q', -3	, 0.266	, -.19, .85)
        #voltage('Q', -2	, 0.928	, -.19, .85)
        #voltage('Q', -1	, 1.587	, -.19, .85)
        #voltage('Q', 0	, -2.109, -.19, .85)
        #voltage('Q', 1	, -2.109, -.19, .85)
        #voltage('Q', 2	, 1.588	, -.19, .85)
        #voltage('Q', 3	, 0.930	, -.19, .85)
        #voltage('Q', 4	, 0.266	, -.19, .85)
        #voltage('Q', 5	, 0.090	, -.19, .85)
        #voltage('Q', 6	, 0.037	, -.19, .85)
        #voltage('Q', 7	, 0.019	, -.19, .85)
        #voltage('Q', 8	, 0.010	, -.19, .85)
        #voltage('Q', 9	, 0.007	, -.19, .85)

    def interpolated_voltage_at(self, (x,y), region):
        region.sub_electrode = True

        left_region = CopyRegion(region)
        right_region = CopyRegion(region)

        left_region.center = left_region.center - region.width/2.0
        right_region.center = right_region.center + region.width/2.0

        if x > region.center - region.width/2.0 and x < region.center + region.width/2.0:
            return self.base_solution.interpolated_voltage_at( (region.center, y), region)

        if x > region.center:
            return self.base_solution.interpolated_voltage_at( (x, y), right_region)
        else:
            return self.base_solution.interpolated_voltage_at( (x, y), left_region)

class UWQuant(Solution):
    for_traps = ('hoa2')
    description = 'UW Quantum Region Solution'
    uses_regions = ('Q')
    adjustable = ('Sym scale')
    
    def __init__(self, p):
        Solution.__init__(self, p)
        voltage = self.voltage
        laser = self.laser
        
        self.add_negatives = True
        
        voltage('Q', -4	, 0.0	    , 0)
        voltage('Q', -3	, 0.266	    , 0)
        voltage('Q', -2	, 0.930	    , 0)
        voltage('Q', -1	, 1.587	    , 0)
        voltage('Q', 0	, -2.109    , 0)
        voltage('Q', 1	, 1.587	    , 0)
        voltage('Q', 2	, 0.930	    , 0)
        voltage('Q', 3	, 0.266	    , 0)
        voltage('Q', 4	, 0	        , 0)
        voltage('Q', 5	, 0	        , 0)
        
        voltage('Q', -4	, 0.0	    , 0 , offset=.0833)
        voltage('Q', -3, 0.718929   , 0 , offset=.0833)
        voltage('Q', -2, 0.778137   , 0 , offset=.0833)
        voltage('Q', -1, 1.58724    , 0 , offset=.0833)
        voltage('Q',  0, -2.09125   , 0 , offset=.0833)
        voltage('Q',  1, 1.56385    , 0 , offset=.0833)
        voltage('Q',  2, 0.90748    , 0 , offset=.0833)
        voltage('Q',  3, 0.463796   , 0 , offset=.0833)
        voltage('Q',  4, 0          , 0 , offset=.0833)
        voltage('Q',  5, 0          , 0 , offset=.0833)
        
        voltage('Q', -4	, 0.0	    , 0 , offset=.166 )
        voltage('Q', -3, 0.528491   , 0 , offset=.166 )
        voltage('Q', -2, 1.8765     , 0 , offset=.166 )
        voltage('Q', -1, 1.64933    , 0 , offset=.166 ) 
        voltage('Q',  0, -2.02426   , 0 , offset=.166 )
        voltage('Q',  1, 1.09393    , 0 , offset=.166 )
        voltage('Q',  2, 1.05327    , 0 , offset=.166 )
        voltage('Q',  3, 0.322058   , 0 , offset=.166 )
        voltage('Q',  4, 0          , 0 , offset=.166 )
        voltage('Q',  5, 0          , 0 , offset=.166 )
        
        voltage('Q', -4	, 0.0	    , 0 , offset=.25 )
        voltage('Q', -3, -0.212357  , 0 , offset=.25 )
        voltage('Q', -2, 2.23654    , 0 , offset=.25 )
        voltage('Q', -1, 1.95669    , 0 , offset=.25 )
        voltage('Q',  0, -1.94595   , 0 , offset=.25 )
        voltage('Q',  1, 0.547035   , 0 , offset=.25 )
        voltage('Q',  2, 1.32921    , 0 , offset=.25 )
        voltage('Q',  3, 0.532968   , 0 , offset=.25 )
        voltage('Q',  4, 0          , 0 , offset=.25 )
        voltage('Q',  5, 0          , 0 , offset=.25 )
        
        voltage('Q', -4	, 0.0	    , 0 , offset=.333 )
        voltage('Q', -3, 1.06518    , 0 , offset=.333 )
        voltage('Q', -2, 1.7089     , 0 , offset=.333 )
        voltage('Q', -1, 2.3241     , 0 , offset=.333 )
        voltage('Q',  0, -1.94588   , 0 , offset=.333 )
        voltage('Q',  1, 0.305831   , 0 , offset=.333 )
        voltage('Q',  2, 1.15094    , 0 , offset=.333 )
        voltage('Q',  3, -0.0490063 , 0 , offset=.333 )
        voltage('Q',  4, 0          , 0 , offset=.333 )
        voltage('Q',  5, 0          , 0 , offset=.333 )
        
        voltage('Q', -4	, 0.0	    , 0 , offset=.416 )
        voltage('Q', -3, 0.572676   , 0 , offset=.416 )
        voltage('Q', -2, -0.548656  , 0 , offset=.416 )
        voltage('Q', -1, 2.51127    , 0 , offset=.416 )
        voltage('Q',  0, -1.38724   , 0 , offset=.416 )
        voltage('Q',  1, -0.783095  , 0 , offset=.416 )
        voltage('Q',  2, 2.22243    , 0 , offset=.416 )
        voltage('Q',  3, 0.487476   , 0 , offset=.416 )
        voltage('Q',  4, 0          , 0 , offset=.416 )
        voltage('Q',  5, 0          , 0 , offset=.416 )

        voltage('Q', -4	, 0.0	    , 0 , offset=.5 )
        voltage('Q', -3, 0.3305371	, 0 , offset=.5 )
        voltage('Q', -2, 0.574142   , 0 , offset=.5 )
        voltage('Q', -1, 2.426975	, 0 , offset=.5 )
        voltage('Q',  0, -1.1787785 , 0 , offset=.5 )
        voltage('Q',  1, -1.1787785	, 0 , offset=.5 )
        voltage('Q',  2, 2.426975   , 0 , offset=.5 )
        voltage('Q',  3, 0.574142	, 0 , offset=.5 )
        voltage('Q',  4, 0.3305371  , 0 , offset=.5 )
        voltage('Q',  5, 0          , 0 , offset=.5 )
        
        laser('Q', 0  , [.1]  )
        laser('Q', 19 , [3.1] )

class LocalCompensatedUW(UWQuant):
    for_traps = ('hoa2')
    description = 'Locally compensated UW-Q'
    uses_regions = ('Q')
    adjustable = ('Sym scale', 'vertical_compensation', 'horizontal_compensation', 'axial_compensation')
 
    def voltage_at(self, (x,y) , region , electrode_offset=0):
        v = super(LocalCompensatedUW, self).voltage_at( (x,y) , region , electrode_offset)
        
        if x == 19 : return 0  # These are the global rotator/compensation electrodes
        
        v = v + region.vertical_compensation
        
        if y > 0:
            v = v + region.horizontal_compensation
        else:
            v = v - region.horizontal_compensation
        
        if x > region.center:
            v = v + region.axial_compensation
        else:
            v = v - region.axial_compensation

        return v

class GlobalCompensatedUW(UWQuant):
    for_traps = ('hoa2')
    description = 'Globally compensated UW-Q'
    uses_regions = ('Q')
    adjustable = ('Sym scale', 'vertical_compensation', 'horizontal_compensation', 'axial_compensation')
 
    def voltage_at(self, (x,y) , region , electrode_offset=0):
        v = super(GlobalCompensatedUW, self).voltage_at( (x,y) , region , electrode_offset)
        
        if x == 19:
            if y > 0:
                v = v + region.vertical_compensation + region.horizontal_compensation
            else:
                v = v + region.vertical_compensation - region.horizontal_compensation
            return v
        
        if x > region.center:
            v = v + region.axial_compensation
        else:
            v = v - region.axial_compensation

        return v
        
class SymMerge(Solution):
    for_traps = ('hoa2')
    description = 'Symmetric merge'
    uses_regions = ('Q')
    adjustable = ('Sym scale', 'width')
    
    def __init__(self, p):
        Solution.__init__(self, p)
        
        self.base_solution = UWQuant(p)
        
        self.laser('Q', 0  , [.1]  )
        self.laser('Q', 19 , [3.1] )
    
    def wells(self, region):
        if region.width <= 4:
            return [(region.name, region.center)]
        elif region.width > 4:
            return [ (region.name, region.center - region.width) ,
                     (region.name, region.center + region.width) ]
    
    def interpolated_voltage_at(self, (x,y), region):
        region.sub_electrode = True
        left_region = CopyRegion(region)
        right_region = CopyRegion(region)
            
        if region.width > 4:
            left_region.center = region.center - region.width
            right_region.center = region.center + region.width
        
            return  self.base_solution.interpolated_voltage_at((x,y), left_region) + \
                    self.base_solution.interpolated_voltage_at((x,y), right_region)
        else:
            # linear interpolation to find the intermediate solution
            v_center = self.base_solution.interpolated_voltage_at((region.center,y), region)
            
            if abs(x-region.center) < region.width:
            
                left_region.center = region.center - 4
                right_region.center = region.center + 4
                v_seperated = self.base_solution.interpolated_voltage_at((x,y), left_region) + \
                              self.base_solution.interpolated_voltage_at((x,y), right_region)
            
                gradient = (v_seperated - v_center) / 4.0
                
                return v_seperated - gradient * (4 - region.width)
                #return region.width * gradient - v_seperated
                
                #return v_center
            else:
                left_region.center = region.center - region.width
                right_region.center = region.center + region.width

                # in the limit x=center need to scale down by .5 otherwise both solutions will add
                # and voltages will be doubled                
                if region.width < 4.0:
                    multiplier = .5 + region.width / 8.0
                else:
                    multiplier = 1.0

                return  multiplier * (self.base_solution.interpolated_voltage_at((x,y), left_region) + \
                                      self.base_solution.interpolated_voltage_at((x,y), right_region))
            
            #gradient = (v_center - v_seperated) / 4.0
            #return gradient * (4-region.width) + v_seperated
class harmonic(Solution):
    for_traps = ('hoa2')
    description = 'harmonic solution'
    uses_regions = ('Q')
    adjustable = ('Sym scale', 'Asym scale', 'width', 'vertical_compensation', 'horizontal_compensation', 'axial_compensation')  #other controls disabled [todo]

    def __init__(self, p):
        Solution.__init__(self, p)

        #self.base_solution = GlobalCompensatedUW(p)

        voltage = self.voltage
        
        #correct scale factor at 250V, 17 MHz should be about .19
        voltage('Q', -9	, 0.010	, -.19, .85)
        voltage('Q', -8	, 0.019	, -.19, .85)
        voltage('Q', -7	, 0.037	, -.19, .85)
        voltage('Q', -6	, 0.089	, -.19, .85)
        voltage('Q', -5	, 0.266	, -.19, .85)
        voltage('Q', -4	, 0.928	, -.19, .85)
        voltage('Q', -3	, 1.587	, -.19, .85)
        voltage('Q', -2	, -2.109*0.5, -.19, .85)
        voltage('Q', -1	, -2.109*0.8, -.19, .85)
        voltage('Q', 0	, -2.109, -.19, .85)
        voltage('Q', 1	, -2.109*0.8, -.19, .85)
        voltage('Q', 2	, -2.109*0.5, -.19, .85)
        voltage('Q', 3	, 1.588, -.19, .85)
        voltage('Q', 4	, 0.930	, -.19, .85)
        voltage('Q', 5	, 0.266	, -.19, .85)
        voltage('Q', 6	, 0.090	, -.19, .85)
        voltage('Q', 7	, 0.037	, -.19, .85)
        voltage('Q', 8	, 0.019	, -.19, .85)
        voltage('Q', 9	, 0.010	, -.19, .85)
class Anharmonic(Solution):
    for_traps = ('hoa2')
    description = 'Anharmonic solution'
    uses_regions = ('Q')
    adjustable = ('Sym scale', 'Asym scale', 'width', 'vertical_compensation', 'horizontal_compensation', 'axial_compensation')  #other controls disabled [todo]

    def __init__(self, p):
        Solution.__init__(self, p)

        #self.base_solution = GlobalCompensatedUW(p)

        voltage = self.voltage
        
        #correct scale factor at 250V, 17 MHz should be about .19
        voltage('Q', -9	, 0.010	, -.19, .85)
        voltage('Q', -8	, 0.019	, -.19, .85)
        voltage('Q', -7	, 0.037	, -.19, .85)
        voltage('Q', -6	, 0.089	, -.19, .85)
        voltage('Q', -5	, 0.266	, -.19, .85)
        voltage('Q', -4	, 0.928	, -.19, .85)
        voltage('Q', -3	, 1.587	, -.19, .85)
        voltage('Q', -2	, -2.109, -.19, .85)
        voltage('Q', -1	, -2.109, -.19, .85)
        voltage('Q', 0	, -2.109, -.19, .85)
        voltage('Q', 1	, -2.109, -.19, .85)
        voltage('Q', 2	, -2.109, -.19, .85)
        voltage('Q', 3	, 1.588, -.19, .85)
        voltage('Q', 4	, 0.93	, -.19, .85)
        voltage('Q', 5	, 0.266	, -.19, .85)
        voltage('Q', 6	, 0.090	, -.19, .85)
        voltage('Q', 7	, 0.037	, -.19, .85)
        voltage('Q', 8	, 0.019	, -.19, .85)
        voltage('Q', 9	, 0.010	, -.19, .85)

    #def interpolated_voltage_at(self, (x,y), region):
        #region.sub_electrode = True

        #left_region = CopyRegion(region)
        #right_region = CopyRegion(region)

        #left_region.center = left_region.center - region.width/2.0
        #right_region.center = right_region.center + region.width/2.0

        #if x > region.center - region.width/2.0 and x < region.center + region.width/2.0:
            #return self.base_solution.interpolated_voltage_at( (region.center, y), region)

        #if x > region.center:
            #return self.base_solution.interpolated_voltage_at( (x, y), right_region)
        #else:
            #return self.base_solution.interpolated_voltage_at( (x, y), left_region)

class ManualTextFile(Solution):
    for_traps = ('hoa2')
    description = 'Manual text file'
    uses_regions = ('Q')
    adjustable = ('Sym scale', 'Asym scale')  #other controls disabled [todo]

    def __init__(self, p):
        Solution.__init__(self, p)
    
    def interpolated_voltage_at(self, (x,y), region):
        
        filename = 'solutions' + os.sep + 'manual.txt'
        undefined = 0
        # Parse file each time incase it changed
        with open(filename) as f:
            for line in f:
                if line.startswith('#') : continue
                if len(line.strip()) == 0: continue
                
                try:
                    position, designator, voltage = line.split()
                    voltage = float(voltage)
                    
                    if position == 'undefined' : 
                        undefined = voltage
                        continue
                    
                    position = int(position)
                    
                    if designator == 'relative':
                        position = int(round(region.center)) - position
                    
                    if position == x:
                        # OK, this is the one
                        if y <= 0 : return voltage * region.sym_scale + voltage * region.asym_scale
                        if y > 0 : return voltage * region.sym_scale - voltage * region.asym_scale
                except:
                    return undefined            
            return undefined
