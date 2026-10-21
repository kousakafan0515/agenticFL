from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from stage2_local_v11.sharded_phase import merge_results, partition, prepare, run, shard_command


class ShardedPhaseTests(unittest.TestCase):
    def test_134_one_task_shards_cover_order_exactly_once(self) -> None:
        tasks = [f"task_{i:03d}" for i in range(134)]
        for count in (2, 4, 8, 134):
            shards = partition(tasks, count)
            self.assertEqual(len(shards), count)
            self.assertEqual([task for shard in shards for task in shard], tasks)
            self.assertTrue(all(shards))
        self.assertTrue(all(len(shard) == 1 for shard in partition(tasks, 134)))

    def test_command_isolates_output_and_preserves_client_options(self) -> None:
        args = Namespace(client="A", python=Path("python"), data_root=Path("data"), api_key_env="TEST_KEY")
        directory = Path("out/shards/shard_001")
        command = shard_command(args, ["pick_and_place_simple-Foo/trial_1"], None, directory)
        self.assertIn("--max-control-retries", command)
        self.assertIn("--send-disable-thinking", command)
        self.assertIn("--skill-mode", command)
        self.assertIn(str(directory / "result.json"), command)
        self.assertEqual(command.count("--only-game-file"), 1)
        args.client = "B"
        self.assertNotIn("--max-control-retries", shard_command(args, ["pick_and_place_simple-Foo/trial_1"], None, directory))

    def test_merge_checks_all_tasks_and_api_markers_before_complete_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = Namespace(output_root=root, phase="validation", generation=0, client="A")
            tasks = [f"task_{i:03d}" for i in range(134)]
            pieces = partition(tasks, 4)
            for i, shard in enumerate(pieces, 1):
                directory = root / "shards" / f"shard_{i:03d}"
                directory.mkdir(parents=True)
                episodes = [{"game_file": f"/data/json_2.1.1/train/{task}/game.tw-pddl", "success": True} for task in shard]
                (directory / "result.json").write_text(json.dumps({"protocol": "test", "model": "qwen3.6-flash", "episodes": episodes}), encoding="utf-8")
            lock = {"experiment_id": "stage2-local-v11-test"}
            summary = merge_results(args, pieces, lock)
            self.assertEqual(summary["task_count"], 134)
            self.assertEqual(summary["success_count"], 134)
            self.assertEqual(len(json.loads((root / "result.json").read_text(encoding="utf-8"))["episodes"]), 134)
            corrupted = root / "shards" / "shard_004" / "result.json"
            value = json.loads(corrupted.read_text(encoding="utf-8"))
            value["episodes"][0]["model_output"] = "APIError"
            corrupted.write_text(json.dumps(value), encoding="utf-8")
            (root / "summary.json").unlink()
            with self.assertRaisesRegex(RuntimeError, "API failure marker"):
                merge_results(args, pieces, lock)
            self.assertFalse((root / "summary.json").exists())

    def test_prepare_rejects_non_v11_manifest_and_bad_shard_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            tasks = [f"{prefix}-Foo/trial_{i:03d}" for prefix in (
                "pick_and_place_simple", "look_at_obj_in_light", "pick_clean_then_place_in_recep",
                "pick_heat_then_place_in_recep", "pick_cool_then_place_in_recep", "pick_two_obj_and_place")
                for i in range(1, 23)]
            tasks.extend(["pick_and_place_simple-Foo/trial_023", "look_at_obj_in_light-Foo/trial_023"])
            path.write_text(json.dumps({"experiment_id": "stage2-local-v10-test", "manifest_content_hash": "test", "validation": {"tasks": tasks}}), encoding="utf-8")
            args = Namespace(manifest=path, phase="validation", generation=0, bank=None, client="A", shards=134, max_workers=134, start_stagger_seconds=1)
            with self.assertRaisesRegex(RuntimeError, "V11"):
                prepare(args)
            value = json.loads(path.read_text(encoding="utf-8"))
            value["experiment_id"] = "stage2-local-v11-test"
            path.write_text(json.dumps(value), encoding="utf-8")
            args.shards = 135
            with self.assertRaisesRegex(RuntimeError, "shards <= pilot-tasks <= 134"):
                prepare(args)

    def test_pilot_is_evenly_sampled_and_cannot_be_formal_complete(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            args = Namespace(manifest=root / "artifacts/manifests/client_a_generation_01.json",
                             phase="validation", generation=0, bank=None, client="A", shards=8,
                             max_workers=8, pilot_tasks=8, start_stagger_seconds=1,
                             output_root=Path(tmp) / "output", execute=False)
            lock, pieces, _ = prepare(args)
            self.assertEqual(len({task.split("-", 1)[0] for piece in pieces for task in piece}), 6)
            self.assertEqual(lock["pilot_task_count"], 8)
            self.assertEqual(run(args)["paid_api_calls"], 0)
            self.assertFalse(args.output_root.exists())


if __name__ == "__main__":
    unittest.main()
