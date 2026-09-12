import hmac
import hashlib
from typing import Optional
from fastapi import HTTPException, Request, Header
from config import settings


def verify_github_signature(payload: bytes, signature_header: str) -> bool:
    """
    Verify GitHub webhook signature using HMAC-SHA256.
    
    GitHub sends a signature in the format: sha256=<signature>
    We compute HMAC-SHA256 of the payload using the webhook secret
    and compare it with the received signature.
    """
    if not signature_header:
        return False
    
    try:
        # Extract the signature from the header
        signature_prefix = "sha256="
        if not signature_header.startswith(signature_prefix):
            return False
        
        github_signature = signature_header[len(signature_prefix):]
        
        # Compute HMAC-SHA256 of the payload
        hmac_obj = hmac.new(
            settings.github_webhook_secret.encode(),
            payload,
            hashlib.sha256
        )
        computed_signature = hmac_obj.hexdigest()
        
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(computed_signature, github_signature)
    except Exception:
        return False


async def verify_webhook_signature(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256")
) -> bytes:
    """
    FastAPI dependency to verify webhook signature before processing.
    Raises HTTPException if signature is invalid.
    """
    payload = await request.body()
    
    if not verify_github_signature(payload, x_hub_signature_256):
        raise HTTPException(
            status_code=403,
            detail="Invalid webhook signature"
        )
    
    return payload
