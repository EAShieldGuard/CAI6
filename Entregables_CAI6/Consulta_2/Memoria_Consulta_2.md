# Resolucion tecnica - Consulta 6.2 (ZTNA y control de acceso dinamico)

## 1. PoC ZTNA Broker + Cliente con CBAC desacoplado
Archivos implementados:
- 1_ztna_broker_poc.py
- 3_ztna_cliente_poc.py
- access_policy.json
- 0_generar_pki_demo.py

### Broker ZTNA (Policy Enforcement Point)
Capacidades de seguridad implementadas:
1. Politica CBAC en JSON, recargada en caliente (sin tocar codigo).
2. Nonce de un solo uso con TTL (anti-replay) y vinculacion nonce-certificado.
3. Verificacion de prueba de posesion por firma de nonce.
4. Compatibilidad de verificacion para certificados RSA y ECC.
5. Validacion de certificado de cliente:
	- Ventana temporal de validez.
	- EKU ClientAuth.
	- Firma del certificado contra CA de confianza (trusted_ca.pem).
6. Decision CBAC con contexto completo:
	- rol, ubicacion, tipo de red,
	- horario laboral,
	- postura del endpoint (AV, firewall, cifrado, parcheo),
	- score EDR y correlacion cita-paciente (si politica lo exige).

### Cliente ZTNA
La PoC cliente:
1. Solicita nonce al broker.
2. Firma challenge nonce_id:nonce con su clave privada.
3. Envia contexto y firma para decision de acceso.
4. Recibe token de sesion y recurso autorizado.

## 2. Mitigacion de fake posture con coste contenido
Se recomienda integrar telemetria de endpoint desde stack open source (Wazuh + osquery) y usar su resultado como input del trust score EDR de la politica CBAC.

Con ello se evita confiar ciegamente en datos locales del cliente y se reduce dependencia de licencias costosas.

## 3. Control de acceso dinamico en Camunda - Modo Offline
Archivos implementados:
- 2_generador_camunda_fairness.py
- compras_sanitarias.bpmn
- 4_camunda_bulk_start.py

Se adopta enfoque Offline por robustez operativa ante sobrecarga y para evitar efecto cherry-picking.

Cobertura R1-R5:
1. R1: T2.1 y T2.2 con usuarios distintos.
2. R2: T3 y T4 con usuarios distintos.
3. R3: si GTR ejecuta T2.1, entonces MDS ejecuta T2.2.
4. R4: si JVG participa, solo puede hacerlo en T1.
5. R5: fairness con optimizacion de carga segun elegibilidad.

### Modelo BPMN (compras_sanitarias.bpmn)
Proceso ejecutable Camunda Platform 7 con:
- 5 User Tasks: T1 (DR), T2.1 (TR), T2.2 (TC), T3 (DM), T4 (DE, PS).
- AND-split tras T1, AND-join previo a T3.
- camunda:assignee="${assigneeTx}" por tarea; variables inyectadas al arrancar instancia.
- candidateGroups por rol para visibilidad en Tasklist.

### Generador de plan (2_generador_camunda_fairness.py)
Salidas implementadas:
- Plan de instancias en JSON (plan_camunda_offline.json).
- Plan de instancias en CSV (plan_camunda_offline.csv).
- Metricas de fairness (media, desviacion, maximo y minimo).

Ejemplo:
python3 2_generador_camunda_fairness.py --instances 20 --output-json plan_camunda_offline.json --output-csv plan_camunda_offline.csv

### Despliegue y arranque masivo (4_camunda_bulk_start.py)
Despliega el BPMN y arranca las 20 instancias via REST API de Camunda Engine:
1. POST /deployment/create (multipart) -> deploymentId.
2. POST /process-definition/key/Process_ComprasSanitarias/start x20 con variables assigneeT1/T2_1/T2_2/T3/T4 + instanceId extraidas del plan JSON.

Ejemplo:
python3 4_camunda_bulk_start.py --camunda-url http://localhost:8080/engine-rest --bpmn compras_sanitarias.bpmn --plan plan_camunda_offline.json

Resultado verificado: 20 processInstanceId generados con businessKey CAI6-INST-01..20; assignees conformes al plan en GET /task?taskDefinitionKey=UserTask_T1.

## 4. Mejoras aplicadas en esta revision

### Broker ZTNA
- Token HMAC con secreto fuerte obligatorio por entorno (`INSEGUS_TOKEN_SECRET`), evitando secretos hardcodeados o tokens efimeros no reproducibles.
- Soporte de `not_valid_before_utc` / `not_valid_after_utc` para evitar APIs deprecadas de `cryptography`.
- Ventana horaria evaluada en la zona horaria definida en politica (`Europe/Madrid`) y opcional `weekdays_only` para restringir acceso a dias laborables.

### Politica CBAC
- Anadido `weekdays_only` en `working_hours`.
- Politica recargada en cada peticion (no reinicio del broker en cambios).

## 5. Plan de pruebas (PoC)
1. `python3 0_generar_pki_demo.py` -> CA + cert/clave de cliente.
2. `uvicorn 1_ztna_broker_poc:app --reload --port 8000` (broker arranca; en produccion detras de TLS reverse proxy).
3. `python3 3_ztna_cliente_poc.py --certificate cliente_ztna_cert.pem --private-key cliente_ztna_key.pem` -> token de sesion.
4. Variantes de prueba:
   - `--role administrativo` -> 403 rol no autorizado.
   - `--location Domicilio` -> 403 ubicacion no autorizada.
   - `--no-appointment-match` -> 403 cita no correlacionada.
   - Modificar `timestamp_utc` fuera de horario -> 403 horario.
5. `python3 2_generador_camunda_fairness.py --instances 20 --output-json plan_camunda_offline.json --output-csv plan_camunda_offline.csv` -> plan offline R1-R5.
6. `python3 4_camunda_bulk_start.py --bpmn compras_sanitarias.bpmn --plan plan_camunda_offline.json` -> despliega BPMN + arranca 20 instancias; verificar en Camunda Tasklist (http://localhost:8080/camunda) que aparecen 20 tareas T1 con assignee conforme al plan.
