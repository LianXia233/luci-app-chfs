# 更新日志

本文件记录 luci-app-chfs 的所有重要变更。

版本号遵循 `MAJOR.MINOR.PATCH-rRELEASE`（对应 OpenWrt 的 `PKG_VERSION` 与 `PKG_RELEASE`），
格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

---

## [1.0.0] - 2026-09-19（首个正式 Release tag）

将代码状态 `1.0.0-r5` 打为首个正式 Release tag `v1.0.0`，并把内核二进制发布到
GitHub Releases，使设备侧「一键下载内核」的 4 个 Release 类下载源（GitHub Release 官方 /
gh.acg2.mom / gh-proxy / ghfast 镜像）从 404 变为可用。

### 新增

- **首个正式 Release tag `v1.0.0`**：对应 `PKG_VERSION 1.0.0` / `PKG_RELEASE 5` 的代码状态。
  推送该 tag 后由 `build.yml` 自动构建并发布插件包（apk + ipk，arm64 / amd64 两类架构）。
- **Apache-2.0 `LICENSE` 文件**：此前 Makefile 已声明 Apache-2.0，但仓库缺少实际的 LICENSE
  文件（GitHub 仓库页显示为无许可证）。本次补齐，与 `PKG_LICENSE` 声明对齐。

### 变更

- **`release.yml` 改为仅手动触发（不再跟随 `v*` tag 自动运行）**。
  - 背景：`build.yml` 与 `release.yml` 都会在 `v*` tag 推送时各自创建同名 Release
    （前者发插件包、后者发内核二进制），并发抢建会导致其中一方收到 GitHub 的
    `422 Release already exists` 而失败。
  - 新流程：tag 推送时由 `build.yml` 独占发布插件包；待其 Release 创建成功后，
    再手动运行 `Release Chfs Kernel` 并指定同一 tag，`release.yml` 以 `PATCH`
    方式向该 Release **追加**内核二进制资产，不再与 `build.yml` 冲突。
  - 内核资产名沿用 `chfs-linux-<arch>-3.1`，下载链路 `releases/latest/download/<资产>`
    因此可用（后端 `kernel_sources` 即使用该路径）。

### 发布资产

`v1.0.0` Release 包含：

| 资产 | 说明 |
| --- | --- |
| `chfs_3.1-1_*.apk` / `*.ipk` | chfs 二进制本体 |
| `luci-app-chfs_1.0.0-5_*.apk` / `*.ipk` | LuCI 应用 |
| `luci-i18n-chfs-zh-cn_*.apk` / `*.ipk` | 简体中文翻译 |
| `chfs-linux-arm64-3.1` | 内核二进制（aarch64） |
| `chfs-linux-amd64-3.1` | 内核二进制（x86_64） |
| `SHA256SUMS` | 内核二进制校验值 |

### 修正

- **`release.yml` 的发布步骤此前缺失 `files:` 参数**：「准备发布资产」已把内核二进制复制到 `dist/`，
  但发布步骤只更新了 Release 的标题与正文，从未上传 `dist/` 文件，导致内核资产始终未进入 Release、
  下载源持续 404。补上 `files: dist/*` 后，该工作流以 `PATCH` 向已存在的 `v1.0.0` Release
  追加 `chfs-linux-arm64-3.1` / `chfs-linux-amd64-3.1` / `SHA256SUMS`，且不清空 `build.yml` 已发布的插件包资产。

### 已知问题

- **内核二进制挂在 `latest` Release 上，存在后续被覆盖的风险**：后端 `kernel_sources`
  使用 `releases/latest/download/`，而 `latest` 是「最新的非预发布 Release」。
  若日后发布仅含插件包、不含内核的 `v1.0.1`，`latest` 会指向它，导致内核下载源再次 404。
  根治方案是把内核二进制固定发布到独立 tag（如 `v3.1`）并让后端改用
  `releases/download/v3.1/` 显式路径，本次暂未做（需改后端 + 重新部署验证），
  留待后续迭代。

---

## [1.0.0-r5] - 2026-09-19

在主配置页补上「一键跳转 WebUI」，并让界面上的端口一律反映服务的真实生效值。

### 新增

- **主配置页「WebUI 访问」行**：展示 chfs 网页界面的完整地址，并在新标签页一键打开。
  服务未运行时按钮禁用并提示先启动服务，避免点开一个必然连不上的地址。
  - 地址三部分的来源都经过刻意选择：协议取「证书与私钥同时非空」的判定结果；
    端口在运行中取**真实监听端口**；主机取当前访问 LuCI 的 `window.location.hostname`，
    不新增「设备地址」配置项，从根源上避免两处地址不一致。
- 后端 `service_status` 新增 `ini_port` 与 `ini_https`：运行中时从已生成的
  `/var/etc/chfs.ini` 解析出实际生效的端口与是否启用 HTTPS，供上述地址拼接使用。
  不新增 rpcd 方法，故 ACL 无需改动。

### 修复

- **「运行状态」行显示的端口可能与服务实际监听的端口不符**。该行此前读 UCI 的 `port`，
  而服务启动时已把配置固化进 `chfs.ini`；改了端口却没重启时，界面会显示新配置值。
  加入 WebUI 跳转按钮后这一点会直接暴露成自相矛盾 —— 同一张卡片里
  「端口: 9090」与按钮地址 `:8080` 并存。现将运行中的端口统一取真实生效值，
  配置与生效值不一致的事实仍由既有告警条说明。

### 变更

- ini 解析一律用 `(^|\n)` 锚定行首，不再裸匹配 `port=` / `ssl.cert=`：
  共享根目录写成 `/mnt/port=9090`、或页面公告里出现 `ssl.cert=` 字样时，
  裸匹配会把它们误当成真实取值（后者会导致地址被错误拼成 `https`）。
- `PKG_RELEASE` 由 4 提升到 5。

### 实测验证（ImmortalWrt SNAPSHOT / mediatek-filogic / aarch64_cortex-a53）

| 场景 | 结果 |
| --- | --- |
| 服务运行中 | 按钮地址 `http://192.168.88.1:8080/`，`cbi-button-action` + `type=button`，未被 mint 主题接管 |
| 点击跳转 | 新标签页地址与按钮一致，页面标题「chfs 文件共享」，成功加载 `chfs.min.js`（HTTP 200） |
| 改端口未重启 | UCI 设为 9090 而服务仍监听 8080 时，按钮地址与运行状态行**都是 8080**，并显示不一致告警 |
| HTTPS | ini 含行首 `ssl.cert=` 时地址变为 `https://192.168.88.1:8443/` |
| 服务已停 | 按钮禁用、样式降为 `cbi-button-neutral`，并给出「先启动服务」提示 |
| 解析反例 | 公告文本内含 `ssl.cert=` → `ini_https=false`；共享根目录含 `port=9090` → `ini_port=8080` |
| 回归 | 服务控制（停止 / 启动 / 重启）正常，PID 变化正确；页面无 JS 错误 |

> 排查提示：`ucode` 的 `match()` 支持 `(^|\n)` 行首锚定，但不支持 `.exec()`；
> 验证时可用伪造的 `/var/etc/chfs.ini` 直接驱动 `ubus call luci.chfs status`，
> 无需真的改动服务配置（校验完务必还原）。

### 已知问题

- **服务状态页的探测与地址仍按 UCI 配置端口进行**。`probe_listen` 与 `probe_webdav`
  都以 UCI 的 `port` 为目标端口，因此在「改了端口但未重启」时，它们探测的是新端口，
  必然得到「未监听 / 无法连接」，而复制出来的 WebDAV 地址也指向尚未生效的端口。
  该页会同时显示「配置端口与运行实例不一致」的告警，语义上不算错，但与本次
  主配置页改用真实生效值的口径不统一。后续可让这两个探测同样优先取 `ini_port`。

## [1.0.0-r4] - 2026-09-19

本次补齐内核管理的界面入口（r2/r3 只做了后端方法，界面上无从操作），
并修掉一个由主题按钮接管引发的缺陷 —— 它同时影响了主配置页已有的「启动」按钮。

### 新增

- **内核管理独立标签页**（`view/chfs/kernel.js`，菜单节点 `admin/nas/chfs/kernel`）
  - 当前内核卡片：设备架构、内核分支、程序路径、大小、ELF `e_machine` 与架构匹配状态、
    SHA256、预期版本；内核缺失时给出告警并提供入口。
  - 一键下载卡片：点「检测下载源」后逐个探测 6 个候选源（HEAD 请求），列出可达性与
    HTTP 状态码，仅可用源可点击下载。探测不放在 `load()` 中，避免 6 次网络探测拖慢首屏。
  - 手动上传卡片：经 `/cgi-bin/cgi-upload` 上传到 `/etc/luci-uploads`，带进度百分比，
    文件名做字符消毒。
  - 待安装文件卡片：`非 ELF` 或架构不符的文件禁用安装按钮，避免无谓的服务重启。
  - 备份卡片：列出历史备份，可一键回滚。
  - 所有写操作均需二次确认；成功时刷新页面以拉取真实状态，**失败时不刷新**，
    否则错误信息会被立即冲掉。
- `po/zh_Hans` 增补 72 条界面文案翻译。

### 修复

- **主题接管 `cbi-button-apply`，导致自定义动作按钮失效**（影响面不止内核管理页）
  - 现象：点击内核管理页的「安装」，确认框不出现，页面直接重新加载；
    而同一页的「回滚」（`cbi-button-negative`）与「下载」（动态插入的 `cbi-button-apply`）
    却都正常。
  - 定位：mint 主题的 `/www/luci-static/resources/menu-mint.js` 会执行

    ```js
    form.querySelectorAll('button.cbi-button-save, input.cbi-button-save, ' +
        'button.cbi-button-apply, input.cbi-button-apply').forEach((btn) => {
        if (btn.getAttribute('data-mint-save-bound')) return;
        btn.setAttribute('data-mint-save-bound', '1');
        btn.addEventListener('click', (ev) => this.mintSave(ev));
    });
    ```

    即把表单内所有 `cbi-button-apply` 按钮改写为「保存并应用」（ubus set+commit 后 reload）。
    真机对照确认：安装按钮带 `data-mint-save-bound` 标记，回滚按钮没有，与现象完全对应。
  - 为什么「下载」侥幸可用：它是点「检测下载源」之后才插入 DOM 的，错过了主题的那次扫描。
    这属于偶然，不能依赖。
  - **同一问题也存在于主配置页的「启动」按钮**：服务未运行时该按钮渲染为
    `cbi-button-apply`，于是点击「启动」实际触发的是保存而非启动 —— 一个此前未被发现的既有缺陷。
  - 修复：全部自建按钮改用 `cbi-button-action`，并显式声明 `type="button"`
    （双保险：同时杜绝 LuCI 主题把视图包进 `<form>` 时默认 `type=submit` 带来的表单提交）。
    覆盖 `kernel.js`（9 个）、`main.js`（1 个）、`status.js`（2 个）。

### 变更

- `Notes` 的 msgid 改为 `Safety notes`：`Notes` 是 LuCI 基础翻译表中的通用词（被译为「备注」），
  与「注意事项」语义不符，改用独特 msgid 避免冲突。
- `PKG_RELEASE` 由 1 提升到 4，与 CHANGELOG 的 `rN` 编号对齐。

### 实测验证（ImmortalWrt SNAPSHOT / mediatek-filogic / aarch64_cortex-a53）

全部通过浏览器 UI 操作，并同时以真实 LuCI 会话调用 `/ubus/` 读后端值交叉校验：

| 步骤 | 结果 |
| --- | --- |
| 一键下载（GitHub Raw 源） | 8388608 字节，sha256 `78ed31c1…`，与 `chfs/bin/SHA256SUMS` 一致 |
| 手动上传 | 文件落到 `/etc/luci-uploads/chfs`，大小与源文件一致 |
| 安装内核 | `/usr/bin/chfs` 由 8344802 字节换为 8388608 字节，sha256 `00b27ac0…` → `78ed31c1…`；服务自动恢复运行；安装前自动生成备份 |
| 回滚备份 | 内核复原为 8344802 字节 / sha256 `00b27ac0…`，服务运行中，备份文件保留 |
| 删除待安装文件 | 待安装区清空 |
| 服务控制按钮 | 停止 → 启动 → 重启 全部生效，重启后 PID 变化 |
| 配置保存 | 合法配置保存成功；非法端口被拒并返回「端口范围必须是 1-65535」；非法 IP 被拒 |
| 标签页导航 | 四个标签页互通，当前页高亮正确 |
| 页面控制台 | 无 JS 错误 |

> 排查提示：判断按钮是否被主题接管，可在浏览器控制台执行
> `document.querySelectorAll('[data-mint-save-bound]')`。
> 判断页面是否被表单提交重载，可注入 `window.addEventListener('error', ...)` 后观察
> `document` 上的标记是否随点击消失。

### 云编译产物端到端验证

以上验证基于手工部署文件。进一步用云编译产物（GitHub Actions run #7）在真机复核：

| 项目 | 结果 |
| --- | --- |
| 产物 | `luci-app-chfs-1.0.0-r4.apk`、`luci-i18n-chfs-zh-cn-0.apk`（apk / aarch64_cortex-a53 / immortalwrt-snapshot） |
| 安装 | `luci-app-chfs` 由 `1.0.0-r1` 升级到 `1.0.0-r4`；`/etc/config/chfs` 作为配置文件未被覆盖（apk 另存为 `.apk-new`，符合预期） |
| 翻译 | `luci-app-chfs.zh-cn.lmo` 由 6200 字节增至 9768 字节，界面文案（含菜单与按钮）全部显示为中文 |
| 前端资源 | 包内 JS 经 `jsmin` 压缩（`kernel.js` 19135 → 13859 字节），功能与压缩前完全一致 |
| 功能回归 | 下载 / 上传 / 安装 / 回滚 / 清理 全流程再次通过；服务控制与配置保存正常 |
| 菜单 | 四个标签页互通；发现 `Kernel management` 一项因未纳入 po 而显示英文，本次一并补入 |

> 两点提醒：
> 1. CI 会对 JS 做 minify，因此包内文件与仓库源文件字节数不同属正常现象，
>    **不能以 md5 是否一致来判断包内容是否正确**，应通过真机功能验证。
> 2. LuCI 用同一个翻译域翻译菜单标题，`menu.d/*.json` 里的 `title` 也必须出现在 po 中，
>    否则界面上会残留英文。

### 云编译产物复验（run #8：菜单翻译修复）

针对上表最后一项发现的 `Kernel management` 残留英文，把菜单标题补进 po 后重跑流水线，
再取新产物装机复核：

| 项目 | 结果 |
| --- | --- |
| 产物 | `luci-app-chfs-1.0.0-r4.apk`、`luci-i18n-chfs-zh-cn-0.apk`（run #8，commit `bc2a69d1`） |
| 翻译 | `luci-app-chfs.zh-cn.lmo` 由 9768 增至 9796 字节 |
| 标签页 | 四个页面均显示「服务设置 / 账户与权限 / 服务状态 / 内核管理」，英文残留为 0 |
| 页面文案 | 卡片名、按钮、说明文本全部为中文；仅 `ImmortalWrt SNAPSHOT`、`GitHub` 等专有名词保留原文 |
| 功能回归 | 下载 / 上传 / 安装 / 回滚 / 清理 五步闭环再次全通过；服务控制（停止 / 启动 / 重启）正常，PID 变化正确 |
| 控制台 | 四个页面均无失败请求与 JS 错误 |

> 说明：`/cgi-bin/luci/` 在登录阶段会出现一次 403（会话重定向），属 LuCI 自身行为，
> 与插件无关；四个插件页面本身无任何 4xx/5xx。

### 已知问题

- **内核备份会重复累积**。每次「安装」都会无条件复制一份当前内核到
  `/etc/chfs/kernel-backup/`，既不按内容去重，也没有保留数量上限。
  同一份内核被反复安装（例如反复试验下载是否正常）时，会生成若干字节完全相同的备份。
  实测连续 4 次安装后积累了 4 份 sha256 均为 `00b27ac0…` 的 7.96 MB 备份，占用约 31.9 MB。
  首次安装前才需要严格留存原件，后续可考虑：内容相同则跳过备份，或只保留最近 N 份。
  当前版本请留意手工清理旧备份。

## [1.0.0-r3] - 2026-09-19

本次修复让内核管理功能真正可用。r2 引入的 8 个方法中有 4 个带参方法
（download / install / restore / discard）一调用即失败；另外「保存配置」也存在同类问题。

### 修复

- **严格模式下访问 `undefined`，导致 4 个带参方法全部失败**
  - 现象：`kernel_download` / `kernel_install` / `kernel_restore` / `kernel_discard`
    调用后 rpcd 返回 `Unknown error`；而 4 个无参方法（info / sources / pending /
    backups）以及既有的 `init_action` 均正常。
  - 根因：文件第 5 行有 `'use strict';`，而 **ucode 没有 `undefined` 这个值** ——
    它既不是关键字也不是内置变量，而是一个未声明的标识符，严格模式下访问即致命错误
    `access to undeclared variable undefined`。
  - 为什么只影响带参方法：这 4 个方法的参数校验首行都写作
    `x === null || x === undefined || ...`。ubus 传入参数时 `x === null` 为假，
    短路失效，进而求值 `x === undefined` 触发错误；不传参数时 `x === null` 为真
    直接短路，所以看不出问题。
  - 同一写法也存在于 `validate_port()`，因此 **保存配置**（`write_config` 传入非空端口）
    同样会失败 —— 这是一个此前未被发现的潜伏缺陷，本次一并修掉。
  - 修复：删除全部 `|| x === undefined` 子句。ucode 中未传参即为 `null`，
    单判 `=== null` 语义等价且完备。
  - 排查提示：`ucode -c` 编译检查会通过（它只做语法检查），运行时照样报错；
    定位手段是在方法注册处注入 try/catch 打印 `e.message`。

- **设备上没有 `install` 命令，安装内核失败（退出码 127）**
  - 根因：安装逻辑用 `install -m0755 <src> <prog>`，但 BusyBox 不含该 applet，
    设备上也没有独立的 `install`。
  - 修复：改用 `chmod 0755` + `mv -f`。`mv` 在同一分区是原子的 inode 替换，
    比 `cp` 覆盖运行中的可执行文件更安全，且只依赖 BusyBox 自带命令。

- **安装失败后服务被遗留在停止状态（比安装失败本身更严重）**
  - 根因有两层：
    1. 安装脚本以 `set -e` 开头，`install` 失败即退出，后面的
       `/etc/init.d/chfs start` 根本没执行；回滚分支同样用 `install`，一并失败，
       于是 `rolled_back` 恒为 `false`。
    2. 改为 ucode 分步调用后，又踩到 **ucode 函数声明顺序敏感**：把
       `wait_chfs_down()` 定义在 `chfs_running()` 之前，前者调用后者时后者尚未声明，
       报 `access to undeclared variable chfs_running`，异常冒泡出 rpcd，
       服务同样停在关闭状态。
  - 修复：把「停服务 → 等进程退出 → 替换 → 启服务」整体收进一段 shell，
    用 `trap "$INIT start" EXIT INT TERM` 兜底 —— 无论脚本正常结束、出错退出
    还是被信号打断，服务都会被拉起。ucode 侧只做参数校验与结果判定，
    不再跨自定义函数调用。

- **ACL 未覆盖新增方法**
  - 补全 `kernel_*` 8 个方法的授权，并新增 `/etc/luci-uploads/*` 的 read/write
    与 `/etc/chfs/kernel-backup/*` 的读写条目。
  - `/etc/luci-uploads/*` 的 write 是前端上传（`cgi-upload`）的必需项 ——
    cgi-io 会按 session 的 ACL 校验目标路径。

### 变更

- `luci.chfs` 新增 `swap_kernel(from, to, consume)` 辅助函数，统一承载
  安装（`consume=true`，走 `mv`）与还原（`consume=false`，走 `cp`）。
  它必须定义在调用方之前 —— ucode 的函数声明没有提升。

### 实测验证（ImmortalWrt SNAPSHOT / mediatek-filogic / aarch64_cortex-a53）

| 方法 | 输入 | 结果 |
| --- | --- | --- |
| `kernel_info` | — | 内核路径、大小、e_machine、sha256、架构匹配均正确 |
| `kernel_sources` | — | 探测 6 个源，Raw 源返回 200，fetcher 识别为 curl |
| `kernel_download` | 本仓库 Raw URL | 8 MB / 1.6 s，sha256 与 `chfs/bin/SHA256SUMS` 一致 |
| `kernel_pending` | — | 正确列出待安装文件及其元数据 |
| `kernel_install` | 待安装文件 | 2.36 s，`SWAP_OK`，服务自动重启 |
| `kernel_backups` | — | 正确列出备份及 sha256 |
| `kernel_restore` | 备份文件名 | 2.34 s，内核完全复原，备份文件保留 |
| `kernel_discard` | 不存在的文件 | 返回业务错误「文件不存在」而非异常 |

安全边界实测：

- `kernel_install` 传 `/tmp/evil` → 拒绝，返回「非法的内核文件路径」
- `kernel_download` 传白名单外 URL → 拒绝，返回「下载地址不在允许列表内」
- 安装与回滚后均验证：HTTP 200、WebDAV 端点返回 401（存在且要求认证）、
  `probe_listen` 确认 8080 监听正常

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

[1.0.0-r3]: https://github.com/LianXia233/luci-app-chfs/releases/tag/v1.0.0
[1.0.0-r2]: https://github.com/LianXia233/luci-app-chfs/releases/tag/v1.0.0
[1.0.0-r1]: https://github.com/LianXia233/luci-app-chfs/releases/tag/v1.0.0
