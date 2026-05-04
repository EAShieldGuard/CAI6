**Hoja de Control del Documento**

* **Título del Informe:** INFORME DE DIGITALIZACIÓN DE LA IDENTIDAD, EL CONTROL DE ACCESO Y LA ACCOUNTABILITY EN LAS COMPRAS DE UN SERVICIO DE SALUD PÚBLICO
* **Fecha:** 04/05/2026
* **Modifica a:** ……………
* **Realizado por:** EA ShieldGuard
* **Integrantes:** Fernando Triguero, José Manuel García y Adrián Ramírez
* **Aprobado por:** CISO de INSEGUS

## 

## **1\. Resumen Ejecutivo**

Este informe detalla la solución técnica desarrollada por EA ShieldGuard para un Servicio de Salud Público en el marco del Plan de Digitalización, con alineación a eIDAS2, ENS Categoría Alta, RGPD, ISO/IEC 27001:2022 y NIST SP 800-57. El trabajo abarca tres líneas de actuación:

1. **Autenticación digital (Consulta 6.1):** Generación de CSR con claves ECC P-256 y RSA-4096 para partes interesadas (empleados, directivos, proveedores) y para los 46 microservicios del Servicio; firma digital cualificada PKCS\#7/CMS para documentos XML/PDF; despliegue de un TLS 1.3 Gateway centralizado que reduce la gestión de certificados de 46 a 1; y modelo de distribución push del certificado raíz a los navegadores corporativos.

2. **Control de acceso (Consulta 6.2):** Broker ZTNA implementado como Reverse Proxy con política contextual (CBAC) cargada desde JSON sin modificación de código, verificación de posesión del certificado mediante nonce con TTL anti-replay, y propuesta de alternativa de bajo coste (Wazuh + osquery) frente a MDM/EDR propietario. Adicionalmente, precálculo offline de las 20 instancias del proceso de compra en Camunda satisfaciendo separación de deberes dinámica, binding de deberes, conflicto de intereses y distribución equitativa de carga.

3. **Accountability en compras (Consulta 6.3):** Desarrollo, análisis estático (Slither + Mythril + Solhint) y despliegue en Ethereum Sepolia de un Smart Contract `HealthProcurementAuction` con esquema commit-reveal para subasta Vickrey inversa. El análisis estático no identificó vulnerabilidades High o Medium. Los 14 casos de prueba automatizados en Hardhat cubren todos los requisitos funcionales y de seguridad.

---

## **2\. Consulta 6.1 – Autenticación Digital con Certificados ECC**

### **Consulta 6.1.1 – CSR para partes interesadas y firma digital cualificada**

#### Metodología y tecnologías usadas

La generación de claves y CSR se realiza mediante el script Python `1_generador_ecc_csr.py`, que admite dos perfiles y dos algoritmos:

* **Perfil empleado (ECC P-256 o RSA-4096):** genera par de claves, aplica extensiones X.509v3 (`BasicConstraints: CA:FALSE`, `KeyUsage: digitalSignature`, `EKU: ClientAuth`) y produce el CSR en formato PEM. La clave privada se almacena con permisos 0600.
* **Perfil servidor (ECC P-256 o RSA-4096):** igual que el anterior, con adición de SANs (`subjectAltName`) para los nombres de dominio y microservicios del Servicio.

Sobre el **método de verificación de identidad recomendado:** de entre las opciones disponibles (DNI presencial, videollamada, firma electrónica con otro certificado), EA ShieldGuard recomienda la **video-identificación asíncrona certificada con lectura NFC del DNIe**, por los siguientes motivos:

1. Extracción de identidad firmada criptográficamente por la Dirección General de la Policía, no declarada por el usuario.
2. Matching biométrico entre el video grabado y la foto del chip NFC, resistente a ataques deepfake con las soluciones certificadas actuales.
3. Proceso remoto, escalable a miles de empleados del Servicio sin desplazamiento presencial.
4. Cumplimiento del nivel de garantía "Alto" que exige eIDAS2 para certificados cualificados.

La video-identificación presencial con DNI físico es más robusta ante suplantaciones digitales, pero su coste operacional no se justifica para la plantilla completa del Servicio cuando existe el proceso NFC certificado.

Para la **firma digital cualificada**, el script `2_firma_verificacion_poc.py` implementa firma PKCS\#7/CMS detached sobre documentos XML o PDF usando la clave privada del empleado. La verificación comprueba la integridad del documento y la cadena de confianza hasta el bundle de la CA corporativa.

| Componente | Implementación | Justificación |
| :---- | :---- | :---- |
| Generación de claves | Python `cryptography`, curva SECP256R1 (ECC P-256) | 256 bits equivalen a RSA-3072 en seguridad (NIST SP 800-57); adecuado para IoT y dispositivos con recursos limitados |
| Alternativa | RSA-4096 (parametrizable) | Compatible con CAs cualificadas que aún no soportan ECC P-256 |
| Formato CSR | PKCS\#10, codificación PEM | Estándar X.509v3; compatible con todas las CAs cualificadas |
| Firma de documentos | PKCS\#7/CMS detached con SHA-256 | Firma separable del documento; verificable sin la herramienta de firma |
| QSCD (producción) | DNIe / Token USB YubiKey-SafeNet / HSM (Cl@ve Firma) | La clave privada nunca se exporta del QSCD, requisito eIDAS2 para Firma Electrónica Cualificada (QES) |

**Límite legal relevante:** la PoC genera firmas con clave privada en fichero PEM. Bajo eIDAS2, esto produce una **Firma Electrónica Avanzada (AdES)**, no cualificada (QES). Para que el Servicio de Salud opere con QES, el empleado debe generar y usar su clave desde el QSCD (DNIe o token USB) invocando la firma vía PKCS\#11. La herramienta desarrollada es válida como demostración del flujo; en producción, el paso de firma se delega al QSCD. La validación del tipo de firma puede realizarse a través de la plataforma **VALIDe** del Gobierno de España.

#### Resultados técnicos obtenidos

Generación de CSR para empleado (perfil ECC P-256):

```bash
python3 1_generador_ecc_csr.py \
  --profile employee --algorithm ecc \
  --common-name "Ana Garcia" \
  --email agarcia@salud.gov \
  --org "Servicio Salud Publico" \
  --country ES --state Andalucia --locality Sevilla

# Salida:
# empleado_key.pem  (permisos 0600)
# empleado_csr.pem  (enviable a la CA cualificada)
```

Generación de CSR para servidor/microservicio con SAN:

```bash
python3 1_generador_ecc_csr.py \
  --profile server --algorithm ecc \
  --common-name api.salud.gov \
  --email admin@salud.gov \
  --san www.api.salud.gov --san gateway.salud.gov

# Salida:
# server_key.pem  (permisos 0600)
# server_csr.pem  (con extensión SAN incluida)
```

Firma y verificación de documento XML/PDF:

```bash
# Firmar
python3 2_firma_verificacion_poc.py sign \
  --document informe.xml \
  --private-key empleado_key.pem \
  --certificate empleado_cert.pem
# Genera: informe.xml.p7s

# Verificar
python3 2_firma_verificacion_poc.py verify \
  --document informe.xml \
  --signature informe.xml.p7s \
  --ca-bundle trusted_ca.pem
```

**Cumplimiento normativo:** eIDAS2 (Reglamento UE obligatorio fin 2026), ENS Art. 11, ISO/IEC 27001:2022 A.8.24, NIST SP 800-57 Part 1 Rev. 5.

---

### **Consulta 6.1.2 – Certificados DV para servidores/microservicios, Gateway TLS y modelo push**

#### Metodología y tecnologías usadas

Para los 46 microservicios del Servicio de Salud se ha optado por **Let's Encrypt con validación DV (Domain Validation)** mediante el desafío HTTP-01: Certbot coloca un token aleatorio en `/.well-known/acme-challenge/` y la CA de Let's Encrypt verifica que el servidor controla el dominio consultando ese recurso. Este proceso prueba tanto el control del dominio como la posesión del par de claves, ya que el token se genera a partir de la clave de cuenta de Certbot registrada.

El problema de gestionar 46 certificados se resuelve con un **TLS 1.3 Gateway centralizado** (Nginx 1.24+): un único punto de entrada termina TLS externamente, gestiona un solo certificado DV y enruta el tráfico hacia los microservicios internos en HTTP plano dentro de la VLAN privada. Las mejoras de seguridad aplicadas incluyen:

* TLS 1.3 exclusivo (`ssl_protocols TLSv1.3`), eliminando TLS 1.2 y versiones previas.
* HSTS con `max-age` de un año e `includeSubDomains`.
* OCSP Stapling activo para evitar latencia en validación de revocación sin contactar a la CA en cada handshake.
* Inclusión modular de los 46 microservicios con un patrón `include /etc/nginx/services/*.conf`, lo que permite añadir o retirar servicios sin tocar la configuración principal.
* Deploy-hook de Certbot con swap atómico del certificado, validación `nginx -t` previa y recarga sin corte de servicio.

Para la **distribución push del certificado CA raíz** a los navegadores de los empleados, el script `5_push_confianza_navegadores.sh` automatiza la instalación en:

* macOS: `security add-trusted-cert` en el System Keychain.
* Linux Debian/Ubuntu: `update-ca-certificates`.
* Linux RHEL/Fedora: `update-ca-trust`.
* Firefox: `certutil` en los perfiles NSS del usuario.
* Windows: `Import-Certificate` (PowerShell) o distribución mediante GPO de Active Directory.

En producción, el push se orquesta con **MDM (Intune o Jamf)** para flotas de dispositivos mixtos o con **Ansible/Salt** para servidores Linux gestionados.

#### Resultados técnicos obtenidos

Fragmento de configuración del Gateway TLS 1.3 (`3_gateway_tls13.conf`):

```nginx
server {
    listen 443 ssl;
    server_name gateway.salud.gov;

    ssl_certificate     /etc/letsencrypt/live/gateway.salud.gov/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/gateway.salud.gov/privkey.pem;
    ssl_protocols       TLSv1.3;
    ssl_stapling        on;
    ssl_stapling_verify on;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;

    # Inclusión de los 46 microservicios
    include /etc/nginx/services/*.conf;
}
```

| Aspecto | Resultado |
| :---- | :---- |
| Certificados a gestionar | Reducción de 46 a 1 (Gateway único) |
| Renovación automática | Certbot cron cada 60 días; alerta si expiración < 30 días |
| Validación de revocación | OCSP Stapling sin contacto adicional a la CA por handshake |
| Distribución CA raíz | Push multi-plataforma sin intervención del usuario |

**Cumplimiento normativo:** ENS Categoría Alta (confidencialidad en transmisiones), NIST SP 800-52 Rev. 2 (TLS 1.3), RGPD Art. 32 (medidas técnicas de seguridad en transmisión de datos de salud).

---

## **3\. Consulta 6.2 – Verificación Automática de Políticas de Control de Acceso**

### **Consulta 6.2.1 – Control de Acceso Basado en Contexto (ZTNA)**

#### Metodología y tecnologías usadas

Se ha implementado un **Broker ZTNA como Reverse Proxy y Policy Enforcement Point (PEP)** mediante Python/FastAPI. La política de control de acceso reside en el fichero `access_policy.json`, recargado en cada petición sin reinicio del Broker (hot-reload), cumpliendo el requisito del Servicio de que los cambios de política no alteren el código del Broker.

El flujo de acceso es el siguiente:

1. El cliente ZTNA (personal sanitario) solicita acceso a un recurso protegido.
2. El Broker genera un **nonce aleatorio de un solo uso con TTL de 120 segundos** (anti-replay) y lo envía al cliente, vinculado al identificador de sesión.
3. El cliente firma el challenge `nonce_id:nonce` con la **clave privada de su certificado digital cualificado** (ECC P-256 o RSA).
4. El Broker verifica la firma (ECDSA/RSA-PKCS1v15 con SHA-256) contra la clave pública del certificado, comprueba la cadena de confianza hasta la CA raíz (`trusted_ca.pem`), y valida la ventana temporal del certificado y la extensión `EKU: ClientAuth`.
5. El Broker evalúa todos los factores del contexto contra la política JSON: rol del empleado, ubicación, tipo de red, horario laboral (08:00–20:00, L-V, zona Europa/Madrid), postura del dispositivo (AV activo, firewall, disco cifrado, parches OS), EDR trust score (mínimo 80/100) y correlación cita-paciente.
6. Si el contexto cumple la política, el Broker emite un **token HMAC-SHA256** de sesión y enruta la petición al recurso protegido; en caso contrario, devuelve 403 con el motivo de denegación en log.

Política JSON cargada dinámicamente:

```json
{
  "allowed_roles": ["medico", "enfermeria"],
  "allowed_locations": ["Hospital_Central", "Hospital_Norte", "Centro_Salud_A"],
  "allowed_networks": ["hospital_lan", "vpn_corp"],
  "allowed_resources": ["/historial/HC39454", "/historial/HC40122"],
  "working_hours": {
    "start": "08:00", "end": "20:00",
    "timezone": "Europe/Madrid", "weekdays_only": true
  },
  "required_posture": {
    "av_active": true, "firewall_active": true,
    "disk_encrypted": true, "os_patched": true
  },
  "min_edr_trust_score": 80,
  "require_appointment_match": true,
  "nonce_ttl_seconds": 120
}
```

**Sobre la postura de seguridad falseada (endpoint comprometido):** el Servicio planteó incorporar MDM (Intune) o EDR (CrowdStrike/SentinelOne) para validar la postura independientemente del agente local. Frente al coste elevado de estas soluciones, EA ShieldGuard recomienda la siguiente alternativa de coste contenido:

* **Wazuh + osquery (stack open source):** Wazuh actúa como SIEM/EDR ligero y agrega información de postura desde osquery (estado de AV, firewall, parches). El Broker consume el EDR trust score resultante como campo del contexto CBAC, sin depender de datos autodeclarados por el cliente. Esta combinación es gratuita para el Servicio y evita el coste de licencias por puesto de CrowdStrike/SentinelOne.
* **Atestación de arranque vía TPM 2.0 (complementario):** los dispositivos con chip TPM 2.0 pueden firmar criptográficamente el estado de arranque. Esta prueba no puede ser falsificada por malware que opere a nivel de sistema operativo, ya que el TPM verifica la cadena de arranque desde firmware. No requiere licencia adicional en hardware corporativo fabricado desde 2016.

#### Resultados técnicos obtenidos

| Escenario de prueba | Resultado | Motivo de decisión |
| :---- | :---- | :---- |
| Médico, hospital\_lan, horario laboral, postura correcta, cita coincidente | ACCESO CONCEDIDO | Todos los factores cumplen la política |
| Médico, red doméstica (IP no autorizada) | 403 DENEGADO | Red no en `allowed_networks` |
| Médico, acceso a las 22:00 (fuera de ventana) | 403 DENEGADO | Fuera de `working_hours` |
| Médico, firewall desactivado | 403 DENEGADO | `firewall_active: false` no cumple postura |
| Médico, EDR trust score = 60 (< 80) | 403 DENEGADO | `min_edr_trust_score` no alcanzado |
| Médico, sin cita con el paciente ese día | 403 DENEGADO | `require_appointment_match` = true |
| Firma de nonce con clave privada incorrecta | 403 DENEGADO | Verificación de firma fallida |
| Modificación de `access_policy.json` en caliente | Política aplicada en < 1 s | Hot-reload en cada petición, sin reinicio del Broker |
| Nonce reutilizado dentro del TTL | 403 DENEGADO | Anti-replay: nonce marcado como usado |

Todas las decisiones quedan registradas en log estructurado con timestamp, identidad del solicitante, recurso solicitado y motivo de la decisión.

**Cumplimiento normativo:** NIST CSF 2.0 (PR.AC-4, DE.CM-7), ENS Categoría Alta (control de acceso contextual), RGPD Art. 25 (privacy by design), ISO/IEC 27001:2022 A.8.2 (gestión de acceso privilegiado).

---

### **Consulta 6.2.2 – Control de Acceso Dinámico en Proceso de Negocio (Camunda BPMS)**

#### Metodología y tecnologías usadas

El proceso de compra de material sanitario modelado en BPMN incluye cinco tareas: T1 (solicitud), T2.1 y T2.2 (aprobación paralela), T3 (supervisión) y T4 (ejecución). EA ShieldGuard ha adoptado el **modo Offline** para la verificación de la política de control de acceso.

La elección del modo Offline sobre el modo Online se justifica por dos razones:

1. **El modo Online no tiene solución válida** para la política definida: la sobrerestricción de la política (R1 a R5 combinadas) imposibilita la asignación progresiva "just-in-time" que usa Camunda en modo Online, al no poder resolver los conflictos de asignación sin visión global de todas las instancias.
2. **El modo Offline garantiza fairness perfecta:** al calcular la distribución de carga antes de la ejecución, se puede optimizar matemáticamente para que la desviación estándar de participaciones por empleado sea mínima, algo imposible en modo Online cuando llegan varias instancias simultáneas.

El script `2_generador_camunda_fairness.py` aplica backtracking con heurística de menor carga para generar el plan, y puede inyectar las asignaciones directamente en Camunda vía `PUT /task/{id}/assignee` de la REST API.

La política de acceso a satisfacer (detalle completo):

| Restricción | Tipo | Descripción |
| :---- | :---- | :---- |
| R1 | SoD dinámico | T2.1 y T2.2 realizadas por usuarios distintos |
| R2 | SoD dinámico | T3 y T4 realizadas por usuarios distintos |
| R3 | Binding de Deberes | Si GTR realiza T2.1, entonces MDS debe realizar T2.2 |
| R4 | Conflicto de Intereses | JVG solo puede participar en T1, y solo si participa |
| R5 | Fairness | Carga equilibrada en las 20 instancias según elegibilidad |

Tabla de asignación de tareas a roles y empleados candidatos:

| Tarea | Rol requerido | Candidatos directos |
| :---- | :---- | :---- |
| T1 | DR | HYV; JVG (DG, nivel superior en jerarquía) |
| T2.1 | TR | GTR, LPG, RGB, HYV, BJC |
| T2.2 | TC | RGB, MDS, LPG; HYV (DR\>TR\>TC por herencia jerárquica) |
| T3 | DM | PGR |
| T4 | DE / PS | MFE (DE), HJR, PTS, IHP (PS) |

#### Resultados técnicos obtenidos

El script genera las 20 instancias con las métricas de fairness calculadas por tarea. El plan completo (`plan_camunda_offline.csv` / `plan_camunda_offline.json`) está disponible como entregable; a continuación se muestra la tabla de instancias:

| Inst. | T1 | T2.1 | T2.2 | T3 | T4 |
| :---: | :--- | :--- | :--- | :--- | :--- |
| 1 | HYV | LPG | RGB | PGR | MFE |
| 2 | HYV | GTR | MDS | PGR | HJR |
| 3 | JVG | BJC | RGB | PGR | PTS |
| 4 | HYV | LPG | HYV | PGR | IHP |
| 5 | JVG | LPG | RGB | PGR | MFE |
| 6 | HYV | GTR | MDS | PGR | HJR |
| 7 | HYV | LPG | RGB | PGR | PTS |
| 8 | HYV | BJC | RGB | PGR | IHP |
| 9 | HYV | LPG | MDS | PGR | MFE |
| 10 | JVG | BJC | RGB | PGR | HJR |
| 11 | HYV | LPG | HYV | PGR | IHP |
| 12 | HYV | LPG | RGB | PGR | PTS |
| 13 | JVG | GTR | MDS | PGR | MFE |
| 14 | HYV | LPG | RGB | PGR | HJR |
| 15 | HYV | BJC | RGB | PGR | PTS |
| 16 | HYV | GTR | MDS | PGR | IHP |
| 17 | JVG | BJC | LPG | PGR | MFE |
| 18 | HYV | LPG | RGB | PGR | HJR |
| 19 | HYV | LPG | RGB | PGR | PTS |
| 20 | HYV | GTR | MDS | PGR | IHP |

**Verificación de restricciones sobre las 20 instancias:**

* **R1 (T2.1 ≠ T2.2):** Verificado en todas las instancias. En inst. 4 y 11, T2.2=HYV se debe a la herencia jerárquica (DR\>TR\>TC en la jerarquía de roles del Servicio): HYV como DR puede ejecutar tareas de TC. T2.1=LPG ≠ T2.2=HYV en ambos casos. ✓
* **R2 (T3 ≠ T4):** T3=PGR (DM) no pertenece a los roles DE ni PS, por lo que la restricción es satisfecha automáticamente en todas las instancias. ✓
* **R3 (GTR→MDS en T2.2):** GTR aparece en T2.1 en las instancias 2, 6, 13, 16, 20. En todas ellas T2.2=MDS. ✓
* **R4 (JVG solo en T1):** JVG aparece en las instancias 3, 5, 10, 13, 17. En todas, únicamente en T1. ✓
* **R5 (Fairness):**

| Tarea | Distribución | Desv. estándar |
| :---- | :---- | :---- |
| T2.1 | LPG×10, GTR×5, BJC×5, RGB×0, HYV×0 | 3.9 |
| T2.2 | RGB×11, MDS×6, HYV×2, LPG×1 | 4.0 |
| T4 | MFE×5, HJR×5, PTS×5, IHP×5 | 0.0 (perfecta) |

La concentración de LPG en T2.1 y RGB en T2.2 responde a la disponibilidad de candidatos por tarea y a la restricción R3 (que reserva MDS para cuando GTR actúa en T2.1), no a un fallo del algoritmo. T4 alcanza distribución perfecta. T3 recae siempre en PGR por ser el único DM.

**Integración con Camunda:** las instancias precalculadas se cargan en Camunda asignando el `assignee` de cada User Task vía REST API antes de iniciar la instancia del proceso:

```bash
curl -X PUT "https://camunda:8080/v1/tasks/{taskId}/assignee" \
  -H "Content-Type: application/json" \
  -d '{"assignee": "GTR"}'
```

El plan puede regenerarse con `--instances N` para futuros ciclos de compra, adaptando la fairness a la disponibilidad de personal en cada periodo.

---

## **4\. Consulta 6.3 – Automatización de Compras mediante Smart Contract en Ethereum**

### Metodología y tecnologías usadas

Se ha desarrollado el contrato `HealthProcurementAuction.sol` (Solidity 0.8.20) que implementa una **subasta Vickrey inversa con esquema commit-reveal** para la adquisición de medicamentos y material sanitario. El esquema commit-reveal garantiza la confidencialidad de las pujas hasta el cierre de la subasta:

* **Fase commit (bidding):** el pujante envía `keccak256(abi.encodePacked(bid, salt))` junto al depósito (≥ 10% de la puja como `msg.value`). El contrato registra el hash y el depósito, sin conocer la puja real.
* **Fase reveal:** tras el cierre (`MAX_BIDS = 30` pujas o `biddingDeadline`), cada pujante revela su puja real y su salt. El contrato verifica que el hash coincide y procesa el resultado.

Mecanismo de segundo precio: gana el pujante con la puja más baja; en caso de empate, el que comprometió antes (campo `commitOrder`). El precio pagado es el segundo precio distinto más bajo; si solo hay una puja válida, el Servicio paga ese valor.

Adicionalmente, se ha desarrollado `HealthProcurementAuctionFactory` para instanciar subastas independientes con parámetros propios (`auctionStart`, `biddingDeadline`, `revealDeadline`, `deliveryDeadline`, `maxAcceptablePrice`), lo que permite al Servicio lanzar varias subastas paralelas sin reutilizar el mismo contrato.

| Componente | Implementación | Justificación |
| :---- | :---- | :---- |
| Lenguaje | Solidity 0.8.20 | Protección nativa contra overflow/underflow; no requiere SafeMath |
| Confidencialidad de pujas | Esquema commit-reveal (`keccak256`) | Único mecanismo que garantiza privacidad de pujas on-chain |
| Anti-reentrancy | `nonReentrant` (OpenZeppelin) + patrón CEI | Prevención de ataques tipo DAO |
| Control de acceso | `onlyHealthService` en funciones críticas | Solo el Servicio puede finalizar, confirmar entrega o penalizar |
| Auditabilidad | Eventos `BidCommitted`, `BidRevealed`, `AuctionFinalized`, `DeliveryConfirmed`, `WinnerPenalized` | Trazabilidad inmutable de cada acción en la blockchain |
| Reutilización | `HealthProcurementAuctionFactory` | Permite múltiples subastas independientes sin redespliegue |
| Framework de desarrollo | Hardhat 2.x | Testing local, compilación y despliegue scriptado |
| Testnet | Ethereum Sepolia (Chain ID: 11155111) | Testnet PoS oficialmente mantenida; Goerli fue deprecada |
| Wallet | MetaMask | Gestión de wallets de proveedores y personal del Servicio |
| Análisis estático | Slither 0.10.x + Mythril + Solhint | Cobertura multi-herramienta frente a distintas clases de vulnerabilidad |

### Resultados técnicos obtenidos

**Análisis estático con Slither (20 detecciones totales):**

| Severidad | Cantidad | Evaluación |
| :---- | :---: | :---- |
| High | 0 | Sin vulnerabilidades de alta severidad |
| Medium | 0 | Sin vulnerabilidades de severidad media |
| Low | 6 | Uso de `block.timestamp` en comparaciones de deadline — aceptado por requisito: el margen de manipulación del timestamp (~15 s por minero) es irrelevante para subastas con horizonte de horas o días |
| Informational | 7 | Pragma `^0.8.20` (Solidity recomienda versión exacta), llamadas de bajo nivel en patrón CEI, convenciones de nomenclatura |
| Optimization | 7 | Variables candidatas a `immutable`, caché de `array.length` en bucles |

**Análisis con Mythril:** 0 vulnerabilidades detectadas. Los vectores SWC-107 (reentrancy), SWC-101 (overflow) y SWC-105 (retiro no autorizado) no aplican al contrato: reentrancy está mitigado por `nonReentrant` y patrón CEI; overflow es imposible en Solidity 0.8; el retiro de fondos está restringido por `onlyHealthService` y `winner`.

El contrato **no presenta vulnerabilidades explotables** tras el análisis estático multi-herramienta.

**Pruebas dinámicas automatizadas (Hardhat, 14 casos):**

| Caso | Descripción | Resultado |
| :---- | :---- | :---- |
| 1 | Rechazo de depósito 0 en commit | ✓ revert |
| 2 | Rechazo de doble commit por el mismo wallet | ✓ revert "Bidder already committed" |
| 3 | Rechazo de puja superior a `maxAcceptablePrice` en reveal | ✓ revert |
| 4 | Rechazo de depósito inferior al 10% de la puja | ✓ revert |
| 5 | Cálculo correcto del ganador (puja mínima) y segundo precio distinto | ✓ ganador y precio correctos |
| 6 | Caso puja única: pago a precio propio | ✓ |
| 7 | Devolución de depósito a no ganadores | ✓ transferencia correcta |
| 8 | El ganador no puede usar `withdrawDeposit` (flujo de entrega) | ✓ revert |
| 9 | `confirmDeliveryAndPay` con `msg.value = secondPrice` | ✓ evento `DeliveryConfirmed` |
| 10 | Penalización por no entrega: depósito retenido para `healthService` | ✓ evento `WinnerPenalized` |
| 11 | Cierre por `MAX_BIDS = 30` | ✓ bids bloqueados tras el cierre |
| 12 | Bloqueo de `finalizeAuction` antes de `revealDeadline` | ✓ revert "Reveal phase not ended" |
| 13 | Control de acceso `onlyHealthService` | ✓ revert para cuentas no autorizadas |
| 14 | Factory crea subastas independientes con parámetros distintos | ✓ |

**Despliegue y pruebas en Sepolia:**

```bash
# Compilar y desplegar
npm run compile
npm run deploy:sepolia

# Verificar bytecode en Etherscan-Sepolia
npx hardhat verify --network sepolia <factoryAddress>
```

El Servicio de Salud puede conectarse a la testnet configurando MetaMask en Sepolia (Chain ID: 11155111) y obteniendo ETH de prueba mediante los faucets oficiales (sepoliafaucet.com o Google faucet). Los proveedores operan con su propio wallet MetaMask; el Servicio de Salud actúa como `healthService` con la dirección del deployer. Las evidencias de transacciones en Sepolia (hashes y capturas de Etherscan) se incluyen en el Anexo D.

**Cumplimiento normativo:** RGPD Art. 5.2 (accountability en compras públicas mediante registro inmutable), ENS (trazabilidad de operaciones críticas), eIDAS2 (uso de identidad digital de wallets para proveedores).

---

## **5\. Conclusiones**

La CAI 6 ofrece al Servicio de Salud soluciones técnicas verificadas sobre identidad digital, control de acceso contextual y accountability en compras. Los certificados ECC P-256 con gestión centralizada en Gateway TLS eliminan el overhead de gestionar 46 certificados independientes. El Broker ZTNA aplica la política sin código hardcodeado y verifica la identidad sin necesidad de segundo factor adicional. Las 20 instancias Camunda precalculadas garantizan cumplimiento de la política antes de la ejecución, sin riesgo de violaciones en tiempo de ejecución. El Smart Contract supera el análisis estático con cero vulnerabilidades High/Medium y los 14 casos de prueba Hardhat pasan correctamente.

Las acciones operativas inmediatas recomendadas son: (1) completar la firma digital del informe con DNIe o Autofirma y adjuntarla como entregable; (2) ejecutar las pruebas OP1–OP9 en Sepolia y registrar los hashes de transacciones como evidencia auditable; y (3) establecer monitorización de expiración de certificados (alerta a 30 días) y revisión semestral de la política CBAC del Broker ZTNA.

---

## **6\. Anexos**

* **Anexo A (Consulta 6.1):** Código fuente de generación de CSR y clave ECC/RSA (`1_generador_ecc_csr.py`), herramienta de firma y verificación PKCS\#7/CMS (`2_firma_verificacion_poc.py`), configuración del Gateway TLS 1.3 (`3_gateway_tls13.conf`), script de renovación automática de certificados (`4_modelo_push_certificados.sh`) y distribución push de CA raíz a navegadores (`5_push_confianza_navegadores.sh`).

* **Anexo B (Consulta 6.2.1):** Broker ZTNA/FastAPI (`1_ztna_broker_poc.py`), cliente ZTNA (`3_ztna_cliente_poc.py`), generador de PKI de demostración (`0_generar_pki_demo.py`), política CBAC (`access_policy.json`) y certificados de demo (`cliente_ztna_cert.pem`, `trusted_ca.pem`).

* **Anexo C (Consulta 6.2.2):** Script de precálculo de instancias Camunda con métricas de fairness (`2_generador_camunda_fairness.py`), plan de instancias en JSON (`plan_camunda_offline.json`) y CSV (`plan_camunda_offline.csv`).

* **Anexo D (Consulta 6.3):** Contrato Solidity (`contracts/HealthProcurementAuction.sol`), suite de tests Hardhat (`test/HealthProcurementAuction.test.js`), scripts de despliegue (`scripts/deploy.js`), informes de análisis estático (`reports/slither.json`, `reports/mythril.md`, `reports/solhint.txt`), plan de pruebas Sepolia (`PlanPruebas.md`) y evidencias de transacciones en Etherscan-Sepolia.
