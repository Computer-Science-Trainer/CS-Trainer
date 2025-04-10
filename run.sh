#!/bin/bash
set -e

show_log_on_error() {
    echo -e "\n❌ ERROR OCCURRED ❌"
    echo "Last 50 lines of ${LOG_FILE}:"
    
    if [ -f "${LOG_FILE}" ]; then
        tail -n 50 "${LOG_FILE}"
    else
        echo "Log file ${LOG_FILE} not found!"
    fi
    
    echo -e "\n⚠️ Check full log at: ${LOG_FILE}"
    exit 1
}

if [ -z "${RESTARTED}" ]; then
    export RESTARTED="true"
else
    echo "Skipping git pull in restarted instance"
    goto_start_server=true
fi

if [ -z "${goto_start_server}" ]; then
    echo "Updating code from Git repository..."
    git fetch --all
    if ! git pull origin main; then
        echo "Warning: Git pull failed! Forcing code reset..."
        git reset --hard origin/main
        git clean -fd
        git pull origin main
    fi

    echo "Restarting script with updated version..."
    exec ./run.sh
fi

VENV_DIR="venv"
PID_FILE="server.pid"
LOG_FILE="server.log"
SSL_CERT_FILE="/etc/letsencrypt/live/cs-trainer.ru/fullchain.pem"
SSL_KEY_FILE="/etc/letsencrypt/live/cs-trainer.ru/privkey.pem"
SSL_PORT=443

if [ ! -d "${VENV_DIR}" ]; then
    python3 -m venv "${VENV_DIR}"
    echo "Virtual environment created at ${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"

if [ -f "requirements.txt" ]; then
    echo "Installing Python dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
else
    echo "Error: requirements.txt not found!"
    exit 1
fi

stop_server() {
    if [ -f "${PID_FILE}" ]; then
        local pid=$(cat "${PID_FILE}")
        echo "Stopping running server (PID: $pid)..."
        kill "$pid" || true
        sleep 2
        if ps -p "$pid" > /dev/null; then
            echo "Force killing server (PID: $pid)..."
            kill -9 "$pid"
        fi
        rm -f "${PID_FILE}"
    else
        local pid=$(pgrep -f "uvicorn main:app")
        if [ -n "$pid" ]; then
            echo "Found orphaned server process (PID: $pid). Stopping it..."
            kill "$pid"
        fi
    fi
}

stop_server

if [ ! -f "${SSL_CERT_FILE}" ] || [ ! -f "${SSL_KEY_FILE}" ]; then
    echo "Error: SSL certificate or key file not found!"
    exit 1
fi

echo "Starting Uvicorn server with SSL..."

sudo -E PATH=$PATH:${VENV_DIR}/bin nohup uvicorn main:app --host 0.0.0.0 --port ${SSL_PORT} --ssl-keyfile "${SSL_KEY_FILE}" --ssl-certfile "${SSL_CERT_FILE}" > "${LOG_FILE}" 2>&1 &
echo $! > "${PID_FILE}"

sleep 3
if ! ps -p $(cat "${PID_FILE}") > /dev/null; then
    show_log_on_error
fi

echo "Server started successfully (PID: $(cat "${PID_FILE}"))"
echo "Logs are being written to: ${LOG_FILE}"
echo "Deployment completed successfully"
