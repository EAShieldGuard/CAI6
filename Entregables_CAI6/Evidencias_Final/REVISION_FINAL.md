# Revision final CAI 6

Fecha: 2026-05-11

## Entorno

- Python: 3.11.9
- Node.js: 20.11.1
- npm: 10.2.4
- OpenSSL usado para CMS/CSR: `C:\Program Files\Git\mingw64\bin\openssl.exe`
- Dependencias Python reproducibles: `Entregables_CAI6/requirements-python.txt`

## Consulta 6.1

- `python -m compileall -q Entregables_CAI6/Consulta_1 Entregables_CAI6/Consulta_2`: OK.
- CSR empleado ECC P-256 generado en `Evidencias_Final/Consulta_1/Ana_Garcia_employee_csr.pem`.
- CSR servidor ECC P-256 generado en `Evidencias_Final/Consulta_1/api_salud_gov_server_csr.pem`.
- Revision OpenSSL del CSR empleado: `id-ecPublicKey`, `Public-Key: (256 bit)`, `NIST CURVE: P-256`, EKU `TLS Web Client Authentication`.
- Revision OpenSSL del CSR servidor: `NIST CURVE: P-256`, SAN `DNS:api.salud.gov`, `DNS:gateway.salud.gov`, `DNS:historial.salud.gov`, EKU `TLS Web Server Authentication`.
- Firma CMS detached de `informe_demo.xml`: OK.
- Verificacion CMS contra `trusted_ca.pem`: OK, firma valida e integridad intacta.

## Consulta 6.2

- PKI demo generada con `0_generar_pki_demo.py`: OK.
- Test ZTNA con `fastapi.testclient`:
  - Acceso valido: HTTP 200 `success`.
  - Reutilizacion de nonce: HTTP 401 `Nonce ya utilizado`.
  - Rol no autorizado: HTTP 403.
  - Acceso en domingo: HTTP 403.
- Plan Camunda offline generado:
  - `Consulta_2/plan_camunda_offline.json`.
  - `Consulta_2/plan_camunda_offline.csv`.
- Verificacion R1-R4 sobre 20 instancias: OK.
- Fairness T4: MFE=5, HJR=5, PTS=5, IHP=5.

## Consulta 6.3

- `npm install`: OK.
- `npm audit --omit=dev`: 0 vulnerabilidades.
- `npm run compile`: OK, Solidity 0.8.24.
- `npm test`: 14 passing.
- `npm run deploy:local`: OK en red Hardhat local.
- `npm run static:solhint`: 0 errores, advertencias de estilo/NatSpec/gas documentadas en `Consulta_3/reporte-solhint.txt`.
- `reporte-slither.json`: 20 detecciones, 0 High, 0 Medium.
- `reporte-mythril.md`: no issues detected.

## Pendientes externos

- Firma cualificada real del PDF final con DNIe/Autofirma o QSCD.
- Ejecucion OP1-OP9 en Sepolia con wallet financiada y registro de hashes Etherscan.
