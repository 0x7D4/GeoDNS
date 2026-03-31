"""
GeoDNS Explorer — Anchor Agent
================================
Lightweight FastAPI service that wraps `dig` to perform DNS lookups.
Runs on each Raspberry Pi anchor node, listens on port 8053.

anchor_id is read from the ANCHOR_ID environment variable.
"""

import asyncio
import os
import re
import time
from enum import Enum
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

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
    query_time_ms: Optional[float] = None
    resolver_used: str = "system default"
    status: str = "OK"
    raw_output: str = ""
    anchor_id: str = ANCHOR_ID


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="GeoDNS Anchor Agent",
    description="DNS resolution agent running on anchor nodes",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_dig_output(raw: str) -> tuple[List[str], Optional[float], Optional[str]]:
    """Parse dig output from `dig +noall +comments +answer +stats`.

    This format gives us:
        - HEADER line with status (NOERROR, NXDOMAIN, SERVFAIL, etc.)
        - ANSWER SECTION with record lines (tab-separated: name TTL class type value)
        - Stats lines with query time

    Returns:
        (answers, query_time_ms, header_status)
    """
    answers: List[str] = []
    query_time_ms: Optional[float] = None
    header_status: Optional[str] = None

    for line in raw.strip().splitlines():
        line = line.strip()
        if not line:
            continue

        # Parse DNS status from HEADER: ";; ->>HEADER<<- ... status: NXDOMAIN, ..."
        header_match = re.search(r"status:\s*(\w+)", line)
        if header_match and line.startswith(";;") and "HEADER" in line:
            header_status = header_match.group(1).upper()
            continue

        # Parse query time from stats: ";; Query time: 12 msec"
        qt_match = re.match(r"^;;\s*Query time:\s*(\d+)\s*msec", line)
        if qt_match:
            query_time_ms = float(qt_match.group(1))
            continue

        # Skip other comment/stats lines (;; Got answer, ;; flags, ;; SERVER, etc.)
        if line.startswith(";;") or line.startswith(";"):
            continue

        # ANSWER SECTION lines: "google.com.  48  IN  A  142.250.207.238"
        # Extract the last field (the answer value) from tab/space-separated output
        parts = line.split()
        if len(parts) >= 5:
            # Standard dig answer: name TTL class type value [value...]
            # For most records, the answer is the last field(s)
            record_type_field = parts[3] if len(parts) > 3 else ""
            answer_value = " ".join(parts[4:])
            answers.append(answer_value)
        elif len(parts) >= 1:
            # Fallback: treat entire line as answer
            answers.append(line)

    return answers, query_time_ms, header_status


def determine_status(
    exit_code: int,
    answers: List[str],
    header_status: Optional[str],
    raw_combined: str,
) -> str:
    """Determine the DNS resolution status.

    Priority:
    1. Header status from dig output (most reliable)
    2. Exit code + output pattern matching (fallback)
    3. Empty answers heuristic (last resort)
    """
    combined_upper = raw_combined.upper()

    # 1. Trust the DNS header status if available
    if header_status:
        if header_status == "NXDOMAIN":
            return "NXDOMAIN"
        if header_status in ("SERVFAIL", "REFUSED"):
            return "BLOCKED"
        if header_status == "NOERROR" and answers:
            return "OK"
        if header_status == "NOERROR" and not answers:
            # NOERROR but no answers — could be empty record set
            return "OK"

    # 2. Fall back to exit code checks
    if exit_code != 0:
        if "NXDOMAIN" in combined_upper:
            return "NXDOMAIN"
        if "SERVFAIL" in combined_upper:
            return "BLOCKED"
        if not answers:
            return "NXDOMAIN"

    # 3. Last resort: exit 0, no header parsed, no answers → BLOCKED
    if exit_code == 0 and not answers and not header_status:
        return "BLOCKED"

    return "OK"


async def run_dig(domain: str, record_type: str) -> ResolveResponse:
    """Execute dig as a subprocess and parse the results.

    Uses `dig +noall +comments +answer +stats` for structured output:
      - +noall: suppress all sections
      - +comments: re-enable header comments (contains DNS status)
      - +answer: re-enable answer section
      - +stats: re-enable query statistics (timing info)
    """
    cmd = ["dig", "+noall", "+comments", "+answer", "+stats", domain, record_type]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(), timeout=15.0
        )
    except asyncio.TimeoutError:
        return ResolveResponse(
            domain=domain,
            record_type=record_type,
            answers=[],
            query_time_ms=None,
            status="TIMEOUT",
            raw_output="dig command timed out after 15 seconds",
            anchor_id=ANCHOR_ID,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="dig binary not found. Install dnsutils: apt install dnsutils",
        )

    raw_stdout = stdout_bytes.decode("utf-8", errors="replace")
    raw_stderr = stderr_bytes.decode("utf-8", errors="replace")
    exit_code = process.returncode or 0

    answers, query_time_ms, header_status = parse_dig_output(raw_stdout)
    status = determine_status(exit_code, answers, header_status, raw_stderr + raw_stdout)

    return ResolveResponse(
        domain=domain,
        record_type=record_type,
        answers=answers,
        query_time_ms=query_time_ms,
        status=status,
        raw_output=raw_stdout.strip(),
        anchor_id=ANCHOR_ID,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "anchor_id": ANCHOR_ID}


@app.post("/resolve", response_model=ResolveResponse)
async def resolve(req: ResolveRequest):
    """Resolve a DNS query using the local system resolver via dig.

    Executes `dig +noall +comments +answer +stats <domain> <record_type>`
    and returns structured results including answers, timing, and status.
    """
    return await run_dig(req.domain, req.record_type.value)
