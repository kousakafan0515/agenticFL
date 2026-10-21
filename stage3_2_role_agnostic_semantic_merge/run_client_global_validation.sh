#!/usr/bin/env bash
set -u -o pipefail

client=${1:?client A, B, or C is required}
case "$client" in
  A|B|C) ;;
  *) printf '%s\n' "unsupported client: $client" >&2; exit 2 ;;
esac

workspace_root=/mnt/d/skillMAS
secrets_root="$workspace_root/SkillAdaptor_MAS_collaboration_20260901"
python_bin=/home/user0515/miniconda3/envs/stage3-alfworld/bin/python
run_root="$workspace_root/stage3_2_role_agnostic_semantic_merge/runs/v9_b1_round1_client_validation_20261014_r1"
client_root="$run_root/client_${client}"
validation_root="$client_root/validation"
status_path="$client_root/background_status.json"
lower=$(printf '%s' "$client" | tr '[:upper:]' '[:lower:]')
module="stage2_local_v9.scripts.run_client_${lower}_phase"
manifest="$workspace_root/stage2_local_v9/artifacts/manifests/client_${lower}_generation_01.json"
bank="$client_root/replacement_skillbank.json"

write_status() {
  local state=$1
  local exit_code=$2
  local detail=$3
  "$python_bin" -c 'import datetime,json,pathlib,sys; p=pathlib.Path(sys.argv[1]); old=json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}; value={**old,"status":sys.argv[2],"exit_code":int(sys.argv[3]),"detail":sys.argv[4],"updated_at":datetime.datetime.now(datetime.timezone.utc).isoformat()}; t=p.with_suffix(p.suffix+".tmp"); t.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); t.replace(p)' "$status_path" "$state" "$exit_code" "$detail"
}

if [[ ! -f "$bank" ]]; then
  printf '%s\n' "replacement bank is missing: $bank" >&2
  exit 1
fi
if [[ -e "$validation_root" || -e "$status_path" ]]; then
  printf '%s\n' "refusing to overwrite existing Client $client validation state" >&2
  exit 1
fi

source "$secrets_root/scripts/load_secrets.sh" "$secrets_root/secrets/.env" >/dev/null
: "${DASHSCOPE_API_KEY:?DASHSCOPE_API_KEY is missing}"
export PYTHONPATH="$workspace_root${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p "$client_root"
write_status running -1 "Client $client frozen 134-task validation is running"

cd "$workspace_root"
set +e
"$python_bin" -m "$module" \
  --phase validation \
  --generation 1 \
  --manifest "$manifest" \
  --bank "$bank" \
  --output-root "$validation_root" \
  --data-root "$workspace_root/alfworld_data" \
  --python "$python_bin"
exit_code=$?
set -e

if [[ $exit_code -eq 0 && -f "$validation_root/summary.json" ]]; then
  write_status complete 0 "Client $client validation completed"
else
  write_status failed "$exit_code" "Client $client validation stopped; inspect stderr and validation/process.log"
fi
exit "$exit_code"
