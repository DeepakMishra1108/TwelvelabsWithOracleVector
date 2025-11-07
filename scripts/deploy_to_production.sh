#!/bin/bash
#
# Production Deployment Script for TwelveLabs Video AI
# Deploy all Phase 1-4 changes + Rate Limiting + OCI Multi-Tenant + Admin Dashboard
#
# VM: 150.136.235.189 (ubuntu user)
# Service: dataguardian.service
# Domain: mishras.online
#
# Usage:
#   # From local machine:
#   scp scripts/deploy_to_production.sh ubuntu@150.136.235.189:/tmp/
#   ssh ubuntu@150.136.235.189
#   bash /tmp/deploy_to_production.sh
#
#   # Or run directly on VM:
#   cd /home/ubuntu/TwelvelabsVideoAI
#   ./scripts/deploy_to_production.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/home/ubuntu/TwelvelabsVideoAI"
SERVICE_NAME="dataguardian"
BACKUP_DIR="/home/ubuntu/backups"
LOG_FILE="/tmp/deployment_$(date +%Y%m%d_%H%M%S).log"

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

# Check if running on correct VM
check_environment() {
    log "Checking environment..."
    
    if [ ! -d "$PROJECT_DIR" ]; then
        error "Project directory not found: $PROJECT_DIR"
        error "This script should be run on the production VM (150.136.235.189)"
        exit 1
    fi
    
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        error ".env file not found in $PROJECT_DIR"
        exit 1
    fi
    
    if ! systemctl is-enabled "$SERVICE_NAME" &>/dev/null; then
        warning "Service $SERVICE_NAME is not enabled"
        info "Service may need to be set up after deployment"
    fi
    
    log "✅ Environment check passed"
}

# Create backup
create_backup() {
    log "Creating backup..."
    
    mkdir -p "$BACKUP_DIR"
    
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$BACKUP_DIR/backup_$TIMESTAMP.tar.gz"
    
    cd /home/ubuntu
    tar -czf "$BACKUP_FILE" \
        --exclude='TwelvelabsVideoAI/.git' \
        --exclude='TwelvelabsVideoAI/__pycache__' \
        --exclude='TwelvelabsVideoAI/temp' \
        --exclude='TwelvelabsVideoAI/static/uploads' \
        TwelvelabsVideoAI/ 2>/dev/null || true
    
    if [ -f "$BACKUP_FILE" ]; then
        log "✅ Backup created: $BACKUP_FILE"
        
        # Keep only last 5 backups
        ls -t "$BACKUP_DIR"/backup_*.tar.gz | tail -n +6 | xargs -r rm
        log "Cleaned up old backups (keeping last 5)"
    else
        warning "Backup creation failed, but continuing..."
    fi
}

# Stop service
stop_service() {
    log "Stopping $SERVICE_NAME service..."
    
    if systemctl is-active "$SERVICE_NAME" &>/dev/null; then
        sudo systemctl stop "$SERVICE_NAME"
        sleep 2
        
        if systemctl is-active "$SERVICE_NAME" &>/dev/null; then
            error "Failed to stop $SERVICE_NAME"
            exit 1
        fi
        
        log "✅ Service stopped"
    else
        info "Service was not running"
    fi
}

# Pull latest changes
pull_changes() {
    log "Pulling latest changes from GitHub..."
    
    cd "$PROJECT_DIR"
    
    # Save current branch
    CURRENT_BRANCH=$(git branch --show-current)
    log "Current branch: $CURRENT_BRANCH"
    
    # Stash any local changes
    if ! git diff --quiet || ! git diff --cached --quiet; then
        warning "Local changes detected, stashing..."
        git stash push -m "Auto-stash before deployment $(date)"
        STASHED=true
    else
        STASHED=false
    fi
    
    # Pull latest changes
    git fetch origin
    
    COMMITS_BEHIND=$(git rev-list --count HEAD..origin/$CURRENT_BRANCH)
    
    if [ "$COMMITS_BEHIND" -gt 0 ]; then
        log "Pulling $COMMITS_BEHIND new commit(s)..."
        git pull origin "$CURRENT_BRANCH"
        log "✅ Changes pulled successfully"
    else
        info "Already up to date"
    fi
    
    # Show what changed
    log "Recent commits:"
    git log --oneline -10 | tee -a "$LOG_FILE"
}

# Check Python dependencies
check_dependencies() {
    log "Checking Python dependencies..."
    
    cd "$PROJECT_DIR"
    
    if [ -f "requirements.txt" ]; then
        # Check if pip packages need updates
        pip3 list --outdated 2>/dev/null | grep -q "." && {
            warning "Some packages are outdated"
            info "Consider running: pip3 install --upgrade -r requirements.txt"
        } || {
            log "✅ Dependencies are up to date"
        }
    else
        warning "requirements.txt not found"
    fi
}

# Run database migrations if needed
run_migrations() {
    log "Checking for database migrations..."
    
    cd "$PROJECT_DIR"
    
    # Check if migration scripts exist
    if [ -d "scripts" ]; then
        # Run create tables if needed
        if [ -f "scripts/run_create_tables.py" ]; then
            info "Running table creation script..."
            python3 scripts/run_create_tables.py 2>&1 | tee -a "$LOG_FILE" || true
        fi
        
        # Run execute migration if needed
        if [ -f "scripts/execute_migration.py" ]; then
            info "Running migration script..."
            python3 scripts/execute_migration.py 2>&1 | tee -a "$LOG_FILE" || true
        fi
        
        log "✅ Database migrations checked"
    fi
}

# Set proper permissions
set_permissions() {
    log "Setting proper permissions..."
    
    cd "$PROJECT_DIR"
    
    # Make scripts executable
    if [ -d "scripts" ]; then
        chmod +x scripts/*.sh 2>/dev/null || true
        chmod +x scripts/*.py 2>/dev/null || true
    fi
    
    # Ensure .env is not world-readable
    if [ -f ".env" ]; then
        chmod 600 .env
    fi
    
    log "✅ Permissions set"
}

# Start service
start_service() {
    log "Starting $SERVICE_NAME service..."
    
    sudo systemctl start "$SERVICE_NAME"
    sleep 3
    
    if systemctl is-active "$SERVICE_NAME" &>/dev/null; then
        log "✅ Service started successfully"
    else
        error "Failed to start $SERVICE_NAME"
        error "Check logs with: sudo journalctl -u $SERVICE_NAME -n 50"
        exit 1
    fi
}

# Verify deployment
verify_deployment() {
    log "Verifying deployment..."
    
    # Check service status
    if systemctl is-active "$SERVICE_NAME" &>/dev/null; then
        log "✅ Service is running"
    else
        error "Service is not running!"
        return 1
    fi
    
    # Check for errors in logs
    RECENT_ERRORS=$(sudo journalctl -u "$SERVICE_NAME" --since "1 minute ago" | grep -i error | wc -l)
    
    if [ "$RECENT_ERRORS" -gt 0 ]; then
        warning "Found $RECENT_ERRORS error(s) in recent logs"
        info "Check logs with: sudo journalctl -u $SERVICE_NAME -n 50"
    else
        log "✅ No recent errors in logs"
    fi
    
    # Try to access the application
    info "Testing application endpoint..."
    
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ | grep -q "200\|302"; then
        log "✅ Application is responding"
    else
        warning "Application may not be responding correctly"
        info "Check with: curl -v http://localhost:8080/"
    fi
}

# Show deployment summary
show_summary() {
    log "=================================================="
    log "          DEPLOYMENT SUMMARY"
    log "=================================================="
    log ""
    log "Deployment Time: $(date)"
    log "Git Branch: $(cd $PROJECT_DIR && git branch --show-current)"
    log "Latest Commit: $(cd $PROJECT_DIR && git log -1 --oneline)"
    log "Service Status: $(systemctl is-active $SERVICE_NAME)"
    log "Log File: $LOG_FILE"
    log ""
    log "✅ DEPLOYMENT COMPLETE!"
    log ""
    log "Next Steps:"
    log "1. Monitor logs: sudo journalctl -u $SERVICE_NAME -f"
    log "2. Check application: https://mishras.online"
    log "3. Test new features:"
    log "   - Admin Dashboard: https://mishras.online/admin/quotas"
    log "   - Rate Limiting: Upload >100 files to test limits"
    log "   - OCI Path Isolation: Upload files as different users"
    log "4. Run OCI tests: cd $PROJECT_DIR && python3 scripts/test_oci_path_isolation.py"
    log ""
}

# Main deployment flow
main() {
    log "=================================================="
    log "   PRODUCTION DEPLOYMENT STARTING"
    log "=================================================="
    log ""
    
    # Pre-deployment checks
    check_environment
    
    # User confirmation
    echo ""
    echo -e "${YELLOW}This will deploy all Phase 1-4 changes to production.${NC}"
    echo -e "${YELLOW}Service will be stopped and restarted.${NC}"
    echo ""
    read -p "Continue with deployment? (yes/no): " -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        error "Deployment cancelled by user"
        exit 1
    fi
    
    # Execute deployment steps
    create_backup
    stop_service
    pull_changes
    check_dependencies
    run_migrations
    set_permissions
    start_service
    sleep 5
    verify_deployment
    show_summary
    
    log "Deployment script completed at $(date)"
}

# Handle errors
trap 'error "Deployment failed at line $LINENO. Check log: $LOG_FILE"; exit 1' ERR

# Run main function
main "$@"
