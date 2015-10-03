#!/usr/bin/env python

import numpy as np
import healpy as hp
import matplotlib.pyplot as plt
from settings import settings
from pysimulators import ProjectionOperator
from pysimulators.sparse import FSRMatrix
from pysimulators import BeamGaussian
from pysimulators.interfaces.healpy import SceneHealpixCMB
from pysimulators.interfaces.healpy import HealpixConvolutionGaussianOperator
import sys, copy
import qubic
import simulation.pointing.generate_pointing as gen_p

#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*
# Simulating the time-ordered data for a pencil beam
#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*

def simulate_tod(settings=None):
    if settings is None:
        from settings import settings

    #*#*#* Generating the time-ordered pointing #*#*#*
    
    if settings.generate_pointing:
        import pointing_settings
        v = gen_p.generate_pointing(pointing_settings.settings)
    elif settings.load_pointing:
        v = np.load(settings.data_folder + "pointing_0.npy") 
    else:
        print "Not loaded any pointing. Exiting"
        sys.exit()
    
    #*#*#* Generating the time-ordered set of hit pixels from the pointing #*#*#*

    hit_pix = hp.vec2pix(settings.nside, v[...,0], v[...,1], v[...,2])
    
    #*#*#* Building the projection matrix P #*#*#*

    nsamples = hit_pix.size
    npix = hp.nside2npix(settings.nside)
    if settings.do_pol:
        matrix = FSRBlockMatrix((nsamples, npix*3), (1, 3), ncolmax=1, dtype=np.float32, dtype_index=np.int32)
        matrix.data.index[:, 0] = pix
        matrix.data.value[:, 0, 0, 0] = 0.5
        matrix.data.value[:, 0, 0, 1] = 0.5 * np.cos(2*pol_dir)
        matrix.data.value[:, 0, 0, 2] = 0.5 * np.sin(2*pol_dir)
    else:
        matrix = FSRMatrix((nsamples, npix), ncolmax=1, dtype=np.float32,
                               dtype_index = np.int32)
        matrix.data.index = hit_pix[..., None]
        matrix.data.value = 1
    P = ProjectionOperator(matrix)#, shapein = npix, shapeout = nsamples)        
    
    #*#*#* Loading the input sky map #*#*#*
    sky_map = load_input_map(settings) 

    #Generating the time ordered signal
    signal = P(sky_map)

    #Generating the hitmap
    hitmap = P.T(np.ones(nsamples, dtype=np.float32))
    if settings.do_pol:
        hitmap = hitmap[:, 0]*2
   
    #Generating the scan patch
    mask = hitmap > 0#np.full(hitmap.size, False, dtype = bool)
    #mask[hitmap > 0] = True
    scanned_map = np.full(hitmap.size, np.nan)
    scanned_map[mask] = sky_map[mask]

    if settings.display_scanned_map:
        hp.mollzoom(hitmap)
        plt.show()
        hp.mollzoom(scanned_map)
        plt.show()
    
    if settings.write_scanned_map:
        hp.write_map(settings.data_folder + "hitmap.fits", hitmap)
        hp.write_map(settings.data_folder + "scanned_map.fits", scanned_map)

    if settings.write_signal:
        np.save(settings.data_folder + "signal", signal)
    elif settings.pipe_with_map_maker:
        return signal, P

#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*
# Simulating the time-ordered data for a pencil beam
#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*

def simulate_beam_tod(settings=None):
    if settings is None:
        from settings import settings
    #Generating the pointing
    from simulation.scanning.beam_kernel import beam_kernel, del_beta
    import pointing_settings
    beta_0 = pointing_settings.settings.beta_0
    beta = beta_0 + del_beta
    
    sky_map = hp.read_map(settings.input_map_path)
    
    #Building the projection matrix P
    nsamples = int(1000.0*pointing_settings.settings.t_flight/pointing_settings.settings.t_sampling) 
    npix = hp.nside2npix(settings.nside)
    matrix = FSRMatrix((nsamples, npix), ncolmax=1, dtype=np.float32,
                           dtype_index = np.int32)
    matrix.data.value = 1
    P = ProjectionOperator(matrix, shapein = npix, shapeout = nsamples)        
     
    signal = np.zeros(nsamples)
    
    for i in range(beta.size):
        v = gen_p.generate_pointing(pointing_settings.settings, beta[i])
        hit_pix = hp.vec2pix(settings.nside, v[...,0], v[...,1], v[...,2])
    
        matrix.data.index = hit_pix[..., None]
        if i is beta.size/2:
            matrix_central = copy.deepcopy(matrix)
        P.matrix = matrix
        #Generating the time ordered signal
        signal += np.convolve(P(sky_map), beam_kernel.T[i], mode = 'same')

    beam_sum = np.sum(beam_kernel)
    signal/=beam_sum

    P.matrix = matrix_central
    
    #Generating the hitmap
    hitmap = P.T(np.ones(nsamples, dtype=np.float32))
   
    #Generating the scan patch
    mask = np.full(hitmap.size, False, dtype = bool)
    mask[hitmap > 0] = True
    scanned_map = np.full(hitmap.size, np.nan)
    scanned_map[mask] = sky_map[mask]

    plt.figure()
    plt.plot(signal)
    plt.show()

    np.save("signal_test", signal)

    if settings.display_scanned_map:
        hp.mollzoom(hitmap)
        plt.show()
        hp.mollzoom(scanned_map)
        plt.show()
    
    if settings.write_scanned_map:
        hp.write_map(settings.data_folder + "hitmap.fits", hitmap)
        hp.write_map(settings.data_folder + "scanned_map.fits", scanned_map)

    if settings.write_signal:
        np.save(settings.data_folder + "signal", signal)
    elif settings.pipe_with_map_maker:
        return signal, P

def load_input_map(settings):
    if settings.do_pol:
        sky_map = hp.read_map(settings.input_map, field = (0,1,2))
    else:
        sky_map = hp.read_map(settings.input_map)
    nside = hp.get_nside(sky_map)

    if nside is not settings.nside:
        print "NSIDE of loaded map and settings do not match"
        sys.exit()
    return sky_map

"""

def get_conversion_factor(a):
    scene = SceneHealpixCMB(NSIDE, absolute = a)
    return scene.get_unit_conversion_operator(nu)



def get_unbeamed_absolute_sky():
    conversion = get_conversion_factor(True)
    sky_abs = conversion(T) + sky
    return sky_abs*nu*0.25

sky_power = get_unbeamed_absolute_sky()

def get_convolved():
    convolved = hp.smoothing(sky, fwhm = np.radians(beam_fwhm/60))
    #conversion = get_conversion_factor(True)
    #return conversion(T) + convolved
    return T + convolved

sky_power = get_convolved()


def get_beam_weight():
    beam = BeamGaussian(np.radians(beam_fwhm*20/60.0))
    beam_healpix = beam.healpix(NSIDE)
    return np.sum(beam_healpix)

"""

if __name__=="__main__":
    from settings import settings
    if settings.do_beam_kernel:
        simulate_beam_tod(settings)
    else:
        simulate_tod(settings)
