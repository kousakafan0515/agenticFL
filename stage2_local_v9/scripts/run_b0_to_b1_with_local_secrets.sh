#!/usr/bin/env bash
set -euo pipefail

workspace_root=/mnt/d/skillMAS
secrets_root="$workspace_root/SkillAdaptor_MAS_collaboration_20260901"
python_bin=/home/user0515/miniconda3/envs/stage3-alfworld/bin/python
run_root="$workspace_root/stage2_local_v9/runs/client_a_generation_01_20261013_r1"
manifest="$workspace_root/stage2_local_v9/artifacts/manifests/client_a_generation_01.json"
b0_bank="$workspace_root/stage2_local_v9/templates/B0_empty_skillbank.json"

source "$secrets_root/scripts/load_secrets.sh" "$secrets_root/secrets/.env" >/dev/null
: "${DASHSCOPE_API_KEY:?DASHSCOPE_API_KEY is missing}"
: "${STAGE3_AGGREGATION_API_KEY:?DeepSeek official API key is missing}"
: "${STAGE3_AGGREGATION_BASE_URL:?DeepSeek official base URL is missing}"
if [[ "${STAGE3_AGGREGATION_BASE_URL%/}" != "https://api.deepseek.com" ]]; then
  printf '%s\n' "DeepSeek official base URL is required" >&2
  exit 1
fi

export LOCAL_EVOLUTION_API_KEY="$STAGE3_AGGREGATION_API_KEY"
export LOCAL_EVOLUTION_BASE_URL="$STAGE3_AGGREGATION_BASE_URL"
export LOCAL_EVOLUTION_MODEL=deepseek-flash
export PYTHONPATH="$workspace_root${PYTHONPATH:+:$PYTHONPATH}"

if [[ -e "$run_root/B0_training" || -e "$run_root/B1_skillbank.json" || -e "$run_root/B1_teacher_record.json" ]]; then
  printf '%s\n' "Refusing to overwrite existing v9 B0/B1 outputs" >&2
  exit 1
fi
mkdir -p "$run_root"
cd "$workspace_root"

"$python_bin" -m stage2_local_v9.scripts.run_client_a_phase \
  --phase training \
  --generation 1 \
  --manifest "$manifest" \
  --output-root "$run_root/B0_training" \
  --data-root "$workspace_root/alfworld_data" \
  --python "$python_bin"

"$python_bin" -m stage2_local_v9.scripts.run_client_a_phase \
  --phase validation \
  --generation 0 \
  --manifest "$manifest" \
  --output-root "$run_root/B0_validation" \
  --data-root "$workspace_root/alfworld_data" \
  --python "$python_bin"
