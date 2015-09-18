#! /usr/bin/env python 

import numpy as np
import healpy as hp
import matplotlib.pyplot as plt
import pyoperators as po
import simulation.lib.plotting.vector_plot_3d as vec

"""
def draw(u, R):
    fig = plt.figure()
    ax = fig.gca(projection = '3d')
    vec.draw_axes(ax, length = 1)
    v = R*u
    vec.draw_vector(u, ax, color = 'g')
    if len(v.shape) == 1:
        vec.draw_vector(v, ax, color = 'r')
    else:
        for vt in v:
            vec.draw_vector(vt, ax, color = 'r')
    plt.show()
"""

def calculate_params(settings = None):
    if settings ==None:
        from settings import settings
    if settings.mode == 1:
        settings.t_spin = 360.0*60.0*np.sin(settings.beta)*settings.t_sampling/1000.0/settings.theta_co
        settings.t_prec = 360.0*60.0*np.sin(settings.alpha)*settings.t_spin/settings.theta_cross

    if settings.mode == 2:
        settings.theta_cross = 360.0*60.0*np.sin(settings.alpha)*settings.t_spin/settings.t_prec
        settings.theta_co = 360*60*np.sin(settings.beta)*settings.t_sampling/1000.0/settings.t_spin

    return settings

def display_params(settings):
    print "alpha : ", np.degrees(settings.alpha), " degrees"
    print "beta : ", np.degrees(settings.beta), " degrees"
    print "T flight : ", settings.t_flight/60.0/60.0, "hours"
    print "T precession : ", settings.t_prec/60.0/60.0, "hours"
    print "T spin : ", settings.t_spin, " seconds"
    print "T sampling : ", settings.t_sampling, " milli-seconds"
    print "Scan frequency : ", 1000.0/settings.t_sampling, "Hz"
    print "Theta co : ", settings.theta_co, " arcmin"
    print "Theta cross : ", settings.theta_cross, " arcmin"
    print "Map resolution : ", hp.nside2resol(settings.nside, arcmin = True), " arcmin"
    print "Max pix radius : ", np.degrees(hp.max_pixrad(settings.nside))*60.0, "arcmin"

def generate_pointing(settings = None):
    if settings == None:
        from settings import settings
    settings = calculate_params(settings)
    display_params(settings)

    u_init = np.array([np.cos(settings.beta), 0.0, np.sin(settings.beta)])
    n_slices = int(1000*settings.t_flight/settings.t_sampling)
    print "No. of time steps : ", n_slices
    print "~Memory usage : ", 10*n_slices*8.0/1024/1024/1024, " GB" 
    t_steps = 0.001*settings.t_sampling*np.arange(n_slices)
    w_prec = 2*np.pi/settings.t_prec
    w_spin = 2*np.pi/settings.t_spin
    R = po.Rotation3dOperator("XY'X''", w_prec*t_steps, -1.0*np.full(n_slices, settings.alpha), w_spin*t_steps)
    v = R*u_init
    if settings.write_pointing:
        np.save(settings.write_folder + "pointing_0", v)
    else:
        return v

if __name__ == "__main__":
    from settings import settings
    generate_pointing(settings)
