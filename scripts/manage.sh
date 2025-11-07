#!/bin/bash

###############################################################################
# Data Guardian - Management Script
# Quick commands for managing the application on OCI VM
###############################################################################

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}=========================================="
    echo -e "$1"
    echo -e "==========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}➜ $1${NC}"
}

# Show usage
show_usage() {
    print_header "Data Guardian Management"
    echo ""
    echo "Usage: ./manage.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start       - Start the application"
    echo "  stop        - Stop the application"
    echo "  restart     - Restart the application"
    echo "  status      - Show service status"
    echo "  logs        - View application logs (follow)"
    echo "  logs-nginx  - View Nginx logs"
    echo "  logs-error  - View error logs"
    echo "  update      - Pull latest code and restart"
    echo "  test        - Test application health"
    echo "  health      - Check all services health"
    echo "  backup      - Create backup of application"
    echo "  stats       - Show system statistics"
    echo ""
}

# Start service
start_service() {
    print_info "Starting Data Guardian..."
    sudo systemctl start dataguardian
    sudo systemctl start nginx
    sleep 3
    if sudo systemctl is-active --quiet dataguardian; then
        print_success "Application started successfully"
    else
        print_error "Failed to start application"
        echo "Check logs: sudo journalctl -u dataguardian -n 50"
    fi
}

# Stop service
stop_service() {
    print_info "Stopping Data Guardian..."
    sudo systemctl stop dataguardian
    print_success "Application stopped"
}

# Restart service
restart_service() {
    print_info "Restarting Data Guardian..."
    sudo systemctl restart dataguardian
    sudo systemctl reload nginx
    sleep 3
    if sudo systemctl is-active --quiet dataguardian; then
        print_success "Application restarted successfully"
    else
        print_error "Failed to restart application"
        echo "Check logs: sudo journalctl -u dataguardian -n 50"
    fi
}

# Show status
show_status() {
    print_header "Service Status"
    echo ""
    
    # Data Guardian service
    echo -n "Data Guardian: "
    if sudo systemctl is-active --quiet dataguardian; then
        print_success "Running"
    else
        print_error "Stopped"
    fi
    
    # Nginx service
    echo -n "Nginx: "
    if sudo systemctl is-active --quiet nginx; then
        print_success "Running"
    else
        print_error "Stopped"
    fi
    
    echo ""
    sudo systemctl status dataguardian --no-pager -l | head -n 15
}

# View logs
view_logs() {
    print_info "Showing application logs (Ctrl+C to exit)..."
    sudo journalctl -u dataguardian -f
}

# View Nginx logs
view_nginx_logs() {
    print_info "Showing Nginx access logs (Ctrl+C to exit)..."
    sudo tail -f /var/log/nginx/dataguardian-access.log
}

# View error logs
view_error_logs() {
    print_header "Recent Errors"
    echo ""
    echo "Application errors:"
    sudo journalctl -u dataguardian -p err -n 20 --no-pager
    echo ""
    echo "Nginx errors:"
    sudo tail -n 20 /var/log/nginx/dataguardian-error.log
}

# Update application
update_app() {
    print_info "Updating application..."
    
    # Check if git repo
    if [ ! -d ".git" ]; then
        print_error "Not a git repository"
        exit 1
    fi
    
    # Stash local changes
    print_info "Stashing local changes..."
    git stash
    
    # Pull latest code
    print_info "Pulling latest code..."
    git pull origin main
    
    # Activate virtual environment
    print_info "Activating virtual environment..."
    source twelvelabvideoai/bin/activate
    
    # Update dependencies
    print_info "Updating dependencies..."
    pip install -r requirements.txt
    
    # Restart service
    print_info "Restarting service..."
    sudo systemctl restart dataguardian
    
    sleep 3
    
    if sudo systemctl is-active --quiet dataguardian; then
        print_success "Update completed successfully"
    else
        print_error "Update failed - service not running"
        echo "Check logs: sudo journalctl -u dataguardian -n 50"
    fi
}

# Test application
test_app() {
    print_info "Testing application health..."
    
    # Get VM IP
    VM_IP=$(curl -s ifconfig.me)
    
    # Test localhost
    echo -n "Testing localhost... "
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:80 | grep -q "200\|302"; then
        print_success "OK"
    else
        print_error "Failed"
    fi
    
    # Test public IP
    echo -n "Testing public IP... "
    if curl -s -o /dev/null -w "%{http_code}" http://$VM_IP | grep -q "200\|302"; then
        print_success "OK"
    else
        print_error "Failed"
    fi
}

# Health check
health_check() {
    print_header "System Health Check"
    echo ""
    
    # Services
    echo "Services:"
    echo -n "  Data Guardian: "
    if sudo systemctl is-active --quiet dataguardian; then
        print_success "Running"
    else
        print_error "Stopped"
    fi
    
    echo -n "  Nginx: "
    if sudo systemctl is-active --quiet nginx; then
        print_success "Running"
    else
        print_error "Stopped"
    fi
    
    # Ports
    echo ""
    echo "Ports:"
    echo -n "  8080 (Gunicorn): "
    if sudo netstat -tuln | grep -q ":8080 "; then
        print_success "Open"
    else
        print_error "Closed"
    fi
    
    echo -n "  80 (Nginx): "
    if sudo netstat -tuln | grep -q ":80 "; then
        print_success "Open"
    else
        print_error "Closed"
    fi
    
    # Disk space
    echo ""
    echo "Disk Usage:"
    df -h / | tail -n 1 | awk '{printf "  Root: %s used of %s (%s)\n", $3, $2, $5}'
    
    # Memory
    echo ""
    echo "Memory:"
    free -h | grep Mem | awk '{printf "  Used: %s of %s\n", $3, $2}'
    
    # CPU Load
    echo ""
    echo "CPU Load:"
    uptime | awk -F'load average:' '{printf "  %s\n", $2}'
    
    # Recent errors
    echo ""
    ERROR_COUNT=$(sudo journalctl -u dataguardian -p err --since "1 hour ago" | grep -c "^-- " || echo "0")
    echo "Recent Errors (last hour): $ERROR_COUNT"
}

# Create backup
create_backup() {
    print_info "Creating backup..."
    
    BACKUP_DIR="/home/dataguardian/backups"
    mkdir -p "$BACKUP_DIR"
    
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_FILE="$BACKUP_DIR/dataguardian_backup_$TIMESTAMP.tar.gz"
    
    # Backup application files
    print_info "Backing up application files..."
    tar -czf "$BACKUP_FILE" \
        --exclude='twelvelabvideoai' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.git' \
        --exclude='logs' \
        -C /home/dataguardian TwelvelabsWithOracleVector
    
    print_success "Backup created: $BACKUP_FILE"
    
    # Show backup size
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "Backup size: $BACKUP_SIZE"
    
    # List recent backups
    echo ""
    echo "Recent backups:"
    ls -lh "$BACKUP_DIR" | tail -n 5
}

# Show system stats
show_stats() {
    print_header "System Statistics"
    echo ""
    
    # Uptime
    echo "System Uptime:"
    uptime -p | sed 's/^/  /'
    
    echo ""
    echo "Application Uptime:"
    sudo systemctl show dataguardian --property=ActiveEnterTimestamp | cut -d= -f2 | sed 's/^/  /'
    
    # Resource usage
    echo ""
    echo "Resource Usage:"
    echo "  CPU:"
    top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print "    " 100 - $1 "% used"}'
    
    echo "  Memory:"
    free -h | grep Mem | awk '{printf "    %s used of %s (%s)\n", $3, $2, int($3/$2 * 100) "%"}'
    
    echo "  Disk:"
    df -h / | tail -n 1 | awk '{printf "    %s used of %s (%s)\n", $3, $2, $5}'
    
    # Request stats (if logs exist)
    if [ -f "/var/log/nginx/dataguardian-access.log" ]; then
        echo ""
        echo "Request Statistics (last 24 hours):"
        TOTAL_REQUESTS=$(sudo grep "$(date +%d/%b/%Y)" /var/log/nginx/dataguardian-access.log | wc -l || echo "0")
        echo "  Total requests: $TOTAL_REQUESTS"
        
        if [ "$TOTAL_REQUESTS" -gt 0 ]; then
            echo "  Status codes:"
            sudo grep "$(date +%d/%b/%Y)" /var/log/nginx/dataguardian-access.log | \
                awk '{print $9}' | sort | uniq -c | sort -rn | head -n 5 | \
                awk '{printf "    %s: %d\n", $2, $1}'
        fi
    fi
}

# Main
case "$1" in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        show_status
        ;;
    logs)
        view_logs
        ;;
    logs-nginx)
        view_nginx_logs
        ;;
    logs-error)
        view_error_logs
        ;;
    update)
        update_app
        ;;
    test)
        test_app
        ;;
    health)
        health_check
        ;;
    backup)
        create_backup
        ;;
    stats)
        show_stats
        ;;
    *)
        show_usage
        ;;
esac
