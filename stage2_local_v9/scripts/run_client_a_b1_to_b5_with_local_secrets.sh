#!/usr/bin/env bash
set -euo pipefail

workspace_root=/mnt/d/skillMAS
secrets_root="$workspace_root/SkillAdaptor_MAS_collaboration_20260901"
python_bin=/home/user0515/miniconda3/envs/stage3-alfworld/bin/python
run_root="$workspace_root/stage2_local_v9/runs/client_a_generation_01_20261013_r1"
manifest="$workspace_root/stage2_local_v9/artifacts/manifests/client_a_generation_01.json"

source "$secrets_root/scripts/load_secrets.sh" "$secrets_root/secrets/.env" >/dev/null
: "${DASHSCOPE_API_KEY:?DASHSCOPE_API_KEY is missing}"
: "${STAGE3_AGGREGATION_API_KEY:?DeepSeek official API key is missing}"
: "${STAGE3_AGGREGATION_BASE_URL:?DeepSeek official base URL is missing}"
if [[ "${STAGE3_AGGREGATION_BASE_URL%/}" != "https://api.deepseek.com" ]]; then
  printf '%s\n' "DeepSeek official base URL is required" >&2
  exit 1
fi
if [[ -e "$workspace_root/stage2_local_v9/TEACHER_PAUSED" ]]; then
  printf '%s\n' "v9 Teacher remains paused" >&2
  exit 1
fi

expected_b1_sha256=84218a56b828fe08b81bd476c62d32950f61764b13390e957fd22c430bf24db4
actual_b1_sha256=$(sha256sum "$run_root/B1_skillbank.json" | awk '{print $1}')
if [[ "$actual_b1_sha256" != "$expected_b1_sha256" ]]; then
  printf '%s\n' "Client A original v9 B1 hash mismatch" >&2
  exit 1
fi

export LOCAL_EVOLUTION_API_KEY="$STAGE3_AGGREGATION_API_KEY"
export LOCAL_EVOLUTION_BASE_URL="$STAGE3_AGGREGATION_BASE_URL"
export LOCAL_EVOLUTION_MODEL=deepseek-flash
export PYTHONPATH="$workspace_root${PYTHONPATH:+:$PYTHONPATH}"

cd "$workspace_root"
exec "$python_bin" -m stage2_local_v9.scripts.run_client_a_to_b5 \
  --run-root "$run_root" \
  --manifest "$manifest" \
  --data-root "$workspace_root/alfworld_data" \
  --start-generation 2 \
  --end-generation 5 \
  "$@"
