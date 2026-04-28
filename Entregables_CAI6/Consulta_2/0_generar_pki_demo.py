from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


BASE_DIR = Path(__file__).resolve().parent


def write_pem(path: Path, content: bytes):
    with open(path, "wb") as f:
        f.write(content)


def build_name(common_name: str, org_unit: str) -> x509.Name:
    return x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Servicio de Salud Publico"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, org_unit),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )


def main():
    now = datetime.now(timezone.utc)

    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_subject = build_name("INSEGUS Demo Root CA", "PKI")
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_subject)
        .issuer_name(ca_subject)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(private_key=ca_key, algorithm=hashes.SHA256())
    )

    client_key = ec.generate_private_key(ec.SECP256R1())
    client_subject = build_name("medico.ana.garcia", "Personal Sanitario")
    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(client_subject)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=False,
        )
        .sign(client_key, hashes.SHA256())
    )

    client_cert = (
        x509.CertificateBuilder()
        .subject_name(csr.subject)
        .issuer_name(ca_cert.subject)
        .public_key(csr.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
        .sign(private_key=ca_key, algorithm=hashes.SHA256())
    )

    write_pem(
        BASE_DIR / "trusted_ca.pem",
        ca_cert.public_bytes(serialization.Encoding.PEM),
    )
    write_pem(
        BASE_DIR / "cliente_ztna_key.pem",
        client_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ),
    )
    write_pem(
        BASE_DIR / "cliente_ztna_cert.pem",
        client_cert.public_bytes(serialization.Encoding.PEM),
    )

    print("[OK] PKI de demo generada")
    print(f"    - {BASE_DIR / 'trusted_ca.pem'}")
    print(f"    - {BASE_DIR / 'cliente_ztna_key.pem'}")
    print(f"    - {BASE_DIR / 'cliente_ztna_cert.pem'}")


if __name__ == "__main__":
    main()
