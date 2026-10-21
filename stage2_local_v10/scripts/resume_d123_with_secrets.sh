#!/usr/bin/env bash
set -euo pipefail

workspace_root=/mnt/d/skillMAS
run_root="$workspace_root/stage2_local_v10/runs/two_local_global3_20261018_r1"
python_bin=/home/user0515/miniconda3/envs/stage3-alfworld/bin/python

"$python_bin" - "$run_root" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
audit = json.loads((root / 'D123_resume_audit.json').read_text(encoding='utf-8-sig'))
for item in audit['files']:
    path = root / item['path']
    if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
        raise SystemExit(f"D123 frozen file changed: {item['path']}")
state = json.loads((root / 'controller_state.json').read_text(encoding='utf-8'))
if state.get('status') != 'failed' or state.get('current_step') != 'local_2':
    raise SystemExit('D123 requires failed local_2 controller')
for client in 'ABC':
    summary = json.loads((root / 'locals' / 'B2' / f'client_{client}' / 'training' / 'summary.json').read_text(encoding='utf-8'))
    if any(summary.get(key) != value for key, value in {'status':'complete', 'task_count':134, 'api_clean':True, 'phase':'training', 'generation':2}.items()):
        raise SystemExit(f'D123 incomplete B2 training for client {client}')
print('D123 frozen evidence and complete B2 training verified', flush=True)
PY

exec bash "$workspace_root/stage2_local_v10/scripts/run_two_local_to_global3_with_secrets.sh" --resume
