#!/usr/bin/env bash
set -euo pipefail

workspace_root=/mnt/d/skillMAS
run_root="$workspace_root/stage2_local_v10/runs/two_local_global3_20261018_r1"
validation_root="$run_root/globals/Global2/validation"
reference_root="$run_root/globals/Global1/validation"
python_bin=/home/user0515/miniconda3/envs/stage3-alfworld/bin/python
secrets_root="$workspace_root/SkillAdaptor_MAS_collaboration_20260901"

source "$secrets_root/scripts/load_secrets.sh" "$secrets_root/secrets/.env" >/dev/null
: "${DASHSCOPE_API_KEY:?DASHSCOPE_API_KEY is missing}"
export PYTHONPATH="$workspace_root${PYTHONPATH:+:$PYTHONPATH}"
cd "$workspace_root"

"$python_bin" -m stage2_local_v10.scripts.audit_global2_resume \
  --run-root "$run_root" --audit-output "$run_root/D125_global2_resume_audit.json" \
  >"$run_root/D125_global2_resume_audit.stdout.json"

"$python_bin" - "$run_root" <<'PY'
import hashlib
import json
import shutil
import sys
from pathlib import Path

root = Path(sys.argv[1])
audit = json.loads((root / 'D125_global2_resume_audit.json').read_text(encoding='utf-8'))
snapshot = root / 'D125_frozen_prefixes'
if snapshot.exists():
    raise SystemExit('D125 frozen prefix snapshot already exists')
for client, row in audit['clients'].items():
    source = root / 'globals' / 'Global2' / 'validation' / f'client_{client}' / 'validation'
    dest = snapshot / f'client_{client}'
    dest.mkdir(parents=True)
    for name in ('result.json', 'source_lock.json', 'command.json', 'process.log'):
        original = source / name
        if original.exists():
            shutil.copy2(original, dest / name)
    for name, expected in (('result.json', row['prefix_result_file_sha256']), ('source_lock.json', row['source_lock_file_sha256'])):
        actual = 'sha256:' + hashlib.sha256((dest / name).read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(f'Client {client} frozen {name} copy hash mismatch')
print('D125 original Global2 prefixes preserved and hash-verified', flush=True)
PY

for client in A B C; do
  for stream in stdout stderr; do
    if [[ -e "$run_root/D125_client_${client}.${stream}.log" ]]; then
      printf 'D125 client %s %s log already exists\n' "$client" "$stream" >&2
      exit 1
    fi
  done
done

pids=()
for client in A B C; do
  lower=${client,,}
  extra=()
  if [[ "$client" == A ]]; then extra=(--max-control-retries 12); fi
  "$python_bin" -m "stage2_local_v9.scripts.run_client_${lower}_phase" \
    --phase validation --generation 4 \
    --manifest "$workspace_root/stage2_local_v10/artifacts/manifests/client_${lower}_generation_01.json" \
    --bank "$validation_root/client_${client}/replacement_skillbank.json" \
    --output-root "$validation_root/client_${client}/validation" \
    --data-root "$workspace_root/alfworld_data" --python "$python_bin" \
    --resume-partial \
    --resume-order-reference "$reference_root/client_${client}/validation/result.json" \
    "${extra[@]}" \
    >"$run_root/D125_client_${client}.stdout.log" \
    2>"$run_root/D125_client_${client}.stderr.log" &
  pids+=("$!")
done

failed=0
for i in 0 1 2; do
  if ! wait "${pids[$i]}"; then failed=1; fi
done
if [[ "$failed" -ne 0 ]]; then
  printf '%s\n' 'D125 Global2 phase resume failed; preserve all segments and do not resume top controller' >&2
  exit 1
fi

"$python_bin" - "$validation_root" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
for client in 'ABC':
    path = root / f'client_{client}' / 'validation' / 'summary.json'
    summary = json.loads(path.read_text(encoding='utf-8'))
    expected = {'status':'complete', 'client':client, 'phase':'validation', 'generation':4, 'task_count':134, 'api_clean':True}
    if any(summary.get(key) != value for key, value in expected.items()):
        raise SystemExit(f'Client {client} Global2 validation incomplete after resume')
print('D125 three Global2 validations complete and API-clean', flush=True)
PY

exec bash "$workspace_root/stage2_local_v10/scripts/run_two_local_to_global3_with_secrets.sh" --resume
