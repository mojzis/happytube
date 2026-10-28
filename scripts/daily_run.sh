#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status
set -o pipefail  # "cmd | tee" fails when cmd fails, not only when tee does

# Configuration
# The repo this script lives in, unless HAPPYTUBE_DIR says otherwise.
HAPPYTUBE_DIR="${HAPPYTUBE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
# Which pipeline to run: "legacy" (YouTube search + happiness, the default) or
# "trusted" (approved channels + rubric, decision 0009).
PIPELINE="${HAPPYTUBE_PIPELINE:-legacy}"
# Trusted only: HAPPYTUBE_PUSH=1 commits and pushes stages/trusted/ after the run
# (the Pages workflow deploys the player from it, decision 0010). Off by default.
PUSH="${HAPPYTUBE_PUSH:-0}"
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

# Commit what the trusted run wrote under stages/trusted/ (only there, never
# `git add -A`; nothing changed → no commit), then push. The push runs every time,
# so a commit left local by an earlier failed push goes out on the next run.
# No stages/trusted/ (nothing fetched yet) → nothing to do. Non-zero on failure.
push_trusted_stages() {
    if [ ! -d stages/trusted ]; then
        log "No stages/trusted directory; nothing to commit or push"
        return 0
    fi
    git add -- stages/trusted || return 1
    if git diff --cached --quiet -- stages/trusted; then
        log "No new trusted stage files; nothing to commit"
    else
        git commit -m "trusted run $DATE" -- stages/trusted 2>&1 | tee -a "$LOG_FILE" \
            || return 1
    fi
    git push 2>&1 | tee -a "$LOG_FILE" || return 1
    log "Pushed stages/trusted for $DATE"
}

if [ "$PIPELINE" = "trusted" ]; then
    log "Running the trusted pipeline (fetch, assess, enhance)..."
    STATUS=0
    uv run happytube trusted run --date "$DATE" 2>&1 | tee -a "$LOG_FILE" || STATUS=1
    if [ "$STATUS" -eq 0 ]; then
        log "Trusted pipeline completed successfully"
        # Informational only: a failure here must not skip the push below.
        uv run happytube trusted status --date "$DATE" 2>&1 | tee -a "$LOG_FILE" \
            || log "WARNING: trusted status failed (the run itself succeeded)"
    else
        log "ERROR: Trusted pipeline failed! See $LOG_FILE (rerunning is safe)"
    fi
    # A failed run may still have written files (other channels, batches):
    # those are pushed too.
    if [ "$PUSH" = "1" ] && ! push_trusted_stages; then
        log "ERROR: committing or pushing stages/trusted failed"
        STATUS=1
    fi
    exit "$STATUS"
elif [ "$PIPELINE" != "legacy" ]; then
    log "ERROR: unknown HAPPYTUBE_PIPELINE '$PIPELINE' (use legacy or trusted)"
    exit 2
fi

# Run full pipeline
log "Running HappyTube pipeline..."

if uv run happytube run-all \
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
