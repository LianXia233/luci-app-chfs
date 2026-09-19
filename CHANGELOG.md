# 更新日志

本文件记录 luci-app-chfs 的所有重要变更。

版本号遵循 `MAJOR.MINOR.PATCH-rRELEASE`（对应 OpenWrt 的 `PKG_VERSION` 与 `PKG_RELEASE`），
格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

---

## [1.0.0-r2] - 2026-09-19

### 新增

- **内核管理**（一键下载 / 手动上传 / 备份回滚）
  - 背景：chfs 上游只发布预编译二进制，且 `iscute.cn` 的 TLS 证书已过期、站点可用性不可控。
    随包入库的二进制存在三种需要替换的场景：目标架构未预置、上游发布新版本、随包二进制损坏。
  - 后端在 `luci.chfs` 中新增 8 个方法：
    | 方法 | 作用 |
    | --- | --- |
    | `kernel_info` | 当前内核路径、大小、ELF 机器类型、架构是否匹配、SHA256 |
    | `kernel_sources` | 探测 6 个候选下载源可用性（Release 官方 / gh.acg2.mom / gh-proxy / ghfast / Raw / Raw 镜像） |
    | `kernel_pending` | 列出待安装的内核文件 |
    | `kernel_backups` | 列出已备份的内核 |
    | `kernel_download` | 按白名单前缀下载指定 URL 到待安装区 |
    | `kernel_install` | 校验后备份现有内核并安装 |
    | `kernel_restore` | 从备份回滚 |
    | `kernel_discard` | 丢弃待安装文件 |
  - 下载源信任锚点是本仓库（HTTPS），相比从上游 HTTP 明文下载更安全。
  - 五道安全边界：
    1. 下载 URL 必须匹配白名单前缀（仅本仓库地址），不接受任意 URL，避免沦为 SSRF / 跳板。
    2. 上传与下载的文件先落到 `/etc/luci-uploads`，不直接覆盖运行中的内核。
    3. 安装前校验 ELF 魔数、`e_machine` 与设备架构匹配、文件非空、大小在 100 KB – 64 MB 之间。
    4. 安装前自动备份现有内核到 `/etc/chfs/kernel-backup`，便于回滚。
    5. 安装后权限固定为 `0755`。

- **Release 工作流**（`.github/workflows/release.yml`）
  - 打 `v*` tag 或手动触发时，校验预置二进制（ELF 魔数 + `e_machine` 183/62）、
    比对 `chfs/bin/SHA256SUMS` 一致性，再发布为 Release 资产：
    `chfs-linux-arm64-<ver>`、`chfs-linux-amd64-<ver>`、`SHA256SUMS`。
  - 这些资产正是路由器侧「一键下载」的目标地址。

- **二进制校验清单**（`chfs/bin/SHA256SUMS`）
  - 按架构记录 SHA256，格式 `<sha256>  <架构目录名>`。
  - 架构目录名与 `uname -m` 的映射：`aarch64`→`arm64`、`x86_64`→`amd64`。

### 修复

- **LuCI 二级页面无法返回主页**
  - 现象：进入「账户与权限」或「服务状态」后，标签栏中没有回到主页的入口。
  - 根因：父菜单 `admin/nas/chfs` 指向视图 `chfs/main`，但菜单树中**没有任何子节点指向该视图**，
    因此 `ui.menu.getChildren()` 生成的标签集合里不含主页，主页不在可跳转目标内。
  - 修复：新增子节点 `admin/nas/chfs/main`（`path: chfs/main`，`order: 10`），
    使主页自身成为标签栏第一项；`accounts` / `status` 的 `order` 顺延为 20 / 30。
  - 实测：标签项由 2 项变为 3 项，三页可互相跳转，选中态高亮正确。

- **`luci.chfs` 缺少可执行位导致 rpcd 不加载**
  - 现象：ucode 后端文件已写入 `/usr/share/rpcd/ucode/luci.chfs`，但 rpcd 未注册其方法。
  - 根因：在 Windows 上开发（`git core.filemode=false`），可执行位无法写入 git 索引，
    检出后文件为 `0644`；rpcd 不把无可执行位的文件视为可加载模块。
  - 修复：在 `Makefile` 的 `install_lib` 钩子中补 `chmod 0755`，
    与 `init.d/chfs`、`uci-defaults/99-luci-app-chfs` 的处理方式一致。

- **`elf_machine()` 读字节方式错误**
  - `fs.open()` 返回的是字符串，取字节须用全局 `ord(str, idx)`；
    用 `s[idx]` 下标访问在 ucode 中返回 `null`。
  - 同时补上 `import { open } from 'fs'`——`open` 不是全局函数。

- **`kernel_sources` 探测全部超时**
  - 根因：设备上的 `/usr/bin/wget` 实为 `/bin/uclient-fetch` 软链，**不支持 `-S` 选项**，
    命令直接报 `unrecognized option: S` 退出。
  - 修复：新增 `detect_fetcher()` 优先使用 `curl`
    （`-s -I -L -o /dev/null -w "%{http_code}"`），`uclient-fetch` 作为兜底
    （`-s -T N` + 退出码判定）。GitHub Release 资产会 302 跳转到 Azure Blob，故需 `-L` 跟随重定向。

- **`push()` 返回值误用**
  - ucode 的 `push(array, value)` 原地修改数组并返回**新长度（整数）**，不返回数组。
    `x = push(x, y)` 会使 `x` 退化为整数，后续再 `push` 即抛错。
    已改为独立成句 `push(out.sources, c);`。

### 变更

- `root/usr/share/rpcd/ucode/chfs.uc` 重命名为 `luci.chfs`，与 rpcd 的
  文件即模块名约定对齐（模块名 `luci.chfs` 对应文件名 `luci.chfs`）。
- 简体中文翻译新增 `Service settings` → 「服务设置」。

---

## [1.0.0-r1] - 2026-09-19

首个公开发布版本。提供 chfs（CuteHttpFileServer）的完整 LuCI 管理界面，
并通过 GitHub Actions 云编译同时产出 **apk** 与 **ipk** 两种包格式。

### 新增

- **LuCI 管理界面**（`luci-app-chfs`）
  - 菜单挂载于「网络存储 → 文件共享」（`admin/nas/chfs`）。
  - 三个视图模块：`main.js`（服务与共享目录配置）、`accounts.js`（账户与权限）、`status.js`（运行状态与日志）。
  - 样式文件 `chfs.css` 随包分发。

- **后端 RPC 接口**（`root/usr/share/rpcd/ucode/luci.chfs`）
  - 通过 `rpcd-mod-ucode` 暴露 `luci.chfs` 命名空间。
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
  - 版本记录于 `chfs/bin-manifest.txt`，哈希清单记录于 `chfs/bin/SHA256SUMS`。
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

[1.0.0-r2]: https://github.com/LianXia233/luci-app-chfs/releases/tag/v1.0.0
[1.0.0-r1]: https://github.com/LianXia233/luci-app-chfs/releases/tag/v1.0.0
