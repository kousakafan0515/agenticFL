#!/usr/bin/env bash
set -euo pipefail

workspace_root=/mnt/d/skillMAS
secrets_root="$workspace_root/SkillAdaptor_MAS_collaboration_20260901"
python_bin=/home/user0515/miniconda3/envs/stage3-alfworld/bin/python

source "$secrets_root/scripts/load_secrets.sh" "$secrets_root/secrets/.env" >/dev/null
: "${STAGE3_AGGREGATION_API_KEY:?DeepSeek official API key is missing}"
: "${STAGE3_AGGREGATION_BASE_URL:?DeepSeek official base URL is missing}"
if [[ "${STAGE3_AGGREGATION_BASE_URL%/}" != "https://api.deepseek.com" ]]; then
  printf '%s\n' 'DeepSeek official base URL required' >&2
  exit 1
fi
export PYTHONPATH="$workspace_root${PYTHONPATH:+:$PYTHONPATH}"
cd "$workspace_root"

if [[ "${1:-}" == "preflight" ]]; then
  "$python_bin" -c 'import openai; print("translation_api_preflight_ok")'
elif [[ "${1:-}" == "translate" ]]; then
  exec "$python_bin" -m stage2_local_v10.scripts.create_chinese_reference translate
else
  printf '%s\n' 'expected preflight or translate' >&2
  exit 2
fi
