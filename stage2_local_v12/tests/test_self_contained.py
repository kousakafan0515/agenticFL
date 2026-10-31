from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path

from stage2_local_v12.orchestration.import_v9_b1 import BUNDLED_SEED, verify_import
from stage2_local_v12.orchestration.materialize_assets import materialize


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIRECTORIES = ("clients", "runtime", "evolution", "federation", "orchestration", "scripts")
FORBIDDEN_ROOTS = {
    "client_code", "originalFL", "stage2_local_v6", "stage2_local_v9",
    "stage2_local_v10", "stage3_federation", "stage3_2_role_agnostic_semantic_merge",
}


class SelfContainedTests(unittest.TestCase):
    def test_runtime_has_no_legacy_project_imports(self) -> None:
        violations: list[str] = []
        for directory in RUNTIME_DIRECTORIES:
            for path in (ROOT / directory).rglob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for node in ast.walk(tree):
                    names: list[str] = []
                    if isinstance(node, ast.Import):
                        names = [item.name for item in node.names]
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        names = [node.module]
                    for name in names:
                        if name.split(".", 1)[0] in FORBIDDEN_ROOTS:
                            violations.append(f"{path.relative_to(ROOT)} imports {name}")
        self.assertEqual(violations, [])

    def test_runtime_commands_do_not_launch_legacy_modules(self) -> None:
        forbidden = (
            '"-m", "stage2_local_v6', '"-m", "stage2_local_v9',
            '"-m", "stage2_local_v10', "stage2_local_v9.scripts.run_client_",
        )
        hits: list[str] = []
        for directory in RUNTIME_DIRECTORIES:
            for path in (ROOT / directory).rglob("*.py"):
                source = path.read_text(encoding="utf-8")
                if any(token in source for token in forbidden):
                    hits.append(str(path.relative_to(ROOT)))
        self.assertEqual(hits, [])

    def test_static_phase_runners_do_not_exec_source_overlays(self) -> None:
        for client in "abc":
            source = (ROOT / "runtime" / f"phase_runner_{client}.py").read_text(encoding="utf-8")
            self.assertNotIn("exec(compile(", source)
            self.assertIn("stage2_local_v12/clients/", source)

    def test_assets_and_bundled_seeds_are_frozen(self) -> None:
        checked = materialize(check=True)
        self.assertEqual(checked["status"], "checked")
        for client in "ABC":
            verified = verify_import(BUNDLED_SEED / f"client_{client}", client)
            self.assertEqual(verified["classification"], "imported_v9_seed_not_native_v10_B1")

    def test_source_manifest_covers_current_files(self) -> None:
        manifest_path = ROOT / "provenance" / "SOURCE_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        recorded = {row["path"]: row for row in manifest["files"]}
        actual = {
            path.relative_to(ROOT).as_posix(): path
            for path in ROOT.rglob("*")
            if path.is_file()
            and path != manifest_path
            and "__pycache__" not in path.parts
            and path.suffix != ".pyc"
        }
        self.assertEqual(set(recorded), set(actual))
        for relative, path in actual.items():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(recorded[relative]["sha256"], digest, relative)


if __name__ == "__main__":
    unittest.main()
