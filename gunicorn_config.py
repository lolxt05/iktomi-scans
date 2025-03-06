
workers = 2
threads = 4
timeout = 120
bind = '0.0.0.0:8080'



forwarded_allow_ips = '*'
secure_scheme_headers = { 'X-Forwarded-Proto': 'https' }


# Logging
accesslog = "/usr/src/app/access.log"  # Log file for access logs
errorlog = "/usr/src/app/error.log"  # Log file for error logs
loglevel = "info"  # Logging level (debug, info, warning, error, critical)
capture_output = True  # Capture print statements in logs

daemon = False  # Run in background (daemon mode)

# Process Name & PID
proc_name = "gunicorn_app"  # Process name
pidfile = "/var/run/gunicorn.pid"  # File to store PID


# Security & User Settings
user = "www-data"  # User to run Gunicorn
group = "www-data"  # Group to run Gunicorn
umask = 0o022  # File permissions mask
# chdir = "/usr/src/app"  # Change to application directory