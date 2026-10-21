#!/usr/bin/env bash
set -u -o pipefail

client=${1:?client A, B, or C is required}
mode=${2:-fresh}
case "$client" in A|B|C) ;; *) exit 2 ;; esac
case "$mode" in fresh|resume) ;; *) exit 2 ;; esac

workspace_root=/mnt/d/skillMAS
python_bin=/home/user0515/miniconda3/envs/stage3-alfworld/bin/python
secrets_root="$workspace_root/SkillAdaptor_MAS_collaboration_20260901"
validation_root="$workspace_root/stage3_2_role_agnostic_semantic_merge/runs/v9_global2_client_validation_20261015_r1"
run_base="$workspace_root/stage3_2_role_agnostic_semantic_merge/runs/v9_global2_to_local_b3_20261015_r1"
lower=$(printf '%s' "$client" | tr '[:upper:]' '[:lower:]')

source "$secrets_root/scripts/load_secrets.sh" "$secrets_root/secrets/.env" >/dev/null
: "${DASHSCOPE_API_KEY:?DASHSCOPE_API_KEY is missing}"
export LOCAL_EVOLUTION_MODEL=deepseek-flash
export PYTHONPATH="$workspace_root${PYTHONPATH:+:$PYTHONPATH}"
cd "$workspace_root"

resume_args=()
if [[ "$mode" == resume ]]; then resume_args+=(--resume); fi

"$python_bin" -m stage3_2_role_agnostic_semantic_merge.run_global2_to_local_b3 \
  --client "$client" \
  --run-root "$run_base/client_${client}" \
  --parent-bank "$validation_root/client_${client}/replacement_skillbank.json" \
  --global2-validation-summary "$validation_root/client_${client}/validation/summary.json" \
  --manifest "$workspace_root/stage2_local_v9/artifacts/manifests/client_${lower}_generation_01.json" \
  --data-root "$workspace_root/alfworld_data" \
  --python "$python_bin" \
  "${resume_args[@]}"
