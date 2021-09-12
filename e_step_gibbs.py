## A class to perform Gibbs sampling
##
## Copyright Lingxue Zhu (lzhu@cmu.edu).
## All Rights Reserved.


import logging
import numpy as np
from numpy import linalg 
import scipy as scp
from scipy import special
import pypolyagamma as ppg
import os


#######################
## Gibbs sampler for bulk data
#######################
class LogitNormalGibbs_BK(object):

    ## constructor: initialize with parameters
    def __init__(self, 
                A, ## profile matrix
                alpha, ## mixture propotion prior 
                BKexpr, ## M-by-N, bulk expression
                iMarkers=None ## indices of marker genes
                ):
        ## data: unchanged throughout sampling
        self.BKexpr, self.iMarkers = BKexpr, iMarkers
        (self.M, self.N, self.K) = (BKexpr.shape[0], A.shape[0], A.shape[1])
        # logging.debug("M=%d, N=%d, K=%d", M, N, K)
        ## read depths
        self.BKrd = BKexpr.sum(axis=1)
        ## parameters: can only be changed by self.update_parameters()
        self.A = np.array(A, dtype=float, copy=True)
        self.alpha = np.array(alpha, dtype=float, copy=True)
    

    def init_gibbs(self):
        """initialize latent variable values"""
        ## initialize Z in a way such that it captures the marker information
        ## without markers, Z's are zero so the first W is drawn according to alpha
        self.Z = np.zeros([self.M, self.N, self.K])
        ## add marker information if any
        if self.iMarkers is not None:
            ## set Z's
            logging.debug("\t\tZ is initialized with Marker info.")
            for index in range(self.iMarkers.shape[0]):
                (i, k) = self.iMarkers[index, :]
                self.Z[:, i, k] = self.BKexpr[:, i] + self.alpha[k] 
            ## use Z's to initialize W's
            self.W = self.Z.sum(axis=1).transpose()
            self.W /= self.W.sum(axis=0)[np.newaxis, :]
        else:
            self.W = np.full([self.K, self.M], 1.0/self.K, dtype=float)



    def init_suffStats(self):
        """initialize sufficient statistics"""
        ## E[mean_j Z_jik] and E[mean_j log W_kj]
        self.suff_stats = {} ## sufficient statistics
        self.suff_stats["exp_Zik"] = np.zeros([self.N, self.K], dtype=float)
        self.suff_stats["exp_Zjk"] = np.zeros([self.M, self.K], dtype=float)
        self.suff_stats["exp_logW"] = np.zeros([self.K, self.M], dtype=float)
        self.suff_stats["exp_W"] = np.zeros([self.K, self.M], dtype=float)


    def update_suffStats(self, sample):
        """update sufficient stats using current values of latent variables"""
        ## E[sum_j Z_jik]
        self.suff_stats["exp_Zik"] += (self.Z).sum(axis=0) / float(sample)
        ## E[sum_i Z_jik]
        self.suff_stats["exp_Zjk"] += (self.Z).sum(axis=1) / float(sample)
        ## E[mean_j log W_kj]
        self.suff_stats["exp_logW"] += np.log(self.W) / float(sample)
        ## E[W]
        self.suff_stats["exp_W"] += self.W / float(sample)


    def update_parameters(self, A, alpha):
        """update parameters"""
        self.A = np.array(A, dtype=float, copy=True)
        self.alpha = np.array(alpha, dtype=float, copy=True)


    #########################
    ## draw Gibbs samples
    #########################
    def gibbs(self, burnin=100, sample=100, thin=1, mean_approx=True):
        """Gibbs sampling cycle"""
        ## initialize sufficient statistics
        self.init_suffStats()  

        if mean_approx:
            ## use one-step update for W based on expectation
            ## this is equivalent to NMF algorithm
            logging.debug("\tE-step (one-step mean-update) for bulk samples started.")
            ## do not re-initialize W; use the value from last iteration.
            ## only update W once.
            self.get_nmf_W()
            self.draw_Z_mean()
            self.update_suffStats(sample=1)

        else:
            ## use the proper gibbs sampling
            logging.debug("\tE-step for bulk samples started.")
            ## burn in
            for giter in range(burnin):
                self.gibbs_cycle()

            ## sampling
            for giter in range(sample*thin):
                self.gibbs_cycle()
                if giter % thin == 0:
                    ## update sufficient statistics
                    self.update_suffStats(sample)


    
    def gibbs_cycle(self):
        """
        perform one cycle of Gibbs sampling.
        use one-step update for W based on expectation
        this is equivalent to NMF algorithm
        """
        ## draw W first because Z may be carefully initialized with marker info
        self.draw_W()
        self.draw_Z()
  

    def draw_Z(self):
        """Z: M x N x K, counts"""
        for j in range(self.M):
            for i in range(self.N):
                pval = self.W[:, j]*self.A[i, :]
                self.Z[j, i, :] = np.random.multinomial(n=self.BKexpr[j, i],
                                    pvals = pval/self.AW[i, j])

    def draw_W(self):
        """W: K x M, proportions"""
        post_alpha = self.Z.sum(axis=1)
        for j in range(self.M):
            self.W[:, j] = np.random.dirichlet(self.alpha + post_alpha[j, :])
        ## update AW: N x M
        self.AW = np.dot(self.A, self.W)


    def draw_Z_mean(self):
        """Z: M x N x K, expected"""
        self.AW = np.dot(self.A, self.W) ## N-by-M
        for j in range(self.M):
            for i in range(self.N):
                pval = self.W[:, j]*self.A[i, :]
                self.Z[j, i, :] = pval * self.BKexpr[j, i] /self.AW[i, j]

    def get_nmf_W(self):
        self.AW = np.dot(self.A, self.W) ## N-by-M
        for k in range(self.K):
            multiplier = self.BKexpr * self.A[:, k].transpose() / self.AW.transpose()
            self.W[k, :] = self.W[k, :] * multiplier.sum(axis=1) + self.alpha[k] - 1   

        ## re-normalize such that each column sums to 1
        self.W /= self.W.sum(axis=0)[np.newaxis, :]



#######################
## Gibbs sampler for single cell
#######################
class LogitNormalGibbs_SC(object):

    ## constructor: initialize with parameters
    def __init__(self, 
                A, ## profile matrix
                pkappa, ## [mean, var] for kappa
                ptau, ## [mean, var] for tau
                SCexpr, ## L-by-N, single cell expression
                G, ## L-by-1, single cell types
                itype ## cell ids in each type
                ):
        ## data: never changed
        (self.SCexpr, self.G, self.L) = (SCexpr, G, SCexpr.shape[0]) 
        (self.N, self.K) = A.shape
        self.SCrd = SCexpr.sum(axis=1) ## read depths
        self.itype = itype
        ## parameters: can only be changed by self.update_parameters()
        self.A = np.array(A, dtype=float, copy=True)
        self.pkappa = np.array(pkappa, dtype=float, copy=True)
        self.ptau = np.array(ptau, dtype=float, copy=True)
        ## zero-expressed entries
        self.izero = np.where(self.SCexpr==0)
        ## for sampling from Polya-Gamma
        # self.ppgs = ppg.PyPolyaGamma(seed=0)
        num_threads = ppg.get_omp_num_threads()
        seeds = np.random.randint(2**16, size=num_threads)
        self.ppgs = self.initialize_polya_gamma_samplers()


    def initialize_polya_gamma_samplers(self):
        if "OMP_NUM_THREADS" in os.environ:
            self.num_threads = int(os.environ["OMP_NUM_THREADS"])
        else:
            self.num_threads = ppg.get_omp_num_threads()
        assert self.num_threads > 0

        # Choose random seeds
        seeds = np.random.randint(2**16, size=self.num_threads)
        return [ppg.PyPolyaGamma(seed) for seed in seeds]


    def init_gibbs(self):
        """initialize latent variable values"""
        self.kappa = np.full([1,self.L], self.pkappa[0], dtype=float)
        self.tau = np.full([1,self.L], self.ptau[0], dtype=float)
        self.S = np.reshape(np.random.binomial(1, 0.5, size=self.L*self.N), 
                            [self.L, self.N])
        ## note: use broadcasting
        self.psi = np.transpose(self.kappa + self.tau * self.A[:, self.G])
        self.w = np.ones([self.L, self.N], dtype=float)
        ## when expression > 0, it's known for sure that S=1
        ipos = np.where(self.SCexpr>0)
        self.S[ipos] = 1
        ## keep track of A[:, G]*S to reduce computation time
        self.sum_AS = (np.transpose(self.A[:, self.G]) * self.S).sum(axis=1)


    def init_suffStats(self):
        """initialize sufficient statistics to be zeros"""
        self.suff_stats = {}
        ## posterior expectations
        self.suff_stats["exp_S"] = np.zeros([self.L, self.N], dtype=float) ## E[S]
        self.suff_stats["exp_kappa"] = np.zeros([1, self.L], dtype=float) ## E[kappa]
        self.suff_stats["exp_tau"] = np.zeros([1, self.L], dtype=float) ## E[tau]
        self.suff_stats["exp_kappasq"] = np.zeros([1, self.L], dtype=float) ## E[kappa^2]
        self.suff_stats["exp_tausq"] = np.zeros([1, self.L], dtype=float) ## E[tau^2]
        ## part of coefficient for A: E[tau_l*(S_il-0.5) - kappa_l*tau_l*w_il]
        self.suff_stats["coeffA"] = np.zeros([self.N, self.K], dtype=float)
        ## coefficient for A^2: E[- tau_l^2 * w_il]
        self.suff_stats["coeffAsq"] = np.zeros([self.N, self.K], dtype=float)
        ## elbo that doesn't involve A
        self.suff_stats["exp_elbo_const"] = 0


    def update_suffStats(self, sample):
        """Update sufficient stats using current values of latent variables"""
        self.suff_stats["exp_S"] += self.S / float(sample)
        self.suff_stats["exp_kappa"] += self.kappa / sample
        self.suff_stats["exp_tau"] += self.tau / sample
        self.suff_stats["exp_kappasq"] += np.square(self.kappa) / sample
        self.suff_stats["exp_tausq"] += np.square(self.tau) / sample

        ## sum_il E[- kappa_l^2 * w_il/2 + (S_il-0.5)*kappa_l ] 
        self.suff_stats["exp_elbo_const"] += (-self.w * \
                np.transpose(np.square(self.kappa))).sum() / (2.0*sample)
        self.suff_stats["exp_elbo_const"] += ((self.S - 0.5) * np.transpose(self.kappa)).sum()/ \
                                    (sample)

        ## E[tau_l*(S_il-0.5) - kappa_l*tau_l*w_il]
        coeffA = (self.S - 0.5) * np.transpose(self.tau) - \
                    self.w * np.transpose(self.tau * self.kappa)
        ## E[- tau_l^2 * w_il]/2
        coeffAsq = (-self.w * np.transpose(np.square(self.tau))) / 2.0
        ## sum over l, mean over gibbs samples
        for k in range(self.K):
            if len(self.itype[k]) > 0:
                self.suff_stats["coeffA"][:, k] += coeffA[self.itype[k],:].sum(axis=0) / \
                                                         float(sample)
                self.suff_stats["coeffAsq"][:, k] += coeffAsq[self.itype[k],:].sum(axis=0) / \
                                                         float(sample)


    def update_parameters(self, A, pkappa, ptau):
        """update parameters"""
        self.A = np.array(A, dtype=float, copy=True)
        self.pkappa = np.array(pkappa, dtype=float, copy=True)
        self.ptau = np.array(ptau, dtype=float, copy=True)
        ## update psi and sum_AS due to updated parameter A
        self.update_psi()
        self.sum_AS = (np.transpose(self.A[:, self.G]) * self.S).sum(axis=1)

        
    #########################
    ## draw Gibbs samples
    #########################
    def gibbs(self, burnin=100, sample=100, thin=1):
        """Gibbs sampling cycle"""
        logging.debug("\tE-step for single cells started.")

        ## initialize sufficient statistics
        self.init_suffStats()   
        ## re-start gibbs chain
        self.init_gibbs()    
        
        ## burnin
        for giter in range(burnin):
            self.gibbs_cycle()

        ## sampling
        for giter in range(sample*thin):
            self.gibbs_cycle()
            if giter % thin == 0:
                ## update sufficient statistics
                self.update_suffStats(sample)


    def gibbs_cycle(self):
        """One cycle through latent variables in Gibbs sampling"""
        self.draw_w()
        self.draw_S()
        self.draw_kappa_tau()
        self.update_psi()

    def update_psi(self):
        """psi: L-by-N; logistic(psi) is the dropout probability"""
        self.psi = np.transpose(self.kappa + self.tau * self.A[:, self.G])

    def draw_w(self):
        """w: L-by-N; augmented latent variable"""
        ns = np.ones(self.N, dtype=np.float)
        ## draw polya gamma parallelly
        for l in range(self.L):
            ppg.pgdrawvpar(self.ppgs, ns, self.psi[l, :], self.w[l, :])


    def draw_S(self):
        """S: L-by-N; binary variables"""
        ## only update the entries where self.SCexpr==0
        for index in range(len(self.izero[0])):
            (l, i) = (self.izero[0][index], self.izero[1][index])
            A_curr = self.A[i, self.G[l]]

            sum_other = self.sum_AS[l] - A_curr * self.S[l, i]
            if sum_other == 0:
                b = scp.special.expit(self.psi[l][i])
            else:
                b = scp.special.expit(self.psi[l][i] - 
                        self.SCrd[l] * np.log(1 + A_curr/sum_other))
            ## note: scp.stats.bernoulli.rv is slow!!!
            self.S[l][i] = np.random.binomial(1, b)
            ## update sum_AS
            self.sum_AS[l] = sum_other + A_curr * self.S[l, i]


    def draw_kappa_tau(self):
        """kappa, tau: scalars that defines psi"""
        for l in range(self.L):
            A_curr = self.A[:, self.G[l]]
            # ## precision matrix
            # offdiag = sum(self.w[l, :] * A_curr)
            # diag = [sum(self.w[l, :]) + self.pkappa[1],
            #     sum(self.w[l, :] * np.square(A_curr)) + self.ptau[1]]
            # PP = np.array([[diag[0], offdiag], [offdiag, diag[1]]])

            # ## PP * mP = bP: solve for the mean vector mP
            # bP = np.array([sum(self.S[l,:]) - self.N/2.0 +\
            #                     self.pkappa[0]*self.pkappa[1],
            #                 self.sum_AS[l] - 0.5 + \
            #                     self.ptau[0]*self.ptau[1]])
            # mP = np.linalg.solve(PP, bP)

            # ## draw (kappa, tau) ~ Gaussian(mP, PP^-1)
            # newdraw = np.random.multivariate_normal(mP, np.linalg.inv(PP))

            ## compute the covariance matrix
            offdiag = sum(self.w[l, :] * A_curr)
            diag = [sum(self.w[l, :]) + 1.0 / self.pkappa[1],
                    sum(self.w[l, :] * np.square(A_curr)) + 1.0 / self.ptau[1]]
            det = diag[0] * diag[1] - offdiag * offdiag
            sigma_mat = np.array([[diag[1], -offdiag], [-offdiag, diag[0]]]) / det
            bP = np.array([sum(self.S[l,:]) - self.N/2.0 +\
                                 self.pkappa[0] / self.pkappa[1],
                             self.sum_AS[l] - 0.5 + \
                                 self.ptau[0] / self.ptau[1]])
            mP = np.dot(sigma_mat, bP)
            newdraw = np.random.multivariate_normal(mP, sigma_mat)
            (self.kappa[0, l], self.tau[0, l]) = newdraw

