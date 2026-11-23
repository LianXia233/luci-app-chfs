#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下载 chfs 二进制并提取裸可执行文件到 chfs/bin/<arch>/chfs。

背景：上游 iscute.cn 证书过期、站点可用性不可控（实测下载常中途断开），
云编译不应依赖实时下载，故把二进制预先入库，Makefile 优先使用本地文件。

上游包内文件名形如 chfs-linux-arm64-3.1（无扩展名），需用 ELF 魔数检测排除误取。

用法：
    python3 tools/fetch-chfs.py              # 仅更新 DEFAULT_ARCHS（arm64/amd64）
    python3 tools/fetch-chfs.py arm64 amd64 mipsle   # 显式指定架构
"""
import hashlib
import os
import subprocess
import sys
import zipfile

VER = "3.1"
BASE = "http://iscute.cn/tar/chfs/%s" % VER

# 默认仅维护云编译实际使用的两个架构。
# 其余架构（arm / 386 / mips / mipsle / mips64 / mips64le / mipssoftfloat /
# mips64softfloat）仍可通过显式参数下载，但不会入库到仓库。
DEFAULT_ARCHS = ["arm64", "amd64"]

# 仓库根目录 = 本脚本所在目录的上一级
ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chfs", "bin"
)
CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp-dl"
)

CURL = os.environ.get("CURL", "curl")


def download(arch):
    os.makedirs(CACHE, exist_ok=True)
    z = os.path.join(CACHE, "chfs-linux-%s-%s.zip" % (arch, VER))
    if os.path.exists(z) and os.path.getsize(z) > 100000:
        print("  使用缓存: %s" % os.path.basename(z))
        return z
    url = "%s/chfs-linux-%s-%s.zip" % (BASE, arch, VER)
    for attempt in (1, 2, 3):
        r = subprocess.run(
            [CURL, "-fsSL", "--max-time", "300", "-o", z, url],
            capture_output=True,
        )
        if r.returncode == 0 and os.path.exists(z) and os.path.getsize(z) > 100000:
            return z
        print("  第 %d 次下载失败: %s" % (attempt, r.stderr.decode(errors="replace")[:120]))
    return None


def extract(zip_path, arch):
    """从 zip 中定位 ELF 二进制，返回 (字节内容, 原始文件名)。"""
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        cands = []
        for n in names:
            low = n.lower()
            if low.endswith((".zip", ".txt", ".md", ".html", ".exe", ".dll",
                             ".bat", ".cmd", ".json", ".ini")):
                continue
            if os.path.basename(n).startswith("."):
                continue
            cands.append(n)

        order = []
        for pat in ("chfs-linux-%s-%s" % (arch, VER), "chfs-linux-%s" % arch, "chfs-", "chfs"):
            for n in cands:
                if pat in os.path.basename(n) and n not in order:
                    order.append(n)
        for n in cands:
            if n not in order:
                order.append(n)

        for n in order:
            data = zf.read(n)
            if data[:4] == b"\x7fELF":
                return data, n
    return None, None


def elf_machine(data):
    """读取 ELF 的 e_machine 字段，用于校验架构是否匹配。"""
    if data[:4] != b"\x7fELF":
        return None
    little = data[5] == 1
    raw = data[18:20]
    return int.from_bytes(raw, "little" if little else "big")


EXPECT_MACHINE = {"arm64": 183, "amd64": 62, "arm": 40, "386": 3,
                  "mips": 8, "mipsle": 8, "mips64": 8, "mips64le": 8,
                  "mipssoftfloat": 8, "mips64softfloat": 8}

# 已发布上游包的 SHA256 基准值。上游不公布校验值，这里记录本仓库验证过的
# 实际值；命中该表时必须完全一致，否则拒绝入库。
EXPECT_SHA256 = {
    "arm64": "78ed31c12b7f1c9679867d5cc9051cc1174740bb88b939eaf32b14436b6d3e53",
    "amd64": "763a557c7b6916a496639a715cd8d6ff1dbb6c15b73bed060a705797d434c6a6",
}


def read_manifest(path):
    """读取已有清单，保留未在本次下载的架构条目。"""
    entries = {}
    if not os.path.exists(path):
        return entries

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 4:
                entries[parts[0]] = parts[1:4]
    return entries


def main():
    archs = sys.argv[1:] or DEFAULT_ARCHS
    print("=== 下载并提取 chfs %s 二进制 ===" % VER)
    print("架构: %s" % ", ".join(archs))

    mf = os.path.join(os.path.dirname(os.path.dirname(ROOT)), "chfs", "bin-manifest.txt")
    entries = read_manifest(mf)
    ok = 0

    for arch in archs:
        print("[%s]" % arch)
        z = download(arch)
        if not z:
            print("  跳过（下载失败）")
            continue
        try:
            data, name = extract(z, arch)
        except zipfile.BadZipFile:
            print("  zip 损坏（多为下载中断），已删除缓存以便重试")
            os.remove(z)
            continue
        if data is None:
            print("  未找到 ELF，zip 内容: %s" % zipfile.ZipFile(z).namelist())
            continue

        mach = elf_machine(data)
        exp = EXPECT_MACHINE.get(arch)
        if exp is not None and mach != exp:
            print("  错误: ELF e_machine=%s 与预期 %s 不符，拒绝入库" % (mach, exp))
            continue

        sha = hashlib.sha256(data).hexdigest()
        expected_sha = EXPECT_SHA256.get(arch)
        if expected_sha is not None and sha != expected_sha:
            print("  错误: SHA256 与内置基准值不符，拒绝入库")
            print("        期望: %s" % expected_sha)
            print("        实际: %s" % sha)
            continue
        if expected_sha is None:
            print("  警告: 该架构没有内置 SHA256 基准值，仅记录本次计算结果")

        outdir = os.path.join(ROOT, arch)
        os.makedirs(outdir, exist_ok=True)
        out = os.path.join(outdir, "chfs")
        with open(out, "wb") as f:
            f.write(data)
        os.chmod(out, 0o755)

        entries[arch] = (name, str(len(data)), sha)
        print("  <- %-32s %9d B  e_machine=%-3s sha256=%s"
              % (name, len(data), mach, sha[:16]))
        ok += 1

    print("\n成功 %d/%d" % (ok, len(archs)))

    if entries:
        os.makedirs(os.path.dirname(mf), exist_ok=True)
        with open(mf, "w", encoding="utf-8", newline="\n") as f:
            f.write("# chfs %s prebuilt binaries\n" % VER)
            f.write("# upstream: %s\n" % BASE)
            f.write("# 说明: 已入库架构供云编译直接使用, 缺失架构需显式提供上游 SHA256\n")
            f.write("# arch\toriginal_name\tsize\tsha256\n")
            for arch in sorted(entries):
                name, size, sha = entries[arch]
                f.write("%s\t%s\t%s\t%s\n" % (arch, name, size, sha))
        print("清单: %s" % mf)


if __name__ == "__main__":
    main()
