"""Despliega compras_sanitarias.bpmn en Camunda y lanza las 20 instancias
con los assignees precalculados por 2_generador_camunda_fairness.py.

Uso:
  python3 4_camunda_bulk_start.py \
      --camunda-url http://localhost:8080/engine-rest \
      --bpmn compras_sanitarias.bpmn \
      --plan plan_camunda_offline.json
"""

import argparse
import json
from pathlib import Path
from urllib import request

PROCESS_KEY = "Process_ComprasSanitarias"

TASK_TO_VAR = {
    "T1": "assigneeT1",
    "T2.1": "assigneeT2_1",
    "T2.2": "assigneeT2_2",
    "T3": "assigneeT3",
    "T4": "assigneeT4",
}


def deploy_bpmn(camunda_url: str, bpmn_path: Path) -> str:
    boundary = "----InsegusCAI6Boundary"
    body = []
    body.append(f"--{boundary}\r\n")
    body.append('Content-Disposition: form-data; name="deployment-name"\r\n\r\n')
    body.append("compras-sanitarias\r\n")
    body.append(f"--{boundary}\r\n")
    body.append(
        f'Content-Disposition: form-data; name="{bpmn_path.name}"; filename="{bpmn_path.name}"\r\n'
    )
    body.append("Content-Type: application/octet-stream\r\n\r\n")
    body_bytes = ("".join(body)).encode("utf-8")
    body_bytes += bpmn_path.read_bytes()
    body_bytes += f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = request.Request(
        f"{camunda_url.rstrip('/')}/deployment/create",
        data=body_bytes,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload.get("id", "")


def start_instance(camunda_url: str, assignment: dict) -> str:
    variables = {
        TASK_TO_VAR[task]: {"value": assignment[task], "type": "String"}
        for task in TASK_TO_VAR
    }
    variables["instanceId"] = {"value": assignment["instance"], "type": "Long"}
    payload = json.dumps({
        "businessKey": f"CAI6-INST-{assignment['instance']:02d}",
        "variables": variables,
    }).encode("utf-8")
    req = request.Request(
        f"{camunda_url.rstrip('/')}/process-definition/key/{PROCESS_KEY}/start",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=15) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body.get("id", "")


def main():
    parser = argparse.ArgumentParser(description="Despliega BPMN y lanza 20 instancias en Camunda")
    parser.add_argument("--camunda-url", default="http://localhost:8080/engine-rest")
    parser.add_argument("--bpmn", default="compras_sanitarias.bpmn")
    parser.add_argument("--plan", default="plan_camunda_offline.json")
    parser.add_argument("--skip-deploy", action="store_true")
    args = parser.parse_args()

    bpmn_path = Path(args.bpmn).resolve()
    plan_path = Path(args.plan).resolve()

    if not args.skip_deploy:
        deployment_id = deploy_bpmn(args.camunda_url, bpmn_path)
        print(f"[OK] Despliegue BPMN: {deployment_id}")

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    for assignment in plan:
        instance_id = start_instance(args.camunda_url, assignment)
        print(f"[OK] Instancia {assignment['instance']:02d} arrancada: {instance_id}")


if __name__ == "__main__":
    main()
