import rpyc

conn = rpyc.connect('localhost', 18861, config = {"allow_public_attrs" : True, \
                                                       "allow_pickle" : True})
print conn.root.roi_names()

mean = 0
for name in conn.root.roi_names():
    mean += conn.root.roi_stats(name)['mean']

print mean
print
conn.close()