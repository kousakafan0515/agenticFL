#!/usr/bin/env bash
set -euo pipefail

workspace_root=/mnt/d/skillMAS
python_bin=/home/user0515/miniconda3/envs/stage3-alfworld/bin/python
run_root="$workspace_root/stage3_2_role_agnostic_semantic_merge/runs/v9_global2_client_validation_20261015_r1"
reference_root="$workspace_root/stage3_2_role_agnostic_semantic_merge/runs/v9_b1_round1_client_validation_20261014_r1"
export PYTHONPATH="$workspace_root${PYTHONPATH:+:$PYTHONPATH}"
cd "$workspace_root"

for client in A B C; do
  lower=$(printf '%s' "$client" | tr '[:upper:]' '[:lower:]')
  "$python_bin" -m "stage2_local_v9.scripts.run_client_${lower}_phase" \
    --phase validation --generation 2 \
    --manifest "$workspace_root/stage2_local_v9/artifacts/manifests/client_${lower}_generation_01.json" \
    --bank "$run_root/client_${client}/replacement_skillbank.json" \
    --output-root "$run_root/client_${client}/validation" \
    --data-root "$workspace_root/alfworld_data" --python "$python_bin" \
    --resume-partial \
    --resume-order-reference "$reference_root/client_${client}/validation/result.json" \
    --dry-run
done
