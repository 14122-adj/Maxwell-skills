# Multi-Objective Motor Design Optimization

## Optimization Problem Formulation

### Variables

| Variable | Symbol | Range | Unit | Step |
|----------|--------|-------|------|------|
| PM thickness | hm | 2.0–8.0 | mm | 0.5 |
| Slot opening | bs0 | 1.5–5.0 | mm | 0.5 |
| Pole arc coefficient | αp | 0.70–0.95 | — | 0.02 |
| Split ratio | Dsi/Dso | 0.50–0.70 | — | 0.02 |
| Turns per phase | Nph | 10–80 | — | 2 |
| Stack length | La | 30–100 | mm | 5 |
| Airgap | δ | 0.35–1.5 | mm | 0.05 |

### Objectives (choose 1–4)

| Objective | Direction | Formula |
|-----------|-----------|---------|
| f1: Efficiency | Maximize | η = P_out / (P_out + P_loss) |
| f2: Cost | Minimize | ¥(magnets + copper + steel + housing) |
| f3: Torque density | Maximize | T_avg / Volume_rotor |
| f4: Torque ripple | Minimize | (T_max - T_min) / T_avg × 100% |
| f5: Power factor | Maximize | cos(φ) = P / (√3 × V_LL × I) |
| f6: Overload capacity | Maximize | T_max / T_rated |
| f7: Mass | Minimize | Total active mass (kg) |

### Constraints

| Constraint | Condition | Tolerance |
|-----------|-----------|-----------|
| Torque | T_avg ≥ T_target | — |
| Efficiency | η ≥ η_target | — |
| Slot fill | kf ≤ 0.50 | — |
| Airgap flux density | Bg ≤ 1.8 T | — |
| Current density | J ≤ J_max | — |
| PM demag margin | B_min > 0.2 T | at 150°C short-circuit |
| Split ratio | 0.50 ≤ Dsi/Dso ≤ 0.70 | — |
| Tooth flux density | Bt ≤ Bsat | ±5% |
| Yoke flux density | By ≤ Bsat | ±5% |

## Algorithm Selection Guide

### NSGA-II (Recommended)

**Best for:** Multi-objective (2-4 objectives), complex Pareto front, global search

```
Parameters:
  population_size: 50-100
  generations: 30-50
  crossover_prob: 0.9
  mutation_prob: 1/n_variables
  tournament_size: 2

Convergence: stable after 30 generations for 5-7 variables
```

**Usage:**
```bash
python scripts/motor_optimizer.py \
  --algorithm NSGA2 \
  --population 60 \
  --generations 40 \
  --objectives efficiency cost \
  --spec spec.json
```

### Particle Swarm Optimization (PSO)

**Best for:** Single-objective or 2-objective (weighted sum), fast convergence

```
Parameters:
  swarm_size: 30-50
  iterations: 20-30
  inertia_weight: 0.7 → 0.4 (linear decay)
  cognitive_coef: 1.5
  social_coef: 2.0

Convergence: 15-25 iterations for smooth objective landscape
```

### Grid Search

**Best for:** < 4 variables, complete landscape understanding, no local minima risk

```
Parameters:
  points_per_variable: 5-10
  Total evaluations: (points_per_variable)^(n_variables)
  Use for: sensitivity analysis, initial exploration
```

### Bayesian Optimization (Gaussian Process)

**Best for:** Expensive evaluations (> 30s each), smooth objectives

```
Parameters:
  initial_samples: 10-20
  iterations: 20-50
  acquisition: Expected Improvement (EI)
  kernel: Matern-5/2
```

## Implementation

### motor_optimizer.py Architecture

```
Input: spec.json (partial or complete motor spec)
    │
    ├─ Define variables with ranges
    ├─ Define objectives
    ├─ Define constraints
    │
    ▼
Algorithm Loop:
    │
    ├─ Sample candidate (x = [hm, bs0, αp, ...])
    │
    ├─ Call motor_param_calc.py(x) → compute EM parameters
    │
    ├─ Evaluate objectives f1..fn
    │
    ├─ Check constraints g1..gm
    │     ├─ Violated → penalize in fitness
    │     └─ Satisfied → raw objective value
    │
    ├─ Update population (GA) / swarm (PSO) / GP model (Bayesian)
    │
    └─ Loop until convergence
    │
    ▼
Output: Pareto front (set of non-dominated solutions)
    │
    ├─ Pareto front JSON
    ├─ Pareto front plot (2D/3D)
    └─ Top-3 solutions ranked by user preference
```

### Constraint Handling

**Penalty method:**
```python
def penalized_fitness(x):
    raw_f = evaluate_objectives(x)  # f = [η, -cost, T_density, ...]
    violations = eval_constraints(x)
    penalty = sum(max(0, v)**2 for v in violations)
    return [f_i + penalty for f_i in raw_f]
```

### Pareto Front Extraction

```python
def extract_pareto_front(solutions):
    """Non-dominated sorting. Solution A dominates B if:
    - A is equal or better in ALL objectives
    - A is strictly better in AT LEAST ONE objective
    """
    pareto = []
    for i, sol_i in enumerate(solutions):
        dominated = False
        for j, sol_j in enumerate(solutions):
            if i == j: continue
            if dominates(sol_j, sol_i):
                dominated = True
                break
        if not dominated:
            pareto.append(sol_i)
    return pareto
```

## Output Interpretation

### Pareto Front Example (Efficiency vs Cost)

```
Efficiency (%)
  94 ┤                    ● Pareto optimal solutions
     │               ●  ●
  92 ┤          ●  ●  ●  ●
     │       ●  ●        ●  ●
  90 ┤    ●  ●              ●  ●
     │ ●  ●                    ●  ●  ← dominated solutions
  88 ┤●
     └───────────────────────────── Cost (¥)
      100    120   140   160   180

Decision: Point at (¥140, 92%) balances cost and performance
```

### Selecting from Pareto Front

If the user doesn't specify preferences, use **utopia point method**:
- Find the solution closest to the ideal (min distance in normalized objective space)
- Or use knee-point detection

If the user specifies priority (e.g., "cost is most important"):
- Apply weighted sum with user weights
- Or filter Pareto front by primary objective

## Integration with Maxwell FEA

For cases where analytical calculation is insufficient:

```python
# High-fidelity optimization loop
for candidate in population:
    # 1. Build Maxwell model with candidate parameters
    maxwell_build_model(candidate)
    
    # 2. Run FEA simulation
    run_simulation("RatedLoad")
    
    # 3. Extract actual performance
    T_actual = get_solution_data(["Moving1.Torque"])
    loss_actual = get_solution_data(["CoreLoss", "StrandedLoss"])
    
    # 4. Compute actual efficiency
    eta_actual = P_out / (P_out + loss_actual)
    
    # 5. Feed back to optimizer
    candidate.fitness = [eta_actual, cost(candidate), ...]
```

**Warning:** FEA-in-the-loop optimization is expensive (2-10 min per candidate).
Use analytical pre-screening to reduce the candidate pool by 80%, then FEA-validate
only the top 20 candidates.
