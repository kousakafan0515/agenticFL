#!/usr/bin/env bash
set -euo pipefail

workspace_root=/mnt/d/skillMAS
secrets_root="$workspace_root/SkillAdaptor_MAS_collaboration_20260901"
python_bin=/home/user0515/miniconda3/envs/stage3-alfworld/bin/python
run_root="$workspace_root/stage2_local_v9/runs/client_a_generation_01_20261013_r1"
manifest="$workspace_root/stage2_local_v9/artifacts/manifests/client_a_generation_01.json"

source "$secrets_root/scripts/load_secrets.sh" "$secrets_root/secrets/.env" >/dev/null
: "${DASHSCOPE_API_KEY:?DASHSCOPE_API_KEY is missing}"
export PYTHONPATH="$workspace_root${PYTHONPATH:+:$PYTHONPATH}"

if [[ ! -e "$run_root/B0_training/summary.json" || ! -e "$run_root/B0_training/evidence.json" ]]; then
  printf '%s\n' "Complete API-clean B0 training evidence is required" >&2
  exit 1
fi
if [[ -e "$run_root/B0_validation" ]]; then
  printf '%s\n' "Refusing to overwrite existing B0 validation output" >&2
  exit 1
fi
cd "$workspace_root"

"$python_bin" -m stage2_local_v9.scripts.run_client_a_phase \
  --phase validation \
  --generation 0 \
  --manifest "$manifest" \
  --output-root "$run_root/B0_validation" \
  --data-root "$workspace_root/alfworld_data" \
  --python "$python_bin"
