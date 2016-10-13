#!/usr/bin/env python

import numpy as np
import healpy as hp
import os
import sys
import shutil
import time
import importlib
from memory_profiler import profile
from mpi4py import MPI
from pysimulators.sparse import FSRBlockMatrix
from pysimulators import ProjectionOperator
from simulation.lib.data_management.data_utilities import get_local_bolo_segment_list
from simulation.timestream_simulation.new_sim_timestream import Bolo
import simulation.lib.utilities.prompter as prompter
from simulation.lib.utilities.time_util import get_time_stamp 


def get_inv_cov_matrix(v, pol, ts, inv_cov_matrix, b_matrix):
    nsamples = hitpix.size
    npix = hp.nside2npix(config.nside_out)

    hitpix = hp.vec2pix(config.nside_out, v[...,0], v[...,1], v[...,2])
    n = np.bincount(hitpix, minlength=npix)
    cos_4 = np.bincount(hitpix, weights=np.cos(4*pol), minlength=npix)
    cos_2_pol = np.cos(2*pol)
    sin_2_pol = np.sin(2*pol)

    #inv_cov_matrix = np.empty((npix, 6))
    #b_matrix = np.empty((npix, 3))

    inv_cov_matrix[..., 0] += n
    inv_cov_matrix[..., 1] += np.bincount(hitpix, weights=cos_2_pol, minlength=npix)
    inv_cov_matrix[..., 2] += np.bincount(hitpix, weights=sin_2_pol, minlength=npix)
    inv_cov_matrix[..., 3] += 0.5*(n + cos_4) 
    inv_cov_matrix[..., 4] += 0.5*np.bincount(hitpix, weights=np.sin(4*pol), minlength=npix)
    inv_cov_matrix[..., 5] += 0.5*(n - cos_4) 

    b_matrix[..., 0] += np.bincount(hitpix, 0.5*ts, minlength=npix)
    b_matrix[..., 1] += np.bincount(hitpix, 0.5*cos_2_pol*ts, minlength=npix)
    b_matrix[..., 2] += np.bincount(hitpix, 0.5*sin_2_pol*ts, minlength=npix)

    #inv_cov_matrix *= 0.25

    #return inv_cov_matrix, b_matrix


def write_maps_and_config(sky_map, hitmap, recon_dir):
    hp.write_map(os.path.join(recon_dir, "reconstructed_map.fits"), sky_map)
    hp.write_map(os.path.join(recon_dir, "hitmap.fits"), hitmap)


def write_covariance_maps(maps, map_type, recon_dir):
    out_dir = os.path.join(recon_dir, map_type)
    os.makedirs(out_dir)

    if map_type == "partial_covariance_maps":
        map_legends = {"QQ" : (0,0), "QU" : (0,1), "UU" : (1,1)}
    else:
        map_legends = {"TT" : (0,0), "TQ" : (0,1), "TU" : (0,2), "QQ" : (1,1), "QU" : (1,2), "UU" : (2,2)}

    for leg in map_legends.keys():
        hp.write_map(os.path.join(out_dir, "map_" + leg + ".fits"), maps[..., map_legends[leg][0], map_legends[leg][1]])
        #np.save(os.path.join(out_dir, "map_" + leg), maps[..., map_legends[leg][0], map_legends[leg][1]])


def run_mpi():
    #start_time = time.time()
    npix = hp.nside2npix(config.nside_out)

    inv_cov_matrix_local = np.zeros((npix, 6))
    b_matrix_local = np.zeros((npix, 3))

    bolo_segment_dict = get_local_bolo_segment_list(rank, size, config.bolo_list, config.segment_list)

    print "Rank :", rank, ", Bolos and Segments :", bolo_segment_dict
    comm.Barrier()

    if rank == 0:
        recon_dir = make_data_dirs() 

    for bolo_name in bolo_segment_dict.keys():
        bolo = Bolo(bolo_name, config)
        for segment in bolo_segment_dict[bolo_name]:
            #segment_start = time.time()
            prompter.prompt("Rank : %d doing Bolo : %s and segment : %d" % (rank, bolo_name, segment))
            if config.simulate_ts:
                signal, v, pol_ang = bolo.simulate_timestream(segment)
            else:
                signal, v, pol_ang = bolo.read_timestream(segment)
            get_inv_cov_matrix(v, pol_ang, signal, inv_cov_matrix_local, b_matrix_local)

            #segment_stop = time.time()
            #prompter.prompt("Rank : %d doing Bolo : %s and segment : %d and time taken : %d" % (rank, bolo_name, segment, segment_stop - segment_start))

    inv_cov_matrix_local *= 0.25

    inv_cov_matrix = np.zeros((npix, 6))
    b_matrix = np.zeros((npix, 3))

    #ar_start_1 = time.time()
    comm.Allreduce(inv_cov_matrix_local, inv_cov_matrix, MPI.SUM)
    comm.Allreduce(b_matrix_local, b_matrix, MPI.SUM)
    #ar_stop_1 = time.time()
    #prompter.prompt("Time taken to ALlreduce b_matrix and inv_cov_matrix : " + str(ar_stop_1 - ar_start_1))
    del b_matrix_local, inv_cov_matrix_local

    #cov_start = time.time()
    hitmap = 4*inv_cov_matrix[..., 0]
    inv_cov_matrix[hitmap<3] = np.array([[1.0, 0.0, 0.0, 1.0, 1.0])
    if rank == 0:
        write_covariance_maps(inv_cov_matrix, "inverse_covariance_maps", recon_dir)
    comm.Barrier()
    
    start, stop = get_local_pix_range()
    prompter.prompt("Rank : %d. Start : %d  Stop : %d" % (rank, start, stop))
    cov_matrix_local = np.zeros((npix, 3, 3))
    #print "npix :", npix
    #print "rank :", rank, "hitmap size :", hitmap.size
    #print "rank :", rank, "inv_cov_matrix shape :", inv_cov_matrix.shape 
    #print "rank :", rank, "cov_matrix shape :", cov_matrix_local.shape 
    #print "rank :", rank, "cov_matrix TT shape :", cov_matrix_local[..., 0].shape 
    cov_matrix_local[start:stop] = np.linalg.inv(inv_cov_matrix[start:stop]) 
    recon_dir = os.path.join(config.general_data_dir, config.sim_tag, config.map_making_tag)
    #hp.write_map(os.path.join(recon_dir, "inv_cov_TT_" + str(rank)), cov_matrix_local[..., 0, 0])
    #print cov_matrix_local
    #print b_matrix
    #cov_stop = time.time()
    #prompter.prompt("Time taken to invert covariance matrix : " + str(cov_stop - cov_start))

    #del inv_cov_matrix

    #map_start = time.time()
    #sky_rec_local = np.zeros((3, npix))
    sky_rec_local = np.sum(cov_matrix*b_matrix[..., None], axis=1).T
    #sky_rec_local[..., start:stop] = np.sum(cov_matrix_local[start:stop]*b_matrix[start:stop, None], axis=1).T
    #if rank==0:
    #    np.save(os.path.join(recon_dir, "b_matrix"), b_matrix

    #hp.write_map(os.path.join(recon_dir, "map_local_" + str(rank)), sky_rec_local)

    sky_rec = np.empty((3, npix))
    comm.Reduce(sky_rec_local, sky_rec, MPI.SUM, 0)
    cov_matrix = np.empty((npix, 3, 3))
    comm.Reduce(cov_matrix_local, cov_matrix, MPI.SUM, 0)
    sky_rec[..., hitmap<3] = np.nan
    #map_stop = time.time() 
    #prompter.prompt("Time taken to make map : " + str(map_stop - map_start))

    if rank==0:
        write_maps_and_config(sky_rec, hitmap, recon_dir)
        write_covariance_maps(cov_matrix, "covariance_maps", recon_dir)
    
    """
        if "partial_covariance_maps" in config.map_making_data_products:
            cov_matrix_partial = np.linalg.inv(inv_cov_matrix[..., 1:, 1:])
            write_covariance_maps(cov_matrix_partial, "partial_covariance_maps", recon_dir)
    """ 
    #stop_time = time.time()

    #prompter.prompt("Total time taken : %d" % (stop_time - start_time))


def make_data_dirs():
    sim_dir = os.path.join(config.general_data_dir, config.sim_tag)
    if not os.path.exists(sim_dir):
        os.makedirs(sim_dir)

    time_stamp = get_time_stamp()

    recon_dir = os.path.join(config.general_data_dir, config.sim_tag, config.map_making_tag)
    config_dir = os.path.join(recon_dir, "config_files")
    default_config_file = "/global/homes/b/banerji/simulation/map_maker/config_files/default_config.py"
    current_config_file = os.path.join("/global/homes/b/banerji/simulation/map_maker/config_files", config_file + ".py")

    if os.path.exists(recon_dir):
        if config.map_making_action == "new":
            shutil.rmtree(recon_dir)
            os.makedirs(recon_dir)
            os.makedirs(config_dir)
        else:
            pass
    else:
        os.makedirs(recon_dir)
        os.makedirs(config_dir)

    shutil.copy(default_config_file, config_dir)
    shutil.copyfile(current_config_file, os.path.join(config_dir, config_file + time_stamp + ".py"))
    
    if config.timestream_data_products:
        scan_dir = os.path.join(sim_dir, config.scan_tag)
        if not os.path.exists(scan_dir):
            os.makedirs(scan_dir)
        config_dir = os.path.join(scan_dir, "config_files")
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        default_config_file = "/global/homes/b/banerji/simulation/timestream_simulation/config_files/default_config.py"
        shutil.copy(default_config_file, config_dir)
        current_config_file = os.path.join("/global/homes/b/banerji/simulation/timestream_simulation/config_files", config_file + '.py') 
        shutil.copy(current_config_file, config_dir)


    return recon_dir


def get_local_pix_range():
    npix = hp.nside2npix(config.nside_out)
    npix_block = npix/size

    start = rank*npix_block
    stop = (rank + 1)*npix_block

    if rank == size - 1:
        stop = npix
    
    return start, stop

if __name__=="__main__":
    config_file = sys.argv[1]
    run_type = sys.argv[2]

    config = importlib.import_module("simulation.map_maker.config_files." + config_file).config

    if run_type=='run_check':
        run_check()

    if run_type=='run_mpi':
        from mpi4py import MPI
        comm = MPI.COMM_WORLD
        size = comm.Get_size()
        rank = comm.Get_rank()
        run_mpi()

    if run_type=='run_serial':
        run_serial()
