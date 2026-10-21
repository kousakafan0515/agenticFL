#!/usr/bin/env bash
set -euo pipefail

workspace_root=/mnt/d/skillMAS
secrets_root="$workspace_root/SkillAdaptor_MAS_collaboration_20260901"
python_bin=/home/user0515/miniconda3/envs/stage3-alfworld/bin/python
run_root="$workspace_root/stage2_local_v10/runs/two_local_global3_20261018_r1"
seed_root="$workspace_root/stage2_local_v10/runs/imported_v9_b0_to_b1_20261018_r1"
logs="$run_root/logs"

source "$secrets_root/scripts/load_secrets.sh" "$secrets_root/secrets/.env" >/dev/null
: "${DASHSCOPE_API_KEY:?DASHSCOPE_API_KEY is missing}"
: "${STAGE3_AGGREGATION_API_KEY:?DeepSeek official API key is missing}"
export LOCAL_EVOLUTION_API_KEY="$STAGE3_AGGREGATION_API_KEY"
export LOCAL_EVOLUTION_BASE_URL="$STAGE3_AGGREGATION_BASE_URL"
export LOCAL_EVOLUTION_MODEL=deepseek-flash
export STAGE3_AGGREGATION_MODEL=deepseek-flash
export PYTHONPATH="$workspace_root${PYTHONPATH:+:$PYTHONPATH}"
cd "$workspace_root"

"$python_bin" - <<'PY'
import hashlib, json
from pathlib import Path
root = Path('/mnt/d/skillMAS/stage2_local_v10/runs/two_local_global3_20261018_r1')
audit = json.loads((root / 'D122_resume_audit.json').read_text(encoding='utf-8-sig'))
for row in audit['entries']:
    path = root / row['relative_path']
    if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
        raise SystemExit(f"D122 frozen evidence changed: {row['relative_path']}")
state = json.loads((root / 'controller_state.json').read_text(encoding='utf-8'))
if state.get('status') != 'failed' or state.get('current_step') != 'local_2':
    raise SystemExit('D122 expected frozen failed local_2 controller')
print('D122 frozen prefixes, training, checkpoint and attempts verified')
PY

for client in A C; do
  if [[ -e "$logs/D122_client_${client}.stdout.log" || -e "$logs/D122_client_${client}.stderr.log" ]]; then
    printf '%s\n' "D122 resume log already exists for $client" >&2
    exit 1
  fi
done

"$python_bin" -m stage2_local_v9.scripts.run_client_a_phase \
  --phase training --generation 2 \
  --manifest "$workspace_root/stage2_local_v10/artifacts/manifests/client_a_generation_01.json" \
  --bank "$seed_root/client_A/B1_skillbank.json" \
  --output-root "$run_root/locals/B2/client_A/training" \
  --data-root "$workspace_root/alfworld_data" --python "$python_bin" \
  --max-control-retries 12 --resume-partial \
  --resume-order-reference "$seed_root/client_A/B0_training/result.json" \
  >"$logs/D122_client_A.stdout.log" 2>"$logs/D122_client_A.stderr.log" &
pid_a=$!

"$python_bin" -m stage2_local_v9.scripts.run_client_c_phase \
  --phase training --generation 2 \
  --manifest "$workspace_root/stage2_local_v10/artifacts/manifests/client_c_generation_01.json" \
  --bank "$seed_root/client_C/B1_skillbank.json" \
  --output-root "$run_root/locals/B2/client_C/training" \
  --data-root "$workspace_root/alfworld_data" --python "$python_bin" \
  --resume-partial \
  --resume-order-reference "$seed_root/client_C/B0_training/result.json" \
  >"$logs/D122_client_C.stdout.log" 2>"$logs/D122_client_C.stderr.log" &
pid_c=$!

status_a=0
status_c=0
wait "$pid_a" || status_a=$?
wait "$pid_c" || status_c=$?
if [[ "$status_a" -ne 0 || "$status_c" -ne 0 ]]; then
  printf 'D122 phase resume failed: A=%s C=%s\n' "$status_a" "$status_c" >&2
  exit 1
fi

for client in A C; do
  "$python_bin" - "$run_root/locals/B2/client_${client}/training/summary.json" <<'PY'
import json, sys
value = json.load(open(sys.argv[1], encoding='utf-8'))
if any(value.get(k) != v for k, v in {'status':'complete','task_count':134,'phase':'training','generation':2,'api_clean':True}.items()):
    raise SystemExit(f'invalid completed resumed training: {sys.argv[1]}')
PY
done

exec bash "$workspace_root/stage2_local_v10/scripts/run_two_local_to_global3_with_secrets.sh" --resume
