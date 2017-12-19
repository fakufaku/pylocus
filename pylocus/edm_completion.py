#!/usr/bin/env python
# module EDM_COMPLETION
import numpy as np
from cvxpy import *


def optspace(edm_missing, rank, niter=500, tol=1e-6, print_out=False):
    """Complete and denoise EDM using OptSpace algorithm.

    Uses OptSpace algorithm to complete and denoise EDM. The problem being solved is
    X,S,Y = argmin_(X,S,Y) || W ° (D - XSY') ||_F^2

    Args:
        edm_missing: EDM with 0 where no measurement was taken
        rank: expected rank of complete EDM
        niter, tol: see opt_space module for description.

    Returns:
        Completed matrix.
    """
    from .opt_space import opt_space
    N = edm_missing.shape[0]
    X, S, Y, __ = opt_space(edm_missing, r=rank, niter=niter,
                            tol=tol, print_out=print_out)
    edm_complete = X.dot(S.dot(Y.T))
    edm_complete[range(N), range(N)] = 0.0
    return edm_complete


def rank_alternation(edm_missing, rank, niter=50, print_out=False, edm_true=None):
    """Complete missing EDM entries using rank alternation.

    Iteratively impose rank and strucutre to complete marix entries

    Args:
        edm_missing: EDM with 0 where no measurement was taken
        rank: expected rank of complete EDM
        niter: maximum number of iterations
        edm: if given, the relative EDM error is tracked. 

    Returns:
        Completed matrix and array of errors (empty if no true edm is given).
        The matrix is of the correct structure, but might not have the right measured entries.

    """
    from .basics import low_rank_approximation
    errs = []
    N = edm_missing.shape[0]
    edm_complete = edm_missing.copy()
    edm_complete[edm_complete == 0] = np.mean(edm_complete[edm_complete > 0])
    for i in range(niter):
        # impose matrix rank
        edm_complete = low_rank_approximation(edm_complete, rank)

        # impose known entries
        edm_complete[edm_missing > 0] = edm_missing[edm_missing > 0]

        # impose matrix structure
        edm_complete[range(N), range(N)] = 0.0
        edm_complete[edm_complete < 0] = 0.0
        edm_complete = 0.5 * (edm_complete + edm_complete.T)

        if edm_true is not None:
            err = np.linalg.norm(edm_complete - edm_true)
            errs.append(err)
    return edm_complete, errs


def semidefinite_relaxation(edm_missing, lamda, W=None, print_out=False, **kwargs):
    from .algorithms import reconstruct_mds
    def kappa(gram):
        n = len(gram)
        e = np.ones(n)
        return np.outer(np.diag(gram), e) + np.outer(e, np.diag(gram).T) - 2 * gram

    def kappa_cvx(gram, n):
        e = np.ones((n, 1))
        return diag(gram) * e.T + e * diag(gram).T - 2 * gram

    method = kwargs.pop('method', 'maximize')
    options = {'solver' : 'CVXOPT'}
    options.update(kwargs)

    if W is None:
        W = (edm_missing > 0)
    else:
        W[edm_missing == 0] = 0.0

    n = edm_missing.shape[0]
    V = np.c_[-np.ones(n - 1) / np.sqrt(n), np.eye(n - 1) -
              np.ones([n - 1, n - 1]) / (n + np.sqrt(n))].T

    # Creates a n-1 by n-1 positive semidefinite variable.
    H = Semidef(n - 1)
    G = V * H * V.T  # * is overloaded
    edm_optimize = kappa_cvx(G, n)

    if method == 'maximize':
        obj = Maximize(trace(H) - lamda * norm(mul_elemwise(W, (edm_optimize - edm_missing))))
    elif method == 'minimize':
        obj = Minimize(trace(H) + lamda * norm(mul_elemwise(W, (edm_optimize - edm_missing))))

    prob = Problem(obj)

    total = prob.solve(**options)
    if print_out:
        print('total cost:', total)
        print('SDP status:',prob.status)

    if H.value is not None:
        Gbest = V * H.value * V.T
        if print_out:
            print('eigenvalues:',np.sum(np.linalg.eigvals(Gbest)[2:]))
        edm_complete = kappa(Gbest)
    else:
        edm_complete = edm_missing

    # TODO why do these two not sum up to the objective?
    if (print_out):
        if H.value is not None:
            print('trace of H:', np.trace(H.value))
        print('other cost:', lamda * norm(mul_elemwise(W, (edm_complete - edm_missing))).value)

    return edm_complete
    # TODO: why does this not work?
    #Ubest, Sbest, Vbest = np.linalg.svd(Gbest)
    #from basics import eigendecomp
    #factor, u = eigendecomp(Gbest, d)
    #Xhat = np.diag(factor).dot(u.T)[:d]

if __name__ == "__main__":
    print('nothing happens when running this module. It is only a container of functions.')
