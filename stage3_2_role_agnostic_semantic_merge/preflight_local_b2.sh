#!/usr/bin/env bash
set -euo pipefail
workspace_root=/mnt/d/skillMAS
python_bin=/home/user0515/miniconda3/envs/stage3-alfworld/bin/python
secrets_root="$workspace_root/SkillAdaptor_MAS_collaboration_20260901"
parent_root="$workspace_root/stage3_2_role_agnostic_semantic_merge/runs/v9_b1_round1_client_validation_20261014_r1"
preflight_root="$workspace_root/stage3_2_role_agnostic_semantic_merge/runs/v9_global1_to_local_b2_20261014_r1_preflight"
source "$secrets_root/scripts/load_secrets.sh" "$secrets_root/secrets/.env" >/dev/null
: "${DASHSCOPE_API_KEY:?DASHSCOPE_API_KEY is missing}"
export LOCAL_EVOLUTION_MODEL=deepseek-flash
export PYTHONPATH="$workspace_root${PYTHONPATH:+:$PYTHONPATH}"
cd "$workspace_root"
"$python_bin" -c 'from originalFL.round1_evolver import _local_evolution_config; import json; c=_local_evolution_config(); d=c.descriptor(); print(json.dumps(d,ensure_ascii=False)); assert c.model=="deepseek-flash" and d["provider"]=="deepseek_official" and d["endpoint_origin"]=="https://api.deepseek.com"; print("teacher_identity=PASS")'
for client in A B C; do
  lower=$(printf '%s' "$client" | tr '[:upper:]' '[:lower:]')
  "$python_bin" -m "stage2_local_v9.scripts.run_client_${lower}_phase" --phase training --generation 2 --manifest "$workspace_root/stage2_local_v9/artifacts/manifests/client_${lower}_generation_01.json" --bank "$parent_root/client_${client}/replacement_skillbank.json" --output-root "$preflight_root/client_${client}" --data-root "$workspace_root/alfworld_data" --python "$python_bin" --dry-run
done
