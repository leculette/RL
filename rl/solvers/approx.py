from abc import ABC, abstractclassmethod
from typing import Sequence, Tuple, Any

import numpy as np
from numpy.linalg import norm as lnorm

from rl.model_free import ModelFree, ModelFreePolicy
from rl.approximators import SGDWA
from rl.solvers.model_free import (
    get_sample,
    _set_s0_a0,
    _set_policy,
)
from rl.utils import (
    _typecheck_all,
    _get_sample_step,
    _check_ranges,
    VQPi,
    Samples,
    Transition,
    MAX_ITER,
    MAX_STEPS,
    TOL
)


def gradient_mc(states: Sequence[Any], actions: Sequence[Any], transition: Transition,
    approximator: SGDWA, state_0: Any=None, action_0: Any=None, alpha: float=0.05, 
    gamma: float=1.0, n_episodes: int=MAX_ITER, max_steps: int=MAX_STEPS,
    samples: int=1000,  optimize: bool=False, policy: ModelFreePolicy=None, 
    tol: float=TOL, eps: float=None) -> Tuple[VQPi, Samples]:
    '''
    TODO: docs
    '''

    policy = _set_policy(policy, eps, actions, states)

    _typecheck_all(tabular_idxs=[states, actions], transition=transition,
        constants=[gamma, alpha, n_episodes, max_steps, samples, tol],
        booleans=[optimize], policies=[policy])

    _check_ranges(values=[gamma, alpha, n_episodes, max_steps, samples],
        ranges=[(0,1), (0,1), (1,np.inf), (1,np.inf), (1,1001)])

    sample_step = _get_sample_step(samples, n_episodes)

    model = ModelFree(states, actions, transition, gamma=gamma, policy=policy)    
    v, q, samples = _gradient_mc(model, approximator, state_0, action_0, 
        alpha, n_episodes, max_steps, tol, optimize, sample_step)

    return VQPi((v, q, policy)), samples
    

def _gradient_mc(MF, approximator, s_0, a_0, alpha, n_episodes, 
    max_steps, tol, optimize, sample_step):

    α, γ, π = alpha, MF.gamma, MF.policy
    v, q = MF.init_vq()
    v_hat = approximator

    n_episode, samples, dnorm = 0, [], TOL*2
    while (n_episode < n_episodes) and (dnorm > tol):
        s_0, a_0 = _set_s0_a0(MF, s_0, a_0)

        episode = MF.generate_episode(s_0, a_0, max_steps)
        sar = np.array(episode)
        v_old = v.copy()

        G = 0   
        for s_t, a_t, r_tt in sar[::-1]:
            s_t, a_t = int(s_t), int(a_t)
            G = γ*G + r_tt

            v_hat.w = v_hat.update(G, α, s_t)

            #if optimize:
            #    π.update_policy(q, s_t)

            v[s_t] = v_hat(s_t)

        dnorm = np.linalg.norm(v_old - v)
        n_episode += 1

        if sample_step and n_episode % sample_step == 0:
            samples.append(get_sample(MF, v, q, π, n_episode, optimize))

    return v, q, samples


def semigrad_tdn(states: Sequence[Any], actions: Sequence[Any], transition: Transition,
    approximator: SGDWA, state_0: Any=None, action_0: Any=None, alpha: float=0.05, 
    n: int=1, gamma: float=1.0, n_episodes: int=MAX_ITER, max_steps: int=MAX_STEPS,
    samples: int=1000,  optimize: bool=False, policy: ModelFreePolicy=None, 
    tol: float=TOL, eps: float=None) -> Tuple[VQPi, Samples]:

    policy = _set_policy(policy, eps, actions, states)

    _typecheck_all(tabular_idxs=[states, actions], transition=transition,
        constants=[gamma, alpha, n_episodes, max_steps, samples, tol, n],
        booleans=[optimize], policies=[policy])
    
    _check_ranges(values=[gamma, alpha, n_episodes, max_steps, samples, n],
        ranges=[(0,1), (0,1), (1,np.inf), (1,np.inf), (1,1001), (1, np.inf)])

    sample_step = _get_sample_step(samples, n_episodes)

    model = ModelFree(states, actions, transition, gamma=gamma, policy=policy)
    v, q, samples = _semigrad_tdn(model, approximator, state_0, action_0,
        alpha, n, n_episodes, max_steps, optimize, sample_step)

    return VQPi((v, q, policy)), samples


def _semigrad_tdn(MF, approximator, s_0, a_0, alpha, n, n_episodes, max_steps, 
    tol, optimize, sample_step):
    '''Semi gradient n-step temporal differnece

    DRY but clear.
    '''

    α, γ, π = alpha, MF.gamma, MF.policy
    v, q  = MF.init_vq()
    gammatron = np.array([γ**i for i in range(n)])
    v_hat = approximator

    n_episode, samples, dnorm = 0, [], TOL*2
    while (n_episode < n_episodes) and (dnorm > tol):
        s_0, a_0 = _set_s0_a0(MF, s_0, a_0)

        s = MF.states.get_index(s_0)
        a = MF.actions.get_index(a_0)
        v_old = v.copy()

        T = int(max_steps)
        R, A, S, G = [], [a], [s], 0 
        for t in range(T):
            if t < T:
                (s, r), end = MF.step_transition(s, a)
                R.append(r)
                S.append(s)
                if end:
                    T = t + 1
                else:
                    a = π(s)
                    A.append(a)
            
            tau = t - n + 1
            if tau >= 0:
                rr = np.array(R[tau:min(tau+n, T)])
                G = gammatron[:rr.shape[0]].dot(rr)
                G_v = G # G_q = G
                if tau + n < T:
                    G_v = G_v + γ**n * v_hat(S[tau+n])
                    #G_q = G_q + γ**n * q[S[tau+n], A[tau+n]]
                
                s_t = S[tau]
                #a_t = A[tau]
                
                v_hat.w = v_hat.update(G_v, α, s_t)

                v[s_t] = v_hat(s_t)
                #q[(s_t, a_t)] = q[(s_t, a_t)] + α * (G_q - q[(s_t, a_t)])

                #π.update_policy(q, s_t)

            if tau == T - 1:
                break

        dnorm = np.linalg.norm(v_old - v)

        if n_episode % sample_step == 0:
            samples.append(get_sample(MF, v, q, π, n_episode, optimize))
        n_episode += 1

    return v, q, samples

