import argparse
import csv
import json
from itertools import product
from pathlib import Path
from statistics import mean, pstdev
from urllib import error, request

TASKS = ["T1", "T2.1", "T2.2", "T3", "T4"]

# Herencia de roles aplicada con la restriccion R4 (JVG solo puede hacer T1).
CANDIDATES = {
    "T1": ["HYV", "JVG"],
    "T2.1": ["GTR", "LPG", "RGB", "HYV", "BJC"],
    "T2.2": ["RGB", "MDS", "LPG", "HYV"],
    "T3": ["PGR"],
    "T4": ["MFE", "HJR", "PTS", "IHP", "PGR"],
}

EMPLOYEES = sorted({employee for task in TASKS for employee in CANDIDATES[task]}.union({"JVG"}))


def _employee_capacities() -> dict[str, int]:
    capacities = {employee: 0 for employee in EMPLOYEES}
    for task in TASKS:
        for employee in CANDIDATES[task]:
            capacities[employee] += 1
    return capacities


def _valid_assignment(assignment: dict[str, str]) -> bool:
    # R1: T2.1 y T2.2 deben ser usuarios distintos.
    if assignment["T2.1"] == assignment["T2.2"]:
        return False

    # R2: T3 y T4 deben ser usuarios distintos.
    if assignment["T3"] == assignment["T4"]:
        return False

    # R3: Si GTR hace T2.1, MDS debe hacer T2.2.
    if assignment["T2.1"] == "GTR" and assignment["T2.2"] != "MDS":
        return False

    # R4: Si JVG participa, solo puede hacerlo en T1.
    if assignment["T1"] != "JVG" and "JVG" in assignment.values():
        return False

    return True


def _all_valid_assignments() -> list[dict[str, str]]:
    all_assignments: list[dict[str, str]] = []
    for values in product(*(CANDIDATES[task] for task in TASKS)):
        assignment = dict(zip(TASKS, values))
        if _valid_assignment(assignment):
            all_assignments.append(assignment)
    return all_assignments


def _fairness_score(projected_loads: dict[str, int], capacities: dict[str, int], assigned_tasks: int) -> tuple[float, float, int]:
    # Objetivo de fairness: aproximar carga observada a carga esperada segun elegibilidad.
    total_capacity = sum(capacities.values())
    weighted_error = 0.0

    for employee, load in projected_loads.items():
        expected = assigned_tasks * (capacities[employee] / total_capacity)
        weighted_error += (load - expected) ** 2

    values = list(projected_loads.values())
    spread = max(values) - min(values)
    deviation = pstdev(values)
    return (weighted_error, deviation, spread)


def generate_offline_plan(num_instances: int = 20) -> tuple[list[dict[str, str]], dict[str, int], dict[str, float]]:
    valid_assignments = _all_valid_assignments()
    capacities = _employee_capacities()
    loads = {employee: 0 for employee in EMPLOYEES}
    plan: list[dict[str, str]] = []

    for instance_idx in range(1, num_instances + 1):
        best_assignment = None
        best_score = None

        for assignment in valid_assignments:
            projected = dict(loads)
            for task in TASKS:
                projected[assignment[task]] += 1

            assigned_tasks = instance_idx * len(TASKS)
            score = _fairness_score(projected, capacities, assigned_tasks)
            if best_score is None or score < best_score:
                best_score = score
                best_assignment = assignment

        if best_assignment is None:
            raise RuntimeError("No se encontro asignacion valida para una instancia")

        applied = dict(best_assignment)
        plan.append(applied)
        for task in TASKS:
            loads[applied[task]] += 1

    metrics = {
        "mean_load": mean(loads.values()),
        "std_load": pstdev(loads.values()),
        "max_load": max(loads.values()),
        "min_load": min(loads.values()),
    }
    return plan, loads, metrics


def export_plan(plan: list[dict[str, str]], output_json: Path, output_csv: Path):
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(
            [{"instance": idx + 1, **assignment} for idx, assignment in enumerate(plan)],
            f,
            indent=2,
            ensure_ascii=False,
        )

    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["instance", *TASKS])
        writer.writeheader()
        for idx, assignment in enumerate(plan):
            writer.writerow({"instance": idx + 1, **assignment})


def push_to_camunda(camunda_url: str, mapping_file: Path, plan: list[dict[str, str]]):
    with open(mapping_file, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    for row in mapping:
        instance = int(row["instance"])
        task_ids = row["task_ids"]
        assignment = plan[instance - 1]

        for task_name, task_id in task_ids.items():
            assignee = assignment[task_name]
            payload = json.dumps({"userId": assignee}).encode("utf-8")
            endpoint = f"{camunda_url.rstrip('/')}/task/{task_id}/assignee"
            req = request.Request(
                endpoint,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=10):
                    pass
            except error.HTTPError as exc:
                raise RuntimeError(f"Error Camunda en tarea {task_name}/{task_id}: {exc.code}") from exc


def print_summary(plan: list[dict[str, str]], loads: dict[str, int], metrics: dict[str, float]):
    print(f"[OK] Plan offline generado para {len(plan)} instancias")
    for idx, assignment in enumerate(plan, start=1):
        print(f"Instancia {idx:02d}: {assignment}")

    print("\nDistribucion de carga (R5 fairness):")
    for employee, load in sorted(loads.items(), key=lambda item: item[1], reverse=True):
        print(f"  - {employee}: {load}")

    print("\nMetricas fairness:")
    print(f"  - mean_load: {metrics['mean_load']:.2f}")
    print(f"  - std_load: {metrics['std_load']:.2f}")
    print(f"  - max_load: {metrics['max_load']:.0f}")
    print(f"  - min_load: {metrics['min_load']:.0f}")


def main():
    parser = argparse.ArgumentParser(description="Generador offline de asignaciones Camunda con SoD/BoD/CoI/Fairness")
    parser.add_argument("--instances", type=int, default=20)
    parser.add_argument("--output-json", default="plan_camunda_offline.json")
    parser.add_argument("--output-csv", default="plan_camunda_offline.csv")
    parser.add_argument("--camunda-url", default=None, help="URL base de Camunda REST, ej: http://localhost:8080/engine-rest")
    parser.add_argument(
        "--camunda-task-mapping",
        default=None,
        help="JSON con instance y task_ids por tarea para push forzado",
    )
    args = parser.parse_args()

    plan, loads, metrics = generate_offline_plan(args.instances)
    export_plan(plan, Path(args.output_json), Path(args.output_csv))
    print_summary(plan, loads, metrics)
    print(f"\n[OK] JSON: {args.output_json}")
    print(f"[OK] CSV: {args.output_csv}")

    if args.camunda_url and args.camunda_task_mapping:
        push_to_camunda(args.camunda_url, Path(args.camunda_task_mapping), plan)
        print("[OK] Asignaciones enviadas a Camunda via REST API")


if __name__ == "__main__":
    main()
