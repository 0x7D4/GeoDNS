#!/usr/bin/env bash
# =============================================================================
# GeoDNS Explorer — Anchor Agent Setup Script
# =============================================================================
# Sets up the anchor agent as a systemd service on a Raspberry Pi.
#
# Usage:
#   sudo ./anchor_setup.sh --anchor-id <id>
#
# Example:
#   sudo ./anchor_setup.sh --anchor-id mumbai-01
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCRIPT_NAME="$(basename "$0")"
readonly SCRIPT_NAME
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
readonly INSTALL_DIR="/opt/anchor-agent"
readonly SERVICE_NAME="anchor-agent"
readonly SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
readonly LISTEN_PORT="8053"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log()   { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO]  $*"; }
warn()  { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARN]  $*" >&2; }
error() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
usage() {
    cat <<EOF
Usage: ${SCRIPT_NAME} --anchor-id <id>

Sets up the GeoDNS anchor agent as a systemd service.

Options:
    --anchor-id <id>    Unique identifier for this anchor (e.g., mumbai-01)
    -h, --help          Show this help message

Examples:
    sudo ${SCRIPT_NAME} --anchor-id mumbai-01
    sudo ${SCRIPT_NAME} --anchor-id delhi-01
EOF
    exit 0
}

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
preflight() {
    # Must run as root
    if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
        error "This script must be run as root (use sudo)"
    fi

    # Ensure we're on a Debian-based system
    if ! command -v apt-get &>/dev/null; then
        error "apt-get not found — this script requires a Debian-based system"
    fi

    # Ensure dig is available (or will be installed)
    if ! command -v dig &>/dev/null; then
        log "dig not found, will be installed via dnsutils"
    fi
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
ANCHOR_ID=""

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --anchor-id)
                [[ $# -lt 2 ]] && error "--anchor-id requires a value"
                ANCHOR_ID="$2"
                shift 2
                ;;
            -h|--help)
                usage
                ;;
            *)
                error "Unknown argument: $1 (see --help)"
                ;;
        esac
    done

    if [[ -z "${ANCHOR_ID}" ]]; then
        error "--anchor-id is required (see --help)"
    fi

    # Validate anchor_id format (alphanumeric, hyphens, underscores)
    if [[ ! "${ANCHOR_ID}" =~ ^[a-zA-Z0-9_-]+$ ]]; then
        error "Invalid anchor-id format: '${ANCHOR_ID}' — use only letters, numbers, hyphens, underscores"
    fi

    log "Anchor ID: ${ANCHOR_ID}"
}

# ---------------------------------------------------------------------------
# Install system dependencies (idempotent)
# ---------------------------------------------------------------------------
install_dependencies() {
    log "Installing system dependencies..."

    apt-get update -qq

    # python3, pip, venv, dnsutils (for dig)
    local -a packages=(python3 python3-pip python3-venv dnsutils)
    for pkg in "${packages[@]}"; do
        if dpkg -s "${pkg}" &>/dev/null; then
            log "  ✓ ${pkg} already installed"
        else
            log "  → Installing ${pkg}..."
            apt-get install -y -qq "${pkg}"
        fi
    done
}

# ---------------------------------------------------------------------------
# Set up application directory and virtual environment
# ---------------------------------------------------------------------------
setup_application() {
    log "Setting up application in ${INSTALL_DIR}..."

    # Create install directory (idempotent)
    mkdir -p "${INSTALL_DIR}"

    # Copy application files
    cp "${SCRIPT_DIR}/anchor_agent.py" "${INSTALL_DIR}/anchor_agent.py"
    cp "${SCRIPT_DIR}/requirements.txt" "${INSTALL_DIR}/requirements.txt"

    # Create virtual environment if it doesn't exist
    if [[ ! -d "${INSTALL_DIR}/venv" ]]; then
        log "  → Creating virtual environment..."
        python3 -m venv "${INSTALL_DIR}/venv"
    else
        log "  ✓ Virtual environment already exists"
    fi

    # Install/upgrade Python dependencies
    log "  → Installing Python dependencies..."
    "${INSTALL_DIR}/venv/bin/pip" install --quiet --upgrade pip
    "${INSTALL_DIR}/venv/bin/pip" install --quiet -r "${INSTALL_DIR}/requirements.txt"

    log "  ✓ Application setup complete"
}

# ---------------------------------------------------------------------------
# Create systemd service unit (idempotent)
# ---------------------------------------------------------------------------
create_service() {
    log "Creating systemd service: ${SERVICE_NAME}..."

    cat > "${SERVICE_FILE}" <<UNIT
[Unit]
Description=GeoDNS Anchor Agent (${ANCHOR_ID})
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/uvicorn anchor_agent:app --host 0.0.0.0 --port ${LISTEN_PORT}
Environment=ANCHOR_ID=${ANCHOR_ID}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

# Hardening
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=${INSTALL_DIR}

[Install]
WantedBy=multi-user.target
UNIT

    log "  ✓ Service file written to ${SERVICE_FILE}"
}

# ---------------------------------------------------------------------------
# Enable and start the service
# ---------------------------------------------------------------------------
enable_service() {
    log "Enabling and starting ${SERVICE_NAME}..."

    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}"
    systemctl restart "${SERVICE_NAME}"

    # Brief status check
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        log "  ✓ ${SERVICE_NAME} is running on port ${LISTEN_PORT}"
    else
        warn "  ✗ ${SERVICE_NAME} may not have started — check: journalctl -u ${SERVICE_NAME}"
    fi
}

# ---------------------------------------------------------------------------
# Cleanup trap
# ---------------------------------------------------------------------------
cleanup() {
    # Nothing to clean up on success, but ensures
    # partial installs don't leave broken state
    if [[ $? -ne 0 ]]; then
        warn "Setup did not complete successfully. Check errors above."
    fi
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    log "============================================="
    log "GeoDNS Anchor Agent Setup"
    log "============================================="

    parse_args "$@"
    preflight
    install_dependencies
    setup_application
    create_service
    enable_service

    log "============================================="
    log "Setup complete!"
    log "  Anchor ID:    ${ANCHOR_ID}"
    log "  Listen port:  ${LISTEN_PORT}"
    log "  Install dir:  ${INSTALL_DIR}"
    log "  Service:      systemctl status ${SERVICE_NAME}"
    log "  Logs:         journalctl -u ${SERVICE_NAME} -f"
    log "============================================="
}

main "$@"
