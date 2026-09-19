# 更新日志

本文件记录 luci-app-chfs 的所有重要变更。

版本号遵循 `MAJOR.MINOR.PATCH-rRELEASE`（对应 OpenWrt 的 `PKG_VERSION` 与 `PKG_RELEASE`），
格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

---

## [1.0.0-r1] - 2026-09-19

首个公开发布版本。提供 chfs（CuteHttpFileServer）的完整 LuCI 管理界面，
并通过 GitHub Actions 云编译同时产出 **apk** 与 **ipk** 两种包格式。

### 新增

- **LuCI 管理界面**（`luci-app-chfs`）
  - 菜单挂载于「网络存储 → 文件共享」（`admin/nas/chfs`）。
  - 三个视图模块：`main.js`（服务与共享目录配置）、`accounts.js`（账户与权限）、`status.js`（运行状态与日志）。
  - 样式文件 `chfs.css` 随包分发。

- **后端 RPC 接口**（`root/usr/share/rpcd/ucode/chfs.uc`，503 行 ucode）
  - 通过 `rpcd-mod-ucode` 暴露 `luci.chfs` 命名空间，共 8 个方法。
  - 覆盖服务启停/重启、配置读取与写入、运行状态查询、日志读取等能力。
  - ACL 声明位于 `root/usr/share/rpcd/acl.d/luci-app-chfs.json`，按读写权限分域授权。

- **UCI 配置与 init 脚本**
  - `root/etc/config/chfs`：默认配置模板（端口、共享目录、账户、IP 黑名单）。
  - `root/etc/init.d/chfs`：procd 服务脚本，支持开机自启与进程守护。
  - `root/etc/uci-defaults/99-luci-app-chfs`：首次安装时套用默认值并触发 LuCI 缓存刷新。

- **国际化**
  - `po/zh_Hans/luci-app-chfs.po`：简体中文翻译。
  - 严格遵循 LuCI 约定——源码中的 `_()` 参数一律使用**英文 msgid**，中文译文仅存放在 `.po` 的 `msgstr` 中。
    这是因为 `po2lmo` 的 `print_msg()` 中有 `if (key_id != val_id)` 判定，若直接把中文当作 msgid，
    该条目会被静默跳过，`.lmo` 条目数会从 125 骤降至 35（已实测复现）。

- **chfs 二进制包**（`chfs`）
  - 支持架构：`aarch64_cortex-a53`（arm64）、`x86_64`（amd64）。
  - 二进制**预先入库**于 `chfs/bin/<arch>/chfs`，构建期不做实时下载。
  - 版本与哈希清单记录于 `chfs/bin-manifest.txt`。
  - `chfs/Makefile` 在检测到本地二进制时把 `PKG_SOURCE_URL` 置空以跳过下载，
    仅在缺失时回退到上游 `http://iscute.cn/tar/chfs/<version>` 拉取。
    （注意：`PKG_SKIP_DOWNLOAD` 无法用于此目的——`include/package.mk` 第 14 行会无条件覆盖它。）

- **云编译流水线**（`.github/workflows/build.yml`）
  - 4 条目构建矩阵，两种包格式 × 两种架构：
    | 包格式 | SDK | 架构 |
    | --- | --- | --- |
    | apk | ImmortalWrt SNAPSHOT（gcc-14.4.0） | aarch64_cortex-a53 / x86_64 |
    | ipk | OpenWrt 24.10.5（gcc-13.3.0） | aarch64_cortex-a53 / x86_64 |
  - 构建期拉取上游 `openwrt/luci` 源码，让 SDK 原生构建 host 工具
    `po2lmo` / `jsmin`（luci 自带 `modules/luci-base/src/contrib/lemon.c`，
    由普通 `cc` 就地编译，无需外部 lemon 依赖）。
  - 产物以 4 个 artifact 上传：`packages-{apk,ipk}-{aarch64_cortex-a53,x86_64}`。
  - 打 `v*` tag 或手动触发并指定 `release_tag` 时自动创建 Release。

- **辅助工具**
  - `tools/fetch-chfs.py`：按架构下载 chfs 二进制并校验 ELF 头（arm64=183 / amd64=62）与 SHA256，
    支持重试与损坏包自动清除，输出 `chfs/bin-manifest.txt`。

- **文档**
  - `README.md`：目录结构、构建方式、包格式与 SDK 对应关系、安装说明。
  - `CHANGELOG.md`：本文件。

### 已知限制

- `chfs` 包为二进制包，与架构强绑定，**不可**标记 `PKGARCH:=all`，
  否则不同架构的包会互相覆盖。
- 仅支持 arm64 与 amd64；mipsel / mips64el / armeb / i386 等老架构未预置二进制。
- `luci-app-chfs` 依赖 `rpcd`、`rpcd-mod-ucode`、`ucode`、`ucode-mod-fs`、`ucode-mod-uci`，
  这些属于 LuCI 运行环境的一部分，需由固件或 feeds 提供。
- 上游 `iscute.cn` 的 TLS 证书已过期，回退下载路径必须使用 `http://` 而非 `https://`。

---

## 版本规划

- **1.1.x**：补充更多架构的预置二进制；增加共享目录在线预览。
- **1.2.x**：支持多实例（不同端口启动多个 chfs 进程）。

[1.0.0-r1]: https://github.com/LianXia233/luci-app-chfs/releases/tag/v1.0.0
