"""TheDevourer — ModuleLoader 模块加载器

扫描 plugins/ 目录 → 校验 manifest → 拓扑排序 → importlib 动态加载 → 注册入口点。
支持 .zip 和目录两种模块形态。
"""
import sys
import zipfile
import json
import importlib
import importlib.util
import tempfile
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Optional, Callable

from core.logger import get_logger
from core.manifest_validator import validate_manifest

logger = get_logger()


# ── 模块数据类 ────────────────────────────────────

@dataclass
class Module:
    """已加载的模块"""
    name: str
    version: str
    path: str                     # 模块原始路径（zip 或目录）
    manifest: dict
    entry_points: dict[str, Any] = field(default_factory=dict)
    instance: Optional[object] = None        # importlib 模块对象

    @property
    def version_tuple(self) -> tuple[int, ...]:
        return tuple(int(x) for x in self.version.split("."))


# ── 模块加载器 ────────────────────────────────────

class ModuleLoader:
    """模块加载器"""

    def __init__(self):
        self._loaded: dict[str, Module] = {}
        self._scan_paths: list[str] = []
        self._temp_dirs: list[str] = []  # zip 解压临时目录

    # ── 扫描 ──────────────────────────────────────

    def scan(self, path: str) -> list[dict]:
        """
        扫描路径下的所有可用模块，返回候选列表。
        支持目录和 .zip 两种形态。
        """
        candidates = []
        scan_dir = Path(path)
        if not scan_dir.exists():
            logger.warning(f"扫描路径不存在: {path}")
            return []

        for entry in sorted(scan_dir.iterdir()):
            manifest = None
            module_path = None

            # 目录形态
            if entry.is_dir():
                mf = entry / "manifest.json"
                if mf.exists():
                    manifest = self._read_manifest(str(mf))
                    module_path = str(entry)

            # ZIP 形态
            elif entry.suffix == ".zip":
                manifest = self._read_manifest_from_zip(str(entry))
                if manifest:
                    module_path = str(entry)

            if manifest:
                candidates.append({
                    "manifest": manifest,
                    "path": module_path,
                    "name": manifest.get("name", ""),
                    "version": manifest.get("version", "0.0.0"),
                })

        return candidates

    # ── 加载 ──────────────────────────────────────

    def load_all(self, path: str) -> dict[str, Module]:
        """加载指定路径下的全部模块（按依赖拓扑排序）"""
        candidates = self.scan(path)
        if not candidates:
            logger.info(f"在 {path} 下未发现模块")
            return {}

        # 拓扑排序
        sorted_candidates = self._topological_sort(candidates)
        logger.info(f"模块加载顺序: {[c['name'] for c in sorted_candidates]}")

        result: dict[str, Module] = {}
        for c in sorted_candidates:
            try:
                mod = self._load_single(c)
                result[mod.name] = mod
                self._loaded[mod.name] = mod
                logger.info(f"模块加载成功: {mod.name} v{mod.version}")
            except Exception as e:
                logger.warning(f"模块加载失败: {c['name']} v{c['version']} — {e}")

        return result

    def load(self, name_or_path: str) -> Module:
        """加载单个模块（路径或名称）。已加载时返回缓存的实例（幂等）。"""
        # 先检查是否已按名称加载
        if name_or_path in self._loaded:
            return self._loaded[name_or_path]

        path = Path(name_or_path)
        if path.exists():
            # 按路径加载
            manifest = None
            actual_path = ""
            if path.is_dir():
                manifest = self._read_manifest(str(path / "manifest.json"))
                actual_path = str(path)
            elif path.suffix == ".zip":
                manifest = self._read_manifest_from_zip(str(path))
                actual_path = str(path)
            else:
                raise ValueError(f"不支持的模块路径: {name_or_path}")

            if not manifest:
                raise ValueError(f"无法读取 manifest: {name_or_path}")

            mod_name = manifest.get("name", "")
            # 加载前检查模块是否已存在
            if mod_name and mod_name in self._loaded:
                return self._loaded[mod_name]

            mod = self._load_single({"manifest": manifest, "path": actual_path, "name": mod_name})
            self._loaded[mod.name] = mod
            return mod

        raise ValueError(f"模块未加载或路径不存在: {name_or_path}")

    def unload(self, name: str) -> bool:
        """卸载模块"""
        if name not in self._loaded:
            logger.warning(f"模块未加载，无法卸载: {name}")
            return False

        mod = self._loaded[name]

        # 执行 on_unload hook
        hook_name = mod.manifest.get("hooks", {}).get("on_unload", "")
        if hook_name and mod.instance:
            try:
                hook_fn = getattr(mod.instance, hook_name, None)
                if hook_fn:
                    hook_fn()
            except Exception as e:
                logger.warning(f"模块卸载 hook 失败: {name} — {e}")

        # 从注册表移除
        del self._loaded[name]
        logger.info(f"模块已卸载: {name}")
        return True

    def get(self, name: str) -> Optional[Module]:
        """获取已加载模块"""
        return self._loaded.get(name)

    def module_list(self) -> list[str]:
        """已加载模块列表"""
        return sorted(self._loaded.keys())

    def get_entry_point(self, module_name: str, ep_type: str, key: str) -> Any:
        """获取模块的某个入口点"""
        mod = self._loaded.get(module_name)
        if not mod:
            return None
        return mod.entry_points.get(f"{ep_type}.{key}")

    # ── 内部方法 ──────────────────────────────────

    def _load_single(self, candidate: dict) -> Module:
        """加载单个候选模块"""
        manifest = candidate["manifest"]
        mod_path = candidate["path"]

        # 校验 manifest
        vr = validate_manifest(manifest)
        if not vr.is_valid:
            raise ValueError(f"manifest 校验失败: {vr.errors}")

        name = manifest["name"]
        version = manifest.get("version", "0.0.0")

        # 处理 ZIP → 解压到临时目录
        actual_path = mod_path
        if mod_path and mod_path.endswith(".zip"):
            tmp_dir = tempfile.mkdtemp(prefix=f"mod_{name}_")
            self._temp_dirs.append(tmp_dir)
            with zipfile.ZipFile(mod_path, "r") as zf:
                zf.extractall(tmp_dir)
            actual_path = tmp_dir

        # 注入路径
        if actual_path not in sys.path:
            sys.path.insert(0, actual_path)

        # importlib 动态加载
        spec = importlib.util.spec_from_file_location(
            name,
            str(Path(actual_path) / "__init__.py"),
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"模块 {name} __init__.py 不存在")

        instance = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(instance)

        # 收集 entry_points
        ep = manifest.get("entry_points", {})
        entry_points: dict[str, Any] = {}
        for ep_type in ("classes", "functions"):
            for item in ep.get(ep_type, []):
                obj = getattr(instance, item, None)
                if obj:
                    entry_points[f"{ep_type}.{item}"] = obj

        # 执行 on_load hook
        hook_name = manifest.get("hooks", {}).get("on_load", "")
        if hook_name:
            hook_fn = getattr(instance, hook_name, None)
            if hook_fn:
                try:
                    hook_fn()
                except Exception as e:
                    logger.warning(f"模块 {name} on_load hook 失败: {e}")

        return Module(
            name=name,
            version=version,
            path=mod_path or "",
            manifest=manifest,
            entry_points=entry_points,
            instance=instance,
        )

    # ── Manifest 读取 ─────────────────────────────

    @staticmethod
    def _read_manifest(path: str) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _read_manifest_from_zip(zip_path: str) -> Optional[dict]:
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                if "manifest.json" in zf.namelist():
                    return json.loads(zf.read("manifest.json").decode("utf-8"))
        except Exception:
            pass
        return None

    # ── 拓扑排序 ──────────────────────────────────

    def _topological_sort(self, candidates: list[dict]) -> list[dict]:
        """按模块依赖关系拓扑排序（依赖者排在依赖项之后）"""
        # 构建名称→候选索引
        by_name = {c["name"]: c for c in candidates}

        # 解析依赖
        graph: dict[str, list[str]] = {}
        for c in candidates:
            deps = c["manifest"].get("dependencies", {}).get("modules", [])
            graph[c["name"]] = []
            for dep in deps:
                # 解析 "name>=version" 格式
                dep_name = dep.split(">=")[0].split("==")[0].strip()
                if dep_name in by_name:
                    graph[c["name"]].append(dep_name)

        # Kahn 拓扑排序
        in_degree = {name: 0 for name in graph}
        for name, deps in graph.items():
            in_degree[name] += len(deps)  # 依赖越多，入度越高，越晚加载

        queue = [name for name, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            name = queue.pop(0)
            if name in by_name:
                result.append(by_name[name])
            for neighbor in graph.get(name, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 检查环
        if len(result) != len(candidates):
            loaded_names = {c["name"] for c in result}
            missing = [c["name"] for c in candidates if c["name"] not in loaded_names]
            logger.warning(f"模块依赖环或缺失: {missing}")

            # 追加未排序的模块
            for c in candidates:
                if c["name"] not in loaded_names:
                    result.append(c)

        return result

    # ── 清理 ──────────────────────────────────────

    def cleanup(self) -> None:
        """卸载全部模块 + 清理临时目录"""
        for name in list(self._loaded.keys()):
            self.unload(name)
        for td in self._temp_dirs:
            shutil.rmtree(td, ignore_errors=True)
        self._temp_dirs.clear()
