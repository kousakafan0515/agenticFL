#!/usr/bin/env bash
set -euo pipefail

workspace_root=/mnt/d/skillMAS
secrets_root="$workspace_root/SkillAdaptor_MAS_collaboration_20260901"
python_bin=/home/user0515/miniconda3/envs/stage3-alfworld/bin/python
date_tag=20261013_r3

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
cd "$workspace_root"

"$python_bin" -m stage2_local_v9.scripts.materialize_client_bc_assets --check
"$python_bin" -m unittest stage2_local_v9.tests.test_v9_protocol -q

for client in B C; do
  lower=${client,,}
  run_root="$workspace_root/stage2_local_v9/runs/client_${lower}_generation_01_${date_tag}"
  if [[ -e "$run_root" ]]; then
    printf '%s\n' "Refusing to overwrite $run_root" >&2
    exit 1
  fi
  "$python_bin" -m stage2_local_v9.scripts.run_client_to_b1 \
    --client "$client" \
    --run-root "$run_root" \
    --data-root "$workspace_root/alfworld_data" \
    --python "$python_bin"
done
