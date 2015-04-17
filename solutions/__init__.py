__all__ = ['hoa', 'hoa2']

# finds all solution classes in package and makes them available in list solution_classes
import pyclbr
_classes = []
solution_classes = []

def has_parent(klass, parent_name):
    "Recursive method to determine if a class inherits at some point from a named class"
    if klass == '' or klass == 'object': return False
    if parent_name in [k.name if isinstance(k, pyclbr.Class) else '' for k in klass.super] : return True
    for k in klass.super:
        if has_parent(k, parent_name) : return True
    return False

for module in __all__:
    _classes = _classes + pyclbr.readmodule('solutions.'+module).values()
for klass in _classes: 
    if not has_parent(klass, 'Solution'): continue
    module = __import__(klass.module, fromlist=[klass.name])
    solution_classes.append( getattr( module , klass.name) ) 
    print 'Found solution class ', klass.name
    
def get_from_description(s):
    for c in solution_classes:
        if c.description == s:
            return c
