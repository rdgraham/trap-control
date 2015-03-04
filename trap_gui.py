import threading
from time import sleep

import wxversion
wxversion.select("2.8")
from traits.api import *
from traitsui.wx.editor import Editor
from traitsui.wx.basic_editor_factory import BasicEditorFactory
from traitsui.api import View, Item, Group, VGroup, HSplit, Handler, EnumEditor, RangeEditor, TableEditor, ButtonEditor, ObjectColumn, CheckListEditor, ListEditor, spring
from traitsui.menu import NoButtons
    
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from mpl_editor import MPLFigureEditor

from scipy import * 
from scipy.stats import norm

import cPickle as pickle
import numpy as np
import numbers
import wx
import sys
import matplotlib

import switches
import solutions
import trap_mapper
import dac_control2 as dac_control
import counters
import lasers

MAP_FILE = 'trap_mappings.ods'
SETTINGS_FILE = 'saved_settings.pk'

try:
    with open(SETTINGS_FILE, 'r') as f:
        saved_settings = pickle.load(f)
except IOError:
    print 'No saved settings found'
    saved_settings = dict()
to_save = dict() #settings to save

# Note: _default() methods only work with inline methods or lambdas, so must wrap in a lambda
class SettingLoader(object):
    def __init__(self, setting_key, default):
        self.setting_key, self.default = setting_key, default
    def __call__(self, ):
        try:
            return saved_settings[self.setting_key]
        except KeyError:
            print 'Unable to load saved setting for ', self.setting_key
            return self.default

class Parameters(SingletonHasTraits):
    """ The fixed parameters for the trap setup
    """
    rf_voltage = Float(100)
    rf_frequency = Float(20)
    ion_mass = Int(137)

class Devices(SingletonHasTraits):
    #dac_driver = String('LPT/0xCD00')
    dac_driver = String('nul')
    dac_print_output = Bool(False)
    counter_driver_name = String('nul')
    lasers_driver_name = String('nul')
    
    _dac_driver_default          = lambda self : SettingLoader('devices.dac_driver', 'nul')()
    _counter_driver_name_default = lambda self : SettingLoader('devices.counter_driver_name', 'nul')()
    _lasers_driver_name_default  = lambda self : SettingLoader('devices.lasers_driver_name', 'nul')()
    @on_trait_change('dac_driver,counter_driver_name,lasers_driver_name')
    def handler(self, name, new):
        to_save['devices.'+name] = new
    
class Chip(SingletonHasTraits):
    available_names = trap_mapper.get_trap_names(MAP_FILE)
    trap = Enum( available_names )
    
    view = View( Item('trap') )
    
    def _trap_default(self):
        try:
            saved = saved_settings['chip.trap']
            if saved in self.available_names:
                return saved
        except KeyError:
            return self.available_names[0]
    
    def _trap_fired(self):
        # update the available regions enum boxes elsewhere in program
        self.mapping = trap_mapper.TrapMapping(self.trap, MAP_FILE)
        
        names = self.mapping.get_region_names()
        
        LasersPanel().region_names = names
        SequenceStart().names = names
        SequenceEnd().names = names
        
        # update available solutions enum box
        available_solutions = [c.description for c in filter(lambda c : self.trap in c.for_traps , solutions.solution_classes)]
        tr = TrapRegion()
        tr.solution_descriptions = available_solutions
        tr.solution_description = SettingLoader('TrapRegion.solution_description' , available_solutions[0])()
        tr.names = names
        tr.name = SettingLoader('TrapRegion.name', names[0])()
        tr._update_limits()
        tr._update_sub_electrode()
        #tr._update_solution_display()
        
        lp = LasersPanel()
        lp.region_names = names
        for name in ['region1', 'region2', 'region3', 'region4']:
            print 'Loading ',name
            region = SettingLoader('LasersPanel.'+name, names[0])()
            lp.__dict__[name] = region
            lp._region_change_handler(name, region)
        
        SequenceBase().solution_descriptions = available_solutions
        SequenceBase().solution_description = SettingLoader('SequenceBase.solution_description', available_solutions[0])()
        SequenceBase()._solution_changed()
        SequenceStart().update_width_allowed()
        SequenceEnd().update_width_allowed()
        
        to_save['chip.trap'] = self.trap

class SolutionPlotUpdater(threading.Thread):
    """ When interpolation of a smooth curve is required, updating the solution display
        can take a while. So this is done in a thread which can be terminated if it is still
        running from a previous call
    """
    def __init__(self):
        super(SolutionPlotUpdater, self).__init__()
        self._stop = threading.Event()
    
    def stop(self):
        self._stop.set()
    
    def stopped(self):
        return self._stop.isSet()
    
    def update_solution_display(self):
        try:
            cp = ControlPanel()
            dp = DisplayPanel()
        except NameError:
            print 'Unable to update disaplay. Probably not built yet.'
            return
            
        ax = dp.solution_figure.axes[0]
        
        #solution_class = solutions.get_from_description( cp.manual_panel.trap_region.solution )
        #if solution_class is None:
        #    print 'No known trapping solution. Can not update display.'
        #    return
        
        #solution = solution_class( cp.setup_panel.parameters )
        #limits = mappings.get_xlimits(cp.setup_panel.chip.trap, cp.manual_panel.trap_region.name)
        
        solution = ManualPanel().trap_region.solution
        
        limits = Chip().mapping.get_xlimits(cp.manual_panel.trap_region.name)
        xvals = np.linspace( limits[0], limits[1], num=1+limits[1]-limits[0] )
        
        if self._stop.is_set(): return #terminate thread now if asked
        
        top = []
        bottom = []
        for x in xvals:
            try:
                top.append( solution.interpolated_voltage_at( (x,1), cp.manual_panel.trap_region) )
                bottom.append( solution.interpolated_voltage_at( (x,-1), cp.manual_panel.trap_region) )
            except (IndexError, TypeError):
                print 'Unable to plot solution, clearing axis'
                ax.clear()
                wx.CallAfter(dp.solution_figure.canvas.draw)
                return
            if self._stop.is_set(): return #terminate thread now if asked
                
        ax.clear()
        self.top_plot = ax.plot(xvals, top, 'b-') 
        self.bottom_plot = ax.plot(xvals, bottom, 'r-' ) 
        
        # mark trap center
        self.marker = ax.plot( [cp.manual_panel.trap_region.center, cp.manual_panel.trap_region.center], [-10, 10], 'g-' )
        
        # mark laser positions
        for region, position in LasersPanel().get_laser_positions():
            if region == cp.manual_panel.trap_region.name:
                ax.plot( [position, position], [-10,10], 'c-' )
        
        ax.add_patch(Rectangle((limits[0],-10),limits[1]-limits[0],20, facecolor='.9', edgecolor='black'))
        ax.set_xticks( np.arange(limits[0], limits[1]) )
        ax.set_xlim(limits)
        ax.set_ylabel('Voltage (V)')
        ax.set_xlabel('Position')
        ax.grid(True)
        
        wx.CallAfter(dp.solution_figure.canvas.draw)
        
        # Write solution info text in bottom panel
        info = solution.solution_info(cp.manual_panel.trap_region)
        s = ''
        for k in info:
            s = s + '   ' + k + ' = ' + str(info[k]) + '\n'
        dp.solution_info = s[:-1]
        
    def run(self):
        #try:
        #    self.update_solution_display()
        #except TypeError:
        #    pass
        self.update_solution_display()

class TrapRegion(SingletonHasTraits):
    """ Paramaters to control the trap region
    """    
    min_center = Float
    max_center = Float
    max_width = Float
    names = List(Str)
    name = Str
    solution_descriptions = List(Str)
    solution_description = Str
    center = Range(-10.0, None, 10.0)
    width = Range(0.0, None, 10.0)
    sym_scale = Range(0.0, 10.0, value=1)
    asym_scale = Range(0.0, 10.0)
    sub_electrode = Bool

    _sub_electrode_allowed = True
    _width_allowed = False
    
    _solution_update_thread = SolutionPlotUpdater()
    
    view = View( Item('solution_description', label='Solution', editor=EnumEditor(name = 'solution_descriptions')),
                 Item('name', editor=EnumEditor(name = 'names'), label='Region name'),
                 Item('sub_electrode', label='Sub-electrode solution', enabled_when='_sub_electrode_allowed'),
                 Item('center', editor=RangeEditor(low_name = 'min_center', high_name = 'max_center', mode='slider')),
                 Item('width', enabled_when='_width_allowed', editor=RangeEditor(high_name = 'max_width', mode='slider')),
                 Item('sym_scale'),
                 Item('asym_scale')
               )
    
    #_name_default           = lambda self : SettingLoader('TrapRegion.name', self.names[0])()
    #_solution_default       = lambda self : SettingLoader('TrapRegion.solution', self.solutions[0])()
    #_center_default         = lambda self : SettingLoader('TrapRegion.center', 0)()
    #_sym_scale_default      = lambda self : SettingLoader('TrapRegion.sym_scale', 1)()
    #_asym_scale_default     = lambda self : SettingLoader('TrapRegion.asym_scale', 0)()
    #_sub_electrode_default  = lambda self : SettingLoader('TrapRegion.sub_electrode', False)()
        
    def _name_fired(self):
        self._update_limits()
    
    def _update_limits(self):
        #limits = mappings.get_xlimits(Chip().trap, self.name)
        limits = Chip().mapping.get_xlimits(self.name)
        try:
            self.min_center = limits[0]
            self.max_center = limits[1]
            self.max_width = limits[1]-limits[0]
            print 'reset range of ', self.name, limits
        except ValueError:
            self.min_center = -1.0
            self.max_center = 1.0
            self.max_width = 1.0        
        except TypeError:
            pass

    @property
    def solution(self):
        try:
            return solutions.get_from_description( self.solution_description )( Parameters() )
        except TypeError:
            print 'Solution with description '+self.solution_description+' not found'

    @on_trait_change('solution_description')
    def _update_sub_electrode(self):
        # Disable and clear the sub_electrodes box if not enough electrode offsets available
        print 'update sub electrode solution for ', self.solution
        try:
            if len(set(self.solution._offsets)) > 2:
                self._sub_electrode_allowed = True
            else:
                self._sub_electrode_allowed = False
                self.sub_electrode = False
        except AttributeError:
            self._sub_electrode_allowed = False
            self.sub_electrode = False
            
    @on_trait_change('solution_description')
    def _update_width_enabled(self):
        "Disable width is not allowed by solution"
        
        self._width_allowed = 'width' in self.solution.adjustable
        
    @on_trait_change('name,solution_description,width,center,sym_scale,asym_scale,sub_electrode')
    def _update_solution_display(self, trait=None, name=None, new=None):
        if self._solution_update_thread.is_alive():
            self._solution_update_thread.stop()
            self._solution_update_thread.join()
        self._solution_update_thread = SolutionPlotUpdater()
        self._solution_update_thread.start()
        
        #Save all settings
        if name is not None and new is not None:
            to_save['TrapRegion.'+name] = new
                        
class PhotonsPlotUpdater(threading.Thread):
    """ Update the scrolling display of the counter, counter specified by given driver drv
    """
    _instance = None
    
    def __init__(self, drv=None):
        super(PhotonsPlotUpdater, self).__init__()
        if drv == None: return
        
        self.drv = drv
        self._stop = threading.Event()
        self.cp = ControlPanel()
        self.dp = DisplayPanel()
        self.update_all = True
        self.ax = self.dp.photons_figure.axes[0]    
        
        self.background = None    
    
    def __new__(cls, *args, **kwargs):
        # make class a singelton
        if not cls._instance:
            cls._instance = super(PhotonsPlotUpdater, cls).__new__(
                                cls, *args, **kwargs)
        return cls._instance
    
    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()
        
    def update_plot(self):
        """Fully update the plot"""
        if not hasattr(self, 'drv'): return
        
        print 'Doing full update of plot'
        
        self.ax.clear()
        #self.ax.grid(True)
        self.ax.set_ylabel('Counts')
        self.ax.set_xlabel('Time (s)')
        
        self.line, = self.ax.plot(self.drv.get_buffer(), '.5')
        self.maline, = self.ax.plot(self.drv.get_moving_avg_buffer(), 'r-')
        
        #self.background = None
        
        #wx.CallAfter(self.dp.photons_figure.canvas.draw)
        self.update_all = False
    
    def _draw_only_line(self):
        self.dp.photons_figure.canvas.restore_region(self.background)
        try:
            self.ax.draw_artist(self.line)
            self.ax.draw_artist(self.maline)
        except RuntimeError:
            pass
        self.dp.photons_figure.canvas.blit(self.ax.bbox)
    
    def update_lines(self):
        """Only update the plot lines. Won't rescale the plot"""
        
        if self.background == None:            
            wx.CallAfter(self.dp.photons_figure.canvas.draw)
            sleep(.1) #sometimes initial call to draw won't have finished yet
            self.background = self.dp.photons_figure.canvas.copy_from_bbox(self.ax.bbox) 
        
        self.line.set_ydata(self.drv.get_buffer())
        self.maline.set_ydata(self.drv.get_moving_avg_buffer())
        
        wx.CallAfter( self._draw_only_line )
        
    def run(self):
        while not self._stop.is_set():
            if self.update_all:
                self.update_plot()
            else:
                self.update_lines()
            sleep(.05)
            
class SwitchPanel(HasTraits):
    
    checklist = List(Str)    
    selection = List
    previous_selection = List
    new_name = Str
    
    view = View( Item('selection', editor=CheckListEditor(name='checklist'), style='custom', show_label=False) )
    
    def __init__(self):
        super(SwitchPanel, self).__init__()
        for switch in switches.switches:
            self.checklist.append(switch.name) 
    
    @on_trait_change('selection')
    def handler(self, name, new):
        # find which switch changed and what it changed to
        turn_on = set(self.selection).difference(set(self.previous_selection))
        turn_off = set(self.previous_selection).difference(set(self.selection))
        new_state = len(turn_off) == 0  #switch on or off
        switch_name = list(turn_on.union(turn_off))[0]
        self.previous_selection = self.selection
        
        # get the switch object
        switch = switches.switches[[s.name for s in switches.switches].index(switch_name)]
        # switch it
        switch.change_to(new_state)
        
class LasersPanel(SingletonHasTraits):
    num_locations = Range(1,4)
    cooling_time = Range(100,1000)
    region_names = List(Str)
    region1, region2, region3, region4  = Str, Str, Str, Str
    location1, location1_min, location1_max = Float, Float, Float 
    location2, location2_min, location2_max = Float, Float, Float
    location3, location3_min, location3_max = Float, Float, Float
    location4, location4_min, location4_max = Float, Float, Float
    
    view = View(Item('num_locations', label='Cooling locations'),
                Item('cooling_time', label='Cooling time (ms)'),
                Group( Item('region1', label='Region 1', editor=EnumEditor(name = 'region_names')),
                       Item('location1', show_label=False, springy=True, editor=RangeEditor(low_name = 'location1_min', high_name = 'location1_max', mode='slider')),
                       orientation = 'horizontal' ),
                Group( Item('region2', label='Region 2', editor=EnumEditor(name = 'region_names')),
                       Item('location2', show_label=False, springy=True, editor=RangeEditor(low_name = 'location2_min', high_name = 'location2_max', mode='slider')),
                       orientation = 'horizontal', enabled_when='num_locations > 1'),
                Group( Item('region3', label='Region 3', editor=EnumEditor(name = 'region_names')),
                       Item('location3', show_label=False, springy=True, editor=RangeEditor(low_name = 'location3_min', high_name = 'location3_max', mode='slider')),
                       orientation = 'horizontal', enabled_when='num_locations > 2'),
                Group( Item('region4', label='Region 4', editor=EnumEditor(name = 'region_names')),
                       Item('location4', show_label=False, springy=True, editor=RangeEditor(low_name = 'location4_min', high_name = 'location4_max', mode='slider')),
                       orientation = 'horizontal',  enabled_when='num_locations > 3'),
               )
    
    def get_laser_positions(self):
        return [(getattr(self, 'region'+str(i)), getattr(self, 'location'+str(i))) for i in range(1,self.num_locations+1)]
            
    @on_trait_change('region1,region2,region3,region4')
    def _region_change_handler(self, name, new):
        print 'Setting limits for region ', name, new
        #limits = mappings.get_xlimits(Chip().trap, new)
        limits = Chip().mapping.get_xlimits(new)
        try:
            setattr(self, 'location'+name[-1]+'_min', limits[0])
            setattr(self, 'location'+name[-1]+'_max', limits[1])
        except ValueError:
            setattr(self, 'location'+name[-1]+'_min', -1)
            setattr(self, 'location'+name[-1]+'_max', 1)        
        except TypeError:
            pass
        
        to_save['LasersPanel.'+name] = new
        #self._update_solution_display()
    
    @on_trait_change('location1,location2,location3,location4')
    def _update_solution_display(self):
        TrapRegion()._update_solution_display()

class SequenceBase(SingletonHasTraits):
    """ Paramaters to control the trap region
    """    
    solution_descriptions = List(Str)
    solution_description = Str
    sym_scale = Range(0.0, 10.0)
    asym_scale = Range(0.0, 10.0)
    _width_allowed = False
    
    view = View( Item('solution_description', label='Solution', editor=EnumEditor(name = 'solution_descriptions')),
                 Item('sym_scale'),
                 Item('asym_scale')
               )
               
    @property
    def solution(self):
        try:
            return solutions.get_from_description( self.solution_description )( Parameters() )
        except TypeError:
            print 'Solution with description '+self.solution_description+' not found'

    @on_trait_change('solution_description')
    def _solution_changed(self):
        
        #Update regions
        SequenceStart()._region_name_fired()
        SequenceEnd()._region_name_fired()
        
        #Disable width if not allowed by solution
        self._width_allowed = 'width' in self.solution.adjustable
        
        to_save['SequenceBase.solution_description'] = self.solution_description
        
class SequenceStart(SingletonHasTraits):

    min_center = Float
    max_center = Float
    max_width = Float
    names = List(Str)
    region_name = Str
    center = Range(-10.0, None, 10.0)
    width = Range(0.0, None, 10.0)
    _width_allowed = Bool
    _sequence_base = Instance(SequenceBase, ())
        
    view = View( Item('region_name', editor=EnumEditor(name = 'names'), label='Region name'),
                 Item('center', editor=RangeEditor(low_name = 'min_center', high_name = 'max_center', mode='slider')),
                 Item('width', enabled_when = '_width_allowed', editor=RangeEditor(high_name = 'max_width', mode='slider'))
               )    
    
    @on_trait_change('_sequence_base.solution_description')
    def update_width_allowed(self):
        self._width_allowed = 'width' in self._sequence_base.solution.adjustable
    
    # TODO: Change everything else to use region_name
    @property
    def name(self):
        # This is a work-around
        if self.region_name == '': self.region_name = self.names[0]
        return self.region_name
    
    @property
    def sym_scale(self):
        return SequenceBase().sym_scale
    
    @property
    def asym_scale(self):
        return SequenceBase().asym_scale
        
    @property
    def solution(self):
        return SequenceBase().solution
    
    def _region_name_fired(self):
        limits = Chip().mapping.get_xlimits(self.region_name)
        try:
            self.min_center = limits[0]
            self.max_center = limits[1]
            self.max_width = limits[1] - limits[0]
            print 'reset range of ', self.region_name, limits
        except ValueError:
            self.min_center = -1.0
            self.max_center = 1.0        
        except TypeError:
            pass

class SequenceEnd(SingletonHasTraits):

    min_center = Float
    max_center = Float
    max_width = Float
    names = List(Str)
    region_name = Str
    center = Range(-10.0, None, 10.0)
    width = Range(0.0, None, 10.0)
    _width_allowed = Bool
    _sequence_base = Instance(SequenceBase, ())
    
    sym_scale = SequenceBase().sym_scale
    asym_scale = SequenceBase().asym_scale
    solution = SequenceBase().solution
        
    view = View( Item('region_name', editor=EnumEditor(name = 'names'), label='Region name'),
                 Item('center', editor=RangeEditor(low_name = 'min_center', high_name = 'max_center', mode='slider')),
                 Item('width', enabled_when = '_width_allowed', editor=RangeEditor(high_name = 'max_width', mode='slider'))
               )

    @on_trait_change('_sequence_base.solution_description')
    def update_width_allowed(self):
        self._width_allowed = 'width' in self._sequence_base.solution.adjustable
    
    # TODO: Change everything else to use region_name
    @property
    def name(self):
        # This is a work-around
        if self.region_name == '': self.region_name = self.names[0]
        return self.region_name
        
    @property
    def sym_scale(self):
        return SequenceBase().sym_scale
    
    @property
    def asym_scale(self):
        return SequenceBase().asym_scale
        
    @property
    def solution(self):
        return SequenceBase().solution
               
    def _region_name_fired(self):
        limits = Chip().mapping.get_xlimits(self.region_name)
        try:
            self.min_center = limits[0]
            self.max_center = limits[1]
            self.max_width = limits[1] - limits[0]
            print 'reset range of ', self.region_name, limits
        except ValueError:
            self.min_center = -1.0
            self.max_center = 1.0        
            self.max_width = 1.0        
        except TypeError:
            pass

class SequenceRun(SingletonHasTraits):
    
    return_to_start = Bool
    steps = Range(1,100)
    move_lasers = Bool
    cooling_time = Range(100,1000)
    move_camera = Bool
    run = Button('Run')
    
    view = View( Item('steps', label='Number of steps'),
                 Item('return_to_start', label='Return to start'),
                 Item('move_lasers', label='Move lasers to end'),
                 Item('cooling_time', label='Cooling time (ms)'),
                 Item('move_camera', label='Move camera to end'),
                 Item('run', show_label=False)
                )
    
    def _run_fired(self):
        sqp = SequencePanel()
        
        print   'Running sequence from ', sqp.sequence_start.center, \
                ' to ', sqp.sequence_end.center, \
                ' in ', self.steps, 'steps'
        
        cp = ControlPanel()
        
        c = dac_control.DacController(Devices().dac_driver, Chip().mapping)
        # TODO: implement clear beforehand

        start_region = SequenceStart()
        end_region = SequenceEnd()
        sequence = c.build_sequence( start_region, end_region, self.steps, 
                                     return_to_start = self.return_to_start,
                                     print_output = Devices().dac_print_output )
        
        c.driver.write_frames(sequence)
        
        if self.move_lasers:
            wells = end_region.solution.wells(end_region)

            driver = lasers.Driver( Devices().lasers_driver_name )
            driver.set_solution( end_region.solution )
            driver.clear_all()
            driver.set_cooling_time(self.cooling_time)
            for region, position in wells:
                #print 'Putting a cooling location at', region, position
                driver.add_position(region, position)

class SequencePanel(SingletonHasTraits):
    
    sequence_base  = Instance(SequenceBase  , ())
    sequence_start = Instance(SequenceStart , ())
    sequence_end   = Instance(SequenceEnd   , ())
    sequence_run   = Instance(SequenceRun   , ())
    
    view = View( Group( \
                    Group( \
                        Item('sequence_base', style='custom', show_label=False),
                        label='Base solution', dock='tab'
                        ) ,\
                    Group( \
                        Item('sequence_start', style='custom', show_label=False),
                        label='Start', dock='tab'
                        ) ,\
                    Group( \
                        Item('sequence_end', style='custom', show_label=False),
                        label='End', dock='tab'
                        ) ,\
                    Group(
                        Item('sequence_run', style='custom', show_label=False),
                        label='Run', dock='tab'
                        ) \
                    )
                )

class SetupPanel(SingletonHasTraits):
    chip         = Instance(Chip, ())
    parameters   = Instance(Parameters, ())
    devices      = Instance(Devices, ())
    
    Chip()._trap_fired() # force fire to ensure update of dependents
    
    view = View( Group( Group(
                            Item('chip', show_label=False, style='custom'),
                            label='Chip'),
                        Group(
                            Item('parameters', style='custom', show_label=False),
                            label = 'Trap parameters'),
                        Group(
                            Item('devices', style='custom', show_label=False),
                            label = 'Devices') \
                      ) \
                )

class AcquisitionPanel(SingletonHasTraits):
    
    count_period = Float()
    frame_rate = Float()
    
    counting = Bool()
    
    view = View( Group( 
                    Group(
                        Item('count_period'), Item('counting', label='Enabled'),
                        label = 'Photon counting',
                        ),
                    Group(
                        Item('frame_rate'),
                        label = 'Imaging',
                        ) 
                    )   
                )
    
    @on_trait_change('counting')
    def handler(self, name, state):
        if state:
            print 'Starting counter task ' + Devices().counter_driver_name
            
            # make new driver
            drv = counters.Driver(Devices().counter_driver_name)
            
            # start display update thread
            self._photons_update_thread = PhotonsPlotUpdater(drv)
            self._photons_update_thread.start()
            
        else:
            print 'Stop counter task'
            
            # stop display update
            self._photons_update_thread.stop()
            
            # stop driver
            drv = counters.Driver(Devices().counter_driver_name)
            drv.stop()

class ManualPanel(SingletonHasTraits):
    trap_region  = Instance(TrapRegion, ())
    switches = Instance(SwitchPanel, ())
    lasers = Instance(LasersPanel, ())
    
    update_electrodes = Button('Electrodes')
    update_lasers = Button('Lasers')
    update_electrodes_and_lasers = Button('Electrodes and Lasers')
    
    view = View(Group( Group(Item('trap_region', style='custom', show_label=False),
                            label='Trap Region', dock='tab'),
                        Group(
                            Item('lasers', style='custom', show_label=False),
                            label='Lasers', dock='tab'
                        ),
                        Group(
                            Item('switches', style='custom', show_label=False),
                            label='Switches', dock='tab'
                        ),
                        Group(
                            Item('update_electrodes', show_label=False),
                            Item('update_lasers', show_label=False),
                            Item('update_electrodes_and_lasers', show_label=False),
                            label='Update',
                        ),
                    ),
               )
    
    def _update_lasers_fired(self):
        lp = LasersPanel()
        cp = ControlPanel()
        #solution_class = solutions.get_from_description( cp.manual_panel.trap_region.solution )
        #if solution_class is None: 
        #    print 'No solution found, not updating lasers'
        #    return
        #solution = solution_class( cp.setup_panel.parameters )
        
        print 'Updating lasers'
        driver = lasers.Driver( Devices().lasers_driver_name )
        driver.set_solution( TrapRegion().solution )
        driver.clear_all()
        driver.set_cooling_time(lp.cooling_time)
        for region, position in lp.get_laser_positions():
            driver.add_position(region, position)
        
    def _update_electrodes_fired(self):
        print 'Updating electrodes for '+Chip().trap+' region ' + TrapRegion().name + ' on device '+Devices().dac_driver
        
        cp = ControlPanel()
        c = dac_control.DacController(Devices().dac_driver, Chip().mapping)
        
        frames = c.build_single(cp.manual_panel.trap_region, print_output=Devices().dac_print_output)
        c.driver.write_frames(frames)
       
class ControlPanel(SingletonHasTraits):
    setup_panel = Instance(SetupPanel, ())
    manual_panel = Instance(ManualPanel, ())
    sequence_panel = Instance(SequencePanel, ())
    acquisition_panel = Instance(AcquisitionPanel, ())
    
    view = View(    Group( Item('setup_panel', style='custom', show_label=False), label = 'Setup', dock='tab'),
                    Group( Item('manual_panel', style='custom', show_label=False),label = 'Manual', dock='tab'),
                    Group( Item('sequence_panel', style='custom', show_label=False), label = 'Sequence', dock='tab'),
                    Group( Item('acquisition_panel', style='custom', show_label=False), label = 'Acquisition', dock='tab'),
                )
       
class DisplayPanel(SingletonHasTraits):

    solution_figure = Instance(Figure)
    solution_info = Str(font='courier')
    photons_figure = Instance(Figure)
    photons_plot_autoscale = Button('Auto-scale')
    
    def _photons_figure_default(self):
        figure = Figure()
        ax = figure.add_axes([0.08, 0.1, 0.9, 0.85])
        return figure
    
    def _solution_figure_default(self):
        figure = Figure()
        ax = figure.add_axes([0.08, 0.1, 0.9, 0.85])
        ax.grid(True)
        ax.set_ylabel('Voltage (V)')
        ax.set_xlabel('Position')
        return figure

    view = View(Group(
                    Group( 
                        Item('solution_figure', editor=MPLFigureEditor(), dock='vertical', height=.9, show_label=False),
                        Item('solution_info', style = 'readonly', height=.1, show_label=False),
                        label='Electrodes'),
                    Group(
                        Item('photons_figure', editor=MPLFigureEditor(), dock='vertical', height=.95, show_label=False),
                        Item('photons_plot_autoscale', height=.05, show_label=False),
                        label='Photons'),
                    layout='tabbed', springy=True
                    )
                )
    def _photons_plot_autoscale_fired(self):
        print 'Auto-scale photons plot'
        PhotonsPlotUpdater().update_all = True

class MainWindowHandler(Handler):
    def close(self, info, is_OK):
        
        print 'Shutting down threads'
        
        try:
            AcquisitionPanel()._photons_update_thread.stop()
        except AttributeError:
            pass
        
        print 'Shutting down driver processes'
        
        if counters.Driver.running : counters.Driver(Devices().counter_driver_name).stop()
        if lasers.Driver.running : lasers.Driver(Devices().lasers_driver_name).stop()

        print 'Saving settings'
        
        with open('saved_settings.pk', 'w') as f:
            pickle.dump( to_save, f)
        
        return True

class MainWindow(HasTraits):
    """ The main window, here go the instructions to create and destroy the application. """
    
    control_panel = Instance(ControlPanel)
    display_panel = Instance(DisplayPanel)
    
    def _display_panel_default(self):
        return DisplayPanel()

    def _control_panel_default(self):
        #return ControlPanel(figure=self.figure)
        return ControlPanel()

    view = View(HSplit(Item('display_panel', style='custom', width = .7),
                       Item('control_panel', style='custom', width = .3),
                       show_labels=False,
                      ),
                resizable=True,
                height=0.75, width=0.75,
                handler=MainWindowHandler(),
                buttons=NoButtons,
                title='Trap Controller')
    
    #TrapRegion().update_all() # Force update, needed because defaults may have been loaded

if __name__ == '__main__':
    MainWindow().configure_traits()
