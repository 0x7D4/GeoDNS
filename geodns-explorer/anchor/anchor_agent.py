"""
GeoDNS Explorer — Anchor Agent
================================
Lightweight FastAPI service that wraps `dig` to perform DNS lookups.
Runs on each Raspberry Pi anchor node, listens on port 8053.

anchor_id is read from the ANCHOR_ID environment variable.
"""

import os
import time
from enum import Enum
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import dns.asyncresolver
import dns.rdatatype
import dns.exception
import dns.rcode

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ANCHOR_ID: str = os.environ.get("ANCHOR_ID", "unknown")

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class RecordType(str, Enum):
    """Supported DNS record types."""
    A = "A"
    AAAA = "AAAA"
    MX = "MX"
    NS = "NS"
    TXT = "TXT"
    CNAME = "CNAME"
    SOA = "SOA"

class ResolveRequest(BaseModel):
    """Incoming DNS resolution request."""
    domain: str = Field(..., min_length=1, max_length=253, examples=["example.com"])
    record_type: RecordType = Field(..., examples=["A"])

class ResolveResponse(BaseModel):
    """DNS resolution result."""
    domain: str
    record_type: str
    answers: List[str]
    ttl: int = 0
    query_time_ms: Optional[float] = None
    nameserver_used: str = "system default"
    resolver_used: str = "system default"
    status: str = "OK"
    raw_output: str = ""
    anchor_id: str = ANCHOR_ID

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="GeoDNS Anchor Agent",
    description="DNS resolution agent running on anchor nodes using Python DNS",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# DNS Logic
# ---------------------------------------------------------------------------

async def resolve_domain(domain: str, record_type: str) -> dict:
    resolver = dns.asyncresolver.Resolver()
    
    try:
        rdtype = dns.rdatatype.from_text(record_type)
    except dns.rdatatype.UnknownRdatatype:
        raise HTTPException(status_code=400, detail=f"Unsupported record type: {record_type}")
        
    start = time.monotonic()
    try:
        answer = await resolver.resolve(domain, rdtype)
        elapsed_ms = round((time.monotonic() - start) * 1000)

        answers = []
        for rr in answer:
            answers.append(rr.to_text())

        return {
            "domain": domain,
            "record_type": record_type,
            "answers": answers,
            "ttl": answer.rrset.ttl,
            "query_time_ms": elapsed_ms,
            "nameserver_used": str(resolver.nameservers[0]) if resolver.nameservers else "system",
            "resolver_used": str(resolver.nameservers[0]) if resolver.nameservers else "system",
            "raw_output": "\\n".join(answers),
            "anchor_id": ANCHOR_ID,
            "status": "RESOLVED",
        }

    except dns.resolver.NXDOMAIN:
        elapsed_ms = round((time.monotonic() - start) * 1000)
        return {
            "domain": domain,
            "record_type": record_type,
            "answers": [],
            "ttl": 0,
            "query_time_ms": elapsed_ms,
            "nameserver_used": str(resolver.nameservers[0]) if resolver.nameservers else "system",
            "resolver_used": str(resolver.nameservers[0]) if resolver.nameservers else "system",
            "raw_output": "",
            "anchor_id": ANCHOR_ID,
            "status": "NXDOMAIN",
        }

    except dns.resolver.NoAnswer:
        # Domain exists but no records of this type
        elapsed_ms = round((time.monotonic() - start) * 1000)
        return {
            "domain": domain,
            "record_type": record_type,
            "answers": [],
            "ttl": 0,
            "query_time_ms": elapsed_ms,
            "nameserver_used": str(resolver.nameservers[0]) if resolver.nameservers else "system",
            "resolver_used": str(resolver.nameservers[0]) if resolver.nameservers else "system",
            "raw_output": "",
            "anchor_id": ANCHOR_ID,
            "status": "NXDOMAIN",
        }

    except dns.exception.Timeout:
        elapsed_ms = round((time.monotonic() - start) * 1000)
        return {
            "domain": domain,
            "record_type": record_type,
            "answers": [],
            "ttl": 0,
            "query_time_ms": elapsed_ms,
            "nameserver_used": "timeout",
            "resolver_used": "timeout",
            "raw_output": "",
            "anchor_id": ANCHOR_ID,
            "status": "BLOCKED",
            # SERVFAIL/timeout from ISP resolver = likely blocking
        }

    except Exception as e:
        elapsed_ms = round((time.monotonic() - start) * 1000)
        return {
            "domain": domain,
            "record_type": record_type,
            "answers": [],
            "ttl": 0,
            "query_time_ms": elapsed_ms,
            "nameserver_used": "error",
            "resolver_used": "error",
            "raw_output": str(e),
            "anchor_id": ANCHOR_ID,
            "status": "ERROR",
        }

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "anchor_id": ANCHOR_ID}

@app.post("/resolve", response_model=ResolveResponse)
async def resolve(request: ResolveRequest):
    """Resolve a DNS query using dnspython."""
    valid_types = {"A","AAAA","MX","NS","TXT","CNAME","SOA"}
    if request.record_type.upper() not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported record type: {request.record_type}"
        )
    return await resolve_domain(request.domain, request.record_type.upper())
