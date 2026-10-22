#!/bin/bash
# Status line: the user's own line (user@host:dir + live model/effort badge) followed by the loop status.
input=$(cat)
own=$(printf '%s' "$input" | bash ~/.claude/statusline-command.sh 2>/dev/null | head -1)
loop=$(printf '%s' "$input" | python3 /workspace/tools/loop_status.py 2>/dev/null | head -1)
printf '%s  %s' "$own" "$loop"
