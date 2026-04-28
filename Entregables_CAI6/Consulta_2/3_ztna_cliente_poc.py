import argparse
import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib import request

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa


def http_post_json(url: str, payload: dict) -> dict:
    req = request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def sign_challenge(private_key_path: Path, challenge: str) -> str:
    private_key = serialization.load_pem_private_key(private_key_path.read_bytes(), password=None)
    payload = challenge.encode("utf-8")

    if isinstance(private_key, rsa.RSAPrivateKey):
        signature = private_key.sign(payload, padding.PKCS1v15(), hashes.SHA256())
    elif isinstance(private_key, ec.EllipticCurvePrivateKey):
        signature = private_key.sign(payload, ec.ECDSA(hashes.SHA256()))
    else:
        raise ValueError("Tipo de clave privada no soportado")

    return base64.b64encode(signature).decode("utf-8")


def main():
    parser = argparse.ArgumentParser(description="Cliente ZTNA PoC para firma de nonce y acceso CBAC")
    parser.add_argument("--broker-url", default="http://127.0.0.1:8000")
    parser.add_argument("--certificate", required=True)
    parser.add_argument("--private-key", required=True)
    parser.add_argument("--resource", default="/historial/HC39454")
    parser.add_argument("--role", default="medico")
    parser.add_argument("--location", default="Hospital_Central")
    parser.add_argument("--network", default="hospital_lan")
    parser.add_argument(
        "--appointment-match",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    args = parser.parse_args()

    cert_pem = Path(args.certificate).read_text(encoding="utf-8")

    nonce_resp = http_post_json(
        f"{args.broker_url}/api/auth/nonce",
        {"certificate_pem": cert_pem},
    )

    signature_b64 = sign_challenge(Path(args.private_key), nonce_resp["challenge"])

    posture_context = {
        "employee_id": "EMP-0001",
        "role": args.role,
        "location": args.location,
        "network_type": args.network,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "resource": args.resource,
        "av_active": True,
        "firewall_active": True,
        "disk_encrypted": True,
        "os_patched": True,
        "edr_trust_score": 95,
        "appointment_match": args.appointment_match,
    }

    verify_resp = http_post_json(
        f"{args.broker_url}/api/auth/verify",
        {
            "nonce_id": nonce_resp["nonce_id"],
            "signature_b64": signature_b64,
            "certificate_pem": cert_pem,
            "posture_context": posture_context,
        },
    )

    print("[OK] Respuesta broker:")
    print(json.dumps(verify_resp, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
