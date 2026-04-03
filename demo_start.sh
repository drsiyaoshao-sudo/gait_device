#!/usr/bin/env bash
# GaitSense Judicial Demo — 4-panel tmux setup
# Run this, start your screen recorder, then follow demo_judicial_sop.md

cd /Users/siyaoshao/gait_device

# Kill any prior session
tmux kill-session -t gaitsense_demo 2>/dev/null || true

# Create session (pane 0)
tmux new-session -d -s gaitsense_demo

# Split into 4 panes: TL=0, BL=1, TR=2, BR=3
tmux split-window -h -t gaitsense_demo:0.0       # 0=left, 1=right
tmux split-window -v -t gaitsense_demo:0.0       # 0=TL, 1=BL, 2=TR
tmux split-window -v -t gaitsense_demo:0.2       # 0=TL, 1=BL, 2=TR, 3=BR

# Force equal 2x2 layout
tmux select-layout -t gaitsense_demo tiled

# Pane 0 — ATTORNEY-A (top-left)
tmux send-keys -t gaitsense_demo:0.0 "cd /Users/siyaoshao/gait_device && clear && echo '=== ATTORNEY-A ===' && claude" Enter

# Pane 1 — ATTORNEY-B (bottom-left)
tmux send-keys -t gaitsense_demo:0.1 "cd /Users/siyaoshao/gait_device && clear && echo '=== ATTORNEY-B ===' && claude" Enter

# Pane 2 — EVIDENCE (top-right)
tmux send-keys -t gaitsense_demo:0.2 "cd /Users/siyaoshao/gait_device && export GAITSENSE_DEMO=1 && clear && echo '=== EVIDENCE TERMINAL — awaiting dispatch from Justice ==='" Enter

# Pane 3 — JUSTICE / main session (bottom-right)
tmux send-keys -t gaitsense_demo:0.3 "cd /Users/siyaoshao/gait_device && clear && echo '=== JUSTICE ===' && claude" Enter

# Focus Justice pane before attaching
tmux select-pane -t gaitsense_demo:0.3

tmux attach-session -t gaitsense_demo
