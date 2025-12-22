# Gunicorn Configuration File (HTTP)

# Server socket
bind = "0.0.0.0:8080"  # HTTP on port 8080

# Worker processes
workers = 2  # Reduced from 5 to minimize ImageBind memory footprint (2GB each)
worker_class = "sync"
worker_connections = 1000
timeout = 300  # Increased to 5 minutes for ImageBind model loading
keepalive = 5

# NOTE: preload_app disabled because ImageBind loading takes ~2min and exceeds systemd timeout
# Workers will load ImageBind on first use (lazy loading)
preload_app = False

# Logging
errorlog = "/home/dataguardian/TwelvelabsWithOracleVector/logs/gunicorn-error.log"
accesslog = "/home/dataguardian/TwelvelabsWithOracleVector/logs/gunicorn-access.log"
loglevel = "info"

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190


