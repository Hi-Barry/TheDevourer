"""TheDevourer — manifest.json 格式校验器

验证模块声明的必填字段、版本号格式、依赖声明完整性。
"""
import re
from pathlib import Path
from typing import Optional

from core.logger import get_logger

logger = get_logger()

# ── 必填字段 ──────────────────────────────────────
REQUIRED_TOP_LEVEL = {"name", "version", "min_core_version", "entry_points", "hooks"}
REQUIRED_ENTRY_POINTS = {"classes", "functions"}
REQUIRED_HOOKS = {"on_load", "on_unload"}

# ── 版本号正则（semver） ──────────────────────────
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")

# ── 模块名正则 ────────────────────────────────────
MODULE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

# ── 校验结果 ──────────────────────────────────────


class ValidationResult:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


# ── 校验函数 ──────────────────────────────────────

def validate_manifest(manifest: dict, file_path: str = "") -> ValidationResult:
    """校验 manifest.json 字典，返回 ValidationResult"""
    result = ValidationResult()

    # 1. 顶层必填字段
    for field in REQUIRED_TOP_LEVEL:
        if field not in manifest:
            result.add_error(f"缺少必填字段: {field}")

    if not result.is_valid:
        return result

    # 2. 模块名
    name = manifest.get("name", "")
    if not MODULE_NAME_PATTERN.match(name):
        result.add_error(
            f"模块名格式错误: {name!r}（需小写字母开头，仅含 a-z0-9_）"
        )

    # 3. 版本号格式
    version = manifest.get("version", "")
    if not SEMVER_PATTERN.match(version):
        result.add_error(
            f"版本号格式错误: {version!r}（需语义化版本号 x.y.z）"
        )

    # 4. min_core_version
    min_core = manifest.get("min_core_version", "")
    if not SEMVER_PATTERN.match(min_core):
        result.add_error(
            f"min_core_version 格式错误: {min_core!r}（需语义化版本号 x.y.z）"
        )

    # 5. entry_points
    ep = manifest.get("entry_points", {})
    for field in REQUIRED_ENTRY_POINTS:
        if field not in ep:
            result.add_warning(f"entry_points 缺少 {field}（非强制但推荐）")

    # 6. hooks
    hooks = manifest.get("hooks", {})
    for field in REQUIRED_HOOKS:
        if field not in hooks:
            result.add_error(f"hooks 缺少必填项: {field}")
        elif not isinstance(hooks.get(field), str) or not hooks[field]:
            result.add_error(f"hooks.{field} 必须是非空字符串")

    # 7. dependencies 格式
    deps = manifest.get("dependencies", {})
    if not isinstance(deps, dict):
        result.add_error("dependencies 必须是字典")
    else:
        # core deps 必须是列表
        core_deps = deps.get("core", [])
        if not isinstance(core_deps, list):
            result.add_error("dependencies.core 必须是列表")
        # modules deps 格式校验
        mod_deps = deps.get("modules", [])
        if isinstance(mod_deps, list):
            for dep in mod_deps:
                if not isinstance(dep, str) or ">=" not in dep:
                    result.add_warning(
                        f"模块依赖格式建议: {dep!r}（推荐格式 name>=version）"
                    )

    # 8. 重复检测（entry_point 同名警告）
    if ep:
        all_ep_names = []
        for ep_type in ("classes", "functions"):
            items = ep.get(ep_type, [])
            if isinstance(items, list):
                for item in items:
                    if item in all_ep_names:
                        result.add_warning(f"entry_point 重复: {item}")
                    all_ep_names.append(item)

    # 9. resources 格式（必须为列表）
    resources = manifest.get("resources", [])
    if not isinstance(resources, list):
        result.add_error("resources 必须是列表")

    return result


def validate_manifest_file(file_path: str) -> ValidationResult:
    """从文件加载并校验 manifest.json"""
    import json
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        result = ValidationResult()
        result.add_error(f"JSON 解析失败: {e}")
        return result
    except FileNotFoundError:
        result = ValidationResult()
        result.add_error(f"文件不存在: {file_path}")
        return result

    result = validate_manifest(data, file_path)
    return result
