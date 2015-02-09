# Copyright 2011 Marco Conti

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#   http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import odf.opendocument
from odf.table import *
from odf.text import P
from collections import defaultdict

DEBUG = False

class ODSReader:

    # loads the file
    def __init__(self, filename):
        self.filename = filename
        self.doc = odf.opendocument.load(filename)
        self.SHEETS = {}
        for sheet in self.doc.spreadsheet.childNodes:
            self.readSheet(sheet)

    # reads a sheet in the sheet dictionary, storing each sheet as an array (rows) of arrays (columns)
    def readSheet(self, sheet):
        try:
            name = sheet.getAttribute("name")
        except ValueError:
            return
            
        print 'Found sheet named',name
        rows = sheet.getElementsByType(TableRow)
        arrRows = []

        # for each row
        for row in rows:
            row_comment = ""
            arrCells = []
            cells = row.getElementsByType(TableCell)

            # for each cell
            for cell in cells:
                # repeated value?
                repeat = cell.getAttribute("numbercolumnsrepeated")
                if(not repeat):
                    repeat = 1

                ps = cell.getElementsByType(P)
                textContent = ""
                
                #print 'cell=',cell.getAttribute('value')
                
                #rdg:  Not sure why I need to do this fix
                #      perhaps open document format changed?
                #      with formulea cells, data is not defined somehow
                #      but I can get the resulting data with 'value' attribute
                for p in ps:
                    try:
                        text = str(p.firstChild.data)
                    except AttributeError:
                        text = str(cell.getAttribute('value'))
                    textContent = textContent + text
                
                # for each text node
                #for p in ps:
                    #print p.getAttribute('value')
                #    text = str(p.firstChild)
                #    textContent = textContent + text
                    #print textContent
                    
                if(textContent):
                    if(textContent[0] != "#"): # ignore comments cells
                        for rr in range(int(repeat)): # repeated?
                            arrCells.append(textContent)

                    else:
                        row_comment = row_comment + textContent + " ";

            # if row contained something
            if(len(arrCells)):
                #print arrCells
                arrRows.append(arrCells)

            #else:
            #   print "Empty or commented row (", row_comment, ")"

        self.SHEETS[name] = arrRows

    # returns a sheet as an array (rows) of arrays (columns)
    def getSheet(self, name):
        return self.SHEETS[name]


def get_trap_names(filename):
    "Available traps found by any any sheets with Electrode as first column header"
    try:
        reader = ODSReader(filename)
    except IOError:
        raise ValueError(filename + ' mapping file not found')
    return filter(lambda s: reader.SHEETS[s][0][0] == 'Electrode', reader.SHEETS)

class TrapMapping(object):
    """ Represents the particular trap being used.
        Contains a maping of electrode to dac number and channel. This is generated from an .ods spreadsheet supplied on init.
    """
    
    def __init__(self, trap_name, filename):
        self.trap_name = trap_name
        
        try:
            self.reader = ODSReader(filename)
        except IOError:
            raise ValueError(filename + ' mapping file not found')
        try:
            self.trap_sheet = self.reader.getSheet(trap_name)
        except (KeyError, IOError):
            raise ValueError(trap_name + ' not a valid trap name')
                
        try:
            # Get the column headers
            electrode_col = self.trap_sheet[0].index('Electrode')
            DAC_col = self.trap_sheet[0].index('DAC Chip')
            DAC_ch_col = self.trap_sheet[0].index('DAC Ch')
            DSUB_col = self.trap_sheet[0].index('DSUB')
            DSUB_pin_col = self.trap_sheet[0].index('DSUB Pin')
        except:
            raise ValueError(trap_name + ' sheet does not contain the required columns.')
        
        electrode_map = {} # mapping of electrode to channel
        electrode_info = defaultdict( list ) # extra info such as controller DSUB
        for c in self.trap_sheet:
            if c[electrode_col].isdigit() or c[electrode_col][1:].isdigit(): #to support electrodes with letter prefix
                try:
                    electrode = c[electrode_col]
                    dac_chip = int(c[DAC_col])
                    dac_ch = int(c[DAC_ch_col])
                    dsub = int(c[DSUB_col])
                    dsub_pin = int(c[DSUB_pin_col])
                except IndexError:
                    continue
                except ValueError:
                    continue
                electrode_info[electrode].append(
                    {'DSUB' : dsub, 'DSUB_pin' : dsub_pin} )
                control_tuple = (dac_chip-1, dac_ch)
                if electrode_map.has_key(electrode):
                    if DEBUG: print "Electrode "+str(electrode)+" already exists" 
                    existing = electrode_map[electrode]
                    
                    # If just an electrode number tupple, put into a list of tuples
                    if type(existing[0]) == type(0): 
                        existing = (existing,)
                    
                    existing = list(existing)
                    existing.append( control_tuple )
                    electrode_map[electrode] = tuple(existing)
                    
                else:
                    electrode_map[electrode] = control_tuple
    
        self.electrode_map = electrode_map
        self.electrode_info = electrode_info
        if DEBUG: print( 'Loaded %i electrode mappings for trap %s' % (len(electrode_map), trap_name) )
        if DEBUG: print( electrode_map )
    
    def get_electrode_locations(self, region):
        try:
            xcol = self.trap_sheet[0].index('Position X')
            ycol = self.trap_sheet[0].index('Position Y')
        except ValueError:
            print 'No position info for this trap'
            return None
            
        locations = []
        for row in self.trap_sheet[1:]:
            prefix = row[0][0]
            if prefix != region: continue
            locations.append( (row[0], int(row[xcol]), int(row[ycol])) )
        return locations

    def get_region_names(self):
        # find available regions, defined by upper case electrode prefixes
        regions = set()
        for row in self.trap_sheet[1:]:
            prefix = row[0][0]
            if prefix.isupper():
                regions.add(prefix)
        return list(regions)
        
    def get_xlimits(self, trapregion):
        # find the min and max center positions for the region
        try:
            col = self.trap_sheet[0].index('Position X')
        except ValueError:
            return
        # has position info'
        positions = []
        error_rows = []
        for i, row in enumerate(self.trap_sheet[1:]):
            if len(row) > col and row[0].startswith(trapregion):
                try:
                    positions.append(float(row[col]))
                except ValueError:
                    error_rows.append(i)
        if len(error_rows) > 0 : print 'Errors reading spreadsheet rows ', error_rows
        try:
            limits = (min(positions), max(positions))
        except ValueError:
            return (-1,1)
        return limits

