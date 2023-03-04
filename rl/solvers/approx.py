from abc import ABC, abstractclassmethod
from typing import Sequence, Tuple, Any, NewType

import numpy as np
from numpy.linalg import norm as lnorm
from tqdm import tqdm

from rl.approximators import Approximator, SGDWA, ModelFreeSAL, ModelFreeSALPolicy
from rl.utils import (
    _typecheck_all,
    _get_sample_step,
    _check_ranges,
    Samples,
    Transition,
    MAX_ITER,
    MAX_STEPS,
    TOL
)

class AVQPi:
    def __init__(self, vqpi:Tuple[Approximator, Approximator, ModelFreeSALPolicy]):
        self._v_hat, self._q_hat, self.pi = vqpi

    @property
    def v_hat(self):
        return self.v
    
    @property
    def q_hat(self):
        return self.q
    

def get_sample(v_hat, q_hat, n_episode, optimize):
    _idx = n_episode
    _v = v_hat.copy() 
    _q = None #AQpi(q_hat.copy())
    _pi = None
    return (_idx, _v, _q, _pi)


def _set_s0_a0():
    raise NotImplementedError


def gradient_mc(transition: Transition, approximator: SGDWA, state_0: Any=None, 
    action_0: Any=None, alpha: float=0.05, gamma: float=1.0, n_episodes: int=MAX_ITER,
    max_steps: int=MAX_STEPS, samples: int=1000, optimize: bool=False, 
    policy: ModelFreeSALPolicy=None, tol: float=TOL, eps: float=None
    ) -> Tuple[AVQPi, Samples]:
    '''
    Parameters
    ----------
    transition : Callable[[Any,Any],[[Any,float], bool]]]
        transition must be a callable function that takes as arguments the
        (state, action) and returns (new_state, reward), end.
    approximator : SGDWA
        Function approximator to use for the state value function
    state_0 : Any, optional
        Initial state, by default None (random)
    action_0 : Any, optional
        Initial action, by default None (random)
    alpha : float, optional
        Learning rate, by default 0.1
    gamma : float, optional
        Discount factor, by default 0.9
    n_episodes : int, optional
        Number of episodes to simulate, by default 1E4
    max_steps : int, optional
        Maximum number of steps per episode, by default 1E3
    samples : int, optional
        Number of samples to take, by default 1000
    optimize : bool, optional
        Whether to optimize the policy or not, by default False
    policy : ModelFreePolicy, optional
        Policy to use, by default equal probability ModelFreePolicy
    tol : float, optional
        Tolerance for estimating convergence estimations
    eps : float, optional
        Epsilon value for the epsilon-soft policy, by default None (no exploration)
    
    Returns
    -------
    vqpi : Tuple[VPi, QPi, Policy]
        Value function, action-value function, policy and samples if any.
    samples : Tuple[int, List[Vpi], List[Qpi], List[np.ndarray]] 
        Samples taken during the simulation if any. The first element is the
        index of the iteration, the second is the value function, the third is
        the action-value function and the fourth is the TODO:.

    Raises
    ------
    TransitionError: If any of the arguments is not of the correct type.
    '''

    _typecheck_all(transition=transition,
        constants=[gamma, alpha, n_episodes, max_steps, samples, tol],
        booleans=[optimize], policies=[policy])

    _check_ranges(values=[gamma, alpha, n_episodes, max_steps, samples],
        ranges=[(0,1), (0,1), (1,np.inf), (1,np.inf), (1,1001)])

    sample_step = _get_sample_step(samples, n_episodes)

    model = ModelFreeSAL(transition, gamma=gamma, policy=policy)    
    vh, qh, samples = _gradient_mc(model, approximator, state_0, action_0, 
        alpha, int(n_episodes), int(max_steps), tol, optimize, sample_step)

    return AVQPi((vh, qh, policy)), samples
    

def _gradient_mc(MFS, approximator, s_0, a_0, alpha, n_episodes, 
    max_steps, tol, optimize, sample_step):

    α, γ, π = alpha, MFS.gamma, MFS.policy
    v_hat = approximator

    n_episode, samples, dnorm = 0, [], TOL*2
    for n_episode in tqdm(range(n_episodes), desc=f'grad-MC', unit='episodes'):
        if dnorm < tol:
            break
        s_0, a_0 = _set_s0_a0(MFS, s_0, a_0)

        episode = MFS.generate_episode(s_0, a_0, π, max_steps)
        w_old = v_hat.w.copy()

        G = 0   
        for s_t, a_t, r_tt in episode[::-1]:
            G = γ*G + r_tt
            v_hat.w = v_hat.update(G, α, s_t)
            
            #if optimize:
            #    π.update_policy(q, s_t)

        dnorm = lnorm(w_old - v_hat.w)

        if sample_step and n_episode % sample_step == 0:
            samples.append(get_sample(v_hat, None, π, n_episode, optimize))

    return v_hat, None, samples #TODO: q function approximator


def semigrad_tdn(transition: Transition, approximator: SGDWA, state_0: Any=None, 
    action_0: Any=None, alpha: float=0.05, n: int=1, gamma: float=1.0, 
    n_episodes: int=MAX_ITER, max_steps: int=MAX_STEPS, samples: int=1000, 
    optimize: bool=False, policy: ModelFreeSALPolicy=None, tol: float=TOL, 
    eps: float=None) -> Tuple[AVQPi, Samples]:
    '''Semi-Gradient n-step Temporal Difference
    
    Solver for the n-step temporal difference algorithm. The algorithm is
    semi-gradient in the sense that it uses a function approximator to
    estimate the _true_ value function. 

    Parameters
    ----------
    transition : Callable[[Any,Any],[[Any,float], bool]]]
        transition must be a callable function that takes as arguments the
        (state, action) and returns (new_state, reward), end.
    approximator : SGDWA
        Function approximator to use for the state value function
    state_0 : Any, optional
        Initial state, by default None (random)
    action_0 : Any, optional
        Initial action, by default None (random)
    alpha : float, optional
        Learning rate, by default 0.1
    n : int, optional
        Number of steps to look ahead, by default 1
    gamma : float, optional
        Discount factor, by default 0.9
    n_episodes : int, optional
        Number of episodes to simulate, by default 1E4
    max_steps : int, optional
        Maximum number of steps per episode, by default 1E3
    samples : int, optional
        Number of samples to take, by default 1000
    optimize : bool, optional
        Whether to optimize the policy or not, by default False
    policy : ModelFreePolicy, optional
        Policy to use, by default equal probability ModelFreePolicy
    tol : float, optional
        Tolerance for estimating convergence estimations
    eps : float, optional
        Epsilon value for the epsilon-soft policy, by default None (no exploration)
    
    Returns
    -------
    vqpi : Tuple[VPi, QPi, Policy]
        Value function, action-value function, policy and samples if any.
    samples : Tuple[int, List[Vpi], List[Qpi], List[np.ndarray]] 
        Samples taken during the simulation if any. The first element is the
        index of the iteration, the second is the value function, the third is
        the action-value function and the fourth is the TODO:.

    Raises
    ------
    TransitionError: If any of the arguments is not of the correct type.
    '''

    _typecheck_all(transition=transition,
        constants=[gamma, alpha, n_episodes, max_steps, samples, tol, n],
        booleans=[optimize], policies=[policy])
    
    _check_ranges(values=[gamma, alpha, n_episodes, max_steps, samples, n],
        ranges=[(0,1), (0,1), (1,np.inf), (1,np.inf), (1,1001), (1, np.inf)])

    sample_step = _get_sample_step(samples, n_episodes)

    model = ModelFreeSAL(transition, gamma=gamma, policy=policy)
    v, q, samples = _semigrad_tdn(model, approximator, state_0, action_0,
        alpha, n, int(n_episodes), int(max_steps), tol, optimize, sample_step)

    return AVQPi((v, q, policy)), samples


def _semigrad_tdn(MFS, approximator, s_0, a_0, alpha, n, n_episodes, max_steps, 
    tol, optimize, sample_step):
    '''Semi gradient n-step temporal differnece

    DRY but clear.
    '''

    α, γ, π = alpha, MFS.gamma, MFS.policy
    gammatron = np.array([γ**i for i in range(n)])
    v_hat = approximator

    n_episode, samples, dnorm = 0, [], TOL*2
    for n_episode in tqdm(range(n_episodes), desc=f'semigrad-TD', unit='episodes'):
        if dnorm < tol:
            break
        s_0, a_0 = _set_s0_a0(MFS, s_0, a_0)

        w_old = v_hat.w.copy()

        T = int(max_steps)
        R, A, S, G = [], [a], [s], 0 
        for t in range(T):
            if t < T:
                (s, r), end = MFS.step_transition(s, a)
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

                #π.update_policy(q, s_t)

            if tau == T - 1:
                break

        dnorm = lnorm(w_old - v_hat.w)

        if n_episode % sample_step == 0:
            samples.append(get_sample(v_hat, None, π, n_episode, optimize))
        n_episode += 1

    return v_hat, None, samples #TODO: q function approximator


def lstd(transition: Transition, state_0: Any=None, action_0: Any=None, 
    alpha: float=0.05, gamma: float=1.0, n_episodes: int=MAX_ITER, 
    max_steps: int=MAX_STEPS, samples: int=1000, optimize: bool=False, 
    policy: ModelFreeSALPolicy=None, tol: float=TOL, eps: float=None
    ) -> Tuple[AVQPi, Samples]:
    '''Least squares n-step temporal differnece
    
    Parameters
    ----------
    states : Sequence[Any]
    actions : Sequence[Any]
    transition : Callable[[Any,Any],[[Any,float], bool]]]
        transition must be a callable function that takes as arguments the
        (state, action) and returns (new_state, reward), end.
    state_0 : Any, optional
        Initial state, by default None (random)
    action_0 : Any, optional
        Initial action, by default None (random)
    alpha : float, optional
        Learning rate, by default 0.1
    gamma : float, optional
        Discount factor, by default 0.9
    n_episodes : int, optional
        Number of episodes to simulate, by default 1E4
    max_steps : int, optional
        Maximum number of steps per episode, by default 1E3
    samples : int, optional
        Number of samples to take, by default 1000
    optimize : bool, optional
        Whether to optimize the policy or not, by default False
    policy : ModelFreePolicy, optional
        Policy to use, by default equal probability ModelFreePolicy
    tol : float, optional
        Tolerance for estimating convergence estimations
    eps : float, optional
        Epsilon value for the epsilon-soft policy, by default None (no exploration)
    
    Returns
    -------
    vqpi : Tuple[VPi, QPi, Policy]
        Value function, action-value function, policy and samples if any.
    samples : Tuple[int, List[Vpi], List[Qpi], List[np.ndarray]] 
        Samples taken during the simulation if any. The first element is the
        index of the iteration, the second is the value function, the third is
        the action-value function and the fourth is the TODO:.

    Raises
    ------
    TransitionError: If any of the arguments is not of the correct type.
    '''

    _typecheck_all(transition=transition,
        constants=[gamma, alpha, n_episodes, max_steps, samples, tol],
        booleans=[optimize], policies=[policy])
    
    _check_ranges(values=[gamma, alpha, n_episodes, max_steps, samples],
        ranges=[(0,1), (0,1), (1,np.inf), (1,np.inf), (1,1001), (1, np.inf)])

    sample_step = _get_sample_step(samples, n_episodes)

    model = ModelFreeSAL(transition, gamma=gamma, policy=policy)
    v, q, samples = _lstd(model, state_0, action_0,
        alpha, int(n_episodes), int(max_steps), tol, optimize, sample_step)

    return AVQPi((v, q, policy)), samples


def _lstd(MF, s_0, a_0, alpha, n_episodes, max_steps, tol, optimize, 
            sample_step):

    raise NotImplementedError