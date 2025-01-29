# gunicorn.conf.py

# Server Socket
bind = "127.0.0.1:8000"  # Bind to IP and port
backlog = 2048  # Maximum number of pending connections

# Worker Processes
workers = 4  # Number of worker processes
worker_class = "sync"  # Worker type (sync, gevent, eventlet, etc.)
threads = 2  # Number of threads per worker
worker_connections = 1000  # Max simultaneous clients (only for async workers)
timeout = 30  # Worker timeout before restart
graceful_timeout = 30  # Extra time to finish requests before killing workers
keepalive = 2  # Keep-alive connections

# Security & User Settings
user = "www-data"  # User to run Gunicorn
group = "www-data"  # Group to run Gunicorn
umask = 0o022  # File permissions mask
chdir = "/path/to/app"  # Change to application directory

# Logging
accesslog = "logs/access.log"  # Log file for access logs
errorlog = "logs/error.log"  # Log file for error logs
loglevel = "info"  # Logging level (debug, info, warning, error, critical)
capture_output = True  # Capture print statements in logs

# Process Name & PID
proc_name = "gunicorn_app"  # Process name
pidfile = "/var/run/gunicorn.pid"  # File to store PID

# Daemon Mode
daemon = False  # Run in background (daemon mode)

# SSL (HTTPS)
certfile = "/path/to/cert.pem"  # SSL certificate file
keyfile = "/path/to/key.pem"  # SSL key file
ca_certs = "/path/to/ca.pem"  # Certificate authority file

# Gunicorn Hooks (for custom behavior)
def on_starting(server):
    print("Starting Gunicorn Server...")

def when_ready(server):
    print("Gunicorn is ready!")

def on_exit(server):
    print("Shutting down Gunicorn...")

