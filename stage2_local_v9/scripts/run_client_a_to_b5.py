"""Run the frozen v6 B2--B5 controller with v9 paths and capacity policy."""

from stage2_local_v9.scripts.overlay import execute


if __name__ == "__main__":
    execute("run_client_a_to_b5", __file__)
