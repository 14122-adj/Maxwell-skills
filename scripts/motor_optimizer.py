#!/usr/bin/env python3
"""
Multi-Objective Motor Design Optimizer.

Finds Pareto-optimal motor designs using NSGA-II, PSO, or grid search.
Evaluates each candidate by calling motor_param_calc.py.

Usage:
    # Standard optimization
    python motor_optimizer.py --power 500 --speed 3000 \
        --objectives efficiency cost --algorithm NSGA2 \
        --population 40 --generations 20

    # With constraints
    python motor_optimizer.py --power 500 --speed 3000 \
        --objectives efficiency torque_density \
        --constraints "outer_dia:60:100" "pm_thickness:2:5" \
        --algorithm PSO

Input:  spec.json or command-line parameters
Output: pareto_front.json + pareto_plot.png (if matplotlib available)
"""

import argparse
import json
import math
import random
import subprocess
import sys
import os
from copy import deepcopy
from typing import Optional

# ──── Try importing visualization libraries ────
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


# ═══════════════════════════════════════════════
# Optimization Algorithms
# ═══════════════════════════════════════════════

class MotorOptimizer:
    """Base optimizer that calls motor_param_calc.py for evaluations."""

    def __init__(self, base_spec: dict, variables: dict, objectives: list[str],
                 constraints: dict, calc_script: str):
        self.base_spec = base_spec
        self.variables = variables  # {name: (min, max, step)}
        self.objectives = objectives
        self.constraints = constraints
        self.calc_script = calc_script
        self.eval_count = 0
        self.history = []

    def evaluate(self, candidate: dict) -> dict:
        """Evaluate a candidate design via motor_param_calc.py."""
        self.eval_count += 1

        # Merge candidate with base spec
        spec = deepcopy(self.base_spec)
        spec.update(candidate)

        # Build CLI args
        cmd = [sys.executable, self.calc_script,
               "--power", str(spec.get("rated_power_W", 500)),
               "--speed", str(spec.get("rated_speed_rpm", 3000)),
               "--json"]
        if spec.get("dc_voltage_V"):
            cmd += ["--voltage", str(spec["dc_voltage_V"])]
        if spec.get("pole_pairs"):
            cmd += ["--poles", str(spec["pole_pairs"] * 2)]
        if spec.get("slots"):
            cmd += ["--slots", str(spec["slots"])]
        if spec.get("outer_diameter_mm"):
            cmd += ["--outer-dia", str(spec["outer_diameter_mm"])]
        if spec.get("stack_length_mm"):
            cmd += ["--length", str(spec["stack_length_mm"])]
        if spec.get("pm_grade"):
            cmd += ["--pm", spec["pm_grade"]]
        if spec.get("steel_grade"):
            cmd += ["--steel", spec["steel_grade"]]
        if spec.get("pm_thickness_mm"):
            cmd += ["--pm-thickness", str(spec["pm_thickness_mm"])]
        if spec.get("airgap_mm"):
            cmd += ["--airgap", str(spec["airgap_mm"])]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0 and result.returncode != 1:
                return {"error": result.stderr[:200], "objectives": [0]*len(self.objectives), "valid": False}
            data = json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            return {"error": str(e), "objectives": [0]*len(self.objectives), "valid": False}

        # Extract objectives
        perf = data.get("performance", {})
        cost = data.get("cost_estimate", {})
        elec = data.get("electromagnetic", {})
        checks = data.get("design_summary", {}).get("checks", {})

        obj_values = []
        for obj_name in self.objectives:
            if obj_name == "efficiency":
                obj_values.append(perf.get("efficiency_pct", 0))
            elif obj_name == "cost":
                obj_values.append(-cost.get("total_cost_yuan", 9999))  # negative for min
            elif obj_name == "torque_density":
                t = perf.get("torque_Nm", 0)
                od = data.get("geometry", {}).get("outer_diameter_mm", 100)
                sl = data.get("geometry", {}).get("stack_length_mm", 50)
                vol = math.pi * (od/20)**2 * (sl/10)  # cm³
                obj_values.append(t / (vol/1000) if vol > 0 else 0)
            elif obj_name == "torque_ripple":
                obj_values.append(-5.0)  # placeholder
            elif obj_name == "Bg":
                obj_values.append(elec.get("Bg_peak_T", 0))
            else:
                obj_values.append(0)

        # Constraint violation
        violations = 0
        for c_name, c_val in self.constraints.items():
            # Check against data
            actual = self._get_constraint_value(data, c_name)
            if actual is not None:
                if isinstance(c_val, tuple) and len(c_val) == 2:
                    lo, hi = c_val
                    if actual < lo:
                        violations += (lo - actual) ** 2
                    elif actual > hi:
                        violations += (actual - hi) ** 2

        penalty = violations * 100  # penalty multiplier

        return {
            "candidate": candidate,
            "objectives": [v - penalty for v in obj_values],  # penalized
            "raw_objectives": obj_values,
            "violations": violations,
            "checks": checks,
            "valid": data.get("design_summary", {}).get("all_checks_pass", False),
        }

    def _get_constraint_value(self, data: dict, name: str) -> Optional[float]:
        perf = data.get("performance", {})
        cost = data.get("cost_estimate", {})
        geo = data.get("geometry", {})
        wind = data.get("winding", {})

        mapping = {
            "efficiency": perf.get("efficiency_pct"),
            "cost": cost.get("total_cost_yuan"),
            "torque": perf.get("torque_Nm"),
            "slot_fill": wind.get("slot_fill_factor"),
            "current_density": wind.get("current_density_Amm2"),
            "pm_thickness": geo.get("pm_thickness_mm"),
            "outer_dia": geo.get("outer_diameter_mm"),
            "airgap": geo.get("airgap_mm"),
        }
        return mapping.get(name)

    def random_candidate(self) -> dict:
        """Generate a random candidate within variable ranges."""
        c = {}
        for name, (lo, hi, step) in self.variables.items():
            if isinstance(lo, int) and isinstance(hi, int):
                c[name] = random.randint(lo, hi)
            else:
                n_steps = int((hi - lo) / step)
                c[name] = round(lo + random.randint(0, n_steps) * step, 2)
        return c


class NSGA2_Optimizer(MotorOptimizer):
    """Non-dominated Sorting Genetic Algorithm II."""

    def __init__(self, *args, population_size=40, generations=20,
                 crossover_prob=0.9, mutation_prob=0.2, **kwargs):
        super().__init__(*args, **kwargs)
        self.pop_size = population_size
        self.generations = generations
        self.cx_prob = crossover_prob
        self.mut_prob = mutation_prob

    def optimize(self, verbose=True) -> list:
        # Initialize population
        pop = [self.random_candidate() for _ in range(self.pop_size)]
        pop = [self.evaluate(c) for c in pop]

        for gen in range(self.generations):
            # Non-dominated sorting
            fronts = self._non_dominated_sort(pop)

            # Create offspring
            offspring = []
            while len(offspring) < self.pop_size:
                p1 = self._tournament_select(pop)
                p2 = self._tournament_select(pop)

                if random.random() < self.cx_prob:
                    c1, c2 = self._crossover(p1["candidate"], p2["candidate"])
                else:
                    c1, c2 = deepcopy(p1["candidate"]), deepcopy(p2["candidate"])

                if random.random() < self.mut_prob:
                    c1 = self._mutate(c1)
                if random.random() < self.mut_prob:
                    c2 = self._mutate(c2)

                offspring.append(self.evaluate(c1))
                if len(offspring) < self.pop_size:
                    offspring.append(self.evaluate(c2))

            # Merge and select
            combined = pop + offspring
            fronts = self._non_dominated_sort(combined)
            pop = []
            for front in fronts:
                if len(pop) + len(front) <= self.pop_size:
                    pop.extend(front)
                else:
                    # Crowding distance selection for last front
                    self._crowding_distance(front)
                    front.sort(key=lambda x: x.get("crowding_dist", 0), reverse=True)
                    pop.extend(front[:self.pop_size - len(pop)])
                    break

            if verbose and gen % 5 == 0:
                best_in_front = fronts[0][0] if fronts else pop[0]
                print(f"  Gen {gen:3d}: best obj={[round(x,2) for x in best_in_front['raw_objectives']]}, "
                      f"evals={self.eval_count}")

        # Return Pareto front (first front)
        final_fronts = self._non_dominated_sort(pop)
        return final_fronts[0] if final_fronts else pop

    def _non_dominated_sort(self, solutions):
        fronts = []
        remaining = list(range(len(solutions)))
        dominated_by = {i: [] for i in remaining}
        dominates_count = {i: 0 for i in remaining}

        for i in remaining:
            for j in remaining:
                if i == j: continue
                if self._dominates(solutions[i], solutions[j]):
                    dominated_by[i].append(j)
                elif self._dominates(solutions[j], solutions[i]):
                    dominates_count[i] += 1

        current_front = [i for i in remaining if dominates_count[i] == 0]
        while current_front:
            fronts.append([solutions[i] for i in current_front])
            next_front = []
            for i in current_front:
                for j in dominated_by[i]:
                    dominates_count[j] -= 1
                    if dominates_count[j] == 0:
                        next_front.append(j)
            current_front = next_front

        return fronts

    def _dominates(self, a, b):
        """a dominates b if a is no worse in all objectives and better in at least one."""
        obj_a = a["raw_objectives"]
        obj_b = b["raw_objectives"]
        better = False
        for fa, fb in zip(obj_a, obj_b):
            if fa > fb:  # maximize
                better = True
            elif fa < fb:
                return False
        return better

    def _crowding_distance(self, front):
        for s in front:
            s["crowding_dist"] = 0
        n_obj = len(front[0]["raw_objectives"])
        for m in range(n_obj):
            front.sort(key=lambda x: x["raw_objectives"][m])
            front[0]["crowding_dist"] = float("inf")
            front[-1]["crowding_dist"] = float("inf")
            f_range = front[-1]["raw_objectives"][m] - front[0]["raw_objectives"][m]
            if f_range == 0: f_range = 1
            for i in range(1, len(front) - 1):
                front[i]["crowding_dist"] += (front[i+1]["raw_objectives"][m] - front[i-1]["raw_objectives"][m]) / f_range

    def _tournament_select(self, pop, k=2):
        contenders = random.sample(pop, k)
        return min(contenders, key=lambda x: x.get("front_rank", 999))

    def _crossover(self, p1, p2):
        c1, c2 = deepcopy(p1), deepcopy(p2)
        for key in self.variables:
            if random.random() < 0.5:
                lo, hi, _ = self.variables[key]
                alpha = random.random()
                v1 = c1[key] + alpha * (c2[key] - c1[key])
                v2 = c2[key] + alpha * (c1[key] - c2[key])
                c1[key] = round(max(lo, min(hi, v1)), 2)
                c2[key] = round(max(lo, min(hi, v2)), 2)
        return c1, c2

    def _mutate(self, c):
        for key in self.variables:
            if random.random() < self.mut_prob:
                lo, hi, step = self.variables[key]
                delta = random.uniform(-step * 3, step * 3)
                c[key] = round(max(lo, min(hi, c[key] + delta)), 2)
        return c


class PSO_Optimizer(MotorOptimizer):
    """Particle Swarm Optimization."""

    def __init__(self, *args, swarm_size=30, iterations=20, **kwargs):
        super().__init__(*args, **kwargs)
        self.swarm_size = swarm_size
        self.iterations = iterations
        self.w = 0.7
        self.c1 = 1.5
        self.c2 = 2.0

    def optimize(self, verbose=True) -> list:
        n_var = len(self.variables)
        var_names = list(self.variables.keys())

        # Convert to single objective (weighted sum)
        # Default: maximize efficiency, minimize cost (equal weight)
        weights = [1.0] * len(self.objectives)
        if "cost" in self.objectives:
            idx = self.objectives.index("cost")
            weights[idx] = 1.0  # cost is already negated in evaluate

        # Initialize swarm
        pos = []
        vel = []
        for _ in range(self.swarm_size):
            pos.append(self.random_candidate())
            vel.append({k: random.uniform(-0.1, 0.1) for k in var_names})

        p_best_pos = deepcopy(pos)
        evals = [self.evaluate(p) for p in pos]
        p_best_fit = [self._single_objective(e["raw_objectives"], weights) for e in evals]

        g_best_idx = max(range(len(p_best_fit)), key=lambda i: p_best_fit[i])
        g_best_pos = deepcopy(pos[g_best_idx])

        for it in range(self.iterations):
            w = self.w * (1 - it / self.iterations)  # linear decay

            for i in range(self.swarm_size):
                for k in var_names:
                    lo, hi, _ = self.variables[k]
                    r1, r2 = random.random(), random.random()
                    vel[i][k] = (w * vel[i][k]
                                 + self.c1 * r1 * (p_best_pos[i][k] - pos[i][k])
                                 + self.c2 * r2 * (g_best_pos[k] - pos[i][k]))
                    pos[i][k] = round(max(lo, min(hi, pos[i][k] + vel[i][k])), 2)

                evals[i] = self.evaluate(pos[i])
                fit = self._single_objective(evals[i]["raw_objectives"], weights)

                if fit > p_best_fit[i]:
                    p_best_fit[i] = fit
                    p_best_pos[i] = deepcopy(pos[i])
                    if fit > p_best_fit[g_best_idx]:
                        g_best_idx = i
                        g_best_pos = deepcopy(pos[i])

            if verbose and it % 5 == 0:
                print(f"  Iter {it:3d}: best fit={p_best_fit[g_best_idx]:.3f}, evals={self.eval_count}")

        # Return top solutions
        sorted_idx = sorted(range(self.swarm_size), key=lambda i: p_best_fit[i], reverse=True)
        return [evals[i] for i in sorted_idx[:10]]

    def _single_objective(self, objectives, weights):
        return sum(w * o for w, o in zip(weights, objectives))


class GridOptimizer(MotorOptimizer):
    """Exhaustive grid search for small variable spaces."""

    def __init__(self, *args, points_per_var=5, **kwargs):
        super().__init__(*args, **kwargs)
        self.points_per_var = points_per_var

    def optimize(self, verbose=True) -> list:
        # Generate grid
        grids = {}
        for name, (lo, hi, _) in self.variables.items():
            grids[name] = [lo + i * (hi - lo) / (self.points_per_var - 1)
                          for i in range(self.points_per_var)]

        # Cartesian product
        from itertools import product
        keys = list(grids.keys())
        all_candidates = []
        for values in product(*[grids[k] for k in keys]):
            all_candidates.append({k: round(v, 2) for k, v in zip(keys, values)})

        if verbose:
            print(f"  Grid search: {len(all_candidates)} candidates")

        results = [self.evaluate(c) for c in all_candidates]

        # Return Pareto front
        opt = NSGA2_Optimizer.__new__(NSGA2_Optimizer)
        fronts = opt._non_dominated_sort(results)
        return fronts[0] if fronts else results


# ═══════════════════════════════════════════════
# Output
# ═══════════════════════════════════════════════

def plot_pareto(pareto: list, objectives: list[str], output_path: str):
    """Plot Pareto front (2D or 3D)."""
    if not HAS_MPL:
        print("  [Warning] matplotlib not available, skipping plot")
        return

    fig, ax = plt.subplots(figsize=(8, 6))

    if len(objectives) == 2:
        x = [s["raw_objectives"][0] for s in pareto]
        y = [s["raw_objectives"][1] for s in pareto]
        ax.scatter(x, y, c="blue", alpha=0.7, edgecolors="black", s=60)
        ax.set_xlabel(objectives[0])
        ax.set_ylabel(objectives[1])
        ax.set_title("Pareto Front")
        ax.grid(True, alpha=0.3)
        # Mark utopia point
        if objectives[0] == "efficiency" and "cost" in objectives[1]:
            idx = objectives.index("cost")
            best = min(pareto, key=lambda s: -s["raw_objectives"][idx])  # after negation
            ax.scatter([best["raw_objectives"][0]], [best["raw_objectives"][1]],
                      c="red", s=120, marker="*", label="Utopia")
            ax.legend()

    elif len(objectives) == 3:
        from mpl_toolkits.mplot3d import Axes3D
        ax = fig.add_subplot(111, projection="3d")
        x = [s["raw_objectives"][0] for s in pareto]
        y = [s["raw_objectives"][1] for s in pareto]
        z = [s["raw_objectives"][2] for s in pareto]
        ax.scatter(x, y, z, c="blue", alpha=0.7, s=40)
        ax.set_xlabel(objectives[0])
        ax.set_ylabel(objectives[1])
        ax.set_zlabel(objectives[2])
        ax.set_title("Pareto Front (3D)")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"  Pareto plot saved: {output_path}")


# ═══════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════

def parse_constraints(constraint_strs: list[str]) -> dict:
    """Parse constraint strings like 'pm_thickness:2:6' → {name: (lo, hi)}."""
    constraints = {}
    for cs in constraint_strs:
        parts = cs.split(":")
        if len(parts) == 3:
            constraints[parts[0]] = (float(parts[1]), float(parts[2]))
    return constraints


def main():
    p = argparse.ArgumentParser(description="Multi-Objective Motor Design Optimizer")
    p.add_argument("--power", type=float, required=True)
    p.add_argument("--speed", type=float, required=True)
    p.add_argument("--voltage", type=float, default=None)
    p.add_argument("--objectives", nargs="+", default=["efficiency", "cost"],
                   choices=["efficiency", "cost", "torque_density", "torque_ripple", "Bg"])
    p.add_argument("--algorithm", default="NSGA2", choices=["NSGA2", "PSO", "grid"])
    p.add_argument("--population", type=int, default=40)
    p.add_argument("--generations", type=int, default=20)
    p.add_argument("--constraints", nargs="*", default=[])
    p.add_argument("--variables", nargs="*",
                   default=["pm_thickness_mm:2:8:0.5", "pole_arc:0.75:0.95:0.02", "airgap_mm:0.35:1.2:0.05"])
    p.add_argument("--output", default="pareto_front.json")
    p.add_argument("--plot", default="pareto_plot.png")
    p.add_argument("--calc-script", default=None)

    args = p.parse_args()

    # Find motor_param_calc.py
    calc_script = args.calc_script
    if calc_script is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        calc_script = os.path.join(script_dir, "motor_param_calc.py")

    # Parse variables
    variables = {}
    for vs in args.variables:
        parts = vs.split(":")
        if len(parts) == 4:
            variables[parts[0]] = (float(parts[1]), float(parts[2]), float(parts[3]))
        elif len(parts) == 3:
            variables[parts[0]] = (float(parts[1]), float(parts[2]), 0.5)

    # Base spec
    base_spec = {
        "rated_power_W": args.power,
        "rated_speed_rpm": args.speed,
    }
    if args.voltage:
        base_spec["dc_voltage_V"] = args.voltage
    else:
        base_spec["dc_voltage_V"] = None  # auto

    constraints = parse_constraints(args.constraints)

    print(f"Optimizer: {args.algorithm}")
    print(f"Objectives: {args.objectives}")
    print(f"Variables: {list(variables.keys())}")
    print(f"Constraints: {constraints or 'none'}")
    print()

    # Select optimizer
    if args.algorithm == "NSGA2":
        opt = NSGA2_Optimizer(base_spec, variables, args.objectives, constraints, calc_script,
                             population_size=args.population, generations=args.generations)
    elif args.algorithm == "PSO":
        opt = PSO_Optimizer(base_spec, variables, args.objectives, constraints, calc_script,
                           swarm_size=args.population, iterations=args.generations)
    elif args.algorithm == "grid":
        opt = GridOptimizer(base_spec, variables, args.objectives, constraints, calc_script,
                           points_per_var=5)
    else:
        print(f"Unknown algorithm: {args.algorithm}")
        sys.exit(1)

    pareto = opt.optimize()

    print(f"\nTotal evaluations: {opt.eval_count}")
    print(f"Pareto front size: {len(pareto)}")
    print()

    # Print top 5
    if pareto:
        for i, sol in enumerate(pareto[:5]):
            if not sol.get("valid"):
                continue
            c = sol["candidate"]
            obj = sol["raw_objectives"]
            print(f"  #{i+1}: {dict(c)} → obj={[round(x,2) for x in obj]}")

    # Save JSON
    output_data = []
    for sol in pareto:
        if sol.get("valid"):
            output_data.append({
                "candidate": sol["candidate"],
                "objectives": {obj: round(v, 2) for obj, v in zip(args.objectives, sol["raw_objectives"])},
            })
    with open(args.output, "w") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    print(f"\nPareto front saved: {args.output}")

    # Plot
    if len(args.objectives) in (2, 3):
        plot_pareto(pareto, args.objectives, args.plot)


if __name__ == "__main__":
    main()
