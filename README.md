# luci-app-chfs

OpenWrt / ImmortalWrt 下的 [chfs](http://iscute.cn/chfs)（CuteHttpFileServer）图形化管理插件。
前端采用 LuCI 现代架构（JS 视图 + ucode 后端），界面基于 LuCI 官方 CSS 变量适配明暗主题。

## 功能特性

- **服务控制**：界面内启动 / 停止 / 重启服务，实时显示运行状态（进程号、内存占用、监听端口）。
- **完整参数配置**：监听端口、共享根目录（支持多目录）、运行身份、IP 白名单、匿名访问、
  日志目录、HTTPS 证书、页面标题与公告、图片缩略图、目录下载策略、文件删除方式、会话超时。
- **账户与权限**：多账户管理，支持按目录粒度配置权限（禁止访问 / 只读 / 读写 / 完全控制）。
- **WebDAV 支持**：chfs 自 1.10 起默认启用 WebDAV，与 HTTP 共用端口。状态页提供真实的
  `PROPFIND` 探测，并给出可直接复制的 WebDAV 地址。
- **状态页真实性**：所有状态数据均通过实际探测获取（`pgrep` 进程检测、`/proc/net/tcp` 端口
  监听检测、`curl PROPFIND` WebDAV 探测），非界面装饰。
- **配置文件预览**：展示由 UCI 配置实际渲染出的 `chfs.ini` 内容。
- **内核管理**：提供「一键下载」与「手动上传」两条内核替换路径，并支持安装前自动备份、
  失败回滚。安装前会校验 ELF 魔数、`e_machine` 与设备架构是否匹配、文件大小是否合理。

## 目录结构

```
.
├── .github/workflows/
│   ├── build.yml                          # 云编译：apk/ipk × arm64/amd64 四条目矩阵
│   └── release.yml                        # 打 tag 时发布内核二进制为 Release 资产
├── chfs/                                  # chfs 二进制包
│   ├── Makefile                           # 预置二进制优先，缺失时回退上游下载
│   ├── extract-bin.sh                     # 从上游 zip 中定位并规范化二进制
│   ├── bin-manifest.txt                   # 预置二进制清单（架构、大小、sha256）
│   └── bin/                               # 预置二进制（已入库，供云编译直接取用）
│       ├── SHA256SUMS                     # 按架构的校验值清单
│       ├── arm64/chfs                     #   OpenWrt ARCH: aarch64
│       └── amd64/chfs                     #   OpenWrt ARCH: x86_64
├── tools/fetch-chfs.py                    # 下载/更新预置二进制并生成清单
├── README.md
└── luci-app-chfs/                         # LuCI 应用包
    ├── Makefile
    ├── htdocs/luci-static/resources/view/chfs/
    │   ├── main.js                        # 主配置页
    │   ├── accounts.js                    # 账户与权限页
    │   ├── status.js                      # 服务状态页
    │   └── chfs.css                       # 样式（基于 LuCI CSS 变量）
    ├── po/zh_Hans/luci-app-chfs.po        # 简体中文翻译
    └── root/
        ├── etc/config/chfs                # UCI 默认配置
        ├── etc/init.d/chfs                # procd 服务脚本（UCI -> chfs.ini 渲染）
        ├── etc/uci-defaults/99-luci-app-chfs
        └── usr/share/
            ├── luci/menu.d/luci-app-chfs.json   # 菜单（挂载于 网络存储）
            ├── rpcd/acl.d/luci-app-chfs.json    # ACL 权限
            └── rpcd/ucode/luci.chfs             # ubus 后端（对象 luci.chfs）
```

## 编译

### 依赖

```sh
# 将两个包放入 OpenWrt 源码树的 package/ 下
cp -r chfs             <openwrt>/package/
cp -r luci-app-chfs    <openwrt>/package/
```

`chfs` 包的 `DEPENDS` 已声明支持的架构（mips/mipsel/mips64/mips64el/arm/aarch64/i386/x86_64）；
其中仅 aarch64 与 x86_64 有预置二进制，其余架构走回退下载。
`luci-app-chfs` 的 `LUCI_DEPENDS` 为：

```
+chfs +rpcd +rpcd-mod-ucode +ucode +ucode-mod-fs +ucode-mod-uci
```

### 编译命令

```sh
# 1) 先构建 luci-base 的 host 工具（提供 po2lmo / jsmin）
make package/luci-base/host/compile V=s

# 2) 再编译两个包
make package/chfs/compile V=s
make package/luci-app-chfs/compile V=s
```

### 关于 host 工具

LuCI 的 `luci.mk` 在打包 JS/CSS 与翻译时会调用 `jsmin`、`csstidy`、`po2lmo`。
其中 **`po2lmo` 是必需项**（用于生成 `.lmo` 翻译文件），无法通过开关绕过。

`po2lmo` 与 `jsmin` 都由 `luci-base` 的 host 部分构建。`luci-base/src/Makefile` 的
依赖链是自包含的：

```
contrib/lemon.c  --cc-->  contrib/lemon
lib/plural_formula.y  --lemon-->  lib/plural_formula.c/.h
po2lmo.c + lib/lmo.c + lib/plural_formula.o  -->  po2lmo
```

即 **luci 仓库自带 `contrib/lemon.c`，会用普通 `cc` 就地编译 lemon**，
不需要系统安装 lemon，也不需要对 `lib/lmo.c` 做任何改写。

因此正确的做法是把 `luci` 仓库源码接入 SDK，然后：

```sh
make package/luci-base/host/compile V=s
```

产物落在 **`<sdk>/staging_dir/hostpkg/bin/`**（注意不是 `staging_dir/host/bin/`）。
原因是 `luci-base` 的 `PKG_BUILD_DEPENDS` 含 `luci-base/host`，SDK 会把该 host 包
归入 `hostpkg` 前缀的 staging 目录。

为兼容 `luci.mk` 中 `$(STAGING_DIR_HOST)/bin/po2lmo` 的查找路径，
云编译在检测到只有 `hostpkg` 版本时会向 `staging_dir/host/bin/` 补一份软链：

```sh
mkdir -p staging_dir/host/bin
ln -sf "$(pwd)/staging_dir/hostpkg/bin/po2lmo" staging_dir/host/bin/po2lmo
ln -sf "$(pwd)/staging_dir/hostpkg/bin/jsmin"  staging_dir/host/bin/jsmin
```

云编译工作流正是采用这一方式（见 `.github/workflows/build.yml` 的「获取 luci feeds」
与「构建 luci-base host 工具」两步）。

> 注意：`luci-base/Makefile` 中写有 `include ../../luci.mk` 以及
> `$(CP) ../../NOTICE ../../LICENSE`。从 `package/luci-base/` 出发，`../../`
> 即 SDK 根目录，所以 `luci.mk`、`NOTICE`、`LICENSE` 必须放在 **SDK 根**，
> 而不是 `feeds/luci/` 下。本仓库为保险起见两处都放。

若 SDK 中已具备 `po2lmo`，打包时可选地关闭压缩以加快构建：

```sh
make package/luci-app-chfs/compile V=s \
    LUCI_MINIFY_JS=0 LUCI_MINIFY_CSS=0 LUCI_MINIFY_LUA=0 LUCI_MINIFY_UT=0
```

关闭后 `JsMin` / `CssTidy` / `SrcDiet` / `UtMin` 退化为打印提示，产物功能完全一致，仅不压缩源码。

### chfs 二进制获取

**本项目已把 arm64 与 amd64 两个架构的二进制预先入库**（`chfs/bin/<arch>/chfs`），
云编译**不再依赖上游实时下载**。原因有两点：`iscute.cn` 的 HTTPS 证书已过期、
站点可用性不可控，且实测下载经常中途断开。

Makefile 的取用逻辑：

- 若 `chfs/bin/$(CHFS_ARCH)/chfs` 存在且非空 → 直接安装，并把 `PKG_SOURCE_URL` 置空，构建系统不发起任何网络请求。
- 否则 → 回退到上游下载（兼容未入库的架构）。

> 关于跳过下载的正确写法：**不能设置 `PKG_SKIP_DOWNLOAD`**。
> `include/package.mk` 第 14 行会无条件覆盖它
> （`PKG_SKIP_DOWNLOAD=$(USE_SOURCE_DIR)$(USE_GIT_TREE)$(USE_GIT_SRC_CHECKOUT)`），
> 而下载判定写在 `Build/DefaultTargets` 中：
> ```make
> $(if $(PKG_SKIP_DOWNLOAD),,$(if $(strip $(PKG_SOURCE_URL)),$(call Download,default)))
> ```
> 所以唯一可靠的方式是**把 `PKG_SOURCE_URL` 置空**。

更新入库二进制：

```sh
python3 tools/fetch-chfs.py          # 下载 arm64/amd64 并刷新 bin-manifest.txt
```

上游下载地址形如：

```
http://iscute.cn/tar/chfs/<版本>/chfs-linux-<架构>-<版本>.zip
```

注意两点：

1. **必须使用 HTTP**。`iscute.cn` 的 HTTPS 证书已过期，使用 `https://` 会导致下载失败
   （`SSL certificate problem: certificate has expired`）。
2. **架构名需要映射**，OpenWrt 的 `ARCH` 与上游命名不一致：

   | OpenWrt  | chfs 上游 | 本项目预置 |
   |----------|-----------|------------|
   | aarch64  | arm64     | 是         |
   | x86_64   | amd64     | 是         |
   | mipsel   | mipsle    | 否         |
   | mips64el | mips64le  | 否         |
   | mips     | mips      | 否         |
   | arm      | arm       | 否         |
   | i386     | 386       | 否         |
   | armeb    | arm       | 否         |

压缩包内的二进制文件名形如 `chfs-linux-arm64-3.1`（无扩展名），由 `extract-bin.sh` 负责
定位并安装为 `chfs-bin`，同时用魔数检测拒绝误取 Windows 可执行文件。

## 配置说明

UCI 配置文件为 `/etc/config/chfs`。init 脚本在服务启动时将其渲染为 `chfs.ini`
（位于 `/var/etc/chfs.ini`），因为 chfs 的命令行只支持 `-file`、`-path`、`-port`、`-version`
四个参数，账户权限、IP 过滤、日志等高级功能**只能通过配置文件下发**。

### 主要选项

| UCI 选项 | 说明 | 取值 |
|---|---|---|
| `enabled` | 开机自启与服务使能 | 0/1 |
| `port` | HTTP/WebDAV 监听端口 | 1-65535 |
| `path` | 共享根目录，多个用 `\|` 分隔 | 路径字符串 |
| `run_as` | 运行身份 | `root` / `nobody` |
| `anonymous` | 允许匿名访问（以 guest 身份） | 0/1 |
| `allow` | IP 白名单，多个用 `\|` 分隔，留空不限制 | 地址或网段 |
| `log_dir` | 操作日志目录，留空禁用 | 路径 |
| `session_timeout` | 会话超时（分钟） | 1-1440 |
| `folder_download` | 目录下载策略 | `disable` / `leaf` / `enable` |
| `file_remove` | 文件删除方式 | `1` 永久 / `2` chfs 回收站 / `3` 系统回收站 |
| `image_preview` | 图片缩略图 | 0/1 |
| `html_title` / `html_notice` | 页面标题 / 公告 | 字符串 |
| `ssl_cert` / `ssl_key` | HTTPS 证书与私钥路径（两者同时填写才启用 HTTPS） | 路径 |

### 账户段

```uci
config account
    option name 'admin'
    option password 'yourpassword'
    option rule_default 'w'
    list rule_r '/public'
    list rule_w '/upload'
    list rule_d 'none'
```

权限取值：`none`（禁止访问）、`r`（只读）、`w`（读写）、`d`（完全控制，含删除）。

`guest` 为内置访客账户，用于匿名访问，**不可删除**（界面已做删除保护）。

## 后端接口

ucode 后端通过 ubus 对象 `luci.chfs` 暴露 16 个方法。

### 服务与配置

| 方法 | 说明 |
|---|---|
| `read_config` | 读取 UCI 配置（含账户列表） |
| `write_config` | 写入 UCI 配置 |
| `init_action` | 服务操作：start / stop / restart / reload / enable / disable |
| `status` | 服务状态：运行中、PID、内存、监听端口、使能状态 |
| `read_ini` | 读取实际生成的 chfs.ini |
| `preview_ini` | 预览待生成的 chfs.ini 内容（不落盘） |
| `probe_listen` | 探测端口监听状态 |
| `probe_webdav` | 通过 PROPFIND 探测 WebDAV 可用性 |

### 内核管理

| 方法 | 说明 |
|---|---|
| `kernel_info` | 当前内核路径、大小、ELF 机器类型、架构是否匹配、SHA256 |
| `kernel_sources` | 探测候选下载源可用性 |
| `kernel_pending` | 列出待安装的内核文件 |
| `kernel_backups` | 列出已备份的内核 |
| `kernel_download` | 按白名单前缀下载指定 URL 到待安装区 |
| `kernel_install` | 校验后备份现有内核并安装 |
| `kernel_restore` | 从备份回滚 |
| `kernel_discard` | 丢弃待安装文件 |

## 内核管理

随包入库的内核覆盖 arm64 与 amd64 两种架构。当出现以下情况时，需要替换设备上的内核：

1. 目标架构未预置二进制（如 mipsle / armv7）；
2. 上游发布了新版本，不希望等待插件重新打包；
3. 随包二进制损坏或缺失。

插件提供两条补充路径：

- **一键下载**：从本仓库的 Release 资产下载对应架构的内核。信任锚点是本仓库且走 HTTPS，
  相比从上游 `http://iscute.cn` 明文下载显著更安全。下载源经白名单前缀校验，
  不接受任意 URL，避免沦为 SSRF 跳板。
- **手动上传**：在网页上自行上传内核文件。

无论哪条路径，文件都先落到 `/etc/luci-uploads` 待安装区，**不会直接覆盖运行中的内核**。
点击安装后按以下流程执行：

```
校验 (ELF 魔数 / e_machine 架构匹配 / 大小 100KB-64MB)
  -> 备份现有内核到 /etc/chfs/kernel-backup/chfs.<时间戳>
  -> 停止服务
  -> install -m0755 覆盖 /usr/bin/chfs
  -> 启动服务
  -> 任一步失败则自动回滚到备份
```

### 下载源与架构映射

`.github/workflows/release.yml` 在打 `v*` tag 或手动触发时，会把预置二进制发布为 Release 资产：

| 设备 `uname -m` | 资产名 | ELF e_machine |
|---|---|---|
| `aarch64` | `chfs-linux-arm64-<ver>` | 183 |
| `x86_64` | `chfs-linux-amd64-<ver>` | 62 |

下载源候选（按顺序探测）：

1. `https://github.com/LianXia233/luci-app-chfs/releases/download/<tag>/<资产>`
2. `https://github.com/LianXia233/luci-app-chfs/releases/latest/download/<资产>`
3. 上述两个地址经 `gh.acg2.mom` / `gh-proxy.com` / `ghfast.top` 镜像代理
4. `https://raw.githubusercontent.com/LianXia233/luci-app-chfs/<branch>/chfs/bin/<arch>/chfs`
   （及其 `gh.acg2.mom` 镜像）

设备侧优先使用 `curl`（GitHub Release 资产会 302 跳转到 Azure Blob，需 `-L` 跟随重定向），
`uclient-fetch` 作为兜底。注意：设备上的 `/usr/bin/wget` 通常是 `/bin/uclient-fetch` 的软链，
**不支持 `-S` 选项**。

## 安装

### apk 系统（ImmortalWrt / OpenWrt SNAPSHOT）

```sh
apk add --allow-untrusted ./chfs-3.1-r1.apk
apk add --allow-untrusted ./luci-app-chfs-1.0.0-r1.apk
apk add --allow-untrusted ./luci-i18n-chfs-zh-cn-*.apk

rm -f /tmp/luci-indexcache*; rm -rf /tmp/luci-modulecache/
/etc/init.d/rpcd reload
```

### ipk 系统（OpenWrt 24.10.x）

```sh
opkg install ./chfs-3.1-r1.ipk
opkg install ./luci-app-chfs-1.0.0-r1.ipk
opkg install ./luci-i18n-chfs-zh-cn-*.ipk

rm -f /tmp/luci-indexcache*; rm -rf /tmp/luci-modulecache/
/etc/init.d/rpcd reload
```

安装后菜单位于 **网络存储（NAS） → chfs 文件共享**。

## 国际化

源码中的 `_()` 使用**英文 msgid**，中文译文位于 `po/zh_Hans/luci-app-chfs.po`，
编译时由 `po2lmo` 生成 `usr/lib/lua/luci/i18n/luci-app-chfs.zh-cn.lmo`。

新增界面文案时请同步更新 po 文件，否则该条在中文环境下会回退显示英文。

> 为什么必须用英文 msgid：`po2lmo` 的 `print_msg()` 中有一条
> `if (key_id != val_id)` 的判定。若把中文直接写成 `_('共享根目录')`，
> msgid 与 msgstr 完全相同、哈希相同，该条会被静默跳过而不写入 `.lmo` 索引，
> 导致翻译在中文环境下大面积失效（实测条数从 125 掉到 35）。

## 构建产物

云编译一次性产出 **两种包格式 × 两个架构**，共 4 组 artifact：

| artifact 名称 | 包格式 | SDK | 目标平台 |
|---|---|---|---|
| `packages-apk-aarch64_cortex-a53` | apk | ImmortalWrt SNAPSHOT | mediatek/filogic |
| `packages-apk-x86_64` | apk | ImmortalWrt SNAPSHOT | x86/64 |
| `packages-ipk-aarch64_cortex-a53` | ipk | OpenWrt 24.10.5 | mediatek/filogic |
| `packages-ipk-x86_64` | ipk | OpenWrt 24.10.5 | x86/64 |

每组包含三个包（以 apk 为例）：

| 包 | 说明 |
|---|---|
| `chfs-3.1-r1.apk` | chfs 二进制本体 |
| `luci-app-chfs-1.0.0-r1.apk` | LuCI 应用（配置页、账户页、状态页、init 脚本、ucode 后端） |
| `luci-i18n-chfs-zh-cn-*.apk` | 简体中文翻译 |

### 包格式与 SDK 的对应关系

| 发行版 | 包格式 | 包管理器 | 索引 |
|---|---|---|---|
| OpenWrt 24.10.x | ipk | opkg | `Packages.gz` |
| OpenWrt SNAPSHOT / ImmortalWrt SNAPSHOT | apk | apk-tools 3.x | `packages.adb` |

ImmortalWrt SNAPSHOT SDK 使用 `gcc-14.4.0_musl`，与 ImmortalWrt 设备环境一致。

### 触发云编译

- 推送到 `main` 分支 或 发起 PR：自动构建全部 4 组，产物上传为 artifact。
- 打 `v*` tag 或手动运行并填写 `release_tag`：构建完成后自动创建 Release 并附带全部包；
  `release.yml` 同时把预置内核二进制发布为 Release 资产，供设备侧「一键下载」使用。

## 已知限制

- chfs 上游不提供源码，仅分发预编译二进制，因此无法在目标平台上自行交叉编译；
  支持的架构受上游发布范围限制。
- WebDAV 无独立开关，始终与 HTTP 共享端口与访问规则。
- 上游 HTTPS 证书过期，`PKG_SOURCE_URL` 使用 HTTP 协议。
- 内核管理仅校验「ELF 格式 + 架构匹配」，不做签名验证。信任锚点完全落在本仓库的可信性上，
  因此下载 URL 强制走白名单前缀。手动上传路径由用户自行保证文件来源可信。
- 设备上无 `curl` 且无 `uclient-fetch` 时，「一键下载」不可用，只能走手动上传。
- 替换内核会短暂中断服务（停止 → 覆盖 → 启动）。备份保留在 `/etc/chfs/kernel-backup`，
  由用户自行清理，插件不做自动回收。
