#!/usr/bin/env bash
set -euo pipefail

workspace_root=/mnt/d/skillMAS
secrets_root="$workspace_root/SkillAdaptor_MAS_collaboration_20260901"
python_bin=/home/user0515/miniconda3/envs/stage3-alfworld/bin/python
run_root="$workspace_root/stage2_local_v9/runs/client_c_generation_01_20261013_r3"
evidence="$run_root/B0_training/evidence.json"
parent_bank="$workspace_root/stage2_local_v9/templates/client_c_B0_empty_skillbank.json"
checkpoint="$run_root/B1_teacher_record.checkpoint.json"
checkpoint_backup="$run_root/B1_teacher_record.checkpoint.pre_resume_20261014_r1.json"
bank="$run_root/B1_skillbank.json"
record="$run_root/B1_teacher_record.json"
order_reference="$workspace_root/stage2_local_v9/runs/client_a_generation_01_20261013_r1/B0_validation/result.json"
teacher_stdout="$run_root/B1_teacher.recovery_20261014_r1.stdout.log"
teacher_stderr="$run_root/B1_teacher.recovery_20261014_r1.stderr.log"
controller_stdout="$run_root/B1_validation.recovery_20261014_r1.stdout.log"
controller_stderr="$run_root/B1_validation.recovery_20261014_r1.stderr.log"

check_hash() {
  local expected=$1
  local path=$2
  local actual
  actual=$(sha256sum "$path" | awk '{print $1}')
  if [[ "$actual" != "$expected" ]]; then
    printf '%s\n' "SHA-256 mismatch for $path" >&2
    exit 1
  fi
}

check_hash e84d79f2f483ceb8f5bcd999fde4c52a0f4e04509604d9ea1b307ad5257f7878 "$run_root/B0_validation/result.json"
check_hash 9661fa7534164d3252e4f1461cd8e82292b2cb402e4dedf2818208891efe2fb7 "$run_root/B0_validation/summary.json"
check_hash f570c9a97f454a1cf4bde26931ff86bca821bce43acf118ba78fe136fd127c25 "$run_root/B0_training/result.json"
check_hash 06c61944edc5d355e6df9c7f5bb1299b019d712108152186e4e6e04f05ddee48 "$run_root/B0_training/summary.json"
check_hash 3036feffb86454acbd3fa269740200c6c5b80cb1f24ea28f143beb943bc05772 "$evidence"
check_hash 3bad9760ffeea8d190a6091c4a4f4e463f2749378f787191ff71760e5f20af80 "$checkpoint"

for path in "$checkpoint_backup" "$bank" "$record" "$teacher_stdout" "$teacher_stderr" "$controller_stdout" "$controller_stderr"; do
  if [[ -e "$path" ]]; then
    printf '%s\n' "Refusing to overwrite $path" >&2
    exit 1
  fi
done

cp --no-clobber "$checkpoint" "$checkpoint_backup"

source "$secrets_root/scripts/load_secrets.sh" "$secrets_root/secrets/.env" >/dev/null
: "${DASHSCOPE_API_KEY:?DASHSCOPE_API_KEY is missing}"
: "${STAGE3_AGGREGATION_API_KEY:?DeepSeek official API key is missing}"
: "${STAGE3_AGGREGATION_BASE_URL:?DeepSeek official base URL is missing}"
test "${STAGE3_AGGREGATION_BASE_URL%/}" = "https://api.deepseek.com"
export LOCAL_EVOLUTION_API_KEY="$STAGE3_AGGREGATION_API_KEY"
export LOCAL_EVOLUTION_BASE_URL="$STAGE3_AGGREGATION_BASE_URL"
export LOCAL_EVOLUTION_MODEL=deepseek-flash
export PYTHONPATH="$workspace_root${PYTHONPATH:+:$PYTHONPATH}"
cd "$workspace_root"

"$python_bin" -m stage2_local_v9.scripts.evolve_client_c_bank \
  --generation 1 \
  --teacher-model deepseek-flash \
  --teacher-provider deepseek_official \
  --evidence "$evidence" \
  --parent-bank "$parent_bank" \
  --output "$bank" \
  --record-output "$record" \
  --max-tokens 16000 \
  >"$teacher_stdout" 2>"$teacher_stderr"

"$python_bin" -m stage2_local_v9.scripts.run_client_to_b1 \
  --client C \
  --run-root "$run_root" \
  --data-root "$workspace_root/alfworld_data" \
  --python "$python_bin" \
  --resume \
  --resume-order-reference "$order_reference" \
  >"$controller_stdout" 2>"$controller_stderr"
