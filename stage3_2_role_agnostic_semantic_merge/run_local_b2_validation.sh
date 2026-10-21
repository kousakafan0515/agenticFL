#!/usr/bin/env bash
set -u -o pipefail

client=${1:?client A, B, or C is required}
mode=${2:-fresh}
case "$client" in A|B|C) ;; *) exit 2 ;; esac
case "$mode" in fresh|resume) ;; *) exit 2 ;; esac
workspace_root=/mnt/d/skillMAS
python_bin=/home/user0515/miniconda3/envs/stage3-alfworld/bin/python
secrets_root="$workspace_root/SkillAdaptor_MAS_collaboration_20260901"
run_root="$workspace_root/stage3_2_role_agnostic_semantic_merge/runs/v9_local_b2_client_validation_20261014_r1"
client_root="$run_root/client_${client}"
validation_root="$client_root/validation"
status_path="$client_root/background_status.json"
lower=$(printf '%s' "$client" | tr '[:upper:]' '[:lower:]')
module="stage2_local_v9.scripts.run_client_${lower}_phase"
manifest="$workspace_root/stage2_local_v9/artifacts/manifests/client_${lower}_generation_01.json"
bank="$client_root/runtime_skillbank.json"
case "$client" in
  A) order_reference="$workspace_root/stage2_local_v9/runs/client_a_generation_01_20261013_r1/B0_validation/result.json" ;;
  B) order_reference="$workspace_root/stage2_local_v9/runs/client_b_generation_01_20261013_r3/B0_validation/result.json" ;;
  C) order_reference="$workspace_root/stage2_local_v9/runs/client_c_generation_01_20261013_r3/B0_validation/result.json" ;;
esac

write_status() {
  "$python_bin" -c 'import datetime,json,pathlib,sys; p=pathlib.Path(sys.argv[1]); old=json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}; value={**old,"status":sys.argv[2],"exit_code":int(sys.argv[3]),"detail":sys.argv[4],"updated_at":datetime.datetime.now(datetime.timezone.utc).isoformat()}; t=p.with_suffix(p.suffix+".tmp"); t.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); t.replace(p)' "$status_path" "$1" "$2" "$3"
}

if [[ ! -f "$bank" ]]; then
  printf '%s\n' "missing runtime bank for Client $client" >&2
  exit 1
fi
if [[ "$mode" == fresh && ( -e "$validation_root" || -e "$status_path" ) ]]; then
  printf '%s\n' "refusing to overwrite Client $client validation state" >&2
  exit 1
fi
if [[ "$mode" == resume && ( ! -f "$validation_root/result.json" || -f "$validation_root/summary.json" || ! -f "$order_reference" ) ]]; then
  printf '%s\n' "Client $client resume requires partial result, no summary, and frozen order reference" >&2
  exit 1
fi
source "$secrets_root/scripts/load_secrets.sh" "$secrets_root/secrets/.env" >/dev/null
: "${DASHSCOPE_API_KEY:?DASHSCOPE_API_KEY is missing}"
export PYTHONPATH="$workspace_root${PYTHONPATH:+:$PYTHONPATH}"
write_status running -1 "Client $client local B2 frozen 134-task validation is running"
extra_args=()
if [[ "$client" == A ]]; then extra_args+=(--max-control-retries 12); fi
if [[ "$mode" == resume ]]; then
  extra_args+=(--resume-partial --resume-order-reference "$order_reference")
fi
cd "$workspace_root"
set +e
"$python_bin" -m "$module" --phase validation --generation 2 --manifest "$manifest" --bank "$bank" --output-root "$validation_root" --data-root "$workspace_root/alfworld_data" --python "$python_bin" "${extra_args[@]}"
exit_code=$?
set -e
if [[ $exit_code -eq 0 && -f "$validation_root/summary.json" ]]; then
  write_status complete 0 "Client $client local B2 validation completed"
else
  write_status failed "$exit_code" "Client $client local B2 validation stopped"
fi
exit "$exit_code"
