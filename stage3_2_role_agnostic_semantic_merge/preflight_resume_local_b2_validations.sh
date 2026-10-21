#!/usr/bin/env bash
set -euo pipefail
workspace_root=/mnt/d/skillMAS
python_bin=/home/user0515/miniconda3/envs/stage3-alfworld/bin/python
run_root="$workspace_root/stage3_2_role_agnostic_semantic_merge/runs/v9_local_b2_client_validation_20261014_r1"
export PYTHONPATH="$workspace_root${PYTHONPATH:+:$PYTHONPATH}"
cd "$workspace_root"
for client in A B C; do
  lower=$(printf '%s' "$client" | tr '[:upper:]' '[:lower:]')
  case "$client" in
    A) order_reference="$workspace_root/stage2_local_v9/runs/client_a_generation_01_20261013_r1/B0_validation/result.json" ;;
    B) order_reference="$workspace_root/stage2_local_v9/runs/client_b_generation_01_20261013_r3/B0_validation/result.json" ;;
    C) order_reference="$workspace_root/stage2_local_v9/runs/client_c_generation_01_20261013_r3/B0_validation/result.json" ;;
  esac
  extra_args=(--resume-partial --resume-order-reference "$order_reference")
  if [[ "$client" == A ]]; then extra_args+=(--max-control-retries 12); fi
  "$python_bin" -m "stage2_local_v9.scripts.run_client_${lower}_phase" \
    --phase validation --generation 2 \
    --manifest "$workspace_root/stage2_local_v9/artifacts/manifests/client_${lower}_generation_01.json" \
    --bank "$run_root/client_${client}/runtime_skillbank.json" \
    --output-root "$run_root/client_${client}/validation" \
    --data-root "$workspace_root/alfworld_data" --python "$python_bin" \
    "${extra_args[@]}" --dry-run
done
