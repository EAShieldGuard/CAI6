import argparse
import os
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def _build_private_key(algorithm: str, rsa_bits: int):
    if algorithm == "ecc":
        return ec.generate_private_key(ec.SECP256R1())
    return rsa.generate_private_key(public_exponent=65537, key_size=rsa_bits)


def _build_subject(args: argparse.Namespace) -> x509.Name:
    return x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, args.country),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, args.state),
            x509.NameAttribute(NameOID.LOCALITY_NAME, args.locality),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, args.organization),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, args.org_unit),
            x509.NameAttribute(NameOID.COMMON_NAME, args.common_name),
            x509.NameAttribute(NameOID.EMAIL_ADDRESS, args.email),
        ]
    )


def _build_csr(private_key, args: argparse.Namespace) -> x509.CertificateSigningRequest:
    builder = x509.CertificateSigningRequestBuilder().subject_name(_build_subject(args))
    builder = builder.add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)

    if args.profile == "server":
        sans = [x509.DNSName(args.common_name)]
        for san in args.san:
            sans.append(x509.DNSName(san))
        builder = builder.add_extension(x509.SubjectAlternativeName(sans), critical=False)
        builder = builder.add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=args.algorithm == "rsa",
                content_commitment=False,
                data_encipherment=False,
                key_agreement=args.algorithm == "ecc",
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        builder = builder.add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
    else:
        builder = builder.add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=False,
                content_commitment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        builder = builder.add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH, ExtendedKeyUsageOID.EMAIL_PROTECTION]),
            critical=False,
        )

    return builder.sign(private_key=private_key, algorithm=hashes.SHA256())


def generate_csr(args: argparse.Namespace) -> tuple[Path, Path]:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    private_key = _build_private_key(args.algorithm, args.rsa_bits)
    csr = _build_csr(private_key, args)

    safe_cn = args.common_name.replace("*", "wildcard").replace(".", "_").replace(" ", "_")
    key_path = output_dir / f"{safe_cn}_{args.profile}_priv.pem"
    csr_path = output_dir / f"{safe_cn}_{args.profile}_csr.pem"

    key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    csr_bytes = csr.public_bytes(serialization.Encoding.PEM)

    with open(key_path, "wb") as f_key:
        f_key.write(key_bytes)
    os.chmod(key_path, 0o600)

    with open(csr_path, "wb") as f_csr:
        f_csr.write(csr_bytes)

    return key_path, csr_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Genera clave privada y CSR X.509 para empleados o servidores del Servicio de Salud.",
    )
    parser.add_argument("--profile", choices=["employee", "server"], default="employee")
    parser.add_argument("--algorithm", choices=["ecc", "rsa"], default="ecc")
    parser.add_argument("--rsa-bits", type=int, default=4096)
    parser.add_argument("--common-name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--country", default="ES")
    parser.add_argument("--state", default="Andalucia")
    parser.add_argument("--locality", default="Sevilla")
    parser.add_argument("--organization", default="Servicio de Salud Publico")
    parser.add_argument("--org-unit", default="INSEGUS Security Team")
    parser.add_argument(
        "--san",
        action="append",
        default=[],
        help="SAN DNS adicional. Repetible. Solo perfil server.",
    )
    parser.add_argument("--output-dir", default=".")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.profile != "server" and args.san:
        parser.error("--san solo aplica al perfil server")

    key_path, csr_path = generate_csr(args)
    print("[OK] Material criptografico generado")
    print(f"    - Clave privada: {key_path}")
    print(f"    - CSR: {csr_path}")
    print("[TIP] Revisar CSR con: openssl req -in <csr.pem> -noout -text")


if __name__ == "__main__":
    main()
