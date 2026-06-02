# bot/health_check.py
import logging
from flask import Flask, jsonify
import sys
import os

# Ensure bot modules can be imported if run directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logger = logging.getLogger(__name__) # Get logger for this module

app = Flask(__name__)

@app.route("/health")
def health_check():
    """Basic health check endpoint."""
    logger.debug("Health check endpoint accessed.")
    return jsonify({"status": "ok"}), 200

# Function to run the Flask app (can be called from scheduler.py or run directly)
def run_server(host="0.0.0.0", port=8080):
    """Runs the Flask development server."""
    logger.info(f"Starting health check server on {host}:{port}")
    # Use Flask's built-in server for simplicity. For production, use a proper WSGI server like Gunicorn.
    app.run(host=host, port=port)

if __name__ == "__main__":
    from bot.log_config import setup_logging
    setup_logging()
    # Allows running the health check server directly
    # Example: python bot/health_check.py
    run_server()
