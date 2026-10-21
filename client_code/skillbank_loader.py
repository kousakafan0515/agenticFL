"""Validated, role-isolated SkillBank loading and prompt injection.

The loader is deliberately read-only.  A server Delta must first be applied to
a copy of the frozen Stage2 bank by a separate materializer.  This module then
loads either the frozen Local bank or that materialized Personalized bank,
checks its manifest and the pre-registered injection capacity, and renders a
stable role-specific system-prompt suffix.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


STANDARD_RENDERER_VERSION = "stage3.skill_prompt.v1"
COLLABORATOR_RENDERER_VERSION = "collaborator.skill_prompt.v1"
BLIND_GLOBAL_RENDERER_VERSION = "stage3_1.blind_global_prompt.v1"
DEFAULT_RENDERER_VERSION = COLLABORATOR_RENDERER_VERSION
SUPPORTED_RENDERER_VERSIONS = (
    COLLABORATOR_RENDERER_VERSION,
    BLIND_GLOBAL_RENDERER_VERSION,
    STANDARD_RENDERER_VERSION,
)
CAPACITY_SCHEMA_VERSION = "stage3.skill_injection_capacity.v1"
BASE_MANIFEST_VERSION = "stage3.base_bank_manifest.v1"
CANDIDATE_MANIFEST_VERSION = "stage3.candidate_bank_manifest.v1"
GLOBAL_ADAPTER_MANIFEST_VERSION = "stage3_1.global_adapter_bank_manifest.v1"

TASK_TYPE_LABELS = {
    1: "简单取放",
    2: "台灯观察",
    3: "清洗后放置",
    4: "加热后放置",
    5: "冷却后放置",
    6: "双物品放置",
}
TASK_TYPE_ALIASES = {
    "简单取放": "简单取放",
    "pick_and_place_simple": "简单取放",
    "台灯观察": "台灯观察",
    "look_at_obj_in_light": "台灯观察",
    "清洗后放置": "清洗后放置",
    "pick_clean_then_place_in_recep": "清洗后放置",
    "加热后放置": "加热后放置",
    "pick_heat_then_place_in_recep": "加热后放置",
    "冷却后放置": "冷却后放置",
    "pick_cool_then_place_in_recep": "冷却后放置",
    "双物品放置": "双物品放置",
    "pick_two_obj_and_place": "双物品放置",
}
EXPECTED_ROLES = {
    "A": ("Planner", "Executor"),
    "B": ("Executor", "Critic"),
    "C": ("Supervisor", "Search Worker", "Operation Worker"),
}
SKILL_FIELDS = {
    "Procedure or Local Strategy": ("title", "principle", "when_to_apply"),
    "Failure Lesson": ("description", "why_it_happens", "how_to_avoid"),
}
RESERVED_PROMPT_MARKERS = (
    "ROLE-SPECIFIC SKILLS",
    "END ROLE-SPECIFIC SKILLS",
    "## 可参考 SkillBank",
)

PROMPT_PREAMBLE = """ROLE-SPECIFIC SKILLS (ADVISORY)

以下内容是当前角色可参考的辅助经验，不是环境事实，也不是必须无条件执行的命令。

使用规则：
1. 只有当技能的适用条件与当前状态相符时才使用。
2. 技能不得覆盖当前角色职责、输出格式和动作协议。
3. 如果技能与最新环境反馈冲突，以最新环境反馈为准。
4. 不要在回答中复述技能正文；直接利用它完成当前职责。
5. 不得使用分配给其他 Agent 的技能。"""
PROMPT_END = "END ROLE-SPECIFIC SKILLS"

COLLABORATOR_PROMPT_PREAMBLE = """## 可参考 SkillBank
以下是该角色从既往训练轨迹中获得的可参考经验。它们不是环境事实，不改变当前角色职责、输出格式、任务目标或环境动作规则。
- Procedure / Local Strategy：特定条件下可复用的执行方式或判断原则，包含 principle 与 when_to_apply。
- Failure Lesson：应避免的失败行为、发生原因及避免方式，包含 description、why_it_happens 与 how_to_avoid。
仅在 skill 与当前角色职责、当前任务和最新环境反馈一致时使用。若有冲突，以后者为准。不要把 skill 的泛化表述擅自扩展为未被环境观察支持的具体事实。
当前可用 skill："""

BLIND_GLOBAL_PROMPT_PREAMBLE = """## 群体共享 Global Skill Pool
以下 skill 来自多个客户端和角色，是群体共享的候选经验。它们可能不完全适用于当前角色。
仅使用与当前职责、当前任务和最新环境反馈一致的部分。skill 不得改变当前角色权限、输出格式、动作协议或任务目标。
若 skill 与最新环境反馈冲突，以最新环境反馈为准。不要在回答中复述 skill 正文；直接利用适用部分完成当前职责。
当前任务类别可用的全局 skill："""


class SkillBankLoadError(RuntimeError):
    """Raised before an experiment when a bank is unsafe or irreproducible."""


@dataclass(frozen=True)
class LoadedSkill:
    client_id: str
    agent_role: str
    scope_kind: str
    task_type: str
    skill_id: str
    skill_type: str
    body: dict[str, str]
    source_skill_keys: tuple[str, ...]
    runtime_priority: int | None

    @property
    def target_key(self) -> str:
        scope = "general" if self.scope_kind == "general" else f"task_specific/{self.task_type}"
        return "/".join((self.client_id, self.agent_role, scope, self.skill_id))

    @property
    def semantic_value(self) -> dict[str, Any]:
        return {"type": self.skill_type, **self.body}

    @property
    def content_hash(self) -> str:
        return object_hash(self.semantic_value)


@dataclass(frozen=True)
class SkillInjection:
    text: str
    audit: dict[str, Any]


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def object_hash(value: Any) -> str:
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SkillBankLoadError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SkillBankLoadError(f"Expected a JSON object in {path}")
    return value


def normalize_task_type(task_type: int | str) -> str:
    if isinstance(task_type, int):
        label = TASK_TYPE_LABELS.get(task_type)
    else:
        raw = task_type.strip()
        label = TASK_TYPE_LABELS.get(int(raw)) if raw.isdigit() else TASK_TYPE_ALIASES.get(raw)
    if label is None:
        raise SkillBankLoadError(f"Unsupported ALFWorld task type {task_type!r}")
    return label


def normalized_text(value: str) -> str:
    return " ".join(value.replace("\r", "\n").split())


def natural_key(value: str) -> tuple[Any, ...]:
    return tuple(int(part) if part.isdigit() else part for part in re.split(r"(\d+)", value))


def _semantic_skill(raw: dict[str, Any], context: str) -> tuple[str, dict[str, str]]:
    skill_type = raw.get("type")
    fields = SKILL_FIELDS.get(skill_type)
    if fields is None:
        raise SkillBankLoadError(f"{context}: unsupported skill type {skill_type!r}")
    body: dict[str, str] = {}
    for field in fields:
        value = raw.get(field)
        if not isinstance(value, str) or not value.strip():
            raise SkillBankLoadError(f"{context}: missing or empty field {field!r}")
        if any(marker in value for marker in RESERVED_PROMPT_MARKERS):
            raise SkillBankLoadError(f"{context}: field {field!r} contains a reserved prompt marker")
        body[field] = value.strip()
    wrong_fields = set(SKILL_FIELDS["Failure Lesson"] if skill_type != "Failure Lesson" else SKILL_FIELDS["Procedure or Local Strategy"])
    mixed = sorted(field for field in wrong_fields if field in raw)
    if mixed:
        raise SkillBankLoadError(f"{context}: fields from the other skill type are not allowed: {mixed}")
    return skill_type, body


def _bank_client_id(bank_doc: dict[str, Any]) -> str:
    value = bank_doc.get("target_client") or bank_doc.get("source_client")
    if not isinstance(value, str) or not value:
        raise SkillBankLoadError("SkillBank requires source_client or target_client")
    return value


def parse_bank(bank_doc: dict[str, Any], expected_client_id: str) -> list[LoadedSkill]:
    bank_client = _bank_client_id(bank_doc)
    if bank_client != expected_client_id:
        raise SkillBankLoadError(
            f"SkillBank belongs to client {bank_client!r}, expected {expected_client_id!r}"
        )
    expected_roles = set(EXPECTED_ROLES.get(expected_client_id, ()))
    if not expected_roles:
        raise SkillBankLoadError(f"Unsupported client id {expected_client_id!r}")
    active = bank_doc.get("active_skillbanks")
    if not isinstance(active, dict):
        raise SkillBankLoadError("SkillBank active_skillbanks must be an object")
    actual_roles = set(active)
    if actual_roles != expected_roles:
        raise SkillBankLoadError(
            f"Client {expected_client_id} role partitions mismatch; "
            f"expected={sorted(expected_roles)}, actual={sorted(actual_roles)}"
        )

    skills: list[LoadedSkill] = []
    for agent_role in EXPECTED_ROLES[expected_client_id]:
        role_bank = active[agent_role]
        if not isinstance(role_bank, dict):
            raise SkillBankLoadError(f"Role bank {agent_role!r} must be an object")
        general = role_bank.get("general", [])
        task_specific = role_bank.get("task_specific", {})
        if not isinstance(general, list) or not isinstance(task_specific, dict):
            raise SkillBankLoadError(f"Role bank {agent_role!r} has malformed partitions")
        collections: list[tuple[str, str, list[Any]]] = [("general", "", general)]
        for task_label, values in sorted(task_specific.items()):
            if task_label not in TASK_TYPE_ALIASES or TASK_TYPE_ALIASES[task_label] != task_label:
                raise SkillBankLoadError(
                    f"Role {agent_role!r} has unsupported task-specific label {task_label!r}"
                )
            if not isinstance(values, list):
                raise SkillBankLoadError(
                    f"Role {agent_role!r} task-specific partition {task_label!r} must be a list"
                )
            collections.append(("task_specific", task_label, values))

        role_ids: set[str] = set()
        for scope_kind, task_label, values in collections:
            for index, raw in enumerate(values, start=1):
                context = f"{expected_client_id}/{agent_role}/{scope_kind}/{task_label or '-'}#{index}"
                if not isinstance(raw, dict):
                    raise SkillBankLoadError(f"{context}: skill must be an object")
                skill_id = raw.get("skill_id")
                if not isinstance(skill_id, str) or not skill_id:
                    raise SkillBankLoadError(f"{context}: missing skill_id")
                if skill_id in role_ids:
                    raise SkillBankLoadError(
                        f"Client {expected_client_id} role {agent_role!r} repeats skill_id {skill_id!r}"
                    )
                role_ids.add(skill_id)
                skill_type, body = _semantic_skill(raw, context)
                priority = raw.get("runtime_priority")
                if priority is not None and (not isinstance(priority, int) or isinstance(priority, bool)):
                    raise SkillBankLoadError(f"{context}: runtime_priority must be an integer")
                source_keys = raw.get("source_skill_keys")
                scope_path = "general" if scope_kind == "general" else f"task_specific/{task_label}"
                default_key = "/".join((expected_client_id, agent_role, scope_path, skill_id))
                if source_keys is None:
                    normalized_sources = (default_key,)
                elif (
                    not isinstance(source_keys, list)
                    or not source_keys
                    or any(not isinstance(item, str) or not item for item in source_keys)
                ):
                    raise SkillBankLoadError(f"{context}: source_skill_keys must be a non-empty string list")
                else:
                    normalized_sources = tuple(sorted(set(source_keys)))
                skills.append(
                    LoadedSkill(
                        client_id=expected_client_id,
                        agent_role=agent_role,
                        scope_kind=scope_kind,
                        task_type=task_label,
                        skill_id=skill_id,
                        skill_type=skill_type,
                        body=body,
                        source_skill_keys=normalized_sources,
                        runtime_priority=priority,
                    )
                )
    return skills


def normalized_bank_state(skills: Iterable[LoadedSkill]) -> list[dict[str, Any]]:
    rows = [
        {
            "agent_role": skill.agent_role,
            "scope": skill.scope_kind,
            "task_type": skill.task_type or None,
            "skill_id": skill.skill_id,
            "skill": skill.semantic_value,
        }
        for skill in skills
    ]
    return sorted(
        rows,
        key=lambda row: (
            row["agent_role"],
            row["scope"],
            row["task_type"] or "",
            row["skill_id"],
        ),
    )


def bank_hash(skills: Iterable[LoadedSkill]) -> str:
    return object_hash(normalized_bank_state(skills))


def _manifest_values(manifest: dict[str, Any]) -> tuple[str, str, str]:
    version = manifest.get("manifest_schema_version")
    if version == BASE_MANIFEST_VERSION:
        client_id = manifest.get("source_client")
        exact_hash = (manifest.get("source_files") or {}).get("bank_file_sha256")
        semantic_hash = manifest.get("frozen_bank_hash")
    elif version == CANDIDATE_MANIFEST_VERSION:
        client_id = manifest.get("target_client")
        exact_hash = manifest.get("candidate_bank_file_sha256")
        semantic_hash = manifest.get("candidate_bank_hash")
    elif version == GLOBAL_ADAPTER_MANIFEST_VERSION:
        client_id = manifest.get("target_client")
        exact_hash = manifest.get("global_adapter_bank_file_sha256")
        semantic_hash = manifest.get("global_adapter_bank_hash")
    else:
        raise SkillBankLoadError(f"Unsupported SkillBank manifest version {version!r}")
    if not all(isinstance(value, str) and value for value in (client_id, exact_hash, semantic_hash)):
        raise SkillBankLoadError(f"Manifest {version!r} is missing client or hash fields")
    return client_id, exact_hash, semantic_hash


def _render_standard_skill(display_id: str, skill: LoadedSkill) -> str:
    body = {key: normalized_text(value) for key, value in skill.body.items()}
    if skill.skill_type == "Procedure or Local Strategy":
        return "\n".join(
            (
                f"【技能 {display_id}｜流程/局部策略】",
                f"名称：{body['title']}",
                f"适用条件：{body['when_to_apply']}",
                f"执行原则：{body['principle']}",
            )
        )
    return "\n".join(
        (
            f"【技能 {display_id}｜失败教训】",
            f"应避免的问题：{body['description']}",
            f"产生原因：{body['why_it_happens']}",
            f"规避方法：{body['how_to_avoid']}",
        )
    )


def _render_collaborator_skill(skill: LoadedSkill) -> str:
    body = {key: normalized_text(value) for key, value in skill.body.items()}
    scope = (
        "General"
        if skill.scope_kind == "general"
        else f"Task-specific: {skill.task_type}"
    )
    lines = [f"[{scope} | {skill.skill_id} | {skill.skill_type}]"]
    lines.extend(f"{field}: {body[field]}" for field in SKILL_FIELDS[skill.skill_type])
    return "\n".join(lines)


class SkillBankLoader:
    """A validated bank plus deterministic role/task rendering policy."""

    def __init__(
        self,
        *,
        mode: str,
        expected_client_id: str,
        bank_path: Path | None = None,
        manifest_path: Path | None = None,
        capacity_profile_path: Path | None = None,
        enforce_capacity: bool = True,
        renderer_version: str | None = None,
    ) -> None:
        if mode not in {"none", "local", "personalized", "global"}:
            raise SkillBankLoadError(f"Unsupported skill mode {mode!r}")
        self.mode = mode
        self.client_id = expected_client_id
        self.bank_path = bank_path.resolve() if bank_path else None
        self.manifest_path = manifest_path.resolve() if manifest_path else None
        self.capacity_profile_path = capacity_profile_path.resolve() if capacity_profile_path else None
        self.manifest_version: str | None = None
        self.candidate_base_hash: str | None = None
        self.delta_hash: str | None = None
        self.skills: list[LoadedSkill] = []
        self.bank_hash = object_hash([])
        self.capacity_profile: dict[str, Any] | None = None
        self.capacity_profile_hash: str | None = None
        self.capacity_policy: dict[str, Any] | None = None
        if renderer_version is not None and renderer_version not in SUPPORTED_RENDERER_VERSIONS:
            raise SkillBankLoadError(f"Unsupported prompt renderer {renderer_version!r}")
        self.renderer_version = renderer_version or DEFAULT_RENDERER_VERSION
        self._renderer_explicit = renderer_version is not None

        if mode == "none":
            if any(path is not None for path in (bank_path, manifest_path, capacity_profile_path)):
                raise SkillBankLoadError("skill mode 'none' must not receive bank, manifest, or capacity files")
            return
        if bank_path is None or manifest_path is None or (enforce_capacity and capacity_profile_path is None):
            raise SkillBankLoadError(
                "local/personalized/global mode requires --skillbank, --skill-manifest, and "
                "--skill-capacity-profile"
            )

        bank_doc = load_json(self.bank_path)
        manifest = load_json(self.manifest_path)
        self.manifest_version = str(manifest.get("manifest_schema_version"))
        if mode == "local" and self.manifest_version != BASE_MANIFEST_VERSION:
            raise SkillBankLoadError(f"local mode requires manifest {BASE_MANIFEST_VERSION}")
        if mode == "personalized" and self.manifest_version != CANDIDATE_MANIFEST_VERSION:
            raise SkillBankLoadError(
                f"personalized mode requires manifest {CANDIDATE_MANIFEST_VERSION}"
            )
        if mode == "global" and self.manifest_version != GLOBAL_ADAPTER_MANIFEST_VERSION:
            raise SkillBankLoadError(
                f"global mode requires manifest {GLOBAL_ADAPTER_MANIFEST_VERSION}"
            )
        if mode == "global":
            global_pool_hash = manifest.get("global_pool_hash")
            if not isinstance(global_pool_hash, str) or not re.fullmatch(
                r"sha256:[0-9a-f]{64}", global_pool_hash
            ):
                raise SkillBankLoadError("Global manifest requires a valid global_pool_hash")
        if mode == "personalized":
            self.candidate_base_hash = manifest.get("base_bank_hash")
            self.delta_hash = manifest.get("delta_hash")
            for field, value in (
                ("base_bank_hash", self.candidate_base_hash),
                ("delta_hash", self.delta_hash),
            ):
                if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
                    raise SkillBankLoadError(
                        f"Personalized manifest requires a valid {field}"
                    )
            self.capacity_policy = manifest.get("capacity_policy")
            if not isinstance(self.capacity_policy, dict):
                raise SkillBankLoadError(
                    "Personalized manifest requires capacity_policy"
                )
        manifest_client, expected_file_hash, expected_bank_hash = _manifest_values(manifest)
        if manifest_client != expected_client_id:
            raise SkillBankLoadError(
                f"Manifest belongs to client {manifest_client!r}, expected {expected_client_id!r}"
            )
        actual_file_hash = file_hash(self.bank_path)
        if actual_file_hash != expected_file_hash:
            raise SkillBankLoadError(
                f"SkillBank file hash mismatch: expected {expected_file_hash}, got {actual_file_hash}"
            )
        self.skills = parse_bank(bank_doc, expected_client_id)
        self.bank_hash = bank_hash(self.skills)
        if self.bank_hash != expected_bank_hash:
            raise SkillBankLoadError(
                f"SkillBank semantic hash mismatch: expected {expected_bank_hash}, got {self.bank_hash}"
            )
        if mode == "personalized":
            self._validate_personalized_capacity_policy()

        if capacity_profile_path is not None:
            self.capacity_profile = load_json(self.capacity_profile_path)
            self.capacity_profile_hash = file_hash(self.capacity_profile_path)
            profile_renderer = self.capacity_profile.get("renderer_version")
            if not self._renderer_explicit and profile_renderer in SUPPORTED_RENDERER_VERSIONS:
                self.renderer_version = str(profile_renderer)
            self._validate_capacity_profile()

    def _validate_personalized_capacity_policy(self) -> None:
        assert self.capacity_policy is not None
        policy = self.capacity_policy
        policy_name = policy.get("policy")
        if policy_name not in {
            "local_bank_plus_bounded_additions",
            "validation_driven_dynamic_capacity",
        }:
            raise SkillBankLoadError("Unsupported personalized capacity policy")
        baseline = policy.get("baseline_active_skill_count")
        candidate = policy.get("candidate_active_skill_count")
        added = policy.get("actual_added_skill_count")
        if any(
            not isinstance(value, int) or isinstance(value, bool)
            for value in (baseline, candidate, added)
        ):
            raise SkillBankLoadError("Personalized capacity counts must be integers")
        if added < 0:
            raise SkillBankLoadError("Personalized actual_added_skill_count cannot be negative")
        if policy_name == "local_bank_plus_bounded_additions":
            maximum = policy.get("max_added_skills")
            if not isinstance(maximum, int) or isinstance(maximum, bool):
                raise SkillBankLoadError("Personalized max_added_skills must be an integer")
            if maximum < 0 or maximum > 3:
                raise SkillBankLoadError("Personalized max_added_skills must be between 0 and 3")
            if added > maximum:
                raise SkillBankLoadError("Personalized candidate exceeds the allowed added skills")
        else:
            if policy.get("selection_policy") != "validation_driven_forward_selection":
                raise SkillBankLoadError("Dynamic capacity requires validation-driven selection")
            growth_budget = policy.get("max_rendered_character_growth_per_role_task")
            if (
                not isinstance(growth_budget, int)
                or isinstance(growth_budget, bool)
                or growth_budget < 0
                or growth_budget > 20000
            ):
                raise SkillBankLoadError(
                    "Dynamic capacity requires a character growth budget between 0 and 20000"
                )
        if candidate != baseline + added:
            raise SkillBankLoadError("Personalized capacity counts are internally inconsistent")
        if candidate != len(self.skills):
            raise SkillBankLoadError(
                "Personalized manifest candidate_active_skill_count does not match the bank"
            )

    def _validate_capacity_profile(self) -> None:
        assert self.capacity_profile is not None
        profile = self.capacity_profile
        if profile.get("profile_schema_version") != CAPACITY_SCHEMA_VERSION:
            raise SkillBankLoadError(
                f"Unsupported capacity profile version {profile.get('profile_schema_version')!r}"
            )
        if profile.get("renderer_version") != self.renderer_version:
            raise SkillBankLoadError("Capacity profile was built with a different prompt renderer")
        if profile.get("source_client") != self.client_id:
            raise SkillBankLoadError("Capacity profile belongs to a different client")
        if not isinstance(profile.get("limits"), dict):
            raise SkillBankLoadError("Capacity profile limits must be an object")
        if self.mode == "local" and profile.get("source_local_bank_hash") != self.bank_hash:
            raise SkillBankLoadError("Local bank does not match the capacity profile source bank")
        if (
            self.mode == "personalized"
            and profile.get("source_local_bank_hash") != self.candidate_base_hash
        ):
            raise SkillBankLoadError(
                "Personalized bank was not derived from the Local bank locked by the capacity profile"
            )
        if (
            self.mode == "global"
            and profile.get("source_local_bank_hash") != self.bank_hash
        ):
            raise SkillBankLoadError(
                "Global adapter bank does not match the exact locked capacity profile"
            )

    @property
    def enabled(self) -> bool:
        return self.mode != "none"

    def descriptor(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "enabled": self.enabled,
            "client_id": self.client_id,
            "renderer_version": self.renderer_version,
            "skillbank_hash": self.bank_hash if self.enabled else None,
            "manifest_version": self.manifest_version,
            "candidate_base_bank_hash": self.candidate_base_hash,
            "delta_hash": self.delta_hash,
            "capacity_profile_sha256": self.capacity_profile_hash,
            "capacity_policy": self.capacity_policy,
        }

    def _eligible_skills(self, agent_role: str, task_label: str) -> list[LoadedSkill]:
        if agent_role not in EXPECTED_ROLES.get(self.client_id, ()):
            raise SkillBankLoadError(
                f"Role {agent_role!r} is not valid for client {self.client_id}"
            )
        eligible = [
            skill
            for skill in self.skills
            if skill.agent_role == agent_role
            and (skill.scope_kind == "general" or skill.task_type == task_label)
        ]
        eligible.sort(
            key=lambda skill: (
                0 if skill.scope_kind == "general" else 1,
                skill.runtime_priority if skill.runtime_priority is not None else 10**9,
                natural_key(skill.skill_id),
            )
        )
        deduplicated: list[LoadedSkill] = []
        merged_sources: dict[str, set[str]] = {}
        by_hash: dict[str, int] = {}
        for skill in eligible:
            content_hash = skill.content_hash
            if content_hash not in by_hash:
                by_hash[content_hash] = len(deduplicated)
                deduplicated.append(skill)
                merged_sources[content_hash] = set(skill.source_skill_keys)
            else:
                merged_sources[content_hash].update(skill.source_skill_keys)
        return [
            LoadedSkill(
                client_id=skill.client_id,
                agent_role=skill.agent_role,
                scope_kind=skill.scope_kind,
                task_type=skill.task_type,
                skill_id=skill.skill_id,
                skill_type=skill.skill_type,
                body=skill.body,
                source_skill_keys=tuple(sorted(merged_sources[skill.content_hash])),
                runtime_priority=skill.runtime_priority,
            )
            for skill in deduplicated
        ]

    def _render_unchecked(self, agent_role: str, task_label: str) -> SkillInjection:
        if not self.enabled:
            return SkillInjection(
                text="",
                audit={
                    "skill_mode": "none",
                    "skillbank_hash": None,
                    "task_type": task_label,
                    "agent_role": agent_role,
                    "injected_skill_keys": [],
                    "display_id_map": {},
                    "injected_skill_count": 0,
                    "injected_character_count": 0,
                    "renderer_version": self.renderer_version,
                },
            )
        skills = self._eligible_skills(agent_role, task_label)
        blocks: list[str] = []
        display_map: dict[str, Any] = {}
        target_keys: list[str] = []
        for index, skill in enumerate(skills, start=1):
            display_id = (
                skill.skill_id
                if self.renderer_version in {
                    COLLABORATOR_RENDERER_VERSION,
                    BLIND_GLOBAL_RENDERER_VERSION,
                }
                else f"S{index:02d}"
            )
            blocks.append(
                _render_collaborator_skill(skill)
                if self.renderer_version in {
                    COLLABORATOR_RENDERER_VERSION,
                    BLIND_GLOBAL_RENDERER_VERSION,
                }
                else _render_standard_skill(display_id, skill)
            )
            target_keys.append(skill.target_key)
            display_map[display_id] = {
                "target_skill_key": skill.target_key,
                "source_skill_keys": list(skill.source_skill_keys),
                "canonical_content_hash": skill.content_hash,
                "type": skill.skill_type,
                "scope": skill.scope_kind,
                "task_type": skill.task_type or None,
            }
        if not blocks:
            text = ""
        elif self.renderer_version == COLLABORATOR_RENDERER_VERSION:
            text = "\n".join((COLLABORATOR_PROMPT_PREAMBLE, *blocks))
        elif self.renderer_version == BLIND_GLOBAL_RENDERER_VERSION:
            text = "\n".join((BLIND_GLOBAL_PROMPT_PREAMBLE, *blocks))
        else:
            text = "\n\n".join((PROMPT_PREAMBLE, *blocks, PROMPT_END))
        return SkillInjection(
            text=text,
            audit={
                "skill_mode": self.mode,
                "skillbank_hash": self.bank_hash,
                "task_type": task_label,
                "agent_role": agent_role,
                "injected_skill_keys": target_keys,
                "display_id_map": display_map,
                "injected_skill_count": len(skills),
                "injected_character_count": len(text),
                "renderer_version": self.renderer_version,
            },
        )

    def render(self, agent_role: str, task_type: int | str) -> SkillInjection:
        task_label = normalize_task_type(task_type)
        injection = self._render_unchecked(agent_role, task_label)
        if not self.enabled or self.capacity_profile is None:
            return injection
        role_limits = self.capacity_profile["limits"].get(agent_role)
        limit = role_limits.get(task_label) if isinstance(role_limits, dict) else None
        if not isinstance(limit, dict):
            raise SkillBankLoadError(
                f"Capacity profile has no limit for {self.client_id}/{agent_role}/{task_label}"
            )
        required_count = limit.get("required_skill_count")
        max_characters = limit.get("max_rendered_characters")
        if not isinstance(required_count, int) or not isinstance(max_characters, int):
            raise SkillBankLoadError("Capacity profile count and character limits must be integers")
        actual_count = injection.audit["injected_skill_count"]
        actual_characters = injection.audit["injected_character_count"]
        policy_name = self.capacity_policy["policy"] if self.capacity_policy else None
        if actual_count != required_count:
            if self.mode != "personalized" or self.capacity_policy is None:
                raise SkillBankLoadError(
                    f"Injection count mismatch for {self.client_id}/{agent_role}/{task_label}: "
                    f"required {required_count}, got {actual_count}"
                )
            maximum = self.capacity_policy.get("max_added_skills")
            if actual_count < required_count or (
                policy_name == "local_bank_plus_bounded_additions"
                and actual_count > required_count + maximum
            ):
                raise SkillBankLoadError(
                    f"Personalized injection count outside the allowed range for "
                    f"{self.client_id}/{agent_role}/{task_label}: baseline {required_count}, "
                    f"got {actual_count}"
                )
        allowed_characters = max_characters
        if (
            self.mode == "personalized"
            and self.capacity_policy is not None
            and self.capacity_policy["policy"] == "validation_driven_dynamic_capacity"
        ):
            allowed_characters += self.capacity_policy[
                "max_rendered_character_growth_per_role_task"
            ]
        enforce_character_budget = self.mode == "local" or (
            self.mode == "personalized"
            and policy_name == "validation_driven_dynamic_capacity"
        )
        if enforce_character_budget and actual_characters > allowed_characters:
            raise SkillBankLoadError(
                f"Injection character budget exceeded for {self.client_id}/{agent_role}/{task_label}: "
                f"maximum {allowed_characters}, got {actual_characters}"
            )
        audit = dict(injection.audit)
        audit["capacity_check"] = {
            "passed": True,
            "baseline_skill_count": required_count,
            "allowed_skill_count_maximum": (
                required_count
                if self.mode == "local"
                else (
                    required_count + self.capacity_policy["max_added_skills"]
                    if policy_name == "local_bank_plus_bounded_additions"
                    else None
                )
            ),
            "baseline_rendered_characters": max_characters,
            "allowed_rendered_characters_maximum": allowed_characters,
            "actual_rendered_characters": actual_characters,
            "rendered_character_growth": max(0, actual_characters - max_characters),
        }
        return SkillInjection(text=injection.text, audit=audit)

    def augment_system_prompt(
        self, base_prompt: str, agent_role: str, task_type: int | str
    ) -> tuple[str, dict[str, Any]]:
        injection = self.render(agent_role, task_type)
        prompt = base_prompt if not injection.text else base_prompt.rstrip() + "\n\n" + injection.text
        return prompt, injection.audit


def build_capacity_profile(loader: SkillBankLoader) -> dict[str, Any]:
    if loader.mode not in {"local", "global"} or not loader.enabled:
        raise SkillBankLoadError(
            "Capacity profiles must be built from an enabled Local or Global loader"
        )
    limits: dict[str, dict[str, dict[str, int]]] = {}
    for role in EXPECTED_ROLES[loader.client_id]:
        limits[role] = {}
        for task_label in TASK_TYPE_LABELS.values():
            injection = loader._render_unchecked(role, task_label)
            limits[role][task_label] = {
                "required_skill_count": injection.audit["injected_skill_count"],
                "max_rendered_characters": injection.audit["injected_character_count"],
            }
    return {
        "profile_schema_version": CAPACITY_SCHEMA_VERSION,
        "renderer_version": loader.renderer_version,
        "source_client": loader.client_id,
        "source_local_bank_hash": loader.bank_hash,
        "limits": limits,
    }


def add_skill_loader_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--skill-mode",
        choices=("none", "local", "personalized", "global"),
        default="none",
        help=(
            "none disables skills; local loads the frozen Stage2 bank; personalized loads "
            "a materialized Stage3 candidate bank; global loads a Stage3.1 Blind Global adapter bank."
        ),
    )
    parser.add_argument("--skillbank", type=Path, default=None)
    parser.add_argument("--skill-manifest", type=Path, default=None)
    parser.add_argument("--skill-capacity-profile", type=Path, default=None)
    parser.add_argument(
        "--skill-renderer-version",
        choices=SUPPORTED_RENDERER_VERSIONS,
        default=None,
        help="Prompt renderer; when omitted, use the version locked by the capacity profile.",
    )


def loader_from_args(args: argparse.Namespace, expected_client_id: str) -> SkillBankLoader:
    try:
        return SkillBankLoader(
            mode=args.skill_mode,
            expected_client_id=expected_client_id,
            bank_path=args.skillbank,
            manifest_path=args.skill_manifest,
            capacity_profile_path=args.skill_capacity_profile,
            renderer_version=getattr(args, "skill_renderer_version", None),
        )
    except SkillBankLoadError as exc:
        raise SystemExit(f"SkillBank Loader configuration error: {exc}") from exc


def _build_profile_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Build a locked Stage3 skill injection capacity profile")
    parser.add_argument("--client-id", choices=tuple(EXPECTED_ROLES), required=True)
    parser.add_argument("--skillbank", type=Path, required=True)
    parser.add_argument("--skill-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--renderer-version",
        choices=SUPPORTED_RENDERER_VERSIONS,
        default=DEFAULT_RENDERER_VERSION,
    )
    args = parser.parse_args(argv)
    try:
        loader = SkillBankLoader(
            mode="local",
            expected_client_id=args.client_id,
            bank_path=args.skillbank,
            manifest_path=args.skill_manifest,
            enforce_capacity=False,
            renderer_version=args.renderer_version,
        )
        profile = build_capacity_profile(loader)
    except SkillBankLoadError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} for Client {args.client_id} ({loader.bank_hash}).")
    return 0


def main(argv: list[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    if not values or values[0] != "build-profile":
        print("Usage: python -m client_code.skillbank_loader build-profile [options]", file=sys.stderr)
        return 2
    return _build_profile_cli(values[1:])


if __name__ == "__main__":
    raise SystemExit(main())
