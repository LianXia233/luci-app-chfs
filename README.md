<div align="center">

# luci-app-chfs

**适用于 OpenWrt / ImmortalWrt 的 [chfs](http://iscute.cn/chfs) (CuteHttpFileServer) 现代图形化管理插件**

[![OpenWrt](https://img.shields.io/badge/OpenWrt-24.10.x-blue?logo=openwrt&logoColor=white)](#)
[![ImmortalWrt](https://img.shields.io/badge/ImmortalWrt-SNAPSHOT-orange?logo=openwrt&logoColor=white)](#)
[![LuCI Architecture](https://img.shields.io/badge/LuCI-JS%20%2B%20ucode-6f42c1)](#)
[![Package Format](https://img.shields.io/badge/Package-apk%20%7C%20ipk-success)](#)
[![Architecture](https://img.shields.io/badge/Arch-x86__64%20%7C%20aarch64__cortex--a53%20%7C%20aarch64__generic-informational)](#)

*基于 LuCI 原生 CSS 变量设计，无缝自适应明暗主题；前后端采用现代架构（客户端 JS 渲染 + ucode 后端），杜绝假状态与多余开销。*

<img src="docs/screenshots/01-settings.png" alt="chfs 服务设置界面" width="820">

---

</div>

## 📌 核心特性

- ⚡ **硬核真实状态探测**：拒绝虚假前端开关，全量状态基于底层探测（`pgrep` 运行检测、`/proc/net/tcp` 端口监听、`curl PROPFIND` WebDAV 端点探测）。
- 🔗 **一键直达 WebUI**：直观展示 chfs 前端入口，自动识别并拼接**当前运行期真实生效**的协议与端口（支持 HTTPS/端口偏差告警）。
- 📁 **精细化账户控制**：内置图形化账户管理，支持针对多路径粒度的权限划分（`禁止访问` / `只读` / `读写` / `完全控制`）。
- 🌐 **原生 WebDAV 支持**：完整兼容 chfs 1.10+ 内置 WebDAV，状态页一键复制挂载链接。
- 🛠️ **完整内核生命周期**：独立管理标签页，支持在线检测下载（多镜像代理白名单）与本地上传，提供 ELF 架构自动匹配、安装前自动备份与原子故障回滚。

---

## 界面预览

截图取自 ImmortalWrt SNAPSHOT 实机（LuCI Master + Aurora 主题）。为便于公开，图中账户密码已掩码、设备管理地址已替换为示例值。

### 服务设置

服务控制与运行状态探测、监听端口、共享根目录、运行身份、匿名访问、IP 白名单、目录下载策略、文件删除方式、会话超时，以及操作日志与 HTTPS 证书路径。

![服务设置](docs/screenshots/01-settings.png)

### 账户与权限

图形化账户管理，列出账户名、密码与默认权限；可针对具体子目录单独设定权限以覆盖默认值。

![账户与权限](docs/screenshots/02-accounts.png)

### 服务状态

全部指标来自底层真实探测：进程信息（PID / 内存 / 程序文件 / 配置文件）、端口监听状态、WebDAV 端点探测（含 HTTP 状态码与访问地址），以及设备实际读取的 ini 配置全文。

![服务状态](docs/screenshots/03-status.png)

### 内核管理

当前内核信息（设备架构、ELF `e_machine` 匹配结果、SHA256、预期版本）、一键检测下载源、手动上传、待安装文件与备份回滚。

![内核管理](docs/screenshots/04-kernel.png)

---

## ⚡ 快速安装

Release 资产按架构分目录，先按下表确认自己该取哪个目录里的包
（菜单位于 **网络存储 (NAS) → chfs 文件共享**）：

| 目录 | 适用设备 | 典型机型 |
|------|----------|----------|
| `x86_64/` | x86_64 软路由 / 虚拟机 | x86/64 目标、PVE / ESXi 虚拟机 |
| `aarch64_cortex-a53/` | MT798x（Filogic）等 64 位 ARM 路由 | H5000M、MT6000、BPI-R3 等 mediatek/filogic |
| `aarch64_generic/` | 通用 ARMv8 | armsr/armv8、RK35xx、多数通用 ARM 固件 |
| `all/` | 架构无关 | LuCI 界面与简体中文语言包，任意设备通用 |

> 目录名即 OpenWrt 的包架构名。设备上可用 `opkg print-architecture`（ipk）
> 或 `apk --print-arch`（apk）核对。

### 方式 A：apk 系统 (ImmortalWrt / OpenWrt SNAPSHOT)

```sh
# 以 x86_64 为例；aarch64_cortex-a53 / aarch64_generic 请换成对应目录
apk add --allow-untrusted ./x86_64/chfs-3.1-r1_x86_64.apk
apk add --allow-untrusted ./all/luci-app-chfs-1.0.0-r6_all.apk
apk add --allow-untrusted ./all/luci-i18n-chfs-zh-cn-0_all.apk

# 清除缓存并重载 RPC 服务
rm -f /tmp/luci-indexcache*; rm -rf /tmp/luci-modulecache/
/etc/init.d/rpcd reload
```

### 方式 B：ipk 系统 (OpenWrt 24.10.x)

```sh
# 以 x86_64 为例；aarch64_cortex-a53 / aarch64_generic 请换成对应目录
opkg install ./x86_64/chfs_3.1-r1_x86_64.ipk
opkg install ./all/luci-app-chfs_1.0.0-r6_all.ipk
opkg install ./all/luci-i18n-chfs-zh-cn_0_all.ipk

# 清除缓存并重载 RPC 服务
rm -f /tmp/luci-indexcache*; rm -rf /tmp/luci-modulecache/
/etc/init.d/rpcd reload
```

> 包管理器按包内控制信息识别包，与文件名无关，因此重命名后的
> `<name>-<version>_<arch>.apk` / `<name>_<version>_<arch>.ipk` 可直接安装。

---

## ⚙️ 配置参考

UCI 配置文件为 `/etc/config/chfs`，由 init 脚本在启动时自动渲染为 `/var/etc/chfs.ini`。

### 核心参数映射

| UCI 字段 | 类型 / 范围 | 默认值 | 作用说明 |
| --- | --- | --- | --- |
| `enabled` | `0` | `1` | `0` | 开机自启与服务总开关 |
| `port` | `1 - 65535` | `8080` | HTTP / WebDAV 共享监听端口 |
| `path` | 路径字符串 | - | 共享根目录，支持使用 `|` 分隔多个路径 |
| `run_as` | `root` | `nobody` | `nobody` | 进程安全执行身份 |
| `anonymous` | `0` | `1` | `1` | 允许 guest 访客身份匿名访问 |
| `allow` | IP / CIDR | - | 客户端 IP 白名单（多项用 `|` 分隔，留空不限制） |
| `folder_download` | `disable` | `leaf` | `enable` | `leaf` | 目录打包下载策略 |
| `file_remove` | `1` | `2` | `3` | `1` | 删除策略：`1` 永久 / `2` chfs 回收站 / `3` 系统回收站 |
| `image_preview` | `0` | `1` | `1` | 是否开启图片缩略图预加载 |
| `ssl_cert` / `ssl_key` | 文件绝对路径 | - | HTTPS 证书与密钥（**两者皆填写**时生效） |
| `log_dir` | 目录路径 | - | 操作日志存储目录（留空禁用） |
| `session_timeout` | `1 - 1440` (分钟) | - | 会话有效时间 |

### 账户段配置范例

```uci
config account
    option name 'admin'
    option password 'yourpassword'
    option rule_default 'w'       # 默认权限: none / r / w / d
    list rule_r '/public'         # /public 设为只读
    list rule_w '/upload'         # /upload 允许读写
    list rule_d 'none'            # 禁用删除权限

```

> [!NOTE]
> `guest` 为内置只读访客账户，用于匿名访问场景，界面已做安全保护**不可删除**。

---

## 🧭 系统设计与运行机制

### 1. WebUI 动态跳转解析逻辑

主界面的跳转链接根据当前运行事实动态组装（`协议://主机:端口/`），彻底杜绝脏配置造成的 404：

```
[LuCI 前端: hostname]  ──┐
[ini 解析: ssl.cert]   ──┼──> [ 真实生效 WebUI 链接 ] ──> 新标签页一键跳转
[ini 解析: port=]      ──┘

```

* **协议探测**：运行中检测 `/var/etc/chfs.ini` 行首 `ssl.cert=` 是否存在；未运行时取 UCI 配置中的双证书项。
* **端口校准**：运行中直接抓取 ini 内的 `port=`，若用户修改了端口但未重载服务，前端将呈现当前**实际监听端口**并附带**不一致告警提示**。
* **边界防误判**：正则表达式强制使用 `(^|\n)` 锚定行首，避免页面公告或目录名称包含 `ssl.cert=` 时触发误判。

### 2. 内核安全替换流程

独立标签页支持一键更新或手动上传内核，整体采用**事务式安全升级策略**：

```mermaid
graph TD
    A[选择下载源 / 上传文件] --> B[写入 /etc/luci-uploads]
    B --> C{静态安全检查}
    C -- 失败: 架构/魔数不匹配 --> D[中断并提示, 不影响现有服务]
    C -- 成功 --> E[自动备份至 /etc/chfs/kernel-backup/]
    E --> F[安全停止现有服务]
    F --> G[原子替换覆盖 /usr/bin/chfs]
    G --> H[启动新内核服务]
    H --> I{健康探测}
    I -- 成功 (HTTP 200) --> J[刷新页面展示新版本]
    I -- 失败 --> K[触发 trap 机制, 从备份瞬间回滚]

```

---

## 🏗️ 编译与源码架构

```
.
├── .github/workflows/
│   ├── build.yml                         # 云编译：apk/ipk × 三架构六矩阵构建 + 发布
│   └── release.yml                       # 手动工作流：向已有 Release 补发内核二进制
├── chfs/                                 # chfs 二进制包封装
│   ├── Makefile                          # 构建逻辑（优先预置，回退上游）
│   ├── extract-bin.sh                    # 二进制解压与规范化清洗
│   ├── bin-manifest.txt                  # 架构、体积与 sha256 校验清单
│   └── bin/                              # 预置二进制库（跳过外部下载）
│       ├── SHA256SUMS                    # 校验值列表
│       ├── arm64/chfs                    # 对应 aarch64
│       └── amd64/chfs                    # 对应 x86_64
├── tools/
│   ├── fetch-chfs.py                     # 自动化抓取上游二进制并同步清单
│   └── package-release.py                # 产物重命名 / SHA256SUMS / manifest / 发布说明
├── docs/screenshots/                     # README 界面预览图（ImmortalWrt 实机截取）
└── luci-app-chfs/                        # LuCI 现代架构应用源码
    ├── Makefile
    ├── htdocs/luci-static/resources/view/chfs/
    │   ├── main.js                       # 主配置视图
    │   ├── accounts.js                   # 账户管理视图
    │   ├── status.js                     # 运行状态视图
    │   ├── kernel.js                     # 内核升级与回滚管理
    │   └── chfs.css                      # 适配主题变量的自定义样式
    ├── po/zh_Hans/luci-app-chfs.po        # 简体中文本地化字典
    └── root/
        ├── etc/config/chfs               # UCI 默认定义
        ├── etc/init.d/chfs               # procd 服务脚本 (UCI -> ini 渲染)
        ├── etc/uci-defaults/99-luci-app-chfs
        └── usr/share/
            ├── luci/menu.d/              # 菜单挂载 (网络存储)
            ├── rpcd/acl.d/               # ACL 鉴权规则
            └── rpcd/ucode/luci.chfs      # ucode 后端 (提供 16 个 ubus RPC 接口)

```

### 本地编译指令

```sh
# 1. 复制源码包至 OpenWrt SDK
cp -r chfs <openwrt>/package/
cp -r luci-app-chfs <openwrt>/package/

# 2. 先构建 luci-base host 工具 (生成必须的 po2lmo 与 jsmin)
make package/luci-base/host/compile V=s

# 3. 编译应用包 (可配置关闭压缩提速)
make package/chfs/compile V=s
make package/luci-app-chfs/compile V=s \
    LUCI_MINIFY_JS=0 LUCI_MINIFY_CSS=0

```

* **关于 `po2lmo**`：`luci-base/src/Makefile` 内嵌 `contrib/lemon.c`，无需宿主机环境预装 lemon 即可编译。产物存放于 `staging_dir/hostpkg/bin/`。云编译环境会自动向 `staging_dir/host/bin/` 创建软链接以兼容 `luci.mk`。
* **跳过上游下载的正确姿势**：不可设置 `PKG_SKIP_DOWNLOAD`（会被 `include/package.mk` 覆盖），正确方式是在预置文件命中时将 `PKG_SOURCE_URL` **置空**。
* **上游连接规范**：上游 `iscute.cn` 的 HTTPS 证书长期过期，必须使用 `http://` 避免触发 SSL 握手阻断。

### 云编译矩阵

`build.yml` 用六个并行 job 覆盖「三架构 × 双格式」：

| 包格式 | SDK | 目标 target | 包架构 |
|--------|-----|-------------|--------|
| apk | ImmortalWrt SNAPSHOT | `x86/64` | `x86_64` |
| apk | ImmortalWrt SNAPSHOT | `mediatek/filogic` | `aarch64_cortex-a53` |
| apk | ImmortalWrt SNAPSHOT | `armsr/armv8` | `aarch64_generic` |
| ipk | OpenWrt 24.10.5 | `x86/64` | `x86_64` |
| ipk | OpenWrt 24.10.5 | `mediatek/filogic` | `aarch64_cortex-a53` |
| ipk | OpenWrt 24.10.5 | `armsr/armv8` | `aarch64_generic` |

五个关键设计：

1. **架构不靠猜**：`defconfig` 后从 `.config` 读出 `CONFIG_TARGET_ARCH_PACKAGES`
   并与矩阵声明比对，不一致立即失败 —— target 改名或选错 target 时不会静默产出错误架构的包。
2. **架构无关包只编一次**：`luci-app-chfs` 与 `luci-i18n-chfs-zh-cn` 是
   `LUCI_PKGARCH:=all`，三架构产物完全一致，故只在每种格式的一个 job 里编译；
   依赖的 `luci-base` host 工具（`po2lmo` / `jsmin`）也随之只构建一次。
3. **SDK 与 luci 源码带缓存**：稳定版 SDK 永久命中缓存，ImmortalWrt SNAPSHOT
   按 UTC 日期命中（snapshot 每日变化，不能长期复用旧包）。
4. **产物在 job 内即重命名**：apk 的文件名不含架构，三个架构 job 会产出同名
   `chfs-3.1-r1.apk`，不区分就无法在同一个 Release 中共存。
5. **架构无关包强制归入 `all/`**：apk 打包会把 `LUCI_PKGARCH:=all` 的包标成
   **构建目标架构**（实测 ImmortalWrt SNAPSHOT 产出 `arch = aarch64_generic`），
   而 ipk 会正确写 `Architecture: all`。这类包只在 `build_luci` 的那个 job 编一次，
   若照搬包内自报架构归档，`x86_64` 与 `aarch64_cortex-a53` 的用户就会拿不到界面包。
   故 `package-release.py` 在 `stage` 与 `finalize` 两处按同一口径把它归一为 `all/`。

### Release 资产结构

发布时由 `tools/package-release.py finalize` 统一汇总，资产按架构分目录：

```
v1.0.1/
├── x86_64/                 chfs-3.1-r1_x86_64.apk / chfs_3.1-r1_x86_64.ipk
├── aarch64_cortex-a53/     chfs-3.1-r1_aarch64_cortex-a53.apk / chfs_3.1-r1_aarch64_cortex-a53.ipk
├── aarch64_generic/        chfs-3.1-r1_aarch64_generic.apk / chfs_3.1-r1_aarch64_generic.ipk
├── all/                    luci-app-chfs-1.0.0-r6_all.apk / luci-app-chfs_1.0.0-r6_all.ipk
│                           luci-i18n-chfs-zh-cn-0_all.apk / luci-i18n-chfs-zh-cn_0_all.ipk
├── chfs-linux-arm64-3.1    内核二进制（LuCI「一键下载内核」的目标）
├── chfs-linux-amd64-3.1
├── SHA256SUMS              全部资产的校验值
└── manifest.json           机器可读清单（包名 / 版本 / 架构 / 大小 / SHA256）
```

> [!IMPORTANT]
> 资产分布在**架构子目录**中，因此 `softprops/action-gh-release` 的 `files`
> 必须写成 `release/**`。写成 `release/*` 时 glob 不递归，Release 里就只会出现
> 根目录的内核二进制与清单，安装包全部丢失。

发布流程同时做三件事：校验预置二进制（ELF 魔数 + `e_machine` + SHA256SUMS）、
生成发布说明、清理该 tag 下不属于本次产出的旧资产（可用 `prune_assets` 关闭）。

---

## ⚠️ 关键注意事项与排坑指南

> [!CAUTION]
> **空路径回退风险**：
> 当配置中的共享路径在设备上不存在时（如移动硬盘未挂载成功），chfs 进程会默认回退至**自身所在目录**（即 `/usr/bin`）作为共享根目录！此行为将导致系统二进制目录直接在网络中暴露。保存配置时请务必核验挂载点真实性。

> [!WARNING]
> **内核备份堆积**：
> 内核管理模块备份位于 `/etc/chfs/kernel-backup`，每次安装新内核均会生成完整快照，且不会做去重或数量上限回收（4 次操作约占用 32 MB 空间）。小容量闪存设备请定期手动清理旧备份。

1. **BusyBox 工具链缺失**：路由器环境中 BusyBox 不含 `install` 命令。原子替换统一采用 `chmod 0755` + `mv -f` 实现。
2. **ucode 语言陷阱**：
* `'use strict'` 下不存在全局 `undefined`，访问会抛出运行时错误；判断空值请使用 `=== null`。
* 自定义函数必须声明在调用代码之前，ucode **不具备变量与函数声明提升机制**。


3. **LuCI 视图组件坑位**：
* `E('button')` 生成的 DOM 默认 `type="submit"`，若放置在 form 内会导致整个页面刷新，自建交互按钮务必显式声明 `type="button"`。
* 避免使用 `cbi-button-apply` 类名，否则会被第三方主题（如 Mint 主题）无条件绑定保存-重载逻辑，导致实际点击事件被拦截。请统一使用 `cbi-button-action`。


4. **国际化哈希失效**：
* 源码中的 `_()` 必须使用**英文 msgid**。若使用中文作为键名，`po2lmo` 会在 `key_id == val_id` 时跳过索引构建，导致中文翻译大规模丢失。



---

## 📦 云端流水线与制品架构

项目通过 GitHub Actions 矩阵生成 4 类构建制品：

| 构建 Artifact 名称 | 封装格式 | 对应系统基底 | 适配目标平台 |
| --- | --- | --- | --- |
| `packages-apk-aarch64_cortex-a53` | **apk** | ImmortalWrt SNAPSHOT | mediatek/filogic (ARM64) |
| `packages-apk-x86_64` | **apk** | ImmortalWrt SNAPSHOT | x86/64 |
| `packages-ipk-aarch64_cortex-a53` | **ipk** | OpenWrt 24.10.x | mediatek/filogic (ARM64) |
| `packages-ipk-x86_64` | **ipk** | OpenWrt 24.10.x | x86/64 |

> [!TIP]
> **Release 竞态避免机制**：打 `v*` tag 时由 `build.yml` 独占创建 Release 并上传基础包；随后的内核二进制由 `release.yml` 通过手动调度（输入指定 tag）追加资产，规避 GitHub API 422 冲突。
