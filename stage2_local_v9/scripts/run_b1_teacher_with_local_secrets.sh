#!/usr/bin/env bash
set -euo pipefail

workspace_root=/mnt/d/skillMAS
secrets_root="$workspace_root/SkillAdaptor_MAS_collaboration_20260901"
python_bin=/home/user0515/miniconda3/envs/stage3-alfworld/bin/python
run_root="$workspace_root/stage2_local_v9/runs/client_a_generation_01_20261013_r1"
evidence="$run_root/B0_training/evidence.json"
parent_bank="$workspace_root/stage2_local_v9/templates/B0_empty_skillbank.json"
expected_evidence_sha256=d8d73561f9381a58a62aa94d038b4c62326c7b458dbcbc8f84e5f24e61c560dd

source "$secrets_root/scripts/load_secrets.sh" "$secrets_root/secrets/.env" >/dev/null
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
if [[ ! -e "$run_root/B0_training/summary.json" || ! -e "$run_root/B0_validation/summary.json" ]]; then
  printf '%s\n' "complete B0 training and validation summaries are required" >&2
  exit 1
fi
actual_evidence_sha256=$(sha256sum "$evidence" | awk '{print $1}')
if [[ "$actual_evidence_sha256" != "$expected_evidence_sha256" ]]; then
  printf '%s\n' "B0 training evidence hash mismatch" >&2
  exit 1
fi
if [[ -e "$run_root/B1_skillbank.json" || -e "$run_root/B1_teacher_record.json" ]]; then
  printf '%s\n' "refusing to overwrite B1 Teacher outputs" >&2
  exit 1
fi

export LOCAL_EVOLUTION_API_KEY="$STAGE3_AGGREGATION_API_KEY"
export LOCAL_EVOLUTION_BASE_URL="$STAGE3_AGGREGATION_BASE_URL"
export LOCAL_EVOLUTION_MODEL=deepseek-flash
export PYTHONPATH="$workspace_root${PYTHONPATH:+:$PYTHONPATH}"
cd "$workspace_root"

"$python_bin" -m stage2_local_v9.scripts.evolve_client_a_bank \
  --generation 1 \
  --teacher-model deepseek-flash \
  --teacher-provider deepseek_official \
  --evidence "$evidence" \
  --parent-bank "$parent_bank" \
  --output "$run_root/B1_skillbank.json" \
  --record-output "$run_root/B1_teacher_record.json"
