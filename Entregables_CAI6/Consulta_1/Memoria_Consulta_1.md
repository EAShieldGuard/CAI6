# Resolucion tecnica - Consulta 6.1 (Identidad y Criptografia)

## 1. Verificacion del solicitante de certificado cualificado
Recomendacion de seguridad para alta remota del personal sanitario:
1. Video-identificacion asincrona certificada con prueba de vida.
2. Lectura NFC de DNIe para extraer identidad firmada por autoridad oficial.
3. Matching biometrico entre video y foto del chip NFC.
4. Validacion final por CA y emision de certificado ligado al CSR.

Esta secuencia minimiza suplantaciones y cumple el enfoque eIDAS para confianza alta.

## 2. PoC de generacion de clave + CSR (empleado y servidor)
Archivo implementado: 1_generador_ecc_csr.py

Capacidades añadidas:
- Perfil employee o server.
- Clave ECC P-256 o RSA 4096 (parametrizable).
- Subject DN completo (C, ST, L, O, OU, CN, email).
- Extensiones X.509: BasicConstraints, KeyUsage y EKU.
- SAN para servidores y microservicios.
- Salida de clave privada con permisos 600.

Ejemplos de uso:
- Empleado (ECC):
	python3 1_generador_ecc_csr.py --profile employee --algorithm ecc --common-name "Ana Garcia" --email agarcia@salud.gov
- Servidor (ECC + SAN):
	python3 1_generador_ecc_csr.py --profile server --algorithm ecc --common-name api.salud.gov --email admin@salud.gov --san www.api.salud.gov --san gateway.salud.gov

## 3. PoC de firma/verificacion XML-PDF
Archivo implementado: 2_firma_verificacion_poc.py

Cobertura del requisito:
- Firma detached PKCS#7/CMS con certificado X.509.
- Verificacion de integridad y firma mediante OpenSSL.
- Verificacion opcional de cadena de confianza (CA bundle).
- Interfaz basica por CLI con comandos sign y verify.

Ejemplos de uso:
- Firmar:
	python3 2_firma_verificacion_poc.py sign --document informe.xml --private-key empleado_key.pem --certificate empleado_cert.pem
- Verificar:
	python3 2_firma_verificacion_poc.py verify --document informe.xml --signature informe.xml.p7s --ca-bundle trusted_ca.pem

## 4. Certificados DV, control de dominio y Gateway TLS 1.3
Archivos implementados:
- 3_gateway_tls13.conf
- 4_modelo_push_certificados.sh

Mejoras aplicadas:
- Terminacion TLS 1.3 en gateway central.
- HSTS y cabeceras de endurecimiento.
- OCSP stapling para validacion de revocacion.
- Correccion de cabecera X-Forwarded-For.
- Patron de escalado con include para 46 microservicios.
- Deploy-hook robusto con copia atomica, backup, validacion nginx -t y recarga sin corte.

## 5. Modelo push de confianza en navegadores
Archivo implementado: 5_push_confianza_navegadores.sh

Automatiza distribucion del certificado CA raiz en:
- macOS (System Keychain via `security add-trusted-cert`).
- Linux Debian/Ubuntu (`update-ca-certificates`).
- Linux RHEL/CentOS/Fedora (`update-ca-trust`).
- Perfiles Firefox (NSS / `certutil`).
- Windows: instrucciones de despliegue por GPO o `Import-Certificate` (PowerShell).

En produccion, este push se orquesta por:
- MDM (Intune, Jamf) para flotas mixtas.
- GPO + AD para Windows en dominio.
- Ansible / Salt para servidores Linux.

## 6. Limites legales: cualificada vs avanzada
- La PoC de firma/verificacion (2_firma_verificacion_poc.py) trabaja con clave privada en fichero PEM. Bajo eIDAS2 esto produce **firma electronica avanzada** (AdES), no cualificada (QES).
- Para alcanzar QES legalmente equivalente a firma manuscrita, la clave debe residir en un **QSCD**:
  * Tarjeta criptografica (DNIe).
  * Token USB (YubiKey, SafeNet) con chip seguro.
  * HSM en la nube (FNMT, Cl@ve Firma) con doble factor.
- En el flujo objetivo del Servicio de Salud, el empleado generaria CSR/clave dentro del QSCD, la CA emitiria el certificado cualificado y la firma se invocaria via PKCS#11 contra el QSCD. El informe del CAI se firma por los consultores con DNIe / Autofirma.
