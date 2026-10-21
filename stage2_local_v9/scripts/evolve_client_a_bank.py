"""Run the v6 Teacher pipeline with only the 14-skill capacity removed."""

from pathlib import Path

from stage2_local_v9.scripts.overlay import execute


if __name__ == "__main__":
    pause_marker = Path(__file__).resolve().parents[1] / "TEACHER_PAUSED"
    if pause_marker.exists():
        raise SystemExit(f"v9 Teacher is paused by {pause_marker}")
    execute("evolve_client_a_bank", __file__)
