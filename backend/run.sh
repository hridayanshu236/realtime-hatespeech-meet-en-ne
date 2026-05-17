#!/bin/bash
# run.sh - Local development server startup

echo "🚀 Starting Hate Speech Detection Backend..."
# Ensure the current directory is in the python path
export PYTHONPATH=$PYTHONPATH:.

# Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
