import threading
import time
from time import sleep

import wxversion
wxversion.select("2.8")
from traits.api import *
from traitsui.wx.editor import Editor
from traitsui.wx.basic_editor_factory import BasicEditorFactory
from traitsui.api import View, Item, Group, VGroup, HSplit, Handler, EnumEditor, RangeEditor, TableEditor, ButtonEditor, ObjectColumn, CheckListEditor, ListEditor, spring
from traitsui.menu import NoButtons
    
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle, Circle
from matplotlib.text import Text
from matplotlib import cm

from mpl_editor import MPLFigureEditor

from scipy import * 
from scipy.stats import norm

import cPickle as pickle
import cStringIO as StringIO
import numpy as np
import numbers
import wx
import sys
import matplotlib

import rpyc

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
            to_save[self.setting_key] = saved_settings[self.setting_key]
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
    clear_dac = Bool(False)
    counter_driver_name = String('nul')
    lasers_driver_name = String('nul')
    
    camera_server = String('nul')
    camera_port = Int(0)
    
    view = View( Item('counter_driver_name'), 
                 Item('lasers_driver_name'), 
                 Item('dac_driver'), 
                 Item('dac_print_output'), 
                 Item('clear_dac') )
    
    _dac_driver_default          = lambda self : SettingLoader('devices.dac_driver', 'nul')()
    _counter_driver_name_default = lambda self : SettingLoader('devices.counter_driver_name', 'nul')()
    _lasers_driver_name_default  = lambda self : SettingLoader('devices.lasers_driver_name', 'nul')()
    _camera_server_default = lambda self : SettingLoader('devices.camera_server', 'localhost')()
    _camera_port_default = lambda self : SettingLoader('devices.camera_port', 18861 )()
    @on_trait_change('dac_driver,counter_driver_name,lasers_driver_name,camera_server,camera_port')
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
            #print 'No trap saved. Assuming default ', self.available_names[0]
            #return self.available_names[0]
            default = solutions.solution_classes[0].for_traps
            if type(default) is type(()): default = default[0]
            print 'No trap saved. Assuming a default from available solution classes : ', default
            return default
    
    def _trap_fired(self):
        # update the available regions enum boxes elsewhere in program
        self.mapping = trap_mapper.TrapMapping(self.trap, MAP_FILE)
        
        names = self.mapping.get_region_names()
        
        LasersPanel().region_names = names
        SequenceStart().names = names
        SequenceEnd().names = names
        
        # update available solutions enum box
        available_solutions = [c.description for c in filter(lambda c : self.trap in c.for_traps , solutions.solution_classes)]
        if len(available_solutions) == 0 : print 'Error : no available solution files which will work with selected trap ', self.trap

        #print 'Available solutions             : ', [c.for_traps for c in solutions.solution_classes]
        #print 'Available solution descriptions : ', available_solutions
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
    vertical_compensation = Range(-10.0, 10.0, value = 0)
    horizontal_compensation = Range(-10.0, 10.0, value = 0)
    axial_compensation = Range(-10.0, 10.0, value = 0)
    
    _sub_electrode_allowed = True
    _width_allowed = False
    _vertical_compensation_allowed = False
    _horizontal_compensation_allowed = False
    _axial_compensation_allowed = False
    
    _solution_update_thread = SolutionPlotUpdater()
    
    view = View( Item('solution_description', label='Solution', editor=EnumEditor(name = 'solution_descriptions')),
                 Item('name', editor=EnumEditor(name = 'names'), label='Region name'),
                 Item('sub_electrode', label='Sub-electrode solution', enabled_when='_sub_electrode_allowed'),
                 Item('center', editor=RangeEditor(low_name = 'min_center', high_name = 'max_center', mode='slider')),
                 Item('width', enabled_when='_width_allowed', editor=RangeEditor(high_name = 'max_width', mode='slider')),
                 Item('vertical_compensation', enabled_when='_vertical_compensation_allowed', editor=RangeEditor(mode = 'slider', low=-10., high=10.)),
                 Item('horizontal_compensation', enabled_when='_horizontal_compensation_allowed', editor=RangeEditor(mode = 'slider', low=-10., high=10.)),
                 Item('axial_compensation', enabled_when='_axial_compensation_allowed', editor=RangeEditor(mode = 'slider', low=-10., high=10.)),
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
    def _update_adjustable_controls(self):
        "Disable width is not allowed by solution"
        
        self._width_allowed = 'width' in self.solution.adjustable
        self._vertical_compensation_allowed   = 'vertical_compensation' in self.solution.adjustable
        self._horizontal_compensation_allowed = 'horizontal_compensation' in self.solution.adjustable
        self._axial_compensation_allowed      = 'axial_compensation' in self.solution.adjustable
        
    @on_trait_change('name,solution_description,width,center,sym_scale,asym_scale,sub_electrode,vertical_compensation,horizontal_compensation,axial_compensation')
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
        
class CameraDisplayUpdater(threading.Thread):
    """ Update the camera display """
    
    _instance = None
    
    def __init__(self, address, port, frame_rate):
        super(CameraDisplayUpdater, self).__init__()
        
        print 'Initilized camera update thread'
        
        self.address = address
        self.port = port
        self.frame_rate = frame_rate
        
        self._stop = threading.Event()
        self.cp = ControlPanel()
        self.dp = DisplayPanel()
        self.update_all = True
        self.ax = self.dp.camera_figure.axes[0]    
        
        self.background = None 
        
        try:
            self.conn = rpyc.connect(self.address, self.port, config = {"allow_public_attrs" : True, \
                                                                        "allow_pickle" : True})
            self.server = self.conn.root
            #self.server = CameraConnectionInterface().root
        except:
            errormsg = 'Unable to connect to camera server at ' + self.address + ':' + str(self.port) + '\n' \
                       'Start server and re-enable display updating'
            print errormsg
            self.ax.clear()
            self.ax.text(0.5, 0.5, errormsg, horizontalalignment='center', verticalalignment='center', transform=self.ax.transAxes)
            wx.CallAfter(self.dp.camera_figure.canvas.draw)
            self.stop()
    
    def __new__(cls, *args, **kwargs):
        # make class a singelton
        if not cls._instance:
            cls._instance = super(CameraDisplayUpdater, cls).__new__(
                                cls, *args, **kwargs)
        return cls._instance
    
    def stop(self):
        print 'Stop camera update forced'
        self.conn.close()
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()
    
    def roi_label_position(self, roi):
        x,y,r = self.server.get_roi(roi)
        if y-r > 0 : 
            return (x,y-r)
        else :
            return (x,y+r)
    
    def update_stats(self):
        stats = self.server.image_stats()
        text = ''
        
        column_length = 25
        items_per_column = 3
        item_number = 0
        
        for k,v in stats.iteritems():
            item_text = str(k) + ' : ' + str(np.round(v, 3))
            item_number += 1
            if item_number == items_per_column : 
                item_text += '\n'
                item_number = 0
            else:
                item_text = item_text.ljust( column_length )
            text += item_text
        
        self.dp.camera_info = text
            
    def update_plot(self):
        """Fully update the plot"""
        
        self.ax.clear()
        data = np.load(StringIO.StringIO(self.server.scaled_image()))  
        self.image = self.ax.imshow(data, cmap=cm.get_cmap(self.dp.camera_colormap), vmin=0, vmax=256)
    
        #for roi in self.server.roi_list():
        #    print 'draw circle for roi at ', roi[0], roi[1], roi[2]
        self.circle_artists = [self.ax.add_artist( Circle( (roi[0], roi[1]), roi[2], color='g', fill=False ) ) for roi in self.server.roi_list()]
            #self.circles = self.ax.plot( roi[0], roi[1], 'b.' )
        self.update_all = False
        #wx.CallAfter(self.dp.camera_figure.canvas.draw)
            
    def _draw_only_image(self):
        
        self.dp.camera_figure.canvas.restore_region(self.background)
        try:
            self.ax.draw_artist(self.image)
        except RuntimeError:
            pass
        

        self.label_artists = [self.ax.add_artist( \
                                Text(x=self.roi_label_position(roi)[0], y=self.roi_label_position(roi)[1], color='g', backgroundcolor='w', \
                                    text=str( np.round(self.server.roi_stats(roi)['mean']) )) \
                            ) for roi in self.server.roi_names()]
                        
        if self.dp.camera_show_roi_circles:
            for artist in self.circle_artists:
                self.ax.draw_artist(artist)
        
        if self.dp.camera_show_roi_info:
            for artist in self.label_artists:
                self.ax.draw_artist(artist)
        
        self.dp.camera_figure.canvas.blit(self.ax.bbox)
        
    def update_data(self):
        """Only update the plot data. Won't rescale the plot"""
        
        if self.background == None:            
            wx.CallAfter(self.dp.camera_figure.canvas.draw)
            sleep(.1) #sometimes initial call to draw won't have finished yet
            self.background = self.dp.camera_figure.canvas.copy_from_bbox(self.ax.bbox) 
        try:
            data = np.load(StringIO.StringIO(self.server.scaled_image()))
            self.image.set_data(data)
            wx.CallAfter( self._draw_only_image )
        except EOFError:
            pass
        
    def run(self):
        while not self._stop.is_set():
            start = time.time()
            
            self.update_stats()
            
            if self.update_all:
                self.update_plot()
            else:
                self.update_data()
            
            # take into account that drawing takes some time ...
            if self.frame_rate == 0 : 
                period = 1.0
            else:
                period = 1.0 / self.frame_rate
            while time.time()-start < period:
                sleep(.01)
            
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
        
        c = dac_control.DacController(Devices().dac_driver, Chip().mapping, clear_dac=Devices().clear_dac)
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
    em_gain = Range(0.0, 200.0)
    autoscale_min = Range(0.0, 1.0)
    autoscale_max = Range(0.0, 1.0)
    counting = Bool()
    update_camera = Bool()
    manual_roi = Bool()
    roi_x = Float()
    roi_y = Float()
    roi_r = Float()
    
    view = View( Group( 
                    Group(
                        Item('count_period'), Item('counting', label='Enabled'),
                        label = 'Photon counting',
                        ),
                    Group(
                        Item('update_camera', label='Update display'),
                        Item('frame_rate', label='Frames / sec'),
                        Item('em_gain', label='EM gain'),
                        Item('autoscale_min', label='Autoscale min', editor=RangeEditor(mode='slider')),
                        Item('autoscale_max', label='Autoscale max', editor=RangeEditor(mode='slider')),
                        label = 'Imaging'
                        ),
                    Group(
                        Item('manual_roi', label='Set manual ROI'),
                        Item('roi_x', label='horizontal center'),
                        Item('roi_y', label='Vertical center'),
                        Item('roi_r', label='Radius'),
                        label = 'Region of interest'
                        )
                    )
                )
    
    # Load and save all the settings for the camera
    _frame_rate_default       = lambda self : SettingLoader('acqusition.camera.frame_rate', 1)()
    _em_gain_default          = lambda self : SettingLoader('acqusition.camera.em_gain', 0)()
    _autoscale_min_default    = lambda self : SettingLoader('acqusition.camera.autoscale_min', 0)()
    _autoscale_max_default    = lambda self : SettingLoader('acqusition.camera.autoscale_max', 0)()
    @on_trait_change('frame_rate, em_gain, autoscale_min, autoscale_max')
    def save_camera_settings(self, name, new):
        to_save['acqusition.camera.'+name] = new
    
    @on_trait_change('autoscale_min, autoscale_max')
    def update_autoscale_settings(self, name, new):
        try:
            conn = rpyc.connect(Devices().camera_server, Devices().camera_port, config = {"allow_public_attrs" : True, "allow_pickle" : True})
            conn.root.limit_autoscale(autoscale_min, autoscale_max)
            conn.close()
        except:
            print 'Connection to camera lost. Unable to change autoscale settings'
    
    @on_trait_change('frame_rate, em_gain')
    def update_camera_settings(self, name, new):
        try:
            conn = rpyc.connect(Devices().camera_server, Devices().camera_port, config = {"allow_public_attrs" : True, "allow_pickle" : True})
            conn.root.camera_setting(name, new)
            conn.close()
        except:
            print 'Connection to camera lost. Not able to set ', name, 'to', new
        
        # Also update how fast the gui update loop asks for new image.
        if name == 'frame_rate' : CameraDisplayUpdater._instance.frame_rate = new
    
    @on_trait_change('update_camera')
    def camera_handler(self, name, state):
        try:
            if state:
                address = Devices().camera_server
                port = Devices().camera_port
                self._camera_update_thread = CameraDisplayUpdater(address, port, self.frame_rate)
                self._camera_update_thread.start()
            else:
                self._camera_update_thread.stop()
        except AttributeError:
            pass
    
    @on_trait_change('manual_roi,roi_x,roi_y,roi_r')
    def roi_handler(self, name, state):
        try:
            conn = rpyc.connect(Devices().camera_server, Devices().camera_port, config = {"allow_public_attrs" : True, "allow_pickle" : True})
        except:
            print 'Can not connect to camera server to set roi'
            return
            
        print 'Sending updated ROI to server'
        if self.manual_roi:
            conn.root.set_roi('manual', self.roi_x, self.roi_y, self.roi_r)
        else:
            conn.root.delete_roi('manual')
        conn.close()
        
        # also need to trigger a full update of the plot so the circles can be drawn
        CameraDisplayUpdater._instance.update_all = True
    
    @on_trait_change('counting')
    def counting_handler(self, name, state):
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
        c = dac_control.DacController(Devices().dac_driver, Chip().mapping, clear_dac=Devices().clear_dac)
        
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
    camera_figure = Instance(Figure)
    camera_info = Str(font='courier')
    camera_autoscale = Button('Auto-scale')
    camera_show_roi_info = Bool()
    camera_show_roi_circles = Bool()
    camera_colormap = Enum('hot', 'gray', 'bone', 'Blues', 'ocean')
    
    def _camera_figure_default(self):
        figure = Figure()
        ax = figure.add_axes([0.08, 0.1, 0.9, 0.85])
        return figure
    
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
                    Group(
                        Item('camera_figure', editor=MPLFigureEditor(), dock='vertical', height=.95, show_label=False),
                        Item('camera_info', style = 'readonly', height=.1, show_label=False),
                        Group(
                            Item('camera_autoscale', height=.05, show_label=False),
                            Item('camera_show_roi_info', label = 'Show ROI label'),
                            Item('camera_show_roi_circles', label = 'Show ROI circles'),
                            Item('camera_colormap', label = 'Colormap'),
                            orientation = 'horizontal'
                        ),
                        label='Camera'),
                    layout='tabbed', springy=True
                    )
                )
    
    def _camera_colormap_fired(self):
        CameraDisplayUpdater._instance.update_all = True            
    
    def _photons_plot_autoscale_fired(self):
        print 'Auto-scale photons plot'
        PhotonsPlotUpdater().update_all = True
        
    def _camera_autoscale_fired(self):
        print 'Auto-scale camera display'
        try:
            conn = rpyc.connect(Devices().camera_server, Devices().camera_port, config = {"allow_public_attrs" : True, "allow_pickle" : True})
            conn.root.autoscale()
            conn.close()
            
            CameraDisplayUpdater._instance.update_all = True
        except:
            print 'Connection to camera lost or camera error. Not able to re-autoscale'

class MainWindowHandler(Handler):
    def close(self, info, is_OK):
        
        print 'Shutting down threads'
        
        try:
            AcquisitionPanel()._photons_update_thread.stop()
            CameraDisplayUpdater._instance.stop()
        except AttributeError:
            pass
        
        print 'Shutting down driver processes'
        
        if counters.Driver.running : counters.Driver(Devices().counter_driver_name).stop()
        if lasers.Driver.running : lasers.Driver(Devices().lasers_driver_name).stop()

        print 'Saving', len(to_save), 'settings ...'
        
        with open('saved_settings.pk', 'w') as f:
            pickle.dump( to_save, f)
        print 'Done saving'

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
