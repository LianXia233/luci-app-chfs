#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""整理 chfs / luci-app-chfs 的构建产物，供 GitHub Release 发布。

三个子命令：

    stage     把单个 SDK 构建出的包重命名并归档到 <out>/<format>/<arch>/
    list     以 markdown 表格行打印已归档的包（用于 CI Job Summary）
    finalize 汇总全部归档目录，产出扁平资产 + SHA256SUMS + manifest.json + 发布说明

为什么要重命名
--------------
apk 的文件名格式是 <name>-<version>.apk，不含架构。三个架构的 job 会产出
完全同名的 chfs-3.1-r1.apk，直接上传到同一个 Release 会互相覆盖。
ipk 的 <name>_<version>_<arch>.ipk 虽含架构，但两种格式的命名风格不一致。
故统一规范为：

    apk: <name>-<version>_<arch>.apk
    ipk: <name>_<version>_<arch>.ipk

包管理器（apk / opkg）安装本地文件时按包内控制信息识别，不依赖文件名，
因此重命名不影响安装。

元数据读取策略
--------------
* apk  : 读包内 .PKGINFO（pkgname / pkgver / arch）。apk v2 在 gzip 段之后
         还拼接了数据段与签名段，故用 zlib 只解第一成员，避免尾部数据干扰。
* ipk  : 直接解析文件名。OpenWrt 24.10 起 ipk 的控制段可能是 zstd 压缩，
         依赖解包会引入额外模块依赖；而 ipk 的命名规范稳定，解析文件名更稳。
         解析失败时再尝试读 control 段，两者都失败才报错。
"""

import argparse
import hashlib
import io
import json
import os
import re
import sys
import tarfile
import zlib
from datetime import datetime, timezone

# 格式 -> 产出自哪个发行版的 SDK（用于发布说明与 manifest）
FORMAT_DIST = {
    "apk": "ImmortalWrt SNAPSHOT",
    "ipk": "OpenWrt 24.10.5",
}

# 架构无关包（LUCI_PKGARCH=all）在任何架构下内容一致，Release 中只保留一份
ARCH_ALL = ("all", "noarch")

# 注意 arch 段本身含下划线（x86_64 / aarch64_cortex-a53），故只有 version 段禁止下划线，
# 否则贪婪匹配会把 x86_64 切成 arch=64。
IPK_NAME_RE = re.compile(r"^(?P<name>[^_]+)_(?P<version>[^_]+)_(?P<arch>.+)\.ipk$")
# 文件名解析规则（仅在 .PKGINFO 失败时回退使用）：
#   OpenWrt SDK 产出的 apk 命名可能是：
#     <name>-<version>.apk
#     <name>-<version>_<arch>.apk
#   其中 name/version 都可能含连字符，arch 可能含下划线（aarch64_cortex-a53）。
#   确定性拆分顺序：
#     1. 按最后一个下划线拆出 arch 与 <name>-<version>
#     2. 对 <name>-<version> 从右往左找第一个以数字开头的片段作为 version 起点
APK_NAME_RE = re.compile(
    r"^(?P<base>.+?)(?:_(?P<arch>[^_]+))?\.apk$"
)


def log(msg):
    print(msg, flush=True)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def apk_pkginfo(path):
    """读取 apk 包第一段 gzip 中的 .PKGINFO，返回字段字典。"""
    with open(path, "rb") as f:
        raw = f.read()
    try:
        dec = zlib.decompressobj(16 + zlib.MAX_WBITS)
        data = dec.decompress(raw)
    except zlib.error:
        return None
    if not data:
        return None
    try:
        tf = tarfile.open(fileobj=io.BytesIO(data))
    except tarfile.TarError:
        return None
    fields = {}
    with tf:
        for member in tf.getmembers():
            if os.path.basename(member.name) != ".PKGINFO":
                continue
            fh = tf.extractfile(member)
            if fh is None:
                continue
            for line in fh.read().decode("utf-8", "replace").splitlines():
                if line.startswith("#"):
                    continue
                # apk-tools 的 .PKGINFO 用 "key = value"，与 ipk control 的
                # "Key: value" 不同，两种分隔符都兼容
                if "=" in line:
                    key, _, val = line.partition("=")
                elif ":" in line:
                    key, _, val = line.partition(":")
                else:
                    continue
                fields[key.strip()] = val.strip()
            break
    return fields or None


def ipk_control(path):
    """尽力读取 ipk 的 control 段（gzip 或 zstd），失败返回 None。"""
    with open(path, "rb") as f:
        raw = f.read()
    if not raw.startswith(b"!<arch>\n"):
        return None
    pos = 8
    while pos + 60 <= len(raw):
        header = raw[pos:pos + 60]
        if header[58:60] != b"`\n":
            break
        name = header[0:16].decode("ascii", "replace").strip()
        try:
            size = int(header[48:58].decode("ascii", "replace").strip())
        except ValueError:
            break
        body = raw[pos + 60:pos + 60 + size]
        pos += 60 + size + (size % 2)
        if not name.startswith("control.tar"):
            continue
        try:
            if name.endswith(".gz"):
                data = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(body)
            elif name.endswith(".zst"):
                import zstandard  # 可选依赖
                data = zstandard.ZstdDecompressor().decompress(body)
            else:
                data = body
            tf = tarfile.open(fileobj=io.BytesIO(data))
        except Exception:
            return None
        with tf:
            for member in tf.getmembers():
                if os.path.basename(member.name) != "control":
                    continue
                fh = tf.extractfile(member)
                if fh is None:
                    continue
                fields = {}
                for line in fh.read().decode("utf-8", "replace").splitlines():
                    if ":" not in line:
                        continue
                    key, _, val = line.partition(":")
                    fields[key.strip()] = val.strip()
                return fields or None
    return None


def read_meta(path):
    """返回 (name, version, arch)；无法识别时抛 ValueError。"""
    ext = os.path.splitext(path)[1].lstrip(".").lower()
    base = os.path.basename(path)

    if ext == "apk":
        info = apk_pkginfo(path)
        if info and info.get("pkgname") and info.get("pkgver"):
            return info["pkgname"], info["pkgver"], (info.get("arch") or "unknown")
        # 确定性拆分（不用正则，避免 arch 含下划线时被截断）：
        #   OpenWrt SDK 原始文件名形如 <name>-<version>.apk，
        #   本脚本 stage 后追加 _<arch>.apk，其中 arch 可能含下划线
        #   （x86_64 / aarch64_cortex-a53 / aarch64_generic / all）。
        #   因此先按已知 arch 后缀反拆，再处理 <name>-<version>。
        stem = base[:-4] if base.endswith(".apk") else base
        arch = "unknown"
        name_ver = stem
        for known in ("aarch64_cortex-a53", "aarch64_generic", "x86_64", "all", "noarch"):
            suffix = "_" + known
            if stem.endswith(suffix):
                arch = known
                name_ver = stem[: -len(suffix)]
                break
        if "-" not in name_ver:
            raise ValueError("apk 文件名缺少版本分隔符 '-': %s" % base)
        parts = name_ver.split("-")
        version_idx = None
        for i in range(len(parts) - 1, -1, -1):
            if parts[i] and parts[i][0].isdigit():
                version_idx = i
                break
        if version_idx is None:
            name, version = name_ver.rsplit("-", 1)
        else:
            name = "-".join(parts[:version_idx]) if version_idx > 0 else ""
            version = "-".join(parts[version_idx:])
        return name, version, arch

    if ext == "ipk":
        m = IPK_NAME_RE.match(base)
        if m:
            return m.group("name"), m.group("version"), m.group("arch")
        ctrl = ipk_control(path)
        if ctrl and ctrl.get("Package") and ctrl.get("Version"):
            return ctrl["Package"], ctrl["Version"], (ctrl.get("Architecture") or "unknown")
        raise ValueError("无法识别 ipk 元数据: %s" % base)

    raise ValueError("不支持的包格式: %s" % base)


def canonical_name(name, version, arch, package_format):
    if package_format == "apk":
        return "%s-%s_%s.apk" % (name, version, arch)
    return "%s_%s_%s.ipk" % (name, version, arch)


def iter_packages(root, pattern="chfs"):
    """递归收集 root 下文件名含 pattern 的 apk / ipk。"""
    found = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in sorted(filenames):
            if pattern and pattern not in fn:
                continue
            if fn.endswith(".apk") or fn.endswith(".ipk"):
                found.append(os.path.join(dirpath, fn))
    return sorted(found)


def cmd_stage(args):
    src = args.src
    if not os.path.isdir(src):
        log("::error::产物目录不存在: %s" % src)
        return 2

    packages = iter_packages(src)
    if not packages:
        log("::error::%s 下没有找到任何 chfs 相关包" % src)
        return 1

    outdir = os.path.join(args.out, args.format, args.arch)
    os.makedirs(outdir, exist_ok=True)

    staged = []
    for path in packages:
        name, version, arch = read_meta(path)
        # apk 的 .PKGINFO 里一定有 arch；若读不到则回退为本次构建的目标架构
        if arch in ("unknown", ""):
            arch = args.arch
        if arch not in ARCH_ALL and arch != args.arch:
            log("::error::%s 的架构 %s 与本次构建目标 %s 不符" % (path, arch, args.arch))
            return 1

        target = os.path.join(outdir, canonical_name(name, version, arch, args.format))
        with open(path, "rb") as fsrc, open(target, "wb") as fdst:
            fdst.write(fsrc.read())
        staged.append({
            "name": name,
            "version": version,
            "arch": arch,
            "format": args.format,
            "file": os.path.relpath(target, args.out),
            "size": os.path.getsize(target),
            "sha256": sha256_of(target),
        })
        log("归档 %-46s <- %s" % (os.path.basename(target), os.path.basename(path)))

    log("")
    log("| 包 | 版本 | 架构 | 大小 |")
    log("|---|---|---|---|")
    for item in staged:
        log("| `%s` | %s | %s | %d |" % (item["name"], item["version"], item["arch"], item["size"]))
    return 0


def cmd_list(args):
    packages = iter_packages(args.src)
    if not packages:
        log("| （无产物） | | | |")
        return 0
    for path in packages:
        name, version, arch = read_meta(path)
        log("| `%s` | %s | %s | %d |" % (name, version, arch, os.path.getsize(path)))
    return 0


def build_notes(tag, packages, kernels, extra_files):
    lines = []
    lines.append("## luci-app-chfs %s" % tag)
    lines.append("")
    lines.append("chfs（CuteHttpFileServer）文件共享服务本体及其 LuCI 管理界面的预编译安装包。")
    lines.append("")
    lines.append("### 资产目录结构")
    lines.append("")
    lines.append("| 目录 | 适用设备 | 包含 |")
    lines.append("|---|---|---|")

    arch_desc = {
        "x86_64": "x86_64 软路由 / 虚拟机",
        "aarch64_cortex-a53": "MT798x（Filogic）等 64 位 ARM 路由",
        "aarch64_generic": "通用 ARMv8（armsr/armv8、RK35xx 等）",
        "all": "架构无关，任意设备通用",
    }
    by_dir = {}
    for p in packages:
        by_dir.setdefault(p["arch"], []).append(p)
    for arch in sorted(by_dir, key=lambda a: (a == "all", a)):
        files = "<br>".join("`%s`" % os.path.basename(p["file"]) for p in by_dir[arch])
        lines.append("| `%s/` | %s | %s |" % (arch, arch_desc.get(arch, ""), files))
    lines.append("| （根目录） | — | 内核二进制 `chfs-linux-arm64-3.1` / `chfs-linux-amd64-3.1`、"
                 "`SHA256SUMS`、`manifest.json` |")
    lines.append("")
    lines.append("`apk` 由 ImmortalWrt SNAPSHOT SDK 产出，`ipk` 由 OpenWrt 24.10.5 SDK 产出；")
    lines.append("`all/` 下的 LuCI 界面与简体中文语言包与 CPU 无关，两种格式各只有一份。")
    lines.append("")

    lines.append("### 包清单")
    lines.append("")
    lines.append("| 路径 | 包 | 版本 | 格式 | 大小 |")
    lines.append("|---|---|---|---|---|")
    for p in sorted(packages, key=lambda p: (p["arch"] == "all", p["arch"], p["format"], p["name"])):
        lines.append("| `%s` | `%s` | %s | %s | %d |" % (
            p["file"], p["name"], p["version"], p["format"], p["size"]))
    lines.append("")

    lines.append("### 安装")
    lines.append("")
    lines.append("先按设备架构与包管理器进入对应目录取包（下面以 `x86_64/` 为例）：")
    lines.append("")
    lines.append("```sh")
    lines.append("# apk 系统（ImmortalWrt / OpenWrt SNAPSHOT）")
    for p in packages:
        if p["format"] == "apk" and p["arch"] == "x86_64":
            lines.append("apk add --allow-untrusted ./%s" % p["file"])
    for p in packages:
        if p["format"] == "apk" and p["arch"] == "all":
            lines.append("apk add --allow-untrusted ./%s" % p["file"])
    lines.append("")
    lines.append("# ipk 系统（OpenWrt 24.10.x）")
    for p in packages:
        if p["format"] == "ipk" and p["arch"] == "x86_64":
            lines.append("opkg install ./%s" % p["file"])
    for p in packages:
        if p["format"] == "ipk" and p["arch"] == "all":
            lines.append("opkg install ./%s" % p["file"])
    lines.append("")
    lines.append("rm -f /tmp/luci-indexcache*; rm -rf /tmp/luci-modulecache/")
    lines.append("/etc/init.d/rpcd reload")
    lines.append("```")
    lines.append("")
    lines.append("菜单位置：**网络存储（NAS）→ chfs 文件共享**。")
    lines.append("")

    if kernels:
        lines.append("### chfs 内核二进制")
        lines.append("")
        lines.append("| 文件 | 架构 | 大小 |")
        lines.append("|---|---|---|")
        for k in kernels:
            lines.append("| `%s` | %s | %d |" % (k["file"], k["arch"], k["size"]))
        lines.append("")
        lines.append("供 LuCI 界面「内核管理 → 从仓库下载」使用，也可手工替换 `/usr/bin/chfs`。")
        lines.append("")

    lines.append("### 校验")
    lines.append("")
    lines.append("```sh")
    lines.append("sha256sum -c SHA256SUMS")
    lines.append("```")
    lines.append("")
    lines.append("`manifest.json` 以机器可读形式记录每个资产的包名、版本、架构、大小与 SHA256。")
    if extra_files:
        lines.append("")
        lines.append("本 Release 共 %d 个资产。" % (len(packages) + len(kernels) + len(extra_files)))
    return "\n".join(lines) + "\n"


def cmd_finalize(args):
    src = args.src
    out = args.out
    os.makedirs(out, exist_ok=True)

    packages = []
    for path in iter_packages(src):
        name, version, arch = read_meta(path)
        package_format = "apk" if path.endswith(".apk") else "ipk"
        if arch in ("unknown", ""):
            log("::warning::无法判定 %s 的架构，按文件名保留" % os.path.basename(path))
            arch = "unknown"
        final = canonical_name(name, version, arch, package_format)
        # 按架构分目录：Release 页会呈现为 x86_64/ aarch64_cortex-a53/
        # aarch64_generic/ all/ 四个分组，避免六个架构的包平铺混在一起
        subdir = arch or "unknown"
        target_dir = os.path.join(out, subdir)
        os.makedirs(target_dir, exist_ok=True)
        target = os.path.join(target_dir, final)
        rel = "%s/%s" % (subdir, final)
        if os.path.exists(target):
            if sha256_of(target) != sha256_of(path):
                log("::error::同名资产内容不一致: %s" % rel)
                return 1
            log("已存在且一致，跳过: %s" % rel)
            continue
        with open(path, "rb") as fsrc, open(target, "wb") as fdst:
            fdst.write(fsrc.read())
        packages.append({
            "name": name,
            "version": version,
            "arch": arch,
            "format": package_format,
            "file": rel,
            "size": os.path.getsize(target),
            "sha256": sha256_of(target),
        })
        log("资产 %s  (%d 字节)" % (rel, os.path.getsize(target)))

    if not packages:
        log("::error::未汇总到任何安装包")
        return 1

    # 内核二进制等非安装包资产（由工作流先行放入 out），一并计入校验清单
    kernels = []
    for fn in sorted(os.listdir(out)):
        # 内核二进制命名形如 chfs-linux-arm64-3.1（含点，不能按"无扩展名"判定）
        if not fn.startswith("chfs-linux-"):
            continue
        if fn.endswith((".apk", ".ipk", ".json")):
            continue
        arch = "aarch64" if "arm64" in fn else ("x86_64" if "amd64" in fn else "unknown")
        kernels.append({
            "file": fn,
            "arch": arch,
            "size": os.path.getsize(os.path.join(out, fn)),
            "sha256": sha256_of(os.path.join(out, fn)),
        })

    # SHA256SUMS：递归覆盖 out 下当时已有的全部资产（含架构子目录）
    entries = []
    for dirpath, _dirnames, filenames in os.walk(out):
        for fn in sorted(filenames):
            rel = os.path.relpath(os.path.join(dirpath, fn), out).replace(os.sep, "/")
            if rel in ("SHA256SUMS", "manifest.json"):
                continue
            entries.append((rel, sha256_of(os.path.join(out, rel))))
    entries.sort()
    with open(os.path.join(out, "SHA256SUMS"), "w", encoding="utf-8", newline="\n") as f:
        f.write("# SHA256SUMS - luci-app-chfs %s\n" % args.tag)
        f.write("# 用法: sha256sum -c SHA256SUMS\n")
        for fn, digest in entries:
            f.write("%s  %s\n" % (digest, fn))

    manifest = {
        "repo": "LianXia233/luci-app-chfs",
        "tag": args.tag,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "formats": {fmt: FORMAT_DIST.get(fmt, fmt) for fmt in sorted({p["format"] for p in packages})},
        "packages": sorted(packages, key=lambda p: (p["format"], p["arch"], p["name"])),
        "kernels": kernels,
    }
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")

    notes = build_notes(args.tag, manifest["packages"], kernels, ["SHA256SUMS", "manifest.json"])
    notes_path = args.notes
    os.makedirs(os.path.dirname(os.path.abspath(notes_path)), exist_ok=True)
    with open(notes_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(notes)

    log("")
    log("| 包 | 版本 | 架构 | 格式 | 大小 |")
    log("|---|---|---|---|---|")
    for p in manifest["packages"]:
        log("| `%s` | %s | %s | %s | %d |" % (p["name"], p["version"], p["arch"], p["format"], p["size"]))
    log("")
    log("发布说明: %s (%d 字节)" % (notes_path, os.path.getsize(notes_path)))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="整理 chfs 构建产物")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_stage = sub.add_parser("stage", help="归档单个 SDK 的产物")
    p_stage.add_argument("--src", required=True, help="SDK 的 bin/packages 目录")
    p_stage.add_argument("--format", required=True, choices=["apk", "ipk"])
    p_stage.add_argument("--arch", required=True, help="本次构建的目标包架构")
    p_stage.add_argument("--out", required=True, help="归档根目录")
    p_stage.set_defaults(func=cmd_stage)

    p_list = sub.add_parser("list", help="打印已归档产物表格")
    p_list.add_argument("--src", required=True, help="归档根目录")
    p_list.set_defaults(func=cmd_list)

    p_fin = sub.add_parser("finalize", help="汇总并生成发布资产与说明")
    p_fin.add_argument("--src", required=True, help="下载到的 artifacts 根目录")
    p_fin.add_argument("--out", required=True, help="最终资产输出目录")
    p_fin.add_argument("--notes", required=True, help="发布说明 markdown 输出路径")
    p_fin.add_argument("--tag", required=True, help="Release tag，用于生成下载链接")
    p_fin.set_defaults(func=cmd_finalize)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
