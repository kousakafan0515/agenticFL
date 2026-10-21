#!/usr/bin/env bash
set -euo pipefail

workspace_root=/mnt/d/skillMAS
secrets_root="$workspace_root/SkillAdaptor_MAS_collaboration_20260901"
output_root="$workspace_root/stage3_2_role_agnostic_semantic_merge/runs/v9_local_b2_round2_20261014_r1"
python_bin=/home/user0515/miniconda3/envs/stage3-alfworld/bin/python

source "$secrets_root/scripts/load_secrets.sh" "$secrets_root/secrets/.env" >/dev/null
: "${STAGE3_AGGREGATION_API_KEY:?DeepSeek official API key is missing}"
: "${STAGE3_AGGREGATION_BASE_URL:?DeepSeek official base URL is missing}"
if [[ "${STAGE3_AGGREGATION_BASE_URL%/}" != "https://api.deepseek.com" ]]; then
  printf '%s\n' "DeepSeek official base URL is required" >&2
  exit 1
fi
export STAGE3_AGGREGATION_MODEL=deepseek-flash
export PYTHONPATH="$workspace_root${PYTHONPATH:+:$PYTHONPATH}"

cd "$workspace_root"
"$python_bin" -m stage3_2_role_agnostic_semantic_merge.round2_aggregate \
  --output-root "$output_root" \
  "$@"
