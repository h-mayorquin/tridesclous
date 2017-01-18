from tridesclous import *
from tridesclous.online import *

import  pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
import pyacq
from pyacq.viewers import QOscilloscope, QTimeFreq


import numpy as np
import time
import os
import shutil




def setup_catalogue():
    if os.path.exists('test_onlinepeeler'):
        shutil.rmtree('test_onlinepeeler')
    
    dataio = DataIO(dirname='test_onlinepeeler')
    
    localdir, filenames, params = download_dataset(name='olfactory_bulb')
    filenames = filenames[:1] #only first file
    dataio.set_data_source(type='RawData', filenames=filenames, **params)
    channel_group = {0:{'channels':[5, 6, 7, 8]}}
    dataio.set_channel_groups(channel_group)
    
    
    catalogueconstructor = CatalogueConstructor(dataio=dataio)

    catalogueconstructor.set_preprocessor_params(chunksize=1024,
            memory_mode='memmap',
            
            #signal preprocessor
            highpass_freq=300,
            backward_chunksize=1280,
            
            #peak detector
            peakdetector_engine='numpy',
            peak_sign='-', relative_threshold=7, peak_span=0.0005,
            )
    
    t1 = time.perf_counter()
    catalogueconstructor.estimate_signals_noise(seg_num=0, duration=10.)
    t2 = time.perf_counter()
    print('estimate_signals_noise', t2-t1)
    
    t1 = time.perf_counter()
    catalogueconstructor.run_signalprocessor()
    t2 = time.perf_counter()
    print('run_signalprocessor', t2-t1)

    
    t1 = time.perf_counter()
    catalogueconstructor.extract_some_waveforms(n_left=-25, n_right=35,  nb_max=10000)
    t2 = time.perf_counter()
    print('extract_some_waveforms', t2-t1)
    print(catalogueconstructor)
        

    # PCA
    t1 = time.perf_counter()
    catalogueconstructor.project(method='pca', n_components=12, batch_size=16384)
    t2 = time.perf_counter()
    print('project', t2-t1)
    
    # cluster
    t1 = time.perf_counter()
    catalogueconstructor.find_clusters(method='kmeans', n_clusters=13)
    t2 = time.perf_counter()
    print('find_clusters', t2-t1)
    
    # trash_small_cluster
    catalogueconstructor.trash_small_cluster()


    catalogueconstructor = CatalogueConstructor(dataio=dataio)
    app = pg.mkQApp()
    win = CatalogueWindow(catalogueconstructor)
    win.show()
    app.exec_()

    


def test_OnlinePeeler():
    dataio = DataIO(dirname='test_onlinepeeler')
    catalogue = dataio.load_catalogue()
    
    #~ def print_dict(d):
        #~ for k, v in d.items():
            #~ if type(v) is dict:
                #~ print('k', k, 'dict')
                #~ print_dict(v)
            #~ else:
                #~ print('k', k, type(v))
        
    #~ print_dict(catalogue)
    
    #~ from pyacq.core.rpc.serializer import MsgpackSerializer
    #~ serializer = MsgpackSerializer()
    #~ serializer.dumps(catalogue)
    #~ exit()
    
    sigs = dataio.datasource.array_sources[0]
    
    sigs = sigs.astype('float32')
    sample_rate = dataio.sample_rate
    in_group_channels = dataio.channel_groups[0]['channels']
    #~ print(channel_group)
    
    chunksize = 1024
    
    
    # Device node
    man = pyacq.create_manager(auto_close_at_exit=True)
    ng0 = man.create_nodegroup()
    #~ ng0 = None
    ng1 = man.create_nodegroup()
    #~ ng1 = None
    
    
    dev = make_pyacq_device_from_buffer(sigs, sample_rate, nodegroup=ng0, chunksize=chunksize)
    

    
    app = pg.mkQApp()
    
    dev.start()
    
    # Node QOscilloscope
    oscope = QOscilloscope()
    oscope.configure(with_user_dialog=True)
    oscope.input.connect(dev.output)
    oscope.initialize()
    oscope.show()
    oscope.start()
    oscope.params['decimation_method'] = 'min_max'
    oscope.params['mode'] = 'scan'    

    # Node Peeler
    if ng1 is None:
        peeler = OnlinePeeler()
    else:
        ng1.register_node_type_from_module('tridesclous.online', 'OnlinePeeler')
        peeler = ng1.create_node('OnlinePeeler')
    
    peeler.configure(catalogue=catalogue, in_group_channels=in_group_channels, chunksize=chunksize)
    
    peeler.input.connect(dev.output)
    stream_params = dict(protocol='tcp', interface='127.0.0.1', transfermode='plaindata')
    peeler.outputs['signals'].configure(**stream_params)
    peeler.outputs['spikes'].configure(**stream_params)
    peeler.initialize()
    peeler.start()
    
    # Node traceviewer
    tviewer = OnlineTraceViewer()
    tviewer.configure(catalogue=catalogue)
    tviewer.inputs['signals'].connect(peeler.outputs['signals'])
    tviewer.inputs['spikes'].connect(peeler.outputs['spikes'])
    tviewer.initialize()
    tviewer.show()
    tviewer.start()
    tviewer.params['xsize'] = 3.
    tviewer.params['decimation_method'] = 'min_max'
    tviewer.params['mode'] = 'scan'
    #~ tviewer.params['mode'] = 'scroll'
    
    tviewer.auto_gain_and_offset(mode=1)
    #~ tviewer.gain_zoom(.3)
    tviewer.gain_zoom(.1)
    
    
    
    def ajust_yrange():
        oscope.auto_gain_and_offset(mode=1)
    
    timer = QtCore.QTimer(interval=1000, singleShot=True)
    timer.timeout.connect(ajust_yrange)
    timer.start()
    
    def terminate():
        dev.stop()
        oscope.stop()
        peeler.stop()
        tviewer.stop()
        app.quit()
    
    app.exec_()
    
    
    
    
    
    
if __name__ =='__main__':
    #~ setup_catalogue()
    
    test_OnlinePeeler()

