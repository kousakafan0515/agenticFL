#!/usr/bin/env bash
set -euo pipefail

workspace_root=/mnt/d/skillMAS
secrets_root="$workspace_root/SkillAdaptor_MAS_collaboration_20260901"
python_bin=/home/user0515/miniconda3/envs/stage3-alfworld/bin/python

cd "$workspace_root"
bash -n stage2_local_v9/scripts/run_client_bc_b0_b1_with_local_secrets.sh
source "$secrets_root/scripts/load_secrets.sh" "$secrets_root/secrets/.env" >/dev/null
: "${DASHSCOPE_API_KEY:?DASHSCOPE_API_KEY is missing}"
: "${STAGE3_AGGREGATION_API_KEY:?DeepSeek official API key is missing}"
: "${STAGE3_AGGREGATION_BASE_URL:?DeepSeek official base URL is missing}"
test "${STAGE3_AGGREGATION_BASE_URL%/}" = "https://api.deepseek.com"
export LOCAL_EVOLUTION_API_KEY="$STAGE3_AGGREGATION_API_KEY"
export LOCAL_EVOLUTION_BASE_URL="$STAGE3_AGGREGATION_BASE_URL"
export LOCAL_EVOLUTION_MODEL=deepseek-flash
export PYTHONPATH="$workspace_root${PYTHONPATH:+:$PYTHONPATH}"

"$python_bin" -m stage2_local_v9.scripts.materialize_client_bc_assets --check
"$python_bin" -m stage2_local_v9.scripts.run_client_to_b1 --client B --run-root /tmp/v9_client_b_preflight --data-root "$workspace_root/alfworld_data" --python "$python_bin" --preflight-only
"$python_bin" -m stage2_local_v9.scripts.run_client_to_b1 --client C --run-root /tmp/v9_client_c_preflight --data-root "$workspace_root/alfworld_data" --python "$python_bin" --preflight-only
printf '%s\n' V9_CLIENT_BC_PREFLIGHT_OK
