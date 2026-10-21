"""Run the frozen v6 Client-A phase under the v9 experiment identity."""

from stage2_local_v9.scripts.overlay import execute


if __name__ == "__main__":
    execute("run_client_a_phase", __file__)
