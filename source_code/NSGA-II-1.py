#!/usr/bin/env python3
"""
Textbook NSGA-II (Deb) for the test↔requirement selection problem.

Usage (example):
    python nsga2_req_test.py --input data.csv --budget 120 --pop 100 --gens 150 --seed 42

Expected input CSV columns (exact names required):
    tc_id, us_id, tc_executiontime, us_businessvalue

Encoding:
    - Binary vector over tests (1 = select test).
    - A requirement (us) is considered COVERED only if ALL its tests are selected.
    - Test execution time counted once; requirement BV counted only when covered.

Outputs:
    - CSV with Pareto front rows: total_BV, num_req_covered, pct_req_covered,
      num_tests_selected, pct_tests_selected, total_time
    - File written to: nsga2_pareto_output.csv (in current working dir)

This is a simple, readable, well-commented implementation intended to be run locally.
"""

import argparse
import random
import csv
from collections import defaultdict
import math
import sys
import pandas as pd
import os

# ------------------------------
# Helpers: problem construction
# ------------------------------
def load_dataset(path):
    """
    Read CSV and validate required columns.
    Returns pandas DataFrame.
    """
    df = pd.read_csv(path)
    required = {'tc_id', 'us_id', 'tc_executiontime', 'us_businessvalue'}
    if not required.issubset(set(df.columns)):
        raise ValueError(f"Input CSV missing required columns. Required: {required}")
    # ensure numeric types
    df['tc_executiontime'] = pd.to_numeric(df['tc_executiontime'], errors='coerce').fillna(0.0).astype(float)
    df['us_businessvalue'] = pd.to_numeric(df['us_businessvalue'], errors='coerce').fillna(0.0).astype(float)
    return df

def build_problem(df):
    """
    Build canonical data structures:
      - tests: list of unique test ids
      - test_index: mapping tc_id -> index
      - test_time: list indexed by test index
      - req_tests: mapping us_id -> set(test indices)
      - req_bv: mapping us_id -> BV (take max if duplicates)
      - requirements: list of us ids
    """
    tests = sorted(df['tc_id'].unique())
    test_index = {tc: i for i, tc in enumerate(tests)}
    # test execution time: use max if test appears multiple times
    tc_time_map = df.groupby('tc_id')['tc_executiontime'].max().to_dict()
    test_time = [float(tc_time_map[tc]) for tc in tests]

    req_tests = defaultdict(set)
    req_bv = dict()
    for _, row in df.iterrows():
        tc = row['tc_id']
        us = row['us_id']
        bv = float(row['us_businessvalue'])
        idx = test_index[tc]
        req_tests[us].add(idx)
        req_bv[us] = max(req_bv.get(us, 0.0), bv)

    requirements = sorted(req_bv.keys())
    return {
        'tests': tests,
        'test_index': test_index,
        'test_time': test_time,
        'req_tests': {k: set(v) for k, v in req_tests.items()},
        'req_bv': req_bv,
        'requirements': requirements
    }

# ------------------------------
# Evaluation & repair
# ------------------------------
def evaluate_solution(chrom, problem):
    """
    Evaluate a binary chromosome (list/iterable of 0/1).
    Returns dict with:
      total_time, selected_tests (set idx), covered_reqs (set us),
      total_BV, num_req_covered, pct_req_covered, num_tests_selected, pct_tests_selected
    """
    selected = {i for i, bit in enumerate(chrom) if bit}
    total_time = sum(problem['test_time'][i] for i in selected)
    covered = set()
    for us, tests_idx in problem['req_tests'].items():
        if tests_idx.issubset(selected):
            covered.add(us)
    total_BV = sum(problem['req_bv'][us] for us in covered)
    num_req_covered = len(covered)
    pct_req_covered = 100.0 * num_req_covered / len(problem['requirements']) if problem['requirements'] else 0.0
    num_tests_selected = len(selected)
    pct_tests_selected = 100.0 * num_tests_selected / len(problem['tests']) if problem['tests'] else 0.0

    return {
        'total_time': total_time,
        'selected_tests': selected,
        'covered_reqs': covered,
        'total_BV': total_BV,
        'num_req_covered': num_req_covered,
        'pct_req_covered': pct_req_covered,
        'num_tests_selected': num_tests_selected,
        'pct_tests_selected': pct_tests_selected
    }

def repair_to_budget(chrom, problem, budget):
    """
    Repair chromosome to satisfy time budget by removing full requirements iteratively.
    Strategy:
      - If covered requirements exist, remove the covered requirement with smallest BV/time ratio (least efficient).
      - If no covered requirement (but still over budget), remove selected test with largest time.
    Returns repaired chromosome (modified copy).
    """
    chrom = list(chrom)
    info = evaluate_solution(chrom, problem)
    if info['total_time'] <= budget:
        return chrom

    while True:
        info = evaluate_solution(chrom, problem)
        if info['total_time'] <= budget:
            break
        covered = info['covered_reqs']
        if covered:
            # compute BV / time for each covered req (time of its tests that are currently selected)
            ratios = []
            for us in covered:
                tests_idx = problem['req_tests'][us]
                time_us = sum(problem['test_time'][i] for i in tests_idx if chrom[i])
                if time_us <= 0:
                    ratios.append((float('inf'), us))
                else:
                    ratios.append((problem['req_bv'][us] / time_us, us))
            ratios.sort()  # smallest ratio first
            _, to_remove = ratios[0]
            # deselect all tests of to_remove
            for i in problem['req_tests'][to_remove]:
                chrom[i] = 0
            continue
        else:
            # no covered reqs, remove largest time test among selected tests
            selected = info['selected_tests']
            if not selected:
                break
            to_remove = max(selected, key=lambda i: problem['test_time'][i])
            chrom[to_remove] = 0
            continue
    return chrom

# ------------------------------
# NSGA-II primitives
# ------------------------------
def dominates(a, b):
    """
    For maximization: a dominates b if a_i >= b_i for all i and > for at least one i.
    a, b: tuples/lists of numeric objectives.
    """
    ge_all = all(x >= y for x, y in zip(a, b))
    gt_any = any(x > y for x, y in zip(a, b))
    return ge_all and gt_any

def nondominated_sort(pop_objs):
    """
    Fast-nondominated-sort for maximization.
    pop_objs: list of objective tuples.
    Returns list of fronts: each front is list of indices.
    """
    N = len(pop_objs)
    S = [set() for _ in range(N)]
    n = [0] * N
    fronts = []

    for p in range(N):
        for q in range(N):
            if p == q:
                continue
            if dominates(pop_objs[p], pop_objs[q]):
                S[p].add(q)
            elif dominates(pop_objs[q], pop_objs[p]):
                n[p] += 1
        if n[p] == 0:
            if not fronts:
                fronts.append([])
            fronts[0].append(p)

    i = 0
    while i < len(fronts):
        next_front = []
        for p in fronts[i]:
            for q in S[p]:
                n[q] -= 1
                if n[q] == 0:
                    next_front.append(q)
        if next_front:
            fronts.append(next_front)
        i += 1
    return fronts

def crowding_distance(values_list):
    """
    Compute crowding distance for list of objective tuples.
    Returns list of distances in same order.
    """
    N = len(values_list)
    if N == 0:
        return []
    distances = [0.0] * N
    num_obj = len(values_list[0])
    for m in range(num_obj):
        # sort indices by objective m ascending
        sorted_idx = sorted(range(N), key=lambda i: values_list[i][m])
        distances[sorted_idx[0]] = float('inf')
        distances[sorted_idx[-1]] = float('inf')
        min_val = values_list[sorted_idx[0]][m]
        max_val = values_list[sorted_idx[-1]][m]
        if max_val == min_val:
            continue
        for k in range(1, N-1):
            prev_i = sorted_idx[k-1]
            next_i = sorted_idx[k+1]
            distances[sorted_idx[k]] += (values_list[next_i][m] - values_list[prev_i][m]) / (max_val - min_val)
    return distances

def tournament_select_index(pop, pop_objs):
    """
    Binary tournament using dominance; if nondominated between pair, prefer larger crowding distance.
    Returns index of winner.
    """
    i, j = random.sample(range(len(pop)), 2)
    if dominates(pop_objs[i], pop_objs[j]):
        return i
    if dominates(pop_objs[j], pop_objs[i]):
        return j
    # tie: compute local crowding distance among the two
    pair = [pop_objs[i], pop_objs[j]]
    cds = crowding_distance(pair)
    return i if cds[0] >= cds[1] else j

# ------------------------------
# Genetic operators
# ------------------------------
def uniform_crossover(p1, p2, prob):
    n = len(p1)
    if random.random() > prob:
        return p1[:], p2[:]
    c1 = p1[:]
    c2 = p2[:]
    for i in range(n):
        if random.random() < 0.5:
            c1[i], c2[i] = c2[i], c1[i]
    return c1, c2

def bitflip_mutation(chrom, pm):
    n = len(chrom)
    c = chrom[:]
    for i in range(n):
        if random.random() < pm:
            c[i] = 1 - c[i]
    return c

# ------------------------------
# NSGA-II main
# ------------------------------
def run_nsga2(problem, budget, pop_size=100, generations=150, cx_prob=0.9, mut_prob=None, seed=None):
    if seed is not None:
        random.seed(seed)

    n_bits = len(problem['tests'])
    if mut_prob is None:
        mut_prob = 1.0 / max(1, n_bits)

    def objectives(chrom):
        info = evaluate_solution(chrom, problem)
        return (info['total_BV'], info['pct_req_covered'])

    # initialize population randomly and repair to budget
    population = []
    for _ in range(pop_size):
        chrom = [1 if random.random() < 0.5 else 0 for _ in range(n_bits)]
        chrom = repair_to_budget(chrom, problem, budget)
        population.append(chrom)

    pop_objs = [objectives(ind) for ind in population]

    for gen in range(generations):
        offspring = []
        # generate offspring until pop_size
        while len(offspring) < pop_size:
            i = tournament_select_index(population, pop_objs)
            j = tournament_select_index(population, pop_objs)
            p1 = population[i]
            p2 = population[j]
            c1, c2 = uniform_crossover(p1, p2, cx_prob)
            c1 = bitflip_mutation(c1, mut_prob)
            c2 = bitflip_mutation(c2, mut_prob)
            # repair
            c1 = repair_to_budget(c1, problem, budget)
            c2 = repair_to_budget(c2, problem, budget)
            offspring.append(c1)
            if len(offspring) < pop_size:
                offspring.append(c2)
        # combine and select next generation
        combined = population + offspring
        combined_objs = [objectives(ind) for ind in combined]
        fronts = nondominated_sort(combined_objs)

        new_pop = []
        new_objs = []
        for front in fronts:
            if len(new_pop) + len(front) <= pop_size:
                for idx in front:
                    new_pop.append(combined[idx])
                    new_objs.append(combined_objs[idx])
            else:
                # need to pick some from front based on crowding distance
                front_vals = [combined_objs[idx] for idx in front]
                distances = crowding_distance(front_vals)
                # pair indices with distance, sort descending
                paired = list(zip(front, distances))
                paired.sort(key=lambda x: x[1], reverse=True)
                for idx, _ in paired:
                    if len(new_pop) < pop_size:
                        new_pop.append(combined[idx])
                        new_objs.append(combined_objs[idx])
                    else:
                        break
                break
        population = new_pop
        pop_objs = new_objs

    # final nondominated front from population
    final_front = nondominated_sort(pop_objs)[0]
    pareto = []
    for idx in final_front:
        info = evaluate_solution(population[idx], problem)
        row = {
            'total_BV': info['total_BV'],
            'num_req_covered': info['num_req_covered'],
            'pct_req_covered': info['pct_req_covered'],
            'num_tests_selected': info['num_tests_selected'],
            'pct_tests_selected': info['pct_tests_selected'],
            'total_time': info['total_time']
        }
        pareto.append(row)
    # sort by total_BV desc then pct_req_covered desc for readability
    pareto.sort(key=lambda r: (r['total_BV'], r['pct_req_covered']), reverse=True)
    return pareto

# ------------------------------
# Hypervolume (2D, maximization)
# ------------------------------
def compute_hv_2d_max(pareto_rows, max_total_bv):
    """
    Computes 2D hypervolume for maximization of:
        (total_BV, pct_req_covered)

    Normalizes to [0,1] using:
        total_BV / max_total_bv
        pct_req_covered / 100

    Reference point = (0,0)
    """

    if max_total_bv <= 0:
        return 0.0

    # Normalize points
    points = []
    for r in pareto_rows:
        x = r['total_BV'] / max_total_bv
        y = r['pct_req_covered'] / 100.0
        points.append((x, y))

    # Remove dominated (safe even if already Pareto)
    points = sorted(set(points), reverse=True)
    nd = []
    best_y = -1
    for x, y in points:
        if y > best_y:
            nd.append((x, y))
            best_y = y

    # Compute area
    hv = 0.0
    prev_y = 0.0
    for x, y in nd:
        if y > prev_y:
            hv += x * (y - prev_y)
            prev_y = y

    return hv

# ------------------------------
# CLI & main
# ------------------------------
def parse_args():
    p = argparse.ArgumentParser(description="Simple textbook NSGA-II for test↔requirement selection")
    p.add_argument('--input', '-i', required=True, help='Input CSV path (cols: tc_id, us_id, tc_executiontime, us_businessvalue)')
    p.add_argument('--budget', '-b', type=float, default=None, help='Time budget (if omitted use 30%% of total test time)')
    p.add_argument('--pop', type=int, default=100, help='Population size')
    p.add_argument('--gens', type=int, default=150, help='Number of generations')
    p.add_argument('--seed', type=int, default=1, help='Random seed')
    p.add_argument('--out', type=str, default='nsga2_pareto_output.csv', help='Output CSV path')
    return p.parse_args()

def main():
    args = parse_args()
    df = load_dataset(args.input)
    problem = build_problem(df)
    total_time_all = sum(problem['test_time'])
    if args.budget is None:
        budget = 0.30 * total_time_all # YOU MUST FIND WAY TO CHNAGE THIS FROM 30% ONLY TO 5%-95%
    else:
        budget = float(args.budget)

    pareto = run_nsga2(problem, budget,
                       pop_size=args.pop,
                       generations=args.gens,
                       cx_prob=0.9,
                       mut_prob=None,
                       seed=args.seed)

    # write output CSV
    fieldnames = ['total_BV', 'num_req_covered', 'pct_req_covered',
                  'num_tests_selected', 'pct_tests_selected', 'total_time']
    with open(args.out, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in pareto:
            writer.writerow(row)

    # ------------------------------
    # Compute Hypervolume
    # ------------------------------
    max_total_bv = sum(problem['req_bv'].values())
    hv = compute_hv_2d_max(pareto, max_total_bv)

    print(f"\nHypervolume (normalized 2D) = {hv:.6f}")

    # Save HV per run
    hv_file = "nsga2_hv_log.csv"
    write_header = not os.path.exists(hv_file)

    with open(hv_file, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["budget", "seed", "pop", "gens", "hv"])
        writer.writerow([budget, args.seed, args.pop, args.gens, hv])

    # Print compact summary to stdout
    print(f"NSGA-II run complete. Budget={budget:.3f}. Pareto solutions saved to: {args.out}")
    print("Pareto front (sorted by total_BV desc):")
    print(pd.DataFrame(pareto)[fieldnames].to_string(index=False))

if __name__ == '__main__':
    main()