import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7


def _read_bytes(path: Path) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _check_supported_document(document_path: Path):
    ext = document_path.suffix.lower()
    if ext not in {".xml", ".pdf"}:
        raise ValueError("Solo se admiten documentos XML o PDF para esta PoC")


def sign_document(document_path: Path, private_key_path: Path, certificate_path: Path, output_path: Path):
    _check_supported_document(document_path)
    doc_bytes = _read_bytes(document_path)

    private_key = serialization.load_pem_private_key(_read_bytes(private_key_path), password=None)
    certificate = x509.load_pem_x509_certificate(_read_bytes(certificate_path))

    builder = pkcs7.PKCS7SignatureBuilder().set_data(doc_bytes)
    builder = builder.add_signer(certificate, private_key, hashes.SHA256())

    signature_der = builder.sign(
        encoding=serialization.Encoding.DER,
        options=[pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary],
    )

    with open(output_path, "wb") as f:
        f.write(signature_der)


def verify_signature_openssl(document_path: Path, signature_path: Path, ca_bundle_path: Optional[Path]):
    _check_supported_document(document_path)
    if shutil.which("openssl") is None:
        raise RuntimeError("OpenSSL no esta disponible en el sistema")

    with tempfile.NamedTemporaryFile(delete=False) as out_file:
        out_path = Path(out_file.name)

    cmd = [
        "openssl",
        "cms",
        "-verify",
        "-binary",
        "-inform",
        "DER",
        "-in",
        str(signature_path),
        "-content",
        str(document_path),
        "-out",
        str(out_path),
    ]

    if ca_bundle_path is not None:
        cmd.extend(["-CAfile", str(ca_bundle_path), "-purpose", "any"])
    else:
        cmd.append("-noverify")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        if proc.returncode != 0:
            stderr = proc.stderr.strip() or "Error de verificacion"
            raise RuntimeError(stderr)

        original = _read_bytes(document_path)
        reconstructed = _read_bytes(out_path)
        if original != reconstructed:
            raise RuntimeError("La firma es criptograficamente valida, pero el contenido reconstruido no coincide")
    finally:
        out_path.unlink(missing_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Firma y verifica documentos XML/PDF con certificado X.509 (PoC consulta 6.1)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sign_parser = subparsers.add_parser("sign", help="Firmar documento con PKCS#7 detached")
    sign_parser.add_argument("--document", required=True)
    sign_parser.add_argument("--private-key", required=True)
    sign_parser.add_argument("--certificate", required=True)
    sign_parser.add_argument("--output", default=None, help="Ruta de salida .p7s (DER)")

    verify_parser = subparsers.add_parser("verify", help="Verificar firma PKCS#7 detached")
    verify_parser.add_argument("--document", required=True)
    verify_parser.add_argument("--signature", required=True)
    verify_parser.add_argument(
        "--ca-bundle",
        default=None,
        help="Bundle PEM de CA confiables. Si no se indica, solo se valida integridad/firma sin cadena.",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "sign":
        document = Path(args.document)
        signature = Path(args.output) if args.output else document.with_suffix(document.suffix + ".p7s")
        sign_document(
            document_path=document,
            private_key_path=Path(args.private_key),
            certificate_path=Path(args.certificate),
            output_path=signature,
        )
        print("[OK] Firma generada")
        print(f"    - Documento: {document}")
        print(f"    - Firma: {signature}")
        return

    if args.command == "verify":
        ca_bundle = Path(args.ca_bundle) if args.ca_bundle else None
        verify_signature_openssl(
            document_path=Path(args.document),
            signature_path=Path(args.signature),
            ca_bundle_path=ca_bundle,
        )
        print("[OK] Verificacion completada: firma valida e integridad intacta")


if __name__ == "__main__":
    main()
