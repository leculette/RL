"""
RL - Copyright © 2023 Iván Belenky @Leculette
"""

from typing import Tuple

import numpy as np
from numpy.linalg import norm as lnorm

from policy import Policy 

MAX_STEPS = 1E3
MAX_ITER = int(1E4)
TOL = 1E-6


def vq_π_iter_naive(
    MDP, 
    policy: Policy, 
    tol: float = TOL,
    max_iters: int = MAX_ITER) -> np.ndarray:

    γ = MDP.gamma
    p_s = MDP.p_s

    vᵢ = np.ones(MDP.S)
    diff_norm = TOL*2

    π_sa = np.array([policy.π(s) for s in range(MDP.S)]) #SxA
    r_sa  = np.array([[MDP.r_sa(s,a) for s in range(MDP.S)]   
        for a in range(MDP.A)]) #AxS

    n_iter = 0
    while (n_iter < max_iters) and (diff_norm > tol):
        vᵢ_1 = vᵢ.copy()
        
        vᵢ = np.diag(π_sa @ r_sa)
        vᵢ = vᵢ + γ * np.diag((p_s @ vᵢ_1) @ π_sa.T)

        diff_norm = lnorm(vᵢ - vᵢ_1)
        n_iter += 1
    
    vπ = vᵢ
    qπ = r_sa + (p_s @ vπ).T

    return vπ, qπ


def policy_iteration(
    MDP, 
    policy: Policy,
    tol_eval: float = TOL,
    max_iters_eval: int = MAX_ITER,
    tol_opt: float = TOL,
    max_iters_opt: int = MAX_ITER) -> np.ndarray:

    vᵢ_1, q_i_1 = vq_π_iter_naive(MDP, policy, tol_eval, max_iters_eval)
    vᵢ, q_i = vᵢ_1.copy(), q_i_1.copy()

    diff_norm = 2*tol_opt

    n_iter = 0
    while (n_iter < max_iters_opt) and (diff_norm > tol_opt):
        vᵢ_1 = vᵢ.copy()
        q_i_1 = q_i.copy()

        policy.update_policy(q_i_1)
        vᵢ, q_i = vq_π_iter_naive(MDP, policy, tol_eval, max_iters_eval)
        
        n_iter += 1 
        diff_norm = lnorm(vᵢ - vᵢ_1)
    
    return vᵢ, q_i
    

def value_iteration(
    MDP, 
    policy: Policy = None,
    tol: float = TOL,
    max_iters: int = MAX_ITER) -> np.ndarray:

    policy = policy if policy else MDP.policy

    γ = MDP.gamma
    p_s = MDP.p_s

    vᵢ = np.ones(MDP.S)
    diff_norm = TOL*2
    
    r_sa  = np.array([[MDP.r_sa(s,a) for s in range(MDP.S)]   
        for a in range(MDP.A)]) #AxS

    n_iter = 0
    while (n_iter < max_iters) and (diff_norm > tol):
        vᵢ_1 = vᵢ.copy()
        
        qᵢ = r_sa + γ * (p_s @ vᵢ_1).T
        vᵢ = np.array([np.max(qᵢ[:,s]) for s in range(MDP.S)])

        diff_norm = lnorm(vᵢ - vᵢ_1)
        n_iter += 1

    policy.update_policy(qᵢ)
    


def first_visit_monte_carlo(MC, policy, max_episodes):
    return _visit_monte_carlo(MC, policy, max_episodes, first_visit = True)


def every_visit_monte_carlo(MC, policy, max_episodes):
    return _visit_monte_carlo(MC, policy, max_episodes, first_visit = False)


def _visit_monte_carlo(
    MF,
    policy: Policy = None,
    max_episodes: int = MAX_ITER,
    max_steps: int = MAX_STEPS,
    first_visit = True,
    exploring_starts = False) -> np.ndarray:
    '''
        Needless to say the inefficiency of the underlying implementation.
        By no means it was a goal to provide an efficient implementation 
        time/space wise. The goal was readability.
    '''

    π = policy if policy else MF.policy
    
    n_episode = 0

    v, q = np.zeros(MF.state.S), np.zeros((MF.action.S, MF.state.A))
    n_s, n_sa = np.zeros(MF.state.S), np.zeros((MF.action.S, MF.state.A))

    γ = MF.gamma

    s_0, a_0 = MF.random_sa()
    while n_episode < max_episodes:
        if exploring_starts:
            s_0, a_0 = MF.random_sa()

        episode = MF.generate_episode(π, s_0, a_0, max_steps)
        G = 0
        sar = np.array(episode)
        s, a, r = sar[:,0], sar[:,1], sar[:,2]

        for t, (s_t, a_t, r_tt) in enumerate(zip(s[::-1],a[::-1],r[::-1])):
            G = γ*G + r_tt
            
            if s_t not in s[:t] or not first_visit:
                n_s[s_t] = n_s[s_t] + 1
                v[s_t] = v[s_t] + (G - v[s_t])/n_s[s_t]
            
            q_key = (s_t, a_t)
            if q_key not in zip(s[:t],a[:t]) or not first_visit:    
                n_sa[q_key] = n_sa[q_key] + 1
                q[q_key] = q[q_key] + (G - q[q_key])/n_sa[q_key]

        n_episode += 1

    return v, q


def off_policy_first_visit(MC, policy, max_episodes):
    return _off_policy_monte_carlo(MC, policy, max_episodes, first_visit=True)


def off_policy_every_visit(MC, policy, max_episodes):
    return _off_policy_monte_carlo(MC, policy, max_episodes, first_visit=False)


def _off_policy_monte_carlo(
    MF,
    off_policy: Policy,
    policy: Policy = None,
    max_episodes: int = MAX_ITER,
    max_steps: int = MAX_STEPS,
    first_visit = True,
    ) -> Tuple[np.ndarray, np.ndarray]:

    γ = MF.gamma
    b = off_policy 
    π = policy if policy else MF.policy

    n_episode = 0

    v, q = np.zeros(MF.state.S), np.zeros((MF.action.S, MF.state.A))
    c, c_q = np.zeros(MF.state.S), np.zeros((MF.action.S, MF.state.A))

    s_0, a_0 = MF.random_sa()
    while n_episode < max_episodes:
        G = 0
        episode = MF.generate_episode(b, s_0, a_0, max_steps)
        sar = np.array(episode)
        s, a, r = sar[:,0], sar[:,1], sar[:,2]

        w = 1
        for t, (s_t, a_t, r_tt) in enumerate(zip(s[::-1],a[::-1],r[::-1])):
            if w == 0:
                break

            G = γ*G + r_tt

            if s_t not in s[:t] or not first_visit:
                c[s_t] = c[s_t] + w
                v[s_t] = v[s_t] + w/c[s_t] * (G - v[s_t])

            q_key = (s_t, a_t)
            if q_key not in zip(s[:t],a[:t]) or not first_visit:
                c_q[q_key] = c_q[q_key] + w
                q[q_key] = q[q_key] + w/c_q[q_key] * (G - q[q_key])

            w = w * π(a_t, s_t)/b(s_t, a_t)

        n_episode += 1
    
    return v, q


def tdn(
    MF,
    policy: Policy = None,
    n: int = 1,
    α: float = 0.1,
    max_episodes: int = MAX_ITER,
    max_steps: int = MAX_STEPS
    ) -> Tuple[np.ndarray, np.ndarray]:

    π = policy if policy else MF.policy

    n_episode = 0

    v, q = np.zeros(MF.state.S), np.zeros((MF.action.S, MF.state.A))
    
    γ = MF.gamma

    gammatron = np.array([γ**i for i in range(n)])

    s_0, a_0 = MF.random_sa()
    while n_episode < max_episodes:
        episode = MF.generate_episode(π, s_0, a_0, max_steps)
        sar = np.array(episode)
        s, a, r = sar[:,0], sar[:,1], sar[:,2]

        T = s.shape[0]
        for t in range(T - 1):
            s_t, a_t, rr = s[t], a[t], r[t:t+n]

            G = np.dot(gammatron[:rr.shape[0]], rr)
            if t + n < T:
                G = G + γ**n * v[s[t+n]]

            v[s_t] = v[s_t] + α * (G - v[s_t])

            q_key = (s_t, a_t)
            q[q_key] = q[q_key] + α * (G - q[q_key])