#!/usr/bin/env bash
set -euo pipefail

workspace_root=/mnt/d/skillMAS
secrets_root="$workspace_root/SkillAdaptor_MAS_collaboration_20260901"
python_bin=/home/user0515/miniconda3/envs/stage3-alfworld/bin/python
run_root="$workspace_root/stage2_local_v9/runs/client_a_generation_01_20261013_r1"
manifest="$workspace_root/stage2_local_v9/artifacts/manifests/client_a_generation_01.json"
b1_bank="$run_root/B1_skillbank.json"
expected_b1_sha256=84218a56b828fe08b81bd476c62d32950f61764b13390e957fd22c430bf24db4

source "$secrets_root/scripts/load_secrets.sh" "$secrets_root/secrets/.env" >/dev/null
: "${DASHSCOPE_API_KEY:?DASHSCOPE_API_KEY is missing}"
export PYTHONPATH="$workspace_root${PYTHONPATH:+:$PYTHONPATH}"

actual_b1_sha256=$(sha256sum "$b1_bank" | awk '{print $1}')
if [[ "$actual_b1_sha256" != "$expected_b1_sha256" ]]; then
  printf '%s\n' "B1 SkillBank hash mismatch" >&2
  exit 1
fi
if [[ -e "$run_root/B1_validation" ]]; then
  printf '%s\n' "refusing to overwrite existing B1 validation output" >&2
  exit 1
fi
cd "$workspace_root"

"$python_bin" -m stage2_local_v9.scripts.run_client_a_phase \
  --phase validation \
  --generation 1 \
  --manifest "$manifest" \
  --bank "$b1_bank" \
  --output-root "$run_root/B1_validation" \
  --data-root "$workspace_root/alfworld_data" \
  --python "$python_bin"
