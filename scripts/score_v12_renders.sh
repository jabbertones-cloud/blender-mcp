#!/bin/bash
cd /Users/tatsheen/claw-architect/openclaw-blender-mcp
RENDERS="renders/v12_renders"

echo "V12 RENDER QUALITY SCORES"
echo "=========================="
echo ""

total_score=0
count=0

for f in $RENDERS/v12_scene*.png; do
  if [ -f "$f" ]; then
    fname=$(basename "$f")
    score=$(node scripts/3d-forge/render-quality-scorer.js --image "$f" --tier 1 2>&1 | grep -o "score=[0-9.]*" | head -1 | cut -d= -f2)
    if [ -n "$score" ]; then
      printf "%-45s %6s\n" "$fname:" "$score"
      total_score=$(echo "$total_score + $score" | bc)
      count=$((count + 1))
    else
      echo "$fname: SCORING FAILED"
    fi
  fi
done

echo ""
echo "=========================="
if [ $count -gt 0 ]; then
  avg=$(echo "scale=2; $total_score / $count" | bc)
  echo "Total renders: $count"
  echo "Average score: $avg"
else
  echo "No renders scored"
fi
