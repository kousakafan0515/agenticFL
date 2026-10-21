#!/usr/bin/env bash
set -euo pipefail

workspace_root=/mnt/d/skillMAS
python_bin=/home/user0515/miniconda3/envs/stage3-alfworld/bin/python
run_root="$workspace_root/stage3_2_role_agnostic_semantic_merge/runs/v9_b1_round1_client_validation_20261014_r1"
export PYTHONPATH="$workspace_root${PYTHONPATH:+:$PYTHONPATH}"
cd "$workspace_root"

for client in A B C; do
  lower=$(printf '%s' "$client" | tr '[:upper:]' '[:lower:]')
  module="stage2_local_v9.scripts.run_client_${lower}_phase"
  manifest="$workspace_root/stage2_local_v9/artifacts/manifests/client_${lower}_generation_01.json"
  bank="$run_root/client_${client}/replacement_skillbank.json"
  output="$run_root/preflight/client_${client}"
  "$python_bin" -m "$module" \
    --phase validation \
    --generation 1 \
    --manifest "$manifest" \
    --bank "$bank" \
    --output-root "$output" \
    --data-root "$workspace_root/alfworld_data" \
    --python "$python_bin" \
    --dry-run
done
