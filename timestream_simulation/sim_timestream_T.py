#!/usr/bin/env python

import numpy as np
import healpy as hp
import matplotlib.pyplot as plt
import sys
import copy
import os
import importlib
import time
from memory_profiler import profile
from simulation.lib.quaternion import quaternion
from pysimulators import ProjectionOperator
from pysimulators.sparse import FSRMatrix
#from simulation.beam.convolution_kernel import get_beam
from simulation.beam.beam_kernel_new import get_beam
from simulation.lib.utilities.time_util import get_time_stamp
import simulation.lib.numericals.filters as filters

class Bolo:

    def __init__(self, bolo_name):
        self.bolo_params = importlib.import_module("simulation.timestream_simulation.bolo_params." + bolo_name).bolo_params
        #Getting the beam profile and the del_beta
        self.beam_kernel, self.del_beta = get_beam(beam_params, self.bolo_params)
        self.axis_spin, self.axis_prec, self.axis_rev = self.get_initial_axes()

#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*
# Simulating the time-ordered data for a given bolo with any beam
#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*

    #@profile
    def simulate_timestream(self, segment, sky_map, out_dir):

        sys.stdout.flush()
        time_segment_start = time.time()

        t_start = scan_params.t_segment*segment
        rot_qt = self.generate_quaternion(t_start)

        pad = self.del_beta.size/2

        nsamples = int(1000.0*scan_params.t_segment/scan_params.t_sampling)*scan_params.oversampling_rate + 2*pad
        npix = hp.nside2npix(scan_params.nside)

        matrix = FSRMatrix((nsamples, npix), ncolmax=1, dtype=np.float32, dtype_index = np.int32)
        matrix.data.value = 1

        P = ProjectionOperator(matrix, shapein=npix, shapeout=nsamples)        

        signal = np.zeros(nsamples - 2*pad)

        for del_beta in self.del_beta:
            v_init = self.get_initial_vec(del_beta)
            v = quaternion.transform(rot_qt, v_init)
            hit_pix = hp.vec2pix(scan_params.nside, v[...,0], v[...,1], v[...,2])
            P.matrix.data.index = hit_pix[...,None]
            sys.stdout.flush()
            if del_beta==0.0:
                if pad==0:
                    v_central = v[::scan_params.oversampling_rate]
                else:
                    v_central = v[pad:-pad][::scan_params.oversampling_rate]
            #Generating the time ordered signal
            signal_int = P(sky_map.T)
            if scan_params.do_filtering:
                signal_int = filters.filter_butter(signal_int, 1000.0/scan_params.t_sampling, 150.0)

            if pad==0: 
                signal += signal_int
            else:
                signal += np.convolve(signal_int, self.beam_kernel[i], mode = 'valid')


        beam_sum = np.sum(self.beam_kernel)
        signal/=beam_sum

        hitmap = self.get_hitmap(v_central)

        np.save(os.path.join(out_dir, "vector"), v_central)
        np.save(os.path.join(out_dir, "ts_signal"), signal[::scan_params.oversampling_rate])

        time_segment_end = time.time() 
        print "Time taken for scanning segment :", (time_segment_end - time_segment_start), "seconds"

        return hitmap

    #@profile
    def get_hitmap(self, v):
        nsamples = v.shape[0]
        npix = hp.nside2npix(scan_params.nside)
        matrix = FSRMatrix((nsamples, npix), ncolmax=1, dtype=np.float32, dtype_index = np.int32)
        matrix.data.value = 1
        P = ProjectionOperator(matrix, shapein=npix, shapeout=nsamples)
        hit_pix = hp.vec2pix(scan_params.nside, v[...,0], v[...,1], v[...,2])
        matrix.data.index = hit_pix[..., None]
        P.matrix = matrix
        hitmap = P.T(np.ones(nsamples, dtype=np.float32))

        return hitmap
    
    #@profile
    def generate_quaternion(self, t_start):

        pad = self.del_beta.size/2
        n_steps = int(1000.0*scan_params.t_segment/scan_params.t_sampling)*scan_params.oversampling_rate + 2*pad
        t_steps = t_start + 0.001*(scan_params.t_sampling/scan_params.oversampling_rate)*np.arange(-pad, n_steps-pad)

        w_spin = -2*np.pi/scan_params.t_spin
        w_prec = -2*np.pi/scan_params.t_prec
        w_rev = -2*np.pi/scan_params.t_year

        r_total = quaternion.multiply(quaternion.make_quaternion(w_rev*t_steps, self.axis_rev), quaternion.multiply(quaternion.make_quaternion(w_prec*t_steps, self.axis_prec), quaternion.make_quaternion(w_spin*t_steps, self.axis_spin)))

        return r_total


    def get_initial_vec(self, del_beta):
        alpha = np.deg2rad(scan_params.alpha)
        beta = np.deg2rad(scan_params.beta)
        del_x = np.deg2rad(self.bolo_params.del_x/60.0)
        del_y = np.deg2rad(self.bolo_params.del_y/60.0)
        del_beta_rad = np.deg2rad(del_beta/60.0)

        u_view = np.array([np.cos(alpha + beta + del_beta_rad), 0.0, np.sin(alpha + beta + del_beta_rad)])

        return u_view

    def get_initial_axes(self):
        alpha = np.deg2rad(scan_params.alpha)
        beta = np.deg2rad(scan_params.beta)

        axis_spin = np.array([np.cos(alpha), 0.0, np.sin(alpha)])
        axis_prec = np.array([1.0, 0.0, 0.0])
        axis_rev = np.array([0.0, 0.0, 1.0])

        return axis_spin, axis_prec, axis_rev


def calculate_params():
    if scan_params.mode is 1:
        scan_params.t_spin = 360.0*60.0*np.sin(np.radians(scan_params.beta))*scan_params.t_sampling/1000.0/scan_params.theta_co
        scan_params.t_prec = 360.0*60.0*np.sin(np.radians(scan_params.alpha))*scan_params.t_spin/scan_params.theta_cross

    if scan_params.mode is 2:
        scan_params.theta_cross = 360.0*60.0*np.sin(np.radians(scan_params.alpha))*scan_params.t_spin/scan_params.t_prec
        scan_params.theta_co = 360*60*np.sin(np.radians(scan_params.beta))*scan_params.t_sampling/1000.0/scan_params.t_spin

    beam_params.beam_resolution = scan_params.theta_co/scan_params.oversampling_rate
    scan_params.scan_resolution = scan_params.theta_co/scan_params.oversampling_rate

def display_params():
    print "alpha : ", scan_params.alpha, " degrees"
    print "beta : ", scan_params.beta, " degrees"
    print "Mode :", scan_params.mode
    print "T flight : ", scan_params.t_flight/60.0/60.0, "hours /", scan_params.t_flight/60.0/60.0/24, "days"
    print "T segment :", scan_params.t_segment/60.0/60.0, "hours /", scan_params.t_segment/60.0/60.0/24, "days"
    print "T precession : ", scan_params.t_prec/60.0/60.0, "hours"
    print "T spin : ", scan_params.t_spin, " seconds"
    print "T sampling : ", scan_params.t_sampling, " milli-seconds"
    print "Scan frequency : ", 1000.0/scan_params.t_sampling, "Hz"
    print "Theta co : ", scan_params.theta_co, " arcmin"
    print "Theta cross : ", scan_params.theta_cross, " arcmin"
    print "Scan resolution for beam integration :", scan_params.scan_resolution, "arcmin"
    print "Beam resolution :", beam_params.beam_resolution, "arcmin"
    print "Pixel size for NSIDE =", scan_params.nside, ":", hp.nside2resol(scan_params.nside, arcmin=True), "arcmin"
    n_steps = int(1000*scan_params.t_segment/scan_params.t_sampling)*scan_params.oversampling_rate
    print "#Samples per segment : ", n_steps
    print "Size of signal array : ", n_steps*8.0/1024/1024, "MB"
    print "Estimated use of memory : ", 15*n_steps*8.0/1024/1024, "MB"

def get_scanned_map(sky_map, hitmap):
    valid = hitmap>0
    sky_map[...,~valid] = np.nan
    return sky_map

def make_output_dirs(out_dir, bolo_names, num_segments):
    os.makedirs(out_dir)
    for bolo in bolo_names:
        os.makedirs(os.path.join(out_dir, bolo))
        for segment in range(num_segments):
            segment_name = str(segment+1).zfill(4)
            os.makedirs(os.path.join(out_dir, bolo, segment_name))
            

def run_serial():
    num_segments = int(scan_params.t_flight/scan_params.t_segment)
    sky_map = hp.read_map(scan_params.input_map) 
    hitmap = np.zeros(hp.nside2npix(scan_params.nside))

    time_stamp = get_time_stamp()
    out_dir = os.path.join(scan_params.global_output_dir, "scanning", time_stamp)
    make_output_dirs(out_dir, scan_params.bolo_names, num_segments)
    
    calculate_params()

    display_params()

    for bolo_name in scan_params.bolo_names:
        bolo = Bolo(bolo_name)
        print "Doing Bolo : ", bolo_name
        for segment in range(num_segments):
            out_dir_local = os.path.join(out_dir, bolo_name, str(segment+1).zfill(4))
            segment_name = str(segment+1).zfill(4)
            print "Segment : ", segment_name
            hitmap += bolo.simulate_timestream(segment, sky_map, out_dir_local)

    scanned_map = get_scanned_map(sky_map, hitmap)
    hp.write_map(os.path.join(out_dir, "scanned_map.fits"), scanned_map)
    hp.write_map(os.path.join(out_dir, "hitmap_in.fits"), hitmap)


def run_mpi():
    time_start = time.time()   

    comm = MPI.COMM_WORLD
    size = comm.Get_size()
    rank = comm.Get_rank()

    num_segments = int(scan_params.t_flight/scan_params.t_segment)

    sky_map = hp.read_map(scan_params.input_map)
    scan_params.nside = hp.get_nside(sky_map)

    time_stamp = [None]
    if rank is 0:
        time_stamp[0] = get_time_stamp()
    time_stamp = comm.bcast(time_stamp, root=0)

    out_dir = os.path.join(scan_params.global_output_dir, "scanning", time_stamp[0])

    calculate_params()

    if rank is 0:
        display_params()
        make_output_dirs(out_dir, scan_params.bolo_names, num_segments)
        hitmap = np.zeros(hp.nside2npix(scan_params.nside), dtype=np.float32)
    else:
        hitmap = None

    comm.Barrier()

    count = 0
    for bolo_name in scan_params.bolo_names:
        for segment in range(num_segments):
            if count%size is rank:
                bolo = Bolo(bolo_name)
                out_dir_local = os.path.join(out_dir, bolo_name, str(segment+1).zfill(4))
                print "Doing Bolo :", bolo_name, " Segment :", segment+1, " Rank :", rank, " Count :", count+1
                hitmap_local = bolo.simulate_timestream(segment, sky_map, out_dir_local)
                del bolo
                comm.Reduce(hitmap_local, hitmap, MPI.SUM, 0)
                del hitmap_local
            count += 1

    if rank is 0:
        scanned_map = get_scanned_map(sky_map, hitmap)
        hp.write_map(os.path.join(out_dir, "scanned_map.fits"), scanned_map)
        hp.write_map(os.path.join(out_dir, "hitmap_in.fits"), hitmap)

    time_end = time.time() 
    if rank is 0:
        print "Total time taken :", (time_end - time_start), "seconds"
        print "Scan time stamp :", time_stamp[0]

if __name__=="__main__":
    from custom_params import scan_params, beam_params
    action = sys.argv[1]

    if action=='display_params':
        calculate_params()
        display_params()

    if action=='run_mpi':
        from mpi4py import MPI
        run_mpi()

    if action=='run_serial':
        run_serial()