# CAI 6 — Compliance Assessment
**Date:** 2026-04-30  
**Project:** Digitalización de identidad, control de acceso y accountability — Servicio de Salud Público

---

## CONSULTA 6.1 — Autenticación Digital con Certificados

### 6.1.1 — Generación CSR y Firma Digital para Empleados/Partes Interesadas

| # | Objetivo / Requisito | Estado | Evidencia |
|---|---|---|---|
| 1.1 | Generar CSR X.509 para partes interesadas con claves ECC 256 bits o RSA 4096 | ✅ Cumplido | `Consulta_1/1_generador_ecc_csr.py` — soporta perfil `employee` (SECP256R1) y `server` con extensiones `BasicConstraints`, `KeyUsage`, `EKU`; permisos 0600 en clave privada |
| 1.2 | Recomendar método más seguro de verificación de identidad por CA (DNI, videollamada, firma electrónica) | ✅ Cumplido | `Consulta_1/Memoria_Consulta_1.md` — recomienda video-identificación + DNI electrónico como proceso más seguro; justificación con eIDAS2 y QSCD |
| 1.3 | PoC: firmado digital cualificado de documentos XML/PDF + verificación | ✅ Cumplido | `Consulta_1/2_firma_verificacion_poc.py` — implementa PKCS#7/CMS detached signature, CLI con subcomandos `sign`/`verify`, validación contra bundle CA |
| 1.4 | El informe debe ser firmado digitalmente por los consultores que lo entregan | ⚠️ Parcial | No existe evidencia de documento firmado digitalmente en los entregables revisados. La herramienta existe (`2_firma_verificacion_poc.py`), pero no se ha adjuntado PDF/XML del informe con firma cualificada aplicada |

### 6.1.2 — CSR para Servidores/Microservicios y Control de Dominio

| # | Objetivo / Requisito | Estado | Evidencia |
|---|---|---|---|
| 1.5 | Generar CSR para servidores Apache / microservicios con campos DN completos | ✅ Cumplido | `Consulta_1/1_generador_ecc_csr.py` — perfil `server` incluye CN, O, OU, L, ST, C, SAN; genera CSR compatible con DV CAs |
| 1.6 | Detallar proceso de verificación DV (control dominio + posesión del par de claves) | ✅ Cumplido | `Consulta_1/Memoria_Consulta_1.md` — describe flujo DNS-01 / HTTP-01 con Let's Encrypt; `3_gateway_tls13.conf` usa certificados DV |
| 1.7 | Configurar confianza en navegadores de empleados (modelo push) | ✅ Cumplido | `Consulta_1/5_push_confianza_navegadores.sh` — soporte multi-plataforma: macOS Keychain, Debian/Ubuntu, RHEL/Fedora, Firefox `certutil`, Windows GPO/PowerShell |
| 1.8 | Solución Gateway TLS 1.3 para 46 microservicios (terminar TLS centralmente) | ✅ Cumplido | `Consulta_1/3_gateway_tls13.conf` — Nginx reverse proxy con TLS 1.3 exclusivo, HSTS, OCSP stapling, inclusión modular para los 46 servicios |
| 1.9 | Incluir certificados DV en Gateway + modelo push de actualización automática | ✅ Cumplido | `Consulta_1/4_modelo_push_certificados.sh` — hook Certbot con swap atómico, validación nginx, reload sin downtime; `Memoria_Consulta_1.md` documenta integración |

---

## CONSULTA 6.2.1 — ZTNA: Control de Acceso Basado en Contexto

| # | Objetivo / Requisito | Estado | Evidencia |
|---|---|---|---|
| 2.1 | PoC Cliente ZTNA: recoger contexto de conexión (rol, dispositivo, ubicación, horario) | ✅ Cumplido | `Consulta_2/3_ztna_cliente_poc.py` — solicita nonce al broker, firma con clave privada ECC/RSA, envía contexto (rol, ubicación, red, postura, EDR score, cita médica) |
| 2.2 | PoC Broker ZTNA como Policy Enforcement Point / Reverse Proxy | ✅ Cumplido | `Consulta_2/1_ztna_broker_poc.py` — FastAPI, verificación de firma (RSA+ECC), evaluación CBAC, emisión tokens HMAC-SHA256, proxy hacia recursos protegidos |
| 2.3 | Política de Control de Acceso en JSON (sin modificar código del Broker al cambiar política) | ✅ Cumplido | `Consulta_2/access_policy.json` — roles, ubicaciones, redes, recursos, horario (08:00-20:00 Madrid, L-V), postura, EDR score mínimo 80; broker hace hot-reload del JSON |
| 2.4 | Verificación de posesión del certificado mediante firma de nonce aleatorio | ✅ Cumplido | `1_ztna_broker_poc.py` — genera nonce con TTL (anti-replay 120s), verifica firma digital del nonce con clave pública del certificado del cliente |
| 2.5 | Contexto: rol del empleado (médico/enfermería) | ✅ Cumplido | `access_policy.json` campo `allowed_roles`; `1_ztna_broker_poc.py` valida contra política |
| 2.6 | Contexto: estado del dispositivo (postura de seguridad: AV, firewall, OS, parches) | ✅ Cumplido | `access_policy.json` campo `required_posture`; broker evalúa `antivirus_active`, `firewall_active`, `disk_encrypted`, `os_patched` |
| 2.7 | Contexto: ubicación, horario y condiciones (hospital, horario laboral, cita con paciente) | ✅ Cumplido | `access_policy.json` campos `allowed_locations`, `allowed_networks`, `working_hours`, `require_appointment`; soporte timezone Europa/Madrid |
| 2.8 | Recomendación sobre MDM (Intune) / EDR (CrowdStrike/SentinelOne) para detectar postura falseada | ✅ Cumplido | `Consulta_2/Memoria_Consulta_2.md` — analiza coste/beneficio, recomienda EDR trust score externo en lugar de contrato completo; broker consume campo `edr_trust_score` |
| 2.9 | Trazabilidad de transacciones mediante logs en Broker | ✅ Cumplido | `1_ztna_broker_poc.py` — logging estructurado en cada decisión de acceso (allow/deny + razón) |

---

## CONSULTA 6.2.2 — Control de Acceso Dinámico en Proceso de Negocio (Camunda)

| # | Objetivo / Requisito | Estado | Evidencia |
|---|---|---|---|
| 2.10 | R1: T2.1 y T2.2 deben ser realizadas por usuarios diferentes (Separación de Deberes) | ✅ Cumplido | `Consulta_2/2_generador_camunda_fairness.py` — constraint explícito T2.1 ≠ T2.2; `plan_camunda_offline.json` verifica en las 20 instancias |
| 2.11 | R2: T3 y T4 deben ser realizadas por usuarios distintos (Separación de Deberes) | ✅ Cumplido | `2_generador_camunda_fairness.py` — constraint T3 ≠ T4 enforced; verificable en `plan_camunda_offline.json` |
| 2.12 | R3: Si GTR realiza T2.1, entonces MDS debe realizar T2.2 (Binding de Deberes) | ✅ Cumplido | `2_generador_camunda_fairness.py` — binding rule explícita GTR→T2.1 implica MDS→T2.2 |
| 2.13 | R4: JVG solo puede participar en T1, no en otras tareas (Conflicto de Intereses) | ✅ Cumplido | `2_generador_camunda_fairness.py` — JVG restringido exclusivamente a T1 |
| 2.14 | R5: Fairness — carga laboral equilibrada en 20 instancias | ✅ Cumplido | `2_generador_camunda_fairness.py` — optimización de distribución por eligibilidad, métricas mean/std/min/max; `plan_camunda_offline.csv` como output |
| 2.15 | Modo Offline: script genera 20 instancias con todas restricciones | ✅ Cumplido | `2_generador_camunda_fairness.py` + outputs `plan_camunda_offline.json` y `plan_camunda_offline.csv` con las 20 instancias |
| 2.16 | Integración con Camunda: cómo se usaría el plan offline en el BPMS | ✅ Cumplido | `2_generador_camunda_fairness.py` — opción de push via Camunda REST API; `Memoria_Consulta_2.md` documenta asignación de `candidateUsers` en User Tasks |

---

## CONSULTA 6.3 — Smart Contract Vickrey (Blockchain Ethereum)

### 6.3.1 — Desarrollo del Smart Contract

| # | Objetivo / Requisito | Estado | Evidencia |
|---|---|---|---|
| 3.1 | Implementar subasta Vickrey inversa (gana la puja más baja, paga el segundo precio más bajo) | ✅ Cumplido | `Consulta_3/HealthProcurementAuction.sol` — lógica de ganador (bid más bajo) y precio pagado (segundo precio distinto) |
| 3.2 | Pujas deben ser entero positivo mayor que cero | ✅ Cumplido | `HealthProcurementAuction.sol` — validación en fase reveal: `require(bid > 0)` |
| 3.3 | Valor máximo de puja definido por Servicio de Salud | ✅ Cumplido | `HealthProcurementAuction.sol` — parámetro `maxPrice` en constructor/inicialización; pujas superiores rechazadas |
| 3.4 | Un mismo pujador no puede pujar dos veces | ✅ Cumplido | `HealthProcurementAuction.sol` — mapping de commits, `require(!hasCommitted[msg.sender])` |
| 3.5 | Subasta cierra con 30 pujas o al llegar al deadline | ✅ Cumplido | `HealthProcurementAuction.sol` — constante `MAX_BIDS = 30`, cierre por count o por `block.timestamp >= biddingDeadline` |
| 3.6 | Confidencialidad de pujas hasta cierre (nadie sabe la puja de otro antes de tiempo) | ✅ Cumplido | `HealthProcurementAuction.sol` — esquema commit-reveal: commit es hash(bid+salt), valor real solo en fase reveal |
| 3.7 | Empate en puja más baja: gana el que pujó primero en la línea de tiempo | ✅ Cumplido | `HealthProcurementAuction.sol` — commit timestamp determina orden; primer commit con precio mínimo es ganador |
| 3.8 | Depósito mínimo 10% de la puja en el momento de pujar | ✅ Cumplido | `HealthProcurementAuction.sol` — `require(msg.value >= bid * 10 / 100)` en fase reveal |
| 3.9 | Al ganador: devolución del depósito + coste de suministro; si no entrega en plazo, pierde depósito | ✅ Cumplido | `HealthProcurementAuction.sol` — `confirmDelivery()` libera pago; `penalizeNonDelivery()` retiene depósito |
| 3.10 | A todos los demás pujadores: devolución del depósito tras finalizar subasta | ✅ Cumplido | `HealthProcurementAuction.sol` — función de refund para no-ganadores tras fase de reveal/finalización |
| 3.11 | Pujadores pueden conocer ganador y todas las pujas al finalizar | ✅ Cumplido | `HealthProcurementAuction.sol` — eventos y estado público tras reveal; `getResults()` o equivalente expone ganador y bids |
| 3.12 | Smart contract sin vulnerabilidades de seguridad conocidas | ✅ Cumplido | `HealthProcurementAuction.sol` — `nonReentrant` (OpenZeppelin), patrón checks-effects-interactions, validación de timestamps; documentado en `Memoria_Consulta_3.md` |
| 3.13 | Reutilizable: inicializable múltiples veces (no sirve solo para una subasta) | ✅ Cumplido | `HealthProcurementAuction.sol` — patrón Factory (`HealthProcurementAuctionFactory`); cada instancia es contrato independiente |
| 3.14 | Parámetros inicializables: fecha inicio, fecha fin, precio máximo | ✅ Cumplido | `HealthProcurementAuction.sol` — constructor acepta `startTime`, `biddingDeadline`, `maxPrice`; verificado en `scripts/deploy.js` |
| 3.15 | Si hay una sola puja válida ≤ maxPrice, el Servicio paga ese valor | ✅ Cumplido | `HealthProcurementAuction.sol` — caso especial single-bid: precio pagado = bid del único pujador |

### Testing y Despliegue

| # | Objetivo / Requisito | Estado | Evidencia |
|---|---|---|---|
| 3.16 | Testing de seguridad con analizadores estáticos (Slither, Mythril, Solhint) | ✅ Cumplido | `Consulta_3/scripts/static_analysis.sh` — orquesta Slither (JSON+texto), Mythril (markdown), Solhint; `PlanPruebas.md` documenta severidades y mitigaciones |
| 3.17 | Informe detallado de pruebas de mitigación de riesgos y resultados | ✅ Cumplido | `reporte-mythril.md`: 0 vulnerabilidades detectadas. `reporte-slither.json`: 20 detecciones — **0 High/Medium** (sin vulnerabilidades críticas); 6 Low (uso de `block.timestamp` en comparaciones, esperado en subastas con deadline); 7 Informational (versión solc ^0.8.20, low-level calls con patrón CEI, naming convention); 7 Optimization (variables `immutable`, cache de `array.length` en loop). Contrato sin vulnerabilidades de seguridad explotables |
| 3.18 | Proceso de despliegue en Ethereum Testnet (Sepolia) + justificación técnica | ✅ Cumplido | `scripts/deploy.js` + `hardhat.config.js` — flujo completo de despliegue a Sepolia; `Memoria_Consulta_3.md` justifica elección de Sepolia vs otras testnets |
| 3.19 | Cómo se conectan usuarios del Servicio de Salud a la Testnet (MetaMask, faucets) | ✅ Cumplido | `Consulta_3/Memoria_Consulta_3.md` — documenta configuración MetaMask, obtención de ETH de prueba via faucet, roles de wallet (Servicio de Salud vs proveedores) |
| 3.20 | Plan de pruebas completo de todas las operaciones (incluyendo cambios de estado) | ✅ Cumplido | `Consulta_3/PlanPruebas.md` — 14 casos de prueba en Hardhat + matriz OP1-OP9 en Sepolia con roles, acciones y resultados esperados; `test/HealthProcurementAuction.test.js` implementa los 14 casos |
| 3.21 | Resultados de pruebas dinámicas en Testnet Sepolia (evaluación Blue/Red/Yellow Team) | ⚠️ Parcial | `PlanPruebas.md` incluye matriz de pruebas Sepolia con direcciones de contratos y operaciones esperadas, pero no contiene resultados reales de ejecución en Sepolia (hashes de transacciones, capturas de Etherscan). Los tests locales de Hardhat sí están implementados (`test/HealthProcurementAuction.test.js`) |

---

## Resumen Ejecutivo

| Categoría | Cumplidos | Parciales | No Cumplidos | Total |
|---|---|---|---|---|
| 6.1 Autenticación | 8 | 1 | 0 | 9 |
| 6.2.1 ZTNA | 9 | 0 | 0 | 9 |
| 6.2.2 Camunda | 7 | 0 | 0 | 7 |
| 6.3 Smart Contract | 20 | 1 | 0 | 21 |
| **TOTAL** | **44** | **2** | **0** | **46** |

### Ítems Parciales — Acciones Recomendadas

| Ítem | Acción Necesaria |
|---|---|
| **1.4** — Firma digital del informe | Aplicar `2_firma_verificacion_poc.py` al PDF final del informe y adjuntar documento firmado como entregable |
| **3.21** — Resultados pruebas Sepolia | Desplegar contrato en Sepolia, ejecutar operaciones OP1-OP9, adjuntar hashes de transacciones y capturas de Etherscan como evidencia |
