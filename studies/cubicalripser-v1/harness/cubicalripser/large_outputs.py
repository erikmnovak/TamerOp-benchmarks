"""Lossless interval-multiplicity canonicalization for integer-grade fixtures."""
import numpy as np
def canonical(result,c):
    a=result[:,:3]
    assert np.all(np.isfinite(a[:,:2])) and np.all(a[:,0]==a[:,0].astype(int))
    assert np.all((a[:,0]>=0)&(a[:,0]<len(c['shape'])))
    assert np.all(a[:,2]>=a[:,1])
    a=a[a[:,1]!=a[:,2]]
    # Exact, reversible integer packing speeds untimed verification. Every
    # grade in this fixed generator is an exactly represented integer; validate
    # that contract before packing. Essential death has its own unused code.
    b=a[:,1];e=a[:,2];finite=np.isfinite(e)
    assert np.all(b==np.floor(b)) and np.all(e[finite]==np.floor(e[finite]))
    assert np.all(np.abs(b)<=65535) and np.all(np.abs(e[finite])<=65535)
    keys=(a[:,0].astype(np.uint64)<<36)|((b+65536).astype(np.uint64)<<18)
    death=np.full(len(a),262143,dtype=np.uint64)
    death[finite]=(e[finite]+65536).astype(np.uint64);keys|=death
    unique,counts=np.unique(keys,return_counts=True)
    return [[int(k)>>36,float(((int(k)>>18)&262143)-65536),
             None if (int(k)&262143)==262143 else float((int(k)&262143)-65536),int(n)]
            for k,n in zip(unique,counts)]

