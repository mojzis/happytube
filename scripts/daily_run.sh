#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status

# Configuration
HAPPYTUBE_DIR="/home/user/happytube"
LOG_DIR="$HAPPYTUBE_DIR/logs"
DATE=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)

# Create log directory
mkdir -p "$LOG_DIR"

# Change to project directory
cd "$HAPPYTUBE_DIR"

# Log file
LOG_FILE="$LOG_DIR/$DATE.log"

# Function to log messages
log() {
    echo "[$(date +%Y-%m-%d\ %H:%M:%S)] $1" | tee -a "$LOG_FILE"
}

# Start logging
log "========================================="
log "Starting HappyTube Pipeline"
log "Date: $DATE"
log "========================================="

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    log "Activating virtual environment..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    log "Activating virtual environment..."
    source venv/bin/activate
fi

# Run full pipeline
log "Running HappyTube pipeline..."

if poetry run happytube run-all \
    --category Music \
    --max-videos 50 \
    --date "$DATE" 2>&1 | tee -a "$LOG_FILE"; then

    log "Pipeline completed successfully"

    # Check if report was generated
    REPORT_PATH="stages/report/$DATE.html"
    if [ -f "$REPORT_PATH" ]; then
        log "Report generated successfully: $REPORT_PATH"

        # Optional: Copy report to web server
        # Uncomment and configure the following line to deploy reports automatically
        # scp "$REPORT_PATH" user@server:/var/www/happytube/reports/

        # Optional: Send email notification
        # Uncomment and configure the following lines to send email notifications
        # SUBJECT="HappyTube Report - $DATE"
        # BODY="HappyTube report for $DATE is ready. See attached log."
        # echo "$BODY" | mail -s "$SUBJECT" -a "$LOG_FILE" user@example.com

        # Optional: Deploy to web player
        # Uncomment to automatically export and deploy to GitHub Pages
        # log "Exporting to web player..."
        # poetry run python -m happytube.web.export 2>&1 | tee -a "$LOG_FILE"
        # if [ -d "happytube/web/static" ]; then
        #     log "Web export completed"
        #     # You can add git commands here to commit and push
        #     # cd happytube/web/static && git add . && git commit -m "Update $DATE" && git push
        # fi

        log "========================================="
        log "Pipeline completed successfully"
        log "========================================="
        exit 0
    else
        log "ERROR: Report not generated at expected path: $REPORT_PATH"
        log "Pipeline may have failed during report stage"
        exit 1
    fi
else
    log "ERROR: Pipeline failed!"
    log "Check the log file for details: $LOG_FILE"

    # Optional: Send failure notification
    # Uncomment and configure the following lines to send failure notifications
    # SUBJECT="HappyTube Pipeline FAILED - $DATE"
    # BODY="HappyTube pipeline failed on $DATE. See attached log for details."
    # echo "$BODY" | mail -s "$SUBJECT" -a "$LOG_FILE" admin@example.com

    log "========================================="
    log "Pipeline failed"
    log "========================================="
    exit 1
fi
