import rpyc

conn = rpyc.connect('localhost', 18861, config = {"allow_public_attrs" : True, \
                                                       "allow_pickle" : True})
mean = conn.root.roi_stats('manual')['mean']
print mean
conn.close()