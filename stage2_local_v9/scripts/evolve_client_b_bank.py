"""Generate one v9 Client-B bank with the role-specific no-capacity Teacher."""

from stage2_local_v9.scripts.client_overlay import execute_source, transformed_evolver_source


if __name__ == "__main__":
    execute_source(transformed_evolver_source("B"), __file__)
