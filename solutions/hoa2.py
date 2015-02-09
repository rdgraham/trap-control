from solution import Solution

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

class John(Solution):
    for_traps = ('hoa2')
    description = 'Johns solution'
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
        
