import tensorflow as tf
from vegasflow.configflow import DTYPE, DTYPEINT, int_me, float_me
from config import DTYPECOMPLEX
from config import complex_tf, complex_me

keys = tf.constant([0,1,2,3,4,5], dtype=DTYPEINT)
vals = tf.constant([1,3,6,6,18,18], dtype=DTYPEINT)
init = tf.lookup.KeyValueTensorInitializer(keys, vals)
spin_to_size = tf.lookup.StaticHashTable(init, default_value=-1)

@tf.function
def WaveFunctionFlow(npoints, spin):
    # this is going to be dropped since since tf arrays doesn't support item
    # assignment, so no point in creating the vector like this before filling it
    print("Retracing")
    size = spin_to_size.lookup(spin)
    shape = tf.stack([npoints, size], axis=0)
    return tf.zeros(shape, dtype=DTYPE)


def sign(x,y):
    """Fortran's sign transfer function"""
    # dropping the checks for the moment
    return x*tf.math.sign(y)

    tmp = tf.constant(0. ,dtype=tf.float64)
    
    if y.dtype == DTYPECOMPLEX:
        if tf.math.abs(tf.math.imag(y)) < 1e-6 * tf.math.abs(tf.math.real(y)):
            tmp = tf.math.real(y)
        else:
            pass
            # TODO: raise here some error (not sure how it can be compatible with tf.function)
    else:
        tmp = tf.cast(y, dtype=DTYPE)
    if (tmp < 0.):
        return -tf.math.abs(x) 
    else:
        return tf.math.abs(x) 

def ixxxxx(p,fmass,nhel,nsf):
    """Defines an inflow fermion."""
    # TODO: make masks to filter the ps points correctly
    # only pp==0, pp3==0 and sqpp0p3 conditions must be changed 
    # an approach like filtering the points and updating a final vector should
    # be the best possible ! 
    # We must take into account the fact that the mask could possibly have zero entries
    # look at how pdfflow is implemented
    # Note: here p[:,i] selects the momentum dimension and is a [nevt,] tensor
    nevts = tf.shape(p, out_type=DTYPEINT)[0]    
    # fi = WaveFunctionFlow(nevts, 2) # output of shape [nevt, 6]    
    v0 = tf.expand_dims(complex_tf(-p[:,0]*nsf,-p[:,3]*nsf), 1) # [nevt,] complex
    v1 = tf.expand_dims(complex_tf(-p[:,1]*nsf,-p[:,2]*nsf), 1) # [nevt,] complex
    nh = nhel*nsf # either +1 or -1
    ip = (1+nh)//2
    im = (1-nh)//2
    if tf.constant(fmass != 0.):
        pp = tf.math.minimum(p[:,0], tf.math.sqrt(p[:,1]**2 + p[:,2]**2 + p[:,3]**2 )) # [nevt,]
        def true_fn():
            sqm = tf.math.sqrt(tf.math.abs(fmass))
            sqm = tf.stack([sqm, sign(sqm,fmass)]) # [fmass, fmass] ---> why calling sign on the result of a sqrt ????
            v2 = complex_tf(ip*sqm[int_me(ip)],0.) # just a complex number
            v3 = complex_tf(im*nsf*sqm[int_me(ip)],0.)
            v4 = complex_tf(ip*nsf*sqm[int_me(im)],0.)
            v5 = complex_tf(im*sqm[int_me(im)],0.)
            v = tf.stack([v2,v3,v4,v5]) # [4,] complex
            return tf.reshape(v, [1,4])
        def false_fn():
            sf = tf.concat([(1+nsf+(1-nsf)*nh)*0.5,(1+nsf-(1-nsf)*nh)*0.5], axis=0) # [2,]
            omega = tf.stack([tf.math.sqrt(p[:,0]+pp),fmass/(tf.math.sqrt(p[:,0]+pp))], axis=0) # [2, nevt]
            sfomeg = tf.stack([sf[0]*omega[int_me(ip)],sf[1]*omega[int_me(im)]], axis=0) # [2,nevt]
            pp3 = tf.math.maximum(pp+p[:,3],0.) # [nevt,]
            chi1 = tf.where(pp3==0, complex_tf(-nh,0), complex_tf(nh*p[:,1], p[:,2]/tf.math.sqrt(2.*pp*pp3))) # [nevt,] complex
            chi2 = tf.complex(tf.math.sqrt(pp3*0.5/pp),float_me(0.)) # [nevt,] complex 
            chi = tf.stack([chi2, chi1], axis=0) # [2, nevt] complex
            v2 = complex_tf(sfomeg[0], 0.)*chi[int_me(im)] # [nevt,] complex
            v3 = complex_tf(sfomeg[0], 0.)*chi[int_me(ip)]
            v4 = complex_tf(sfomeg[1], 0.)*chi[int_me(im)]
            v5 = complex_tf(sfomeg[1], 0.)*chi[int_me(ip)]
            return tf.stack([v2,v3,v4,v5], axis=1) # [nevt, 4] complex
        cond = tf.expand_dims(pp==0, 1)
        v = tf.where(cond, true_fn(), false_fn()) # [nevt, 4] complex
    else: 
        sqp0p3 = sqrt(max(p[:,0]+p[:,3],0.))*nsf # [nevt,]
        def true_fn():
            return complex_tf(-nhel*tf.math.sqrt(2.*p[:,0]),0.) # [nevt,] complex
        def false_fn():
            return complex_fn(nh*p[:,1]/sqp0p3,p[:,2]/sqp0p3) # [nevt,] complex
        chi1 = tf.where(sqp0p3, true_fn(), false_fn())
        chi = tf.concat([complex_fn(sqp0p3,0.),chi1], axis=0) # [2, nevt]
        def true_fn():
            v4 = chi[0] # [nevt,] complex
            v5 = chi[1] # [nevt,] complex
            v2 = tf.ones_like(v4)*complex_fn(0.,0.) # [nevt,] complex
            v3 = tf.ones_like(v4)*complex_fn(0.,0.) # [nevt,] complex
            return tf.stack([v2,v3,v4,v5], axis=1)
        def false_fn():
            v2 = chi[1]
            v3 = chi[0]
            v4 = tf.ones_like(v2)*complex_fn(0.,0.)
            v5 = tf.ones_like(v2)*complex_fn(0.,0.)
            return tf.stack([v2,v3,v4,v5], axis=1)
        v = tf.where(nh==1, true_fn(), false_fn())
    fi = tf.concat([v0,v1,v], axis=1)
    return fi


def oxxxxx(p,fmass,nhel,nsf):
    """ initialize an outgoing fermion"""
    # TODO: make masks to filter the ps points correctly
    # only pp==0, pp3==0 and sqpp0p3 conditions must be changed
    nevts = tf.shape(p, out_type=DTYPEINT)[0]
    # fo = WaveFunction(2)
    # fo[0] = complex(p[0]*nsf,p[3]*nsf)
    # fo[1] = complex(p[1]*nsf,p[2]*nsf)
    v0 = tf.expand_dims(complex_tf(p[:,0]*nsf,p[:,3]*nsf), 1) # [nevt,] complex
    v1 = tf.expand_dims(complex_tf(p[:,1]*nsf,p[:,2]*nsf), 1) # [nevt,] complex
    nh = nhel*nsf # either +1 or -1
    ip = -((1-nh)//2) * nhel
    im = (1+nh)//2 * nhel
    if tf.constant(fmass != 0.):
        pp = tf.math.minimum(p[:,0], tf.math.sqrt(p[:,1]**2 + p[:,2]**2 + p[:,3]**2 )) # [nevt,]
        def true_fn():
            sqm = tf.math.sqrt(tf.math.abs(fmass))
            sqm = tf.stack([sqm, sign(sqm,fmass)]) # [fmass, fmass] ---> why calling sign on the result of a sqrt ????
            v2 = complex_tf(im*sqm[int_me(tf.math.abs(im))],0.) # just a complex number
            v3 = complex_tf(ip*nsf*sqm[int_me(tf.math.abs(im))],0.)
            v4 = complex_tf(im*nsf*sqm[int_me(tf.math.abs(ip))],0.)
            v5 = complex_tf(ip*sqm[int_me(tf.math.abs(ip))],0.)
            v = tf.stack([v2,v3,v4,v5]) # [4,] complex
            return tf.reshape(v, [1,4])
        def false_fn():
            sf = tf.concat([(1+nsf+(1-nsf)*nh)*0.5,(1+nsf-(1-nsf)*nh)*0.5], axis=0) # [2,]
            omega = tf.stack([tf.math.sqrt(p[:,0]+pp),fmass/(tf.math.sqrt(p[:,0]+pp))], axis=0) # [2, nevt]
            sfomeg = tf.stack([sf[0]*omega[int_me(ip)],sf[1]*omega[int_me(im)]], axis=0) # [2,nevt]
            pp3 = tf.math.maximum(pp+p[:,3],0.) # [nevt,]
            chi1 = tf.where(pp3==0, complex_tf(-nh,0), complex_tf(nh*p[:,1], -p[:,2]/tf.math.sqrt(2.*pp*pp3))) # [nevt,] complex
            chi2 = tf.complex(tf.math.sqrt(pp3*0.5/pp),float_me(0.)) # [nevt,] complex 
            chi = tf.stack([chi2, chi1], axis=0) # [2, nevt] complex
            v2 = complex_tf(sfomeg[0], 0.)*chi[int_me(im)] # [nevt,] complex
            v3 = complex_tf(sfomeg[0], 0.)*chi[int_me(ip)]
            v4 = complex_tf(sfomeg[1], 0.)*chi[int_me(im)]
            v5 = complex_tf(sfomeg[1], 0.)*chi[int_me(ip)]
            return tf.stack([v2,v3,v4,v5], axis=1) # [nevt, 4] complex
        cond = tf.expand_dims(pp==0, 1)
        v = tf.where(cond, true_fn(), false_fn()) # [nevt, 4] complex
    else: 
        sqp0p3 = sqrt(max(p[:,0]+p[:,3],0.))*nsf # [nevt,]
        def true_fn():
            return complex_tf(-nhel*tf.math.sqrt(2.*p[:,0]),0.) # [nevt,] complex
        def false_fn():
            return complex_fn(nh*p[:,1]/sqp0p3, -p[:,2]/sqp0p3) # [nevt,] complex
        chi1 = tf.where(sqp0p3, true_fn(), false_fn())
        chi = tf.concat([complex_fn(sqp0p3,0.),chi1], axis=0) # [2, nevt]
        def true_fn():
            v2 = chi[0] # [nevt,] complex
            v3 = chi[1] # [nevt,] complex
            v4 = tf.ones_like(v4)*complex_fn(0.,0.) # [nevt,] complex
            v5 = tf.ones_like(v4)*complex_fn(0.,0.) # [nevt,] complex
            return tf.stack([v2,v3,v4,v5], axis=1)
        def false_fn():
            v2 = tf.ones_like(v2)*complex_fn(0.,0.)
            v3 = tf.ones_like(v2)*complex_fn(0.,0.)
            v4 = chi[1]
            v5 = chi[0]
            return tf.stack([v2,v3,v4,v5], axis=1)
        v = tf.where(nh==1, true_fn(), false_fn())
    fo = tf.concat([v0,v1,v], axis=1)
    return fo


def vxxxxx(p,vmass,nhel,nsv):
    """ initialize a vector wavefunction. nhel=4 is for checking BRST"""
    # TODO: change the following conditions: 
    # pp==0, pt!=0 count
    nevts = tf.shape(p, out_type=DTYPEINT)[0]
    #vc = WaveFunction(3) # [nevt, 6]
    
    sqh = float_me(tf.math.sqrt(0.5))
    nsvahl = nsv*tf.math.abs(nhel)
    pt2 = p[:,1]**2 + p[:,2]**2 
    pp = tf.math.minimum(p[:,0],tf.math.sqrt(pt2 + p[:,3]**2))
    pt = tf.math.minimum(pp,tf.math.sqrt(pt2))

    v0 = tf.expand_dims(complex_tf(p[:,0]*nsv,p[:,3]*nsv), 1) # [nevts,1] complex
    v1 = tf.expand_dims(complex_tf(p[:,1]*nsv,p[:,2]*nsv), 1)

    if (nhel == 4):
        if (vmass == 0.):
            vc2 = tf.ones(nevts, dtype=DTYPECOMPLEX)
            vc3= p[:,1]/p[:,0]
            vc4= p[:,2]/p[:,0]
            vc5= p[:,3]/p[:,0]
        else:
            vc2 = p[:,0]/vmass
            vc3 = p[:,1]/vmass
            vc4 = p[:,2]/vmass
            vc5 = p[:,3]/vmass
        
        return tf.stack([vc0,vc1,vc2,vc3,vc4,v5], axis=1) # [nevts, 6] complex 

    if (vmass != 0.):
        hel0 = 1.-tf.math.abs(nhel)
        def true_fn():
            hel0 = 1.-tf.math.abs(nhel)
            v2 = tf.ones(nevts, dtype=DTYPECOMPLEX)
            v3 = tf.ones_like(v2)*complex_tf(-nhel*sqh,0.)
            v4 = tf.ones_like(v2)*complex_tf(0.,nsvahl*sqh)
            v5 = tf.ones_like(v2)*complex_tf(hel0,0.)
            return tf.stack([v2,v3,v4,v5], axis=1) # [nevts,4] complex
        def false_fn():
            emp = p[:,0]/(vmass*pp)
            v2 = tf.expand_dims(complex_tf(hel0*pp/vmass,0.), 1)
            v5 = tf.expand_dims(complex_tf(hel0*p[:,3]*emp+nhel*pt/pp*sqh), 1)
            def true_f():
                pzpt = p[:,3]/(pp*pt)*sqh*nhel
                vc3 = complex_tf(hel0*p[:,1]*emp-p[:,1]*pzpt, \
                    -nsvahl*p[:,2]/pt*sqh)
                vc4 = complex_tf(hel0*p[:,2]*emp-p[:,2]*pzpt, \
                    nsvahl*p[:,1]/pt*sqh) 
                return tf.stack([v3,v4], axis=1)
            def false_f():
                v3 = tf.ones(nevts, dtype=DTYPECOMPLEX)*complex_tf(-nhel*sqh,0.)
                v4 = complex_tf(0.,nsvahl*sign(sqh,p[:,3])) # <------ this enters the sign operation with y as a real vector
                return tf.stack([v3,v4], axis=1)
            condition = tf.expand_dims(pt!=0, 1)
            v34 = tf.where(condition, true_f(), false_f())            
            return tf.concat([v2,v34,v5], axis=1) # [nevts,4] complex
        cond = tf.expand_dims(pp==0, 1)
        v = tf.where(cond, true_fn(), false_fn())
    else:
        pp = p[:,0]
        pt = tf.math.sqrt(p[:,1]**2 + p[:,2]**2)
        v2 = tf.ones([nevts,1], dtype=DTYPECOMPLEX)*complex_tf(0.,0.)
        v5 = tf.expand_dims(complex_tf(nhel*pt/pp*sqh), 1)
        def true_fn():
            pzpt = p[:,3]/(pp*pt)*sqh*nhel
            v3 = complex_tf(-p[:,1]*pzpt,-nsv*p[:,2]/pt*sqh)
            v4 = complex_tf(-p[:,2]*pzpt,nsv*p[:,1]/pt*sqh)
            return tf.stack([v3,v4], axis=1)
        def false_fn():
            v3 = tf.ones(nevts, dtype=DTYPECOMPLEX)*complex_tf(-nhel*sqh,0.)
            v4 = complex_tf(0.,nsv*sign(sqh,p[:,3])) # <------ this enters the sign operation with y as a real vector
            return tf.stack([v3,v4], axis=1)
        cond = tf.expand_dims(pt!=0, 1)
        v34 = tf.where(cond, true_fn(), false_fn())
        v = tf.concat([v2,v34,v5], axis=1)
    return tf.concat([v0,v1,v], axis=1)
