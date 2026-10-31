"""Migration-only generator for the static V12 compatibility runners.

This script is not a V12 runtime dependency.  It records exactly how the
audited v6 -> v9 overlays were materialized during the V12 migration.
"""

from __future__ import annotations

from pathlib import Path

from stage2_local_v10.bootstrap_b1 import v10_source
from stage2_local_v9.scripts.client_overlay import transformed_phase_source
from stage2_local_v9.scripts.overlay import transformed_source


ROOT = Path(__file__).resolve().parents[2]
V12 = ROOT / "stage2_local_v12"


def internalize(source: str) -> str:
    replacements = {
        "from client_code.skillbank_loader import ":
            "from stage2_local_v12.clients.skillbank_loader import ",
        "from originalFL.banks import ":
            "from stage2_local_v12.runtime.banks import ",
        "from originalFL.paired_evaluator import ":
            "from stage2_local_v12.runtime.paired_evaluator import ",
        "from originalFL.runtime_adapter import ":
            "from stage2_local_v12.runtime.runtime_adapter import ",
        "from originalFL.training_runner import ":
            "from stage2_local_v12.runtime.training_runner import ",
        "from originalFL.round1_evolver import ":
            "from stage2_local_v12.evolution.teacher_api import ",
        "from stage2_local_v9.capacity_policy import ":
            "from stage2_local_v12.evolution.capacity_policy import ",
        "client_code/": "stage2_local_v12/clients/",
        "stage2_local_v9/artifacts/manifests/":
            "stage2_local_v12/assets/manifests/",
    }
    for old, new in replacements.items():
        source = source.replace(old, new)
    forbidden = ("from originalFL", "from client_code", "from stage2_local_v9")
    if any(item in source for item in forbidden):
        raise RuntimeError("materialized runner retained an external project import")
    return source


def write(relative: str, source: str) -> None:
    path = V12 / relative
    path.write_text(internalize(source), encoding="utf-8", newline="\n")


def main() -> None:
    write("runtime/phase_runner_a.py", transformed_source("run_client_a_phase"))
    write("runtime/phase_runner_b.py", transformed_phase_source("B"))
    write("runtime/phase_runner_c.py", transformed_phase_source("C"))
    write("evolution/bootstrap_bank_a.py", v10_source("A"))
    write("evolution/bootstrap_bank_b.py", v10_source("B"))
    write("evolution/bootstrap_bank_c.py", v10_source("C"))


if __name__ == "__main__":
    main()
