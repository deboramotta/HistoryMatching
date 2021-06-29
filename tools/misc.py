"""Common tools."""

import numpy as np
import scipy.linalg as sla
from tqdm.auto import tqdm as progbar


def repeat(model_step, nSteps, x0, dt, obs_model=None, pbar=True, **kwargs):
    """Recursively apply `model_step` `nSteps` times. Also apply `obs_model`.

    Note that the output time series of states includes the initial conditions
    `x0`, while the observation model is not applied at time 0, so that
    `len(xx) = len(yy) + 1`.
    """
    # Range with or w/o progbar
    rge = np.arange(nSteps)
    if pbar:
        rge = progbar(rge, "Simulation")

    # Init
    xx = np.zeros((nSteps+1,)+x0.shape)
    xx[0] = x0

    # Step
    for iT in rge:
        xx[iT+1] = model_step(xx[iT], dt, **kwargs)

    # Observe
    if obs_model:
        for iT in rge:
            y = obs_model(xx[iT+1])
            if iT == 0:
                yy = np.zeros((nSteps,)+(len(y),))
            yy[iT] = y

        return xx, yy

    else:
        return xx


def square_sum(X):
    return np.sum(X*X)


def norm(xx):
    # return nla.norm(xx/xx.size)
    return np.sqrt(np.mean(xx * xx))


class RMS:
    """Compute RMS error & dev of ensemble."""

    def __init__(self, truth, ensemble):
        mean = ensemble.mean(axis=0)
        err = truth - mean
        dev = ensemble - mean
        self.rmse = norm(err)
        self.rmsd = norm(dev)

    def __str__(self):
        return "%6.4f (rmse),  %6.4f (std)" % (self.rmse, self.rmsd)


def RMS_all(series, vs):
    """RMS for each item in series."""
    for k in series:
        if k != vs:
            print(f"{k:8}:", str(RMS(series[vs], series[k])))


def svd0(A):
    """Similar to Matlab's svd(A,0).

    Compute the

     - full    svd if nrows > ncols
     - reduced svd otherwise.

    As in Matlab: svd(A,0),
    except that the input and output are transposed, in keeping with DAPPER convention.
    It contrasts with scipy.linalg's svd(full_matrice=False) and Matlab's svd(A,'econ'),
    both of which always compute the reduced svd.

    .. seealso:: tsvd() for rank (and threshold) truncation.
    """
    M, N = A.shape
    if M > N:
        return sla.svd(A, full_matrices=True)
    return sla.svd(A, full_matrices=False)


def pad0(ss, N):
    """Pad ss with zeros so that len(ss)==N."""
    out = np.zeros(N)
    out[:len(ss)] = ss
    return out


def pows(U, sig):
    """Prepare the computation of the matrix power of a symmetric matrix.

    The input matrix is specified by its eigen-vectors (U) and -values (sig).
    """
    def compute(expo):
        return (U * sig**expo) @ U.T
    return compute


def center(E, axis=0, rescale=False):
    """Center ensemble.

    Makes use of np features: keepdims and broadcasting.

    - rescale: Inflate to compensate for reduction in the expected variance.
    """
    x = np.mean(E, axis=axis, keepdims=True)
    X = E - x

    if rescale:
        N = E.shape[axis]
        X *= np.sqrt(N/(N-1))

    x = x.squeeze()

    return X, x


def mean0(E, axis=0, rescale=True):
    """Like `center`, but only return the anomalies (not the mean).

    Uses `rescale=True` by default, which is beneficial
    when used to center observation perturbations.
    """
    return center(E, axis=axis, rescale=rescale)[0]


def inflate_ens(E, factor):
    """Inflate the ensemble (center, inflate, re-combine)."""
    if factor == 1:
        return E
    X, x = center(E)
    return x + X*factor


def cov(a, b):
    """Compute covariance between multivariate ensembles.

    Input `a` and `b` must have same `shape[0]` (ensemble size).
    """
    A, _ = center(a)
    B, _ = center(b)
    return A.T @ B / (len(B) - 1)


def corr(a, b):
    """Compute correlation between multivariate ensembles. See `cov`."""
    C = cov(a, b)
    sa = np.std(a, axis=0, ddof=1)
    sb = np.std(b, axis=0, ddof=1)[..., None]
    return C / sa / sb