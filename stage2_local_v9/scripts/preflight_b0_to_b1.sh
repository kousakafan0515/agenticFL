#!/usr/bin/env bash
set -euo pipefail

workspace_root=/mnt/d/skillMAS
secrets_root="$workspace_root/SkillAdaptor_MAS_collaboration_20260901"
python_bin=/home/user0515/miniconda3/envs/stage3-alfworld/bin/python
run_root="$workspace_root/stage2_local_v9/runs/client_a_generation_01_20261012_r1"

cd "$workspace_root"
bash -n stage2_local_v9/scripts/run_b0_to_b1_with_local_secrets.sh
test -x "$python_bin"
test -f "$secrets_root/scripts/load_secrets.sh"
source "$secrets_root/scripts/load_secrets.sh" "$secrets_root/secrets/.env" >/dev/null
: "${DASHSCOPE_API_KEY:?DASHSCOPE_API_KEY is missing}"
: "${STAGE3_AGGREGATION_API_KEY:?DeepSeek official API key is missing}"
: "${STAGE3_AGGREGATION_BASE_URL:?DeepSeek official base URL is missing}"
test "${STAGE3_AGGREGATION_BASE_URL%/}" = "https://api.deepseek.com"
test ! -e "$run_root"
export PYTHONPATH="$workspace_root${PYTHONPATH:+:$PYTHONPATH}"
"$python_bin" -m unittest stage2_local_v9.tests.test_v9_protocol -q
printf '%s\n' "V9_B0_TO_B1_PREFLIGHT_OK"
