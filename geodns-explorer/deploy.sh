#!/usr/bin/env bash
# =============================================================================
# GeoDNS Explorer — Cloud VM Deployment Script
# =============================================================================
#
# Deploys the complete GeoDNS Explorer stack on an Ubuntu/Debian server:
#   - Python backend (FastAPI + Uvicorn) as a systemd service
#   - React frontend (Vite build) served as static files via nginx
#   - Nginx reverse proxy (/api/ → backend, / → frontend)
#   - Optional HTTPS via Let's Encrypt / certbot
#
# Usage:
#   bash deploy.sh [OPTIONS]
#
# Options:
#   --domain <domain>  Set nginx server_name and enable HTTPS via certbot.
#                      If omitted, runs HTTP-only with catch-all server_name.
#   --port <port>      Backend port (default: 8000)
#   --dry-run          Print all steps without executing any commands
#   -h, --help         Show this help message
#
# Examples:
#   bash deploy.sh                                # HTTP only, raw IP
#   bash deploy.sh --domain geodns.amiphoria.in   # subdomain with HTTPS
#   bash deploy.sh --domain yourtool.xyz          # any custom domain
#   bash deploy.sh --dry-run                      # preview all steps
#
# Idempotent: safe to re-run for updates. Will restart services, overwrite
# configs, and rebuild the frontend on every run.
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SCRIPT_NAME="$(basename "$0")"
readonly SCRIPT_NAME
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
readonly BACKEND_DIR="${SCRIPT_DIR}/backend"
readonly FRONTEND_DIR="${SCRIPT_DIR}/frontend"
readonly NGINX_CONF_SRC="${SCRIPT_DIR}/nginx/geodns.conf"
readonly NGINX_SITES_AVAILABLE="/etc/nginx/sites-available/geodns-explorer"
readonly NGINX_SITES_ENABLED="/etc/nginx/sites-enabled/geodns-explorer"
readonly FRONTEND_WEBROOT="/var/www/geodns-explorer"
readonly SERVICE_NAME="geodns-backend"
readonly SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# ---------------------------------------------------------------------------
# Configuration (overridable via flags)
# ---------------------------------------------------------------------------
DOMAIN=""
PORT="8000"
DRY_RUN=false
STEP_NUM=0

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log()   { echo -e "\033[0;32m[INFO]\033[0m  $*"; }
warn()  { echo -e "\033[0;33m[WARN]\033[0m  $*" >&2; }
error() { echo -e "\033[0;31m[ERROR]\033[0m $*" >&2; }
step()  {
    STEP_NUM=$((STEP_NUM + 1))
    echo ""
    echo -e "\033[0;36m[ STEP ${STEP_NUM} ]\033[0m $*"
    echo "────────────────────────────────────────────────"
}
success() { echo -e "  \033[0;32m✓\033[0m $*"; }
fail()    { echo -e "  \033[0;31m✗\033[0m $*"; }

# ---------------------------------------------------------------------------
# Dry-run wrapper — executes command or prints it
# ---------------------------------------------------------------------------
run() {
    if [[ "${DRY_RUN}" == true ]]; then
        echo "  [DRY-RUN] $*"
    else
        "$@"
    fi
}

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
usage() {
    cat <<EOF
Usage: ${SCRIPT_NAME} [OPTIONS]

Deploy GeoDNS Explorer on an Ubuntu/Debian server.

Options:
    --domain <domain>  Set nginx server_name and enable HTTPS via certbot
    --port <port>      Backend port (default: 8000)
    --dry-run          Print all steps without executing
    -h, --help         Show this help message

Examples:
    bash ${SCRIPT_NAME}
    bash ${SCRIPT_NAME} --domain geodns.example.com
    bash ${SCRIPT_NAME} --dry-run
EOF
    exit 0
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --domain)
                [[ $# -lt 2 ]] && { error "--domain requires a value"; exit 1; }
                DOMAIN="$2"
                shift 2
                ;;
            --port)
                [[ $# -lt 2 ]] && { error "--port requires a value"; exit 1; }
                PORT="$2"
                shift 2
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            -h|--help)
                usage
                ;;
            *)
                error "Unknown argument: $1 (see --help)"
                exit 1
                ;;
        esac
    done

    # Validate port is numeric
    if [[ ! "${PORT}" =~ ^[0-9]+$ ]]; then
        error "Invalid port: '${PORT}' — must be a number"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Step 1: Check OS
# ---------------------------------------------------------------------------
step_check_os() {
    step "Checking operating system"

    if [[ "${DRY_RUN}" == true ]]; then
        echo "  [DRY-RUN] Check /etc/os-release for Ubuntu/Debian"
        return
    fi

    if [[ ! -f /etc/os-release ]]; then
        fail "Cannot detect OS — /etc/os-release not found"
        error "This script requires Ubuntu or Debian."
        exit 1
    fi

    # shellcheck source=/dev/null
    source /etc/os-release

    if [[ "${ID}" != "ubuntu" && "${ID}" != "debian" ]]; then
        fail "Unsupported OS: ${PRETTY_NAME}"
        error "This script requires Ubuntu or Debian. Detected: ${PRETTY_NAME}"
        exit 1
    fi

    success "OS: ${PRETTY_NAME}"
}

# ---------------------------------------------------------------------------
# Step 2: Install system packages
# ---------------------------------------------------------------------------
step_install_packages() {
    step "Installing system packages"

    # Add nodesource PPA for Node.js 20 LTS if not already present
    if ! command -v node &>/dev/null || [[ "$(node --version 2>/dev/null | cut -d. -f1 | tr -d 'v')" -lt 18 ]]; then
        log "Adding NodeSource PPA for Node.js 20 LTS..."
        if [[ "${DRY_RUN}" == true ]]; then
            echo "  [DRY-RUN] curl -fsSL https://deb.nodesource.com/setup_20.x | bash -"
        else
            curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
        fi
    else
        success "Node.js $(node --version) already installed"
    fi

    run apt-get update -qq

    local -a packages=(
        python3
        python3-pip
        python3-venv
        nodejs
        nginx
    )

    log "Installing: ${packages[*]}"
    run apt-get install -y -qq "${packages[@]}"

    if [[ "${DRY_RUN}" != true ]]; then
        success "Python: $(python3 --version)"
        success "Node: $(node --version)"
        success "npm: $(npm --version)"
        success "nginx: $(nginx -v 2>&1 | cut -d/ -f2)"
    fi
}

# ---------------------------------------------------------------------------
# Step 3: Set up backend Python environment
# ---------------------------------------------------------------------------
step_setup_backend() {
    step "Setting up backend Python environment"

    if [[ ! -d "${BACKEND_DIR}" ]]; then
        fail "Backend directory not found: ${BACKEND_DIR}"
        error "Are you running this script from the project root?"
        exit 1
    fi

    log "Creating virtual environment..."
    run python3 -m venv "${BACKEND_DIR}/venv"

    log "Installing Python dependencies..."
    if [[ "${DRY_RUN}" == true ]]; then
        echo "  [DRY-RUN] ${BACKEND_DIR}/venv/bin/pip install -r ${BACKEND_DIR}/requirements.txt"
    else
        "${BACKEND_DIR}/venv/bin/pip" install --quiet --upgrade pip
        "${BACKEND_DIR}/venv/bin/pip" install --quiet -r "${BACKEND_DIR}/requirements.txt"
    fi

    success "Backend environment ready"
}

# ---------------------------------------------------------------------------
# Step 4: Build frontend and deploy to webroot
# ---------------------------------------------------------------------------
step_build_frontend() {
    step "Building frontend and deploying to webroot"

    if [[ ! -d "${FRONTEND_DIR}" ]]; then
        fail "Frontend directory not found: ${FRONTEND_DIR}"
        error "Are you running this script from the project root?"
        exit 1
    fi

    log "Installing npm dependencies..."
    if [[ "${DRY_RUN}" == true ]]; then
        echo "  [DRY-RUN] cd ${FRONTEND_DIR} && npm ci"
        echo "  [DRY-RUN] npm run build"
        echo "  [DRY-RUN] cp -r dist/ → ${FRONTEND_WEBROOT}/"
    else
        (cd "${FRONTEND_DIR}" && npm ci --silent)

        log "Building production bundle..."
        (cd "${FRONTEND_DIR}" && npm run build)

        if [[ ! -d "${FRONTEND_DIR}/dist" ]]; then
            fail "Build failed — dist/ directory not created"
            exit 1
        fi

        log "Deploying to ${FRONTEND_WEBROOT}..."
        mkdir -p "${FRONTEND_WEBROOT}"
        # Clean old files and copy new build
        rm -rf "${FRONTEND_WEBROOT:?}"/*
        cp -r "${FRONTEND_DIR}/dist/"* "${FRONTEND_WEBROOT}/"
        chown -R www-data:www-data "${FRONTEND_WEBROOT}"
    fi

    success "Frontend deployed to ${FRONTEND_WEBROOT}"
}

# ---------------------------------------------------------------------------
# Step 5: Configure nginx
# ---------------------------------------------------------------------------
step_configure_nginx() {
    step "Configuring nginx"

    if [[ ! -f "${NGINX_CONF_SRC}" ]]; then
        fail "Nginx config template not found: ${NGINX_CONF_SRC}"
        exit 1
    fi

    log "Writing nginx configuration..."
    if [[ "${DRY_RUN}" == true ]]; then
        echo "  [DRY-RUN] Copy ${NGINX_CONF_SRC} → ${NGINX_SITES_AVAILABLE}"
        if [[ -n "${DOMAIN}" ]]; then
            echo "  [DRY-RUN] sed: server_name _ → server_name ${DOMAIN}"
        fi
        echo "  [DRY-RUN] ln -sf ${NGINX_SITES_AVAILABLE} → ${NGINX_SITES_ENABLED}"
        echo "  [DRY-RUN] Remove default site if exists"
        echo "  [DRY-RUN] sed: proxy_pass port → ${PORT}"
        echo "  [DRY-RUN] nginx -t"
        echo "  [DRY-RUN] systemctl reload nginx"
    else
        cp "${NGINX_CONF_SRC}" "${NGINX_SITES_AVAILABLE}"

        # Set the backend port in proxy_pass
        sed -i "s|proxy_pass http://127.0.0.1:8000|proxy_pass http://127.0.0.1:${PORT}|" \
            "${NGINX_SITES_AVAILABLE}"

        # Set server_name if domain provided
        if [[ -n "${DOMAIN}" ]]; then
            sed -i "s|server_name _;|server_name ${DOMAIN};|" "${NGINX_SITES_AVAILABLE}"
            success "server_name set to: ${DOMAIN}"
        else
            success "server_name: _ (catch-all, HTTP only)"
        fi

        # Enable site
        ln -sf "${NGINX_SITES_AVAILABLE}" "${NGINX_SITES_ENABLED}"

        # Remove default site to avoid conflicts
        rm -f /etc/nginx/sites-enabled/default

        # Test configuration
        if ! nginx -t 2>&1; then
            fail "nginx config test failed"
            error "Check: ${NGINX_SITES_AVAILABLE}"
            exit 1
        fi

        systemctl reload nginx
    fi

    success "Nginx configured and reloaded"
}

# ---------------------------------------------------------------------------
# Step 6 & 7: Create and start systemd service
# ---------------------------------------------------------------------------
step_setup_service() {
    step "Setting up systemd service: ${SERVICE_NAME}"

    local venv_uvicorn="${BACKEND_DIR}/venv/bin/uvicorn"

    if [[ "${DRY_RUN}" == true ]]; then
        echo "  [DRY-RUN] Write ${SERVICE_FILE}"
        echo "  [DRY-RUN] systemctl daemon-reload"
        echo "  [DRY-RUN] systemctl enable ${SERVICE_NAME}"
        echo "  [DRY-RUN] systemctl restart ${SERVICE_NAME}"
    else
        cat > "${SERVICE_FILE}" <<UNIT
[Unit]
Description=GeoDNS Explorer Backend
After=network.target

[Service]
WorkingDirectory=${BACKEND_DIR}
ExecStart=${venv_uvicorn} main:app --host 127.0.0.1 --port ${PORT}
Restart=always
RestartSec=5
User=www-data
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
UNIT

        # Ensure www-data can read the backend directory
        chown -R www-data:www-data "${BACKEND_DIR}"

        systemctl daemon-reload
        systemctl enable "${SERVICE_NAME}"
        # Use restart (not start) for idempotency — works on first run and re-runs
        systemctl restart "${SERVICE_NAME}"

        # Brief check
        sleep 2
        if systemctl is-active --quiet "${SERVICE_NAME}"; then
            success "Service ${SERVICE_NAME} is active"
        else
            fail "Service ${SERVICE_NAME} failed to start"
            warn "Check logs: journalctl -u ${SERVICE_NAME} -n 20"
            exit 1
        fi
    fi
}

# ---------------------------------------------------------------------------
# Step 8: HTTPS via certbot (only if --domain given)
# ---------------------------------------------------------------------------
step_setup_https() {
    if [[ -z "${DOMAIN}" ]]; then
        step "HTTPS setup (skipped — no --domain provided)"
        log "To add HTTPS later: re-run with --domain yourdomain.com"
        return
    fi

    step "Setting up HTTPS via certbot for ${DOMAIN}"

    # Validate domain resolves to this server's IP
    if [[ "${DRY_RUN}" != true ]]; then
        local server_ip
        server_ip="$(curl -s --max-time 5 https://api.ipify.org 2>/dev/null || \
                     curl -s --max-time 5 https://ifconfig.me 2>/dev/null || \
                     echo "")"

        if [[ -z "${server_ip}" ]]; then
            warn "Could not detect this server's public IP — skipping DNS validation"
        else
            local domain_ip
            domain_ip="$(dig +short "${DOMAIN}" A 2>/dev/null | head -1)"

            if [[ -z "${domain_ip}" ]]; then
                fail "Domain ${DOMAIN} does not resolve to any IP address."
                error "Point your DNS A record to ${server_ip} first, then re-run."
                exit 1
            fi

            if [[ "${domain_ip}" != "${server_ip}" ]]; then
                fail "Domain ${DOMAIN} does not resolve to this server's IP (${server_ip})."
                error "It currently resolves to: ${domain_ip}"
                error "Point your DNS A record to ${server_ip} first, then re-run."
                exit 1
            fi

            success "DNS verified: ${DOMAIN} → ${server_ip}"
        fi
    fi

    log "Installing certbot..."
    run apt-get install -y -qq certbot python3-certbot-nginx

    log "Requesting certificate for ${DOMAIN}..."
    if [[ "${DRY_RUN}" == true ]]; then
        echo "  [DRY-RUN] certbot --nginx -d ${DOMAIN} --non-interactive --agree-tos -m admin@${DOMAIN} --keep-until-expiring"
    else
        certbot --nginx \
            -d "${DOMAIN}" \
            --non-interactive \
            --agree-tos \
            -m "admin@${DOMAIN}" \
            --keep-until-expiring

        systemctl reload nginx
    fi

    success "HTTPS configured for ${DOMAIN}"
}

# ---------------------------------------------------------------------------
# Step 8.5: IP Detection Health Check
# ---------------------------------------------------------------------------
check_ip_detection() {
  if [[ "${DRY_RUN}" == true ]]; then
    echo "  [DRY-RUN] Verifying IP detection..."
    return
  fi

  echo "[ HEALTH ] Verifying IP detection..."
  RESPONSE=$(curl -s http://localhost/api/locate)
  SOURCE=$(echo "$RESPONSE" | python3 -c \
    "import sys,json; print(json.load(sys.stdin)[\"location\"][\"source\"])")
  IP=$(echo "$RESPONSE" | python3 -c \
    "import sys,json; print(json.load(sys.stdin)[\"location\"][\"ip\"])")

  if [ "$SOURCE" = "mock-local" ]; then
    echo "✗ IP detection still returning mock-local."
    echo "  Check: nginx X-Forwarded-For headers not passing through."
    echo "  Run: grep 'X-Forwarded-For' /etc/nginx/sites-available/geodns-explorer"
    exit 1
  fi

  echo "✓ IP detection: $IP (source: $SOURCE)"
}

# ---------------------------------------------------------------------------
# Step 9: Success banner
# ---------------------------------------------------------------------------
step_success_banner() {
    step "Deployment complete!"

    local frontend_url

    if [[ -n "${DOMAIN}" ]]; then
        frontend_url="https://${DOMAIN}"
    else
        if [[ "${DRY_RUN}" == true ]]; then
            frontend_url="http://<server-public-ip>"
        else
            local public_ip
            public_ip="$(curl -s --max-time 5 https://api.ipify.org 2>/dev/null || \
                         curl -s --max-time 5 https://ifconfig.me 2>/dev/null || \
                         echo "<server-ip>")"
            frontend_url="http://${public_ip}"
        fi
    fi

    echo ""
    echo "  ┌─────────────────────────────────────────────────┐"
    echo "  │         GeoDNS Explorer — Deployed! 🚀          │"
    echo "  └─────────────────────────────────────────────────┘"
    echo ""
    echo "  ✓ Backend : running on 127.0.0.1:${PORT}"
    echo "  ✓ Frontend: ${frontend_url}"
    echo "  ✓ Nginx   : active"

    if [[ -z "${DOMAIN}" ]]; then
        echo "  ✓ To add HTTPS later: re-run with --domain yourdomain.com"
    else
        echo "  ✓ HTTPS   : enabled for ${DOMAIN}"
    fi

    echo ""
    echo "  Useful commands:"
    echo "    journalctl -u ${SERVICE_NAME} -f     # backend logs"
    echo "    systemctl status ${SERVICE_NAME}      # backend status"
    echo "    systemctl status nginx                # nginx status"
    echo "    nginx -t                              # test nginx config"
    echo ""
}

# ---------------------------------------------------------------------------
# Cleanup trap
# ---------------------------------------------------------------------------
cleanup() {
    local exit_code=$?
    if [[ ${exit_code} -ne 0 && ${STEP_NUM} -gt 0 ]]; then
        echo ""
        fail "FAILED at step ${STEP_NUM}"
        error "Deployment did not complete successfully. Check errors above."
    fi
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
preflight() {
    # Must run as root (unless dry-run)
    if [[ "${DRY_RUN}" != true && "${EUID:-$(id -u)}" -ne 0 ]]; then
        error "This script must be run as root (use: sudo bash ${SCRIPT_NAME})"
        exit 1
    fi

    # Verify project structure exists
    if [[ ! -d "${BACKEND_DIR}" || ! -d "${FRONTEND_DIR}" ]]; then
        error "Project structure incomplete. Expected backend/ and frontend/ directories."
        error "Run this script from the geodns-explorer/ project root."
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    echo ""
    echo "  ╔═══════════════════════════════════════════════════╗"
    echo "  ║        GeoDNS Explorer — Deployment Script        ║"
    echo "  ╚═══════════════════════════════════════════════════╝"
    echo ""

    parse_args "$@"

    if [[ "${DRY_RUN}" == true ]]; then
        warn "DRY-RUN MODE — no commands will be executed"
        echo ""
    fi

    log "Configuration:"
    log "  Domain:  ${DOMAIN:-<none — HTTP only>}"
    log "  Port:    ${PORT}"
    log "  Dry-run: ${DRY_RUN}"
    log "  Project: ${SCRIPT_DIR}"

    preflight

    step_check_os
    step_install_packages
    step_setup_backend
    step_build_frontend
    step_configure_nginx
    step_setup_service
    step_setup_https
    check_ip_detection
    step_success_banner
}

main "$@"
