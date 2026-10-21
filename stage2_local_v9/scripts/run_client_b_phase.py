"""Run one frozen v9 Client-B phase."""

from stage2_local_v9.scripts.client_overlay import execute_source, transformed_phase_source


if __name__ == "__main__":
    execute_source(transformed_phase_source("B"), __file__)
