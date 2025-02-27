import numpy as np
import matplotlib.pyplot as plt
from scipy.spatial import distance_matrix
from scipy.stats import uniform, norm, multivariate_normal
import matplotlib.cm as cm
import copy


def GaussianKernel(x, l):
    """ Generate Gaussian kernel matrix efficiently using scipy's distance matrix function"""
    D = distance_matrix(x, x)
    return np.exp(-pow(D, 2)/(2*pow(l, 2)))


def subsample(N, factor, seed=None):
    assert factor>=1, 'Subsampling factor must be greater than or equal to one.'
    N_sub = int(np.ceil(N / factor))
    if seed: np.random.seed(seed)
    idx = np.random.choice(N, size=N_sub, replace=False)  # Indexes of the randomly sampled points
    return idx


def get_G(N, idx):
    """Generate the observation matrix based on datapoint locations.
    Inputs:
        N - Length of vector to subsample
        idx - Indexes of subsampled coordinates
    Outputs:
        G - Observation matrix"""
    M = len(idx)
    G = np.zeros((M, N))
    for i in range(M):
        G[i,idx[i]] = 1
    return G


def probit(v):
    return np.array([0 if x < 0 else 1 for x in v])


def predict_t(samples):
    return # TODO: Return p(t=1|samples)


###--- Density functions ---###

def log_prior(u, K_inverse):
    d = u.shape[0]  # Dimension of u
    
    # Mahalanobis term: u^T K^{-1} u
    mahalanobis = u.T @ K_inverse @ u
    
    # Compute log(det(K)) from log(det(K_inverse))
    sign, logdetK_inv = np.linalg.slogdet(K_inverse)
    # Usually sign should be 1 for a valid covariance, but we keep it to handle numerical aspects.
    logdetK = -logdetK_inv
    
    # Combine terms
    log_pdf = - 0.5 * mahalanobis \
              - 0.5 * logdetK \
              - 0.5 * d * np.log(2 * np.pi)
    
    return log_pdf

def log_continuous_likelihood(u, v, G):
    
    # Predicted true value
    v_true = G @ u
    
    # Noise term
    noise = v - v_true
    
    # Mahalanobis term (squared norm of noise, since covariance is identity)
    mahalanobis = np.sum(noise**2)
    
    # Log probability
    n = v.shape[0]  # Dimension of v
    log_pdf = -0.5 * mahalanobis - 0.5 * n * np.log(2 * np.pi)
    
    return log_pdf


def log_probit_likelihood(u, t, G):
    phi = norm.cdf(G @ u)
    return # TODO: Return likelihood p(t|u)


def log_poisson_likelihood(u, c, G):
    return # TODO: Return likelihood p(c|u)


def log_continuous_target(u, y, K_inverse, G):
    return log_prior(u, K_inverse) + log_continuous_likelihood(u, y, G)


def log_probit_target(u, t, K_inverse, G):
    return log_prior(u, K_inverse) + log_probit_likelihood(u, t, G)


def log_poisson_target(u, c, K_inverse, G):
    return log_prior(u, K_inverse) + log_poisson_likelihood(u, c, G)


###--- MCMC ---###

def grw(log_target, u0, data, K, G, n_iters, beta):
    """ Gaussian random walk Metropolis-Hastings MCMC method
        for sampling from pdf defined by log_target.
    Inputs:
        log_target - log-target density
        u0 - initial sample
        y - observed data
        K - prior covariance
        G - observation matrix
        n_iters - number of samples
        beta - step-size parameter
    Returns:
        X - samples from target distribution
        acc/n_iters - the proportion of accepted samples"""

    X = []
    acc = 0
    u_prev = u0

    # Inverse computed before the for loop for speed
    N = K.shape[0]
    Kc = np.linalg.cholesky(K + 1e-6 * np.eye(N))
    Kc_inverse = np.linalg.inv(Kc)
    K_inverse = Kc_inverse.T @ Kc_inverse # TODO: compute the inverse of K using its Cholesky decomopsition

    lt_prev = log_target(u_prev, data, K_inverse, G)

    for i in range(n_iters):

        # generate a gaussian noise with identity covariance
        zeta = Kc @ np.random.normal(0, 1, u_prev.shape)
        u_new = u_prev + beta * zeta # TODO: Propose new sample - use prior covariance, scaled by beta

        lt_new = log_target(u_new, data, K_inverse, G)

        log_alpha = lt_new - lt_prev # TODO: Calculate acceptance probability based on lt_prev, lt_new
        log_u = np.log(np.random.random())

        # Accept/Reject
        accept = log_alpha > log_u  # TODO: Compare log_alpha and log_u to accept/reject sample (accept should be boolean)
        if accept:
            acc += 1
            X.append(u_new)
            u_prev = u_new
            lt_prev = lt_new
        else:
            X.append(u_prev)

    return X, acc / n_iters


def pcn(log_likelihood, u0, y, K, G, n_iters, beta):
    """ pCN MCMC method for sampling from pdf defined by log_prior and log_likelihood.
    Inputs:
        log_likelihood - log-likelihood function
        u0 - initial sample
        y - observed data
        K - prior covariance
        G - observation matrix
        n_iters - number of samples
        beta - step-size parameter
    Returns:
        X - samples from target distribution
        acc/n_iters - the proportion of accepted samples"""

    X = []
    acc = 0
    u_prev = u0
    
    # Inverse computed before the for loop for speed
    N = K.shape[0]
    Kc = np.linalg.cholesky(K + 1e-6 * np.eye(N))
    Kc_inverse = np.linalg.inv(Kc)
    K_inverse = Kc_inverse.T @ Kc_inverse # TODO: compute the inverse of K using its Cholesky decomopsition

    ll_prev = log_likelihood(u_prev, y, G)

    for i in range(n_iters):
        
        zeta = Kc @ np.random.normal(0, 1, u_prev.shape)
        u_new = np.sqrt(1 - beta**2) * u_prev + beta * zeta # TODO: Propose new sample using pCN proposal

        ll_new = log_likelihood(u_new, y, G)

        log_alpha = ll_new - ll_prev # TODO: Calculate pCN acceptance probability
        log_u = np.log(np.random.random())

        # Accept/Reject
        accept = log_alpha > log_u # TODO: Compare log_alpha and log_u to accept/reject sample (accept should be boolean)
        if accept:
            acc += 1
            X.append(u_new)
            u_prev = u_new
            ll_prev = ll_new
        else:
            X.append(u_prev)

    return X, acc / n_iters


###--- Plotting ---###

def plot_3D(u, x, y, title=None):
    """Plot the latent variable field u given the list of x,y coordinates"""
    fig = plt.figure()
    ax = fig.add_subplot(projection='3d')
    ax.plot_trisurf(x, y, u, cmap='viridis', linewidth=0, antialiased=False)
    if title:  plt.title(title)
    plt.show()


def plot_2D(counts, xi, yi, title=None, colors='viridis'):
    """Visualise count data given the index lists"""
    Z = -np.ones((max(yi) + 1, max(xi) + 1))
    for i in range(len(counts)):
        Z[(yi[i], xi[i])] = counts[i]
    my_cmap = copy.copy(cm.get_cmap(colors))
    my_cmap.set_under('k', alpha=0)
    fig, ax = plt.subplots()
    im = ax.imshow(Z, origin='lower', cmap=my_cmap, clim=[-0.1, np.max(counts)])
    fig.colorbar(im)
    if title:  plt.title(title)
    plt.show()


def plot_result(u, data, x, y, x_d, y_d, title=None):
    """Plot the latent variable field u with the observations,
        using the latent variable coordinate lists x,y and the
        data coordinate lists x_d, y_d"""
    fig = plt.figure()
    ax = fig.add_subplot(projection='3d')
    ax.plot_trisurf(x, y, u, cmap='viridis', linewidth=0, antialiased=False)
    ax.scatter(x_d, y_d, data, marker='x', color='r')
    if title:  plt.title(title)
    plt.show()
