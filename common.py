## Imports
import warnings
import builtins

# from pylib.all import *
import numpy as np
import scipy as sp
import numpy.random
import scipy.linalg as sla
import numpy.linalg as nla
import scipy.stats as ss

from scipy.linalg import svd
from numpy.linalg import eig
# eig() of scipy.linalg necessitates using np.real_if_close().
from scipy.linalg import sqrtm, inv, eigh

from numpy import \
    pi, nan, \
    log, log10, exp, sin, cos, tan, \
    sqrt, floor, ceil, \
    mean, prod, \
    diff, cumsum, \
    array, asarray, asmatrix, \
    linspace, arange, reshape, \
    eye, zeros, ones, diag, trace \
    # Don't shadow builtins: sum, max, abs, round, pow

np.set_printoptions(suppress=True,threshold=200,precision=6)
# Instead of set_np_linewidth, just let terminal do wrapping:
np.set_printoptions(linewidth=9999)

import matplotlib as mpl
from matplotlib import pyplot as plt

# I think this makes sense,
# since pylib is only meant for toying around.
plt.ion()


class JsonDict(dict):
    """Provide json pretty-printing"""
    def __str__(self): return repr(self)
    def __repr__(self):
        s = json.dumps(self, indent=4, sort_keys=False, default=str)
        crop = lambda t: t[:80] + ("" if len(t)<80 else "...")
        s = "\n".join([crop(ln) for ln in s.split("\n")])
        return s

class Bunch(JsonDict):
    """A dict that also has attribute (dot) access.

    Benefit compared to a dict:

     - Verbosity of ``mycontainer.a`` vs. ``mycontainer['a']``.
     - Includes JsonDict.

    As seen from its creation in ``__init__``,
     - Bunch is not very hackey.
     - Bunch is also quite robust.

    Source: stackoverflow.com/a/14620633

    Similar constructs are quite common, eg IPython/utils/ipstruct.py.
    """
    def __init__(self,*args,**kwargs):
        "Init like a normal dict."
        super(Bunch, self).__init__(*args,**kwargs) # Make a (normal) dict
        self.__dict__ = self                        # assign it to self.__dict__


## Others
from scipy import sparse
# from scipy.special import errstate
# from scipy.linalg import solve_banded
from scipy.sparse.linalg import spsolve

from mpl_tools.misc import *


# Profiling
try:
    profile = builtins.profile     # will exists if launched via kernprof
except AttributeError:
    def profile(func): return func # provide a pass-through version.


# Ignore warnings
from contextlib import contextmanager
@contextmanager
def ignore_inefficiency():
    warnings.simplefilter("ignore",sparse.SparseEfficiencyWarning)
    yield
    warnings.simplefilter("default",sparse.SparseEfficiencyWarning)

rand = ss.uniform(0,1).rvs
randn = ss.norm(0,1).rvs


## Grid
# Note: x is 1st coord, y is 2nd.
Dx, Dy    = 1,1    # lengths
Nx, Ny    = 32, 32 # num. of pts.
gridshape = Nx,Ny
grid      = Nx, Ny, Dx, Dy
M         = np.prod(gridshape)
sub2ind = lambda ix,iy: np.ravel_multi_index((ix,iy), gridshape)
xy2sub  = lambda x,y: (int(round( x/Dx*(Nx-1) )),
                       int(round( y/Dy*(Ny-1) )))
xy2i    = lambda x,y: sub2ind(*xy2sub(x,y))
ind2sub = lambda ind: np.unravel_index(ind, gridshape)
def ind2xy(ind):
    i,j = ind2sub(ind)
    x   = i/(Nx-1)*Dx
    y   = j/(Ny-1)*Dy
    return x,y

# Resolution
hx, hy = Dx/Nx, Dy/Ny
h2 = hx*hy # Cell volumes (could be array?)

Gridded = Bunch(
    K  =np.ones((2,*gridshape)), # permeability
    por=np.ones(gridshape),   # porosity
)

Fluid = Bunch(
     vw=1.0,  vo=1.0,  # Viscosities
    swc=0.0, sor=0.0 # Irreducible saturations
)


def normalize_wellset(ww):
    ww = array(ww,float).T
    ww[0] *= Dx
    ww[1] *= Dy
    ww[2] /= ww[2].sum()
    return ww.T

def init_Q(injectors,producers):

    injectors = normalize_wellset(injectors)
    producers = normalize_wellset(producers)

    # Scale production so as to equal injection.
    # Otherwise, model will silently input deficit from SW corner.
    # producers[:,2] *= injectors[:,2].sum() / producers[:,2].sum()

    # Insert in source FIELD
    Q = np.zeros(M)
    for x,y,q in injectors: Q[xy2i(x,y)] += q
    for x,y,q in producers: Q[xy2i(x,y)] -= q

    assert np.isclose(Q.sum(),0)
    return injectors, producers, Q


def norm(xx):
    # return nla.norm(xx/xx.size)
    return np.sqrt(np.sum(xx@xx)/xx.size)

def center(E):
    return E - E.mean(axis=0)

def plot_field(ax, field, vm=None, **kwargs):
    if vm is not None: kwargs["vmin"], kwargs["vmax"] = vm

    # Center nodes (coz finite-volume)
    xx = linspace(0,Dx-hx,Nx)+hx/2
    yy = linspace(0,Dy-hy,Ny)+hy/2

    # Need to transpose coz contour() uses
    # the same orientation as array printing.
    field = field.reshape(gridshape).T

    # ax.imshow(field[::-1])
    collections = ax.contourf(xx, yy, field, levels=21, **kwargs)

    ax.set(xlim=(0,1),ylim=(0,1))
    # ax.set(xlim=(hx/2,1-hx/2),ylim=(hy/2,1-hy/2)) # tight
    if ax.is_first_col(): ax.set_ylabel("y")
    if ax.is_last_row (): ax.set_xlabel("x")

    return collections

def plot_corr_field(ax,A,b,title=""):
    N = len(b)
    # CovMat = X.T @ X / (N-1)
    # CovMat = np.cov(E.T)
    # vv = diag(CovMat)
    # CorrMat = CovMat/sqrt(vv)/sqrt(vv[:,None])
    # corrs = CorrMat[i]
    A     = A - A.mean(axis=0)
    b     = b - b.mean(axis=0)
    covs  = b @ A / (N-1)
    varA  = np.sum(A*A,0) / (N-1)
    varb  = np.sum(b*b,0) / (N-1)
    corrs = covs/sqrt(varb)/sqrt(varA)

    ax.set(title=f"Corr. for {title}")
    return plot_field(ax, corrs, cmap=mpl.cm.bwr, vmax=1, vmin=-1)

def plot_realizations(axs,E,title="",vm=None):
    fig = axs.ravel()[0].figure
    for i, (ax, S) in enumerate(zip(axs.ravel(),E)):
        # ax.text(0,.85*Ny,str(i),c="w",size=12) # yields enormous top margin in jupyter
        collections = plot_field(ax, 1-S, vm=vm)
    fig.suptitle(f"Some realizations -- {title}")
    fig_colorbar(fig, collections)
    plt.pause(.01)

def plot_corr_field_vs(ax,E,xy,title=""):
    i = xy2i(*xy)
    b = E[:,i]
    collections = plot_corr_field(ax,E,b,f"{title}")
    ax.plot(*xy, '*k',ms=4)
    return collections

def plot_wells(ax, ww, inj=True):
    ax.plot(*ww.T[:2], "v" if inj else "^", ms=16)
    for i,w in enumerate(ww):
        ax.text(*w[:2], i, color="w" if inj else "k", ha="center", va="center")

def plot_prod(ax, production, dt, nT, obs=None):
    tt = dt*(1+arange(nT))
    hh = []
    for i,p in enumerate(1-production.T):
        hh += ax.plot(tt,p,"-",label=i)

    if obs is not None:
        for i,y in enumerate(1-obs.T):
            ax.plot(tt,y,"*",c=hh[i].get_color())

    ax.legend(title="(Production)\nwell num.")
    ax.set_ylabel("Oil saturation (rel. production)")
    ax.set_xlabel("Time")
    plt.pause(.01)
    return hh

def fig_colorbar(fig,collections,*args,**kwargs):
    fig.subplots_adjust(right=0.8)
    cax = fig.add_axes([0.85, 0.15, 0.05, 0.7])
    fig.colorbar(collections, cax, *args, **kwargs)
    plt.pause(.01)