#!/bin/bash
# HH:MM | S3(5.5) | ctx 71k/1M 7% | 2m36s | 5h 2h14m | wk 3d6h
input=$(cat)
j() { printf '%s' "$input" | jq -r "$1" 2>/dev/null; }
D=$'\e[90m'; G=$'\e[32m'; C=$'\e[36m'; Y=$'\e[33m'; R=$'\e[31m'; M=$'\e[35m'; W=$'\e[97m'; Z=$'\e[0m'
SEP="${D} │ ${Z}"
sev() { # value warn crit [invert] -> color
  awk -v v="$1" -v w="$2" -v c="$3" -v inv="$4" -v G="$G" -v Y="$Y" -v R="$R" 'BEGIN{
    if (inv) { if (v<c) print R; else if (v<w) print Y; else print G }
    else     { if (v>=c) print R; else if (v>=w) print Y; else print G } }'; }
human() { awk -v n="$1" 'BEGIN{ if(n>=1e6) printf "%.3gM",n/1e6; else if(n>=1e3) printf "%.3gk",n/1e3; else printf "%d",n }'; }
dur() { awk -v s="$1" 'BEGIN{ s=int(s); d=int(s/86400); h=int((s%86400)/3600); m=int((s%3600)/60);
  if(d>0) printf "%dd%dh",d,h; else if(h>0) printf "%dh%dm",h,m; else if(m>0) printf "%dm%02ds",m,s%60; else printf "%ds",s }'; }

t="${G}$(TZ=America/New_York date +%H:%M)${Z}"

# model: letter + effort digit + (version)
name=$(j '.model.display_name // ""'); id=$(j '.model.id // ""')
case "${name,,}${id,,}" in *opus*) L=O;; *sonnet*) L=S;; *haiku*) L=H;; *fable*) L=F;; *) L=${name:0:1};; esac
ver=$(printf '%s %s' "$name" "$id" | grep -oE '[0-9]+([.-][0-9]+)?' | head -1 | tr - .)
eff=$(j '.effort.level // .effort // .reasoning_effort // empty')
[ -z "$eff" ] && eff=$(jq -r '.effortLevel // empty' ~/.claude/settings.json 2>/dev/null)
case "$eff" in none|minimal) e=0;; low) e=1;; medium) e=2;; high) e=3;; xhigh) e=4;; max) e=5;; *) e="";; esac
case "$e" in 0|1) ec=$D;; 2|3) ec=$C;; 4|5) ec=$M;; *) ec=$D;; esac
model="${C}${L}${Z}${ec}${e}${Z}${D}(${ver})${Z}"

# context
size=$(j '.context_window.context_window_size // 0'); pct=$(j '.context_window.used_percentage // 0')
cu=$(j '[.context_window.current_usage.input_tokens, .context_window.current_usage.cache_creation_input_tokens, .context_window.current_usage.cache_read_input_tokens] | map(. // 0) | add // 0')
cc=$(sev "$pct" 50 80)
ctx="${D}ctx ${Z}${cc}$(human "$cu")${Z}${D}/$(human "$size") ${Z}${cc}$(printf '%.0f' "$pct")%${Z}"


# user:dir and cc version
cwd=$(j '.workspace.current_dir // .cwd // ""'); cwd="${cwd/#$HOME/\~}"
ccv=$(j '.version // empty')
where="${G}$(whoami)${Z}${D}:${Z}${C}${cwd}${Z}"

# session time
ms=$(j '.cost.total_duration_ms // 0'); tm="${C}$(dur $((ms/1000)))${Z}"

# rate-limit countdowns
now=$(date +%s)
cd_field() { # label path warnsec critsec
  local r left col
  r=$(j ".rate_limits.$2.resets_at // empty")
  if [ -z "$r" ]; then printf '%s%s –%s' "$D" "$1" "$Z"; return; fi
  left=$(( r - now )); [ $left -lt 0 ] && left=0
  col=$W; [ $left -lt $3 ] && col=$Y; [ $left -lt $4 ] && col=$R
  printf '%s%s %s%s%s%s' "$D" "$1" "$Z" "$col" "$(dur $left)" "$Z"
}
f5=$(cd_field 5h five_hour 1800 600); f7=$(cd_field wk seven_day 21600 3600)

printf '%s%s%s%s%s%s%s%s%s%s%s' "$where" $'\n' "$t" "$SEP" "$model" "$SEP" "$ctx" "$SEP" "$tm" "$SEP" "$f5"
printf '%s%s' "$SEP" "$f7"
[ -n "$ccv" ] && printf '%s%scc%s%s' "$SEP" "$D" "$ccv" "$Z"
