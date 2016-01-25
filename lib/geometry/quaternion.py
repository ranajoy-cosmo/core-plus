#!/usr/bin/env python 

import numpy as np
from conversions import deg2rad

#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*
# Initialising an Nx4 dimensional array of quaternions ndarray(w, x, y, z)
# Each row is an individual quaternion given by
# [cos(theta/2), sin(theta/2)*(x, y, z)]
# theta input shape : (N,)     
# vectors input shape : (N,3)
# output shape : (N,4)
#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*

def make_quaternion(thetas, vectors, degree=False):
    if degree is True:
        thetas = deg2rad(thetas)
    return np.insert(np.sin(thetas/2)[...,None]*vectors, 0, np.cos(thetas/2), axis=-1)

#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*
# Finding the conjugate of an array of quaternions 
# Conjugate of (w, x, y, z) is (w, -x, -y, -z) 
# input shape : (N,4)
# output shape : (N,4)
#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*

def conjugate(q):
    return q*np.array([1, -1, -1, -1]) 

#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*
# Finding the norm of an array of quaternions 
# Norm of (w, x, y, z) is sqrt((w^2 + x^2 + y^2 + z^2)) 
# input Shape = (N,4)
# output shape = (N,1)
#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*

def norm(q):
    return np.sqrt(np.sum(q*q, axis=-1))[...,None]
    
#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*
# Finding the inverse of an array of quaternions 
# Inverse of q is conjugate(q)/norm(q)^2 
# input Shape = (N,4)
# output shape = (N,4)
#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*

def inverse(q):
    return conjugate(q)/norm(q) 
    
#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*
# Normalising the array of quaternions 
# Norm of (w, x, y, z) is sqrt((w^2 + x^2 + y^2 + z^2)) 
# input shape : (N,4)
# output shape : (N,4)
#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*

def normalise(q, n=None):
    if n is None:
        n = norm(q)
    return q/norm

#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*
# Construct an array of quaternions from an array of vectors 
# input shape : (N,3)
# output shape : (N,4)
#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*

def vec2quat(vectors):
    return np.insert(vectors, 0, 0, axis=-1)

#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*
# Multiplication of two quaternions a and b 
# input shape : (N,4), (N,4)
# output shape : (N,4)
# s -> scalar part
# v -> vector part
# a*b = (as*bs - av.bv, as*bv + bs*av + avXbv)
# input shape : (N,4), (N,4)
# output shape : (N,4)
#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*

def multiply(q1, q2):
    q1s = q1[...,0]
    q2s = q2[...,0]
    q1v = q1[...,1:]
    q2v = q2[...,1:]

    qs = q1s*q2s - np.sum(q1v*q2v, axis=-1)
    qv = q1s[...,None]*q2v + q2s[...,None]*q1v + np.cross(q1v, q2v)

    return np.insert(qv, 0, qs, axis=-1) 

#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*
# Rotate a vector v by the normalised quaternion q
# v' = q*v*conj(q)
# input shape : (N,4), (N,3)
# output shape : (N,3)
#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*

def rotate(q, v):
    return multiply(multiply(q, vec2quat(v)), conjugate(q))[...,1:]

#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*
# Rotate vectors about an axis by angles of theta 
# input shape : (N,), (3,), (N,3)
# output shape : (N,3)
#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*#*

def rotate_about_fixed_axis(thetas, axis, vectors):
    return rotate(make_quaternion(thetas, axis), vectors)

def quaternion_XYX(theta1, theta2, theta3):
    q1 = np.cos(theta2/2)*np.cos((theta1+theta3)/2)
    q2 = np.cos(theta2/2)*np.sin((theta1+theta3)/2)
    q3 = np.sin(theta2/2)*np.cos((theta1-theta3)/2)
    q4 = np.sin(theta2/2)*np.sin((theta1-theta3)/2)

    return np.hstack((q1[...,None], q2[...,None], q3[...,None], q4[...,None]))
