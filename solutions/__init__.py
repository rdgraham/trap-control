__all__ = ['hoa', 'hoa2']


# finds all solution classes in package and makes them available in list solution_classes
import pyclbr
_classes = []
solution_classes = []
for module in __all__:
    _classes = _classes + pyclbr.readmodule('solutions.'+module).values()
for klass in _classes: 
    try:
        if klass.super[0].name != 'Solution' :
            continue
    except AttributeError:
        continue
    module = __import__(klass.module, fromlist=[klass.name])
    solution_classes.append( getattr( module , klass.name) ) 
    print 'Found solution class ', klass.name
    
def get_from_description(s):
    for c in solution_classes:
        if c.description == s:
            return c




