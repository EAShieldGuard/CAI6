import base64
import hashlib
import hmac
import json
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv

load_dotenv()
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel

app = FastAPI(title="ZTNA Broker PoC", version="2.1")

BASE_DIR = Path(__file__).resolve().parent
POLICY_FILE = BASE_DIR / "access_policy.json"
TRUSTED_CA_FILE = BASE_DIR / "trusted_ca.pem"
TOKEN_SECRET = os.environ.get("INSEGUS_TOKEN_SECRET")
if not TOKEN_SECRET:
    raise RuntimeError("INSEGUS_TOKEN_SECRET is required to start the broker")
UPSTREAM_BASE_URL = os.environ.get("INSEGUS_UPSTREAM_URL", "http://127.0.0.1:9000")

NONCE_STORE: dict[str, dict[str, Any]] = {}
SESSION_STORE: dict[str, dict[str, Any]] = {}


class NonceRequest(BaseModel):
    certificate_pem: str


class VerifyRequest(BaseModel):
    nonce_id: str
    signature_b64: str
    certificate_pem: str
    posture_context: dict[str, Any]


def _load_policy() -> dict[str, Any]:
    if not POLICY_FILE.exists():
        raise HTTPException(status_code=503, detail="No existe politica CBAC activa")
    with open(POLICY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _cleanup_expired_nonces():
    now = _utc_now()
    expired = [nonce_id for nonce_id, data in NONCE_STORE.items() if data["expires_at"] <= now]
    for nonce_id in expired:
        NONCE_STORE.pop(nonce_id, None)


def _certificate_fingerprint(cert: x509.Certificate) -> str:
    return cert.fingerprint(hashes.SHA256()).hex()


def _load_certificate(cert_pem: str) -> x509.Certificate:
    try:
        return x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Certificado PEM invalido: {exc}")


def _verify_cert_chain_and_purpose(cert: x509.Certificate):
    now = _utc_now()
    not_before = getattr(cert, "not_valid_before_utc", None) or cert.not_valid_before.replace(tzinfo=timezone.utc)
    not_after = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after.replace(tzinfo=timezone.utc)
    if not_before > now or not_after < now:
        raise HTTPException(status_code=401, detail="Certificado fuera de validez temporal")

    try:
        eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        if ExtendedKeyUsageOID.CLIENT_AUTH not in eku:
            raise HTTPException(status_code=401, detail="El certificado no tiene uso ClientAuth")
    except x509.ExtensionNotFound:
        raise HTTPException(status_code=401, detail="Falta EKU en el certificado de cliente")

    if not TRUSTED_CA_FILE.exists():
        raise HTTPException(status_code=503, detail="No existe CA de confianza configurada")

    ca_cert = x509.load_pem_x509_certificate(TRUSTED_CA_FILE.read_bytes())
    if cert.issuer != ca_cert.subject:
        raise HTTPException(status_code=401, detail="Issuer no coincide con la CA de confianza")

    ca_public_key = ca_cert.public_key()
    try:
        if isinstance(ca_public_key, rsa.RSAPublicKey):
            ca_public_key.verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                padding.PKCS1v15(),
                cert.signature_hash_algorithm,
            )
        elif isinstance(ca_public_key, ec.EllipticCurvePublicKey):
            ca_public_key.verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                ec.ECDSA(cert.signature_hash_algorithm),
            )
        else:
            raise HTTPException(status_code=401, detail="Tipo de clave de CA no soportado")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="No se pudo validar firma de certificado contra CA")


def _verify_nonce_signature(cert: x509.Certificate, challenge: bytes, signature_b64: str):
    try:
        signature = base64.b64decode(signature_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Firma no esta en Base64 valido")

    public_key = cert.public_key()
    try:
        if isinstance(public_key, rsa.RSAPublicKey):
            public_key.verify(signature, challenge, padding.PKCS1v15(), hashes.SHA256())
        elif isinstance(public_key, ec.EllipticCurvePublicKey):
            public_key.verify(signature, challenge, ec.ECDSA(hashes.SHA256()))
        else:
            raise HTTPException(status_code=401, detail="Algoritmo de clave publica no soportado")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Firma de nonce invalida")


def _in_working_hours(timestamp_utc: str, policy: dict[str, Any]) -> bool:
    config = policy.get("working_hours", {})
    start_str = config.get("start", "08:00")
    end_str = config.get("end", "20:00")
    tz_name = config.get("timezone", "UTC")
    weekdays_only = bool(config.get("weekdays_only", True))
    try:
        event_dt = datetime.fromisoformat(timestamp_utc.replace("Z", "+00:00"))
        if event_dt.tzinfo is None:
            event_dt = event_dt.replace(tzinfo=timezone.utc)
        local_dt = event_dt.astimezone(ZoneInfo(tz_name))
        if weekdays_only and local_dt.weekday() > 4:
            return False
        start_hour, start_minute = [int(x) for x in start_str.split(":")]
        end_hour, end_minute = [int(x) for x in end_str.split(":")]
        current_minutes = local_dt.hour * 60 + local_dt.minute
        start_minutes = start_hour * 60 + start_minute
        end_minutes = end_hour * 60 + end_minute
        return start_minutes <= current_minutes <= end_minutes
    except Exception:
        return False


def _check_context(context: dict[str, Any], policy: dict[str, Any]) -> tuple[bool, str]:
    required_fields = [
        "role",
        "location",
        "network_type",
        "timestamp_utc",
        "resource",
        "av_active",
        "firewall_active",
        "disk_encrypted",
        "os_patched",
    ]
    missing = [field for field in required_fields if field not in context]
    if missing:
        return False, f"Faltan campos de contexto: {','.join(missing)}"

    if context["role"] not in policy.get("allowed_roles", []):
        return False, "Rol no autorizado"
    if context["location"] not in policy.get("allowed_locations", []):
        return False, "Ubicacion no autorizada"
    if context["network_type"] not in policy.get("allowed_networks", []):
        return False, "Tipo de red no autorizado"
    if context["resource"] not in policy.get("allowed_resources", []):
        return False, "Recurso no autorizado por politica"
    if not _in_working_hours(context["timestamp_utc"], policy):
        return False, "Acceso fuera de horario laboral"

    posture = policy.get("required_posture", {})
    for key, required in posture.items():
        if context.get(key) != required:
            return False, f"Postura de seguridad incumple {key}"

    min_trust = policy.get("min_edr_trust_score", 80)
    if context.get("edr_trust_score", 0) < min_trust:
        return False, "Trust score de EDR insuficiente"

    if policy.get("require_appointment_match", False) and not context.get("appointment_match", False):
        return False, "No existe correlacion cita-paciente-hora"

    return True, "OK"


def _build_token(payload: dict[str, Any]) -> str:
    payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("utf-8").rstrip("=")
    signature = hmac.new(TOKEN_SECRET.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
    return f"{payload_b64}.{sig_b64}"


def _verify_token(token: str) -> dict[str, Any]:
    try:
        payload_b64, sig_b64 = token.split(".")
    except ValueError:
        raise HTTPException(status_code=401, detail="Token mal formado")

    expected_sig = hmac.new(TOKEN_SECRET.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    expected_b64 = base64.urlsafe_b64encode(expected_sig).decode("utf-8").rstrip("=")
    if not hmac.compare_digest(expected_b64, sig_b64):
        raise HTTPException(status_code=401, detail="Token invalido")

    pad = "=" * (-len(payload_b64) % 4)
    payload_json = base64.urlsafe_b64decode((payload_b64 + pad).encode("utf-8"))
    payload = json.loads(payload_json)

    if int(payload.get("exp", 0)) < int(_utc_now().timestamp()):
        raise HTTPException(status_code=401, detail="Token expirado")
    return payload


@app.post("/api/auth/nonce")
async def get_nonce(payload: NonceRequest):
    _cleanup_expired_nonces()

    cert = _load_certificate(payload.certificate_pem)
    cert_fp = _certificate_fingerprint(cert)

    policy = _load_policy()
    ttl_seconds = int(policy.get("nonce_ttl_seconds", 120))
    nonce_id = str(uuid.uuid4())
    nonce = secrets.token_hex(16)
    expires_at = _utc_now() + timedelta(seconds=ttl_seconds)

    NONCE_STORE[nonce_id] = {
        "nonce": nonce,
        "fingerprint": cert_fp,
        "expires_at": expires_at,
        "used": False,
    }

    return {
        "nonce_id": nonce_id,
        "nonce": nonce,
        "challenge": f"{nonce_id}:{nonce}",
        "expires_at": expires_at.isoformat(),
    }


@app.post("/api/auth/verify")
async def verify_access(payload: VerifyRequest):
    _cleanup_expired_nonces()

    nonce_data = NONCE_STORE.get(payload.nonce_id)
    if nonce_data is None:
        raise HTTPException(status_code=401, detail="Nonce inexistente o expirado")
    if nonce_data["used"]:
        raise HTTPException(status_code=401, detail="Nonce ya utilizado")

    cert = _load_certificate(payload.certificate_pem)
    cert_fp = _certificate_fingerprint(cert)
    if cert_fp != nonce_data["fingerprint"]:
        raise HTTPException(status_code=401, detail="El certificado no coincide con el nonce solicitado")

    _verify_cert_chain_and_purpose(cert)

    policy = _load_policy()
    context_ok, reason = _check_context(payload.posture_context, policy)
    if not context_ok:
        raise HTTPException(status_code=403, detail=f"Acceso denegado por CBAC: {reason}")

    challenge = f"{payload.nonce_id}:{nonce_data['nonce']}".encode("utf-8")
    _verify_nonce_signature(cert, challenge, payload.signature_b64)

    nonce_data["used"] = True

    now = _utc_now()
    token_payload = {
        "sub": cert.subject.rfc4514_string(),
        "role": payload.posture_context.get("role"),
        "resource": payload.posture_context.get("resource"),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
    }
    token = _build_token(token_payload)
    SESSION_STORE[token] = token_payload

    return {
        "status": "success",
        "token": token,
        "token_type": "bearer",
        "redirect": payload.posture_context.get("resource"),
    }


@app.api_route("/proxy/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def reverse_proxy(path: str, request: Request):
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Falta token Bearer")
    token = auth_header.split(" ", 1)[1]
    payload = _verify_token(token)

    requested_resource = "/" + path
    token_resource = payload.get("resource")
    if not token_resource or token_resource != requested_resource:
        raise HTTPException(status_code=403, detail="Token no autoriza este recurso")

    upstream_url = f"{UPSTREAM_BASE_URL.rstrip('/')}{requested_resource}"
    forwarded_headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in {"host", "authorization", "content-length"}
        and not k.lower().startswith("x-ztna-")
    }
    forwarded_headers["X-ZTNA-Subject"] = payload.get("sub", "")
    forwarded_headers["X-ZTNA-Role"] = payload.get("role", "")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            proxy_resp = await client.request(
                request.method,
                upstream_url,
                headers=forwarded_headers,
                content=await request.body(),
                params=dict(request.query_params),
            )
            return Response(
                content=proxy_resp.content,
                status_code=proxy_resp.status_code,
                headers={k: v for k, v in proxy_resp.headers.items() if k.lower() not in {"content-encoding", "transfer-encoding"}},
            )
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Error conectando al backend: {exc}")
