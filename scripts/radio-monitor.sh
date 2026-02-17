#!/bin/bash
# Radio Monitor - Automated capture, transcribe, translate
# Runs entirely standalone — no LLM tokens burned
# Usage: ./radio-monitor.sh [duration_sec] [interval_sec] [num_clips]
#   or: ./radio-monitor.sh --continuous (runs until killed)

set -euo pipefail

RADIO_HOST="192.168.10.179"
RADIO_PORT="2222"
RADIO_USER="bonsaihorn"
RADIO_API="http://localhost:8000"
AUDIO_DEV="hw:CARD=CODEC"
OPENAI_API_KEY="${OPENAI_API_KEY:-$(grep OPENAI_API_KEY ~/Projects/helios/.env 2>/dev/null | cut -d= -f2)}"

CLIP_DURATION="${1:-20}"
INTERVAL="${2:-120}"
NUM_CLIPS="${3:-0}"  # 0 = continuous

OUTDIR="$HOME/Projects/lbf-ham-radio/logs/radio-monitor"
mkdir -p "$OUTDIR"

LOG="$OUTDIR/monitor.log"
TRANSCRIPT_LOG="$OUTDIR/transcripts_$(date +%Y%m%d).jsonl"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# Get current radio status
get_status() {
    ssh -p "$RADIO_PORT" "$RADIO_USER@$RADIO_HOST" \
        "curl -s $RADIO_API/api/status" 2>/dev/null
}

# Record audio clip from radio
record_clip() {
    local outfile="$1"
    local duration="$2"
    ssh -p "$RADIO_PORT" "$RADIO_USER@$RADIO_HOST" \
        "arecord -D $AUDIO_DEV -f S16_LE -r 48000 -c 1 -d $duration /tmp/_radio_clip.wav 2>/dev/null" && \
    scp -P "$RADIO_PORT" "$RADIO_USER@$RADIO_HOST:/tmp/_radio_clip.wav" "$outfile" 2>/dev/null
}

# Apply bandpass filter + AGC
filter_audio() {
    local infile="$1"
    local outfile="$2"
    sox "$infile" "$outfile" \
        sinc 200-3400 \
        compand 0.3,1 6:-70,-60,-20 -5 -90 0.2 \
        norm 2>/dev/null
}

# Transcribe via OpenAI Whisper API
transcribe() {
    local audiofile="$1"
    local language="${2:-es}"
    local prompt="${3:-Conversación de radioaficionados.}"
    
    curl -s "https://api.openai.com/v1/audio/transcriptions" \
        -H "Authorization: Bearer $OPENAI_API_KEY" \
        -F "file=@$audiofile" \
        -F "model=whisper-1" \
        -F "language=$language" \
        -F "prompt=$prompt" \
        -F "response_format=json" 2>/dev/null
}

# Translate via OpenAI (cheap gpt-4o-mini, ~$0.0001 per clip)
translate() {
    local text="$1"
    curl -s "https://api.openai.com/v1/chat/completions" \
        -H "Authorization: Bearer $OPENAI_API_KEY" \
        -H "Content-Type: application/json" \
        -d "$(jq -n --arg t "$text" '{
            model: "gpt-4o-mini",
            max_tokens: 500,
            messages: [{
                role: "user",
                content: ("Translate this ham radio conversation from Spanish to English. Preserve any callsigns (like KP4ABC, WP4XYZ, W1ABC) exactly as spoken. Keep it natural.\n\n" + $t)
            }]
        }')" 2>/dev/null | jq -r '.choices[0].message.content // "TRANSLATION_FAILED"'
}

# Check if transcription is just noise/hallucination
is_valid_transcript() {
    local text="$1"
    local len=${#text}
    # Too short = noise
    [[ $len -lt 10 ]] && return 1
    # Repeated prompt text = hallucination
    echo "$text" | grep -qiE "(QTH.*QTH.*QTH|señal report.*señal report|www\.|visite|suscríbete)" && return 1
    return 0
}

# Extract callsigns from text
extract_callsigns() {
    local text="$1"
    echo "$text" | grep -oiE '\b[AKNW][A-Z]?[0-9][A-Z]{1,3}\b' | tr '[:lower:]' '[:upper:]' | sort -u
}

log "=== Radio Monitor Started ==="
log "Clip duration: ${CLIP_DURATION}s, Interval: ${INTERVAL}s, Clips: ${NUM_CLIPS:-continuous}"

clip_count=0
while true; do
    clip_count=$((clip_count + 1))
    timestamp=$(date +%Y%m%d_%H%M%S)
    
    # Get radio status
    status=$(get_status 2>/dev/null || echo '{}')
    freq=$(echo "$status" | jq -r '.status.frequency_a // 0' 2>/dev/null)
    freq_mhz=$(echo "scale=3; $freq / 1000000" | bc 2>/dev/null || echo "?.???")
    smeter=$(echo "$status" | jq -r '.status.s_meter // 0' 2>/dev/null)
    mode=$(echo "$status" | jq -r '.status.mode // "?"' 2>/dev/null)
    
    log "Clip $clip_count: ${freq_mhz} MHz ($mode), S-meter: $smeter"
    
    # Skip if S-meter too low (just noise)
    if [[ "$smeter" -lt 20 ]]; then
        log "  S-meter too low ($smeter), waiting ${INTERVAL}s"
        if [[ "$NUM_CLIPS" -gt 0 && "$clip_count" -ge "$NUM_CLIPS" ]]; then
            break
        fi
        sleep "${INTERVAL:-5}"
        continue
    fi
    
    # Record
    raw_file="$OUTDIR/clip_${timestamp}.wav"
    filt_file="$OUTDIR/clip_${timestamp}_filt.wav"
    
    if ! record_clip "$raw_file" "$CLIP_DURATION"; then
        log "  Recording failed, skipping"
        sleep "$INTERVAL"
        continue
    fi
    
    # Filter
    filter_audio "$raw_file" "$filt_file"
    
    # Transcribe (Spanish by default for 14.270 etc)
    response=$(transcribe "$filt_file" "es" "Conversación de radioaficionados en español caribeño. Indicativos KP4, WP4, NP4, W, K, N.")
    es_text=$(echo "$response" | jq -r '.text // ""' 2>/dev/null)
    
    if ! is_valid_transcript "$es_text"; then
        log "  Invalid/noise transcript, skipping"
        rm -f "$raw_file"  # Clean up noise clips
        sleep "$INTERVAL"
        continue
    fi
    
    log "  ES: $es_text"
    
    # Translate
    en_text=$(translate "$es_text")
    log "  EN: $en_text"
    
    # Check for callsigns
    callsigns=$(extract_callsigns "$es_text $en_text")
    if [[ -n "$callsigns" ]]; then
        log "  🎯 CALLSIGNS DETECTED: $callsigns"
    fi
    
    # Log as JSONL
    jq -n \
        --arg ts "$timestamp" \
        --arg freq "$freq_mhz" \
        --arg mode "$mode" \
        --arg smeter "$smeter" \
        --arg es "$es_text" \
        --arg en "$en_text" \
        --arg calls "$callsigns" \
        '{timestamp: $ts, freq_mhz: $freq, mode: $mode, s_meter: $smeter, spanish: $es, english: $en, callsigns: $calls}' \
        >> "$TRANSCRIPT_LOG"
    
    # Clean up raw file (keep filtered for review)
    rm -f "$raw_file"
    
    # Check if we've done enough
    if [[ "$NUM_CLIPS" -gt 0 && "$clip_count" -ge "$NUM_CLIPS" ]]; then
        log "Completed $NUM_CLIPS clips, exiting"
        break
    fi
    
    sleep "$INTERVAL"
done

log "=== Radio Monitor Stopped ==="
