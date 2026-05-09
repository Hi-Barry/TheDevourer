"""TheDevourer — 模块独立打包工具

将 modules/{name} 打包为 outputs/{name}_v{version}.zip。
支持校验和生成、增量打包。
"""
import sys, os, json, zipfile, hashlib
from pathlib import Path


def pack_module(module_name: str, source_dir: str = None, output_dir: str = None) -> dict:
    """
    打包单个模块。
    source_dir: 模块源码根目录（默认 project/modules/{name})
    output_dir: 打包产物输出目录（默认 project/outputs)
    返回: {name, version, zip_path, sha256, files, size}
    """
    project_root = Path(__file__).resolve().parent.parent

    src = Path(source_dir) if source_dir else (project_root / "modules" / module_name)

    # 支持两种传参方式：
    # 1. source_dir 指向模块目录本身：直接使用
    # 2. source_dir 指向模块父目录：拼接 module_name
    if source_dir:
        if not (src / "manifest.json").exists():
            src = Path(source_dir) / module_name
    out = Path(output_dir) if output_dir else (project_root / "outputs")

    if not src.exists():
        raise FileNotFoundError(f"模块目录不存在: {src}")
    if not (src / "manifest.json").exists():
        raise FileNotFoundError(f"模块缺少 manifest.json: {src / 'manifest.json'}")

    # 读取 manifest
    manifest = json.loads((src / "manifest.json").read_text(encoding="utf-8"))
    version = manifest.get("version", "0.0.0")
    name = manifest.get("name", module_name)

    # 创建输出目录
    out.mkdir(parents=True, exist_ok=True)

    # 打包
    zip_name = f"{name}_v{version}.zip"
    zip_path = out / zip_name

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in src.rglob("*"):
            if file_path.is_file():
                # 排除不必要的文件
                rel = file_path.relative_to(src)
                if any(part.startswith("__pycache__") for part in rel.parts):
                    continue
                if file_path.suffix in (".pyc", ".pyo"):
                    continue
                zf.write(file_path, arcname=str(rel))

    # 生成校验和
    sha256 = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    sha_path = out / f"{zip_name}.sha256"
    sha_path.write_text(sha256, encoding="utf-8")

    # 统计打包文件
    files = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            files.append({"name": info.filename, "size": info.file_size})

    result = {
        "name": name,
        "version": version,
        "zip_path": str(zip_path),
        "sha256": sha256,
        "files": files,
        "file_count": len(files),
        "size_bytes": zip_path.stat().st_size,
    }
    return result


def pack_all(source_dir: str = None, output_dir: str = None) -> list[dict]:
    """打包全部模块"""
    project_root = Path(__file__).resolve().parent.parent
    src = Path(source_dir) if source_dir else (project_root / "modules")

    if not src.exists():
        raise FileNotFoundError(f"模块目录不存在: {src}")

    results = []
    for entry in sorted(src.iterdir()):
        if entry.is_dir() and (entry / "manifest.json").exists():
            try:
                result = pack_module(entry.name, source_dir=str(src), output_dir=output_dir)
                print(f"  ✓ {result['name']} v{result['version']} → {result['zip_path']} ({result['size_bytes']:,} bytes)")
                results.append(result)
            except Exception as e:
                print(f"  ✗ {entry.name}: {e}")
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TheDevourer 模块打包工具")
    parser.add_argument("module", nargs="?", help="模块名（留空=打包全部）")
    parser.add_argument("--output", "-o", help="输出目录（默认 outputs/）")
    parser.add_argument("--source", "-s", help="源码目录（默认 modules/）")
    args = parser.parse_args()

    if args.module:
        result = pack_module(args.module, source_dir=args.source, output_dir=args.output)
        print(f"\n✅ 打包完成: {result['name']} v{result['version']}")
        print(f"   路径: {result['zip_path']}")
        print(f"   大小: {result['size_bytes']:,} bytes")
        print(f"   文件: {result['file_count']} 个")
    else:
        results = pack_all(source_dir=args.source, output_dir=args.output)
        total_size = sum(r["size_bytes"] for r in results)
        print(f"\n✅ 打包 {len(results)} 个模块, 总大小 {total_size:,} bytes")
