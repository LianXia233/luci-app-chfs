// chfs 后端接口
// 提供配置读写、参数校验、服务控制与状态探测能力。
// 由 rpcd-mod-ucode 加载, 前端通过 ubus 对象 'luci.chfs' 调用。

'use strict';

import { cursor } from 'uci';
import { readfile, stat, popen } from 'fs';

const UCI_PACKAGE = 'chfs';
const GEN_INI = '/var/etc/chfs.ini';
const PROG = '/usr/bin/chfs';
const INIT_SCRIPT = '/etc/init.d/chfs';

// 取值白名单
// 依据 ucode 官方文档, `in` 运算符对数组执行严格相等比较,
// 即 `value in array` 可直接用于成员判断, 无需自定义辅助函数.
const VALID_FOLDER_DOWNLOAD = [ 'disable', 'leaf', 'enable' ];
const VALID_RULE = [ 'none', 'r', 'w', 'd' ];
const VALID_FILE_REMOVE = [ '1', '2', '3' ];
const VALID_ACTIONS = [ 'start', 'stop', 'restart', 'reload', 'enable', 'disable' ];
const WEBDAV_OK_CODES = [ '200', '207', '301', '302', '401', '403', '405' ];

// ---------------------------------------------------------------------------
// 参数校验规则
// ---------------------------------------------------------------------------

function validate_port(port) {
	if (port === null || port === undefined || port === '')
		return { ok: false, msg: '端口不能为空' };

	const s = '' + port;

	if (match(s, /[^0-9]/))
		return { ok: false, msg: '端口只能包含数字' };

	const n = +s;
	if (n < 1 || n > 65535)
		return { ok: false, msg: '端口范围必须是 1-65535' };

	if (n < 1024)
		return { ok: true, warn: true, msg: '端口小于 1024 属特权端口, 需 root 身份运行' };

	return { ok: true };
}

function validate_paths(pathstr) {
	if (!pathstr || pathstr === '')
		return { ok: false, msg: '共享根目录不能为空' };

	let parts = split('' + pathstr, '|');
	let missing = [];
	let count = 0;

	for (let p in parts) {
		p = trim(p);
		if (p === '') continue;
		count++;

		let st = stat(p);
		if (st == null || st.type !== 'directory')
			push(missing, p);
	}

	if (count === 0)
		return { ok: false, msg: '共享根目录不能为空' };

	if (length(missing) > 0)
		return { ok: true, warn: true, msg: '以下目录不存在或不是目录: ' + join(', ', missing) };

	return { ok: true };
}

function validate_allow(allowstr) {
	if (!allowstr || allowstr === '')
		return { ok: true };

	let parts = split('' + allowstr, '|');
	let bad = [];

	for (let p in parts) {
		p = trim(p);
		if (p === '') continue;
		if (!match(p, /^[0-9a-fA-F:.]+$/))
			push(bad, p);
	}

	if (length(bad) > 0)
		return { ok: false, msg: 'IP 规则格式非法: ' + join(', ', bad) };

	return { ok: true };
}

function validate_session_timeout(v) {
	const s = '' + (v ?? '');

	if (s === '' || match(s, /[^0-9]/))
		return { ok: false, msg: '会话超时必须是整数分钟' };

	const n = +s;
	if (n < 1 || n > 1440)
		return { ok: false, msg: '会话超时范围是 1-1440 分钟' };

	return { ok: true };
}

// ---------------------------------------------------------------------------
// 读取配置
// ---------------------------------------------------------------------------

const MAIN_DEFAULTS = {
	enabled: '0',
	port: '8080',
	bind_addr: '',
	path: '/mnt/sda1',
	run_as: 'root',
	allow: '',
	anonymous: '1',
	log_path: '',
	html_title: 'chfs 文件共享',
	html_notice: '',
	image_preview: '0',
	folder_download: 'enable',
	session_timeout: '30',
	file_remove: '1',
	ssl_cert: '',
	ssl_key: '',
	syslog: '1',
	webdav_show: '1'
};

function read_config() {
	let uci = cursor();
	let main = {};
	let accounts = [];

	uci.load(UCI_PACKAGE);

	for (let k, v in MAIN_DEFAULTS) {
		let cur = uci.get(UCI_PACKAGE, 'main', k);
		main[k] = (cur == null) ? v : cur;
	}

	uci.foreach(UCI_PACKAGE, 'account', function(s) {
		push(accounts, {
			'.name': s['.name'],
			name: s.name ?? '',
			password: s.password ?? '',
			rule_default: s.rule_default ?? 'r',
			rule_none: s.rule_none ?? '',
			rule_r: s.rule_r ?? '',
			rule_w: s.rule_w ?? '',
			rule_d: s.rule_d ?? ''
		});
	});

	return { main, accounts };
}

// ---------------------------------------------------------------------------
// 写入配置, 校验失败整体拒绝
// ---------------------------------------------------------------------------

function write_config(payload) {
	if (type(payload) !== 'object' || payload == null)
		return { ok: false, msg: '请求数据格式非法' };

	let main = payload.main;
	let accounts = payload.accounts;

	if (type(main) !== 'object' || main == null)
		return { ok: false, msg: '缺少主配置段' };

	let errors = [];

	let r_port = validate_port(main.port);
	if (!r_port.ok) push(errors, '端口: ' + r_port.msg);

	let r_path = validate_paths(main.path);
	if (!r_path.ok) push(errors, '共享目录: ' + r_path.msg);

	let r_allow = validate_allow(main.allow);
	if (!r_allow.ok) push(errors, 'IP 过滤: ' + r_allow.msg);

	let r_timeout = validate_session_timeout(main.session_timeout);
	if (!r_timeout.ok) push(errors, '会话超时: ' + r_timeout.msg);

	if (!(main.folder_download in VALID_FOLDER_DOWNLOAD))
		push(errors, '下载策略: 取值必须是 disable / leaf / enable');

	if (!(main.file_remove in VALID_FILE_REMOVE))
		push(errors, '删除模式: 取值必须是 1 / 2 / 3');

	let has_cert = (main.ssl_cert ?? '') !== '';
	let has_key = (main.ssl_key ?? '') !== '';

	if (has_cert != has_key)
		push(errors, 'HTTPS: 证书与私钥必须同时填写或同时留空');

	if (has_cert && has_key) {
		for (let f in [ 'ssl_cert', 'ssl_key' ]) {
			let p = main[f] ?? '';
			let st = stat(p);
			if (st == null || st.type !== 'file')
				push(errors, 'HTTPS: 文件不存在 - ' + p);
		}
	}

	if (type(accounts) === 'array') {
		let seen = {};
		for (let a in accounts) {
			let nm = trim(a.name ?? '');

			if (nm === '') {
				push(errors, '账户名不能为空');
				continue;
			}

			if (seen[nm] != null)
				push(errors, '账户名重复: ' + nm);
			else
				seen[nm] = true;

			if (!(a.rule_default in VALID_RULE))
				push(errors, '账户 ' + nm + ': 默认权限取值非法');
		}
	}

	if (length(errors) > 0)
		return { ok: false, msg: '配置校验未通过', errors };

	let uci = cursor();
	uci.load(UCI_PACKAGE);

	let strkeys = [
		'port', 'bind_addr', 'path', 'run_as', 'allow',
		'log_path', 'html_title', 'html_notice', 'folder_download',
		'session_timeout', 'file_remove', 'ssl_cert', 'ssl_key'
	];
	let boolkeys = [ 'enabled', 'anonymous', 'image_preview', 'syslog', 'webdav_show' ];

	for (let k in strkeys)
		uci.set(UCI_PACKAGE, 'main', k, '' + (main[k] ?? ''));

	for (let k in boolkeys) {
		let v = main[k];
		uci.set(UCI_PACKAGE, 'main', k,
			(v === '1' || v === 1 || v === true) ? '1' : '0');
	}

	if (type(accounts) === 'array') {
		let existing = [];
		uci.foreach(UCI_PACKAGE, 'account', function(s) {
			push(existing, s['.name']);
		});

		for (let n in existing)
			uci.delete(UCI_PACKAGE, n);

		let idx = 0;
		for (let a in accounts) {
			let sec = 'account_' + idx;
			idx++;

			uci.set(UCI_PACKAGE, sec, 'account');
			uci.set(UCI_PACKAGE, sec, 'name', trim(a.name ?? ''));
			uci.set(UCI_PACKAGE, sec, 'password', '' + (a.password ?? ''));
			uci.set(UCI_PACKAGE, sec, 'rule_default', a.rule_default ?? 'r');
			uci.set(UCI_PACKAGE, sec, 'rule_none', '' + (a.rule_none ?? ''));
			uci.set(UCI_PACKAGE, sec, 'rule_r', '' + (a.rule_r ?? ''));
			uci.set(UCI_PACKAGE, sec, 'rule_w', '' + (a.rule_w ?? ''));
			uci.set(UCI_PACKAGE, sec, 'rule_d', '' + (a.rule_d ?? ''));
		}
	}

	uci.commit(UCI_PACKAGE);

	let warnings = [];
	if (r_port.warn) push(warnings, r_port.msg);
	if (r_path.warn) push(warnings, r_path.msg);

	return { ok: true, warnings };
}

// ---------------------------------------------------------------------------
// 服务控制
// ---------------------------------------------------------------------------

function init_action(action) {
	if (!(action in VALID_ACTIONS))
		return { ok: false, msg: '不支持的操作: ' + action };

	let res = popen(INIT_SCRIPT + ' ' + action + ' 2>&1');
	let out = res.read('all') ?? '';
	let code = res.close();

	if (code != 0)
		return { ok: false, msg: trim('' + out) || ('操作失败, 退出码 ' + code) };

	return { ok: true, output: trim('' + out) };
}

function service_status() {
	let res = popen('pgrep -f "' + PROG + ' -file" >/dev/null 2>&1; echo $?');
	let out = trim('' + (res.read('all') ?? '1'));
	res.close();

	let running = (out === '0');
	let st = { running };

	if (running) {
		let p1 = popen('pidof chfs 2>/dev/null | head -n1');
		let pid = trim('' + (p1.read('all') ?? ''));
		p1.close();

		if (pid !== '') {
			st.pid = pid;

			let p2 = popen('awk \'/VmRSS/{print $2}\' /proc/' + pid + '/status 2>/dev/null');
			let rss = trim('' + (p2.read('all') ?? ''));
			p2.close();

			if (rss !== '')
				st.mem_mb = '%.1f'.format((+rss) / 1024);
		}
	}

	let uci = cursor();
	uci.load(UCI_PACKAGE);

	st.enabled = (uci.get(UCI_PACKAGE, 'main', 'enabled') ?? '0') === '1';
	st.port = uci.get(UCI_PACKAGE, 'main', 'port') ?? '8080';

	let bst = stat(PROG);
	st.binary_ok = (bst != null);

	let ist = stat(GEN_INI);
	st.ini_exists = (ist != null);

	// ini 中的端口与 UCI 不一致, 说明改过配置但未重启
	if (st.ini_exists) {
		let content = readfile(GEN_INI) ?? '';
		let re = regexp(/port=([0-9]+)/);
		let m = re.exec(content);

		if (m != null && m[1] != st.port)
			st.port_mismatch = true;
	}

	return st;
}

function read_ini() {
	if (stat(GEN_INI) == null)
		return { ok: false, msg: '配置文件尚未生成, 请先启动一次服务' };

	return { ok: true, content: readfile(GEN_INI) ?? '' };
}

// 实时渲染 ini 预览, 不写盘
function preview_ini(payload) {
	let main = (payload != null && type(payload.main) === 'object') ? payload.main : {};
	let accounts = (payload != null && type(payload.accounts) === 'array') ? payload.accounts : [];
	let lines = [];

	push(lines, '# 预览内容, 未写入磁盘');
	push(lines, 'port=' + (main.port ?? ''));
	push(lines, 'path=' + (main.path ?? ''));
	push(lines, 'allow=' + (main.allow ?? ''));
	push(lines, 'log=' + (main.log_path ?? ''));
	push(lines, 'html.title=' + (main.html_title ?? ''));
	push(lines, 'html.notice=' + (main.html_notice ?? ''));
	push(lines, 'image.preview=' + ((main.image_preview === '1') ? 'true' : 'false'));
	push(lines, 'folder.download=' + (main.folder_download ?? 'enable'));
	push(lines, 'session.timeout=' + (main.session_timeout ?? '30'));
	push(lines, 'file.remove=' + (main.file_remove ?? '1'));

	if ((main.ssl_cert ?? '') !== '' && (main.ssl_key ?? '') !== '') {
		push(lines, 'ssl.cert=' + main.ssl_cert);
		push(lines, 'ssl.key=' + main.ssl_key);
	}

	for (let a in accounts) {
		push(lines, '');
		push(lines, '[' + (a.name ?? '') + ']');
		push(lines, 'password=' + (a.password ?? ''));
		push(lines, 'rule.default=' + (a.rule_default ?? 'r'));

		if ((a.rule_none ?? '') !== '') push(lines, 'rule.none=' + a.rule_none);
		if ((a.rule_r ?? '') !== '')    push(lines, 'rule.r=' + a.rule_r);
		if ((a.rule_w ?? '') !== '')    push(lines, 'rule.w=' + a.rule_w);
		if ((a.rule_d ?? '') !== '')    push(lines, 'rule.d=' + a.rule_d);
	}

	return { ok: true, content: join('\n', lines) + '\n' };
}

// ---------------------------------------------------------------------------
// 连通性探测
// ---------------------------------------------------------------------------

function probe_listen() {
	let uci = cursor();
	uci.load(UCI_PACKAGE);

	let port = uci.get(UCI_PACKAGE, 'main', 'port') ?? '8080';

	let res = popen('netstat -ltn 2>/dev/null | grep -c ":' + port + ' "');
	let cnt = trim('' + (res.read('all') ?? '0'));
	res.close();

	return { port: +port, listening: ((+cnt) > 0) };
}

// 探测 WebDAV 端点
// chfs 的 WebDAV 与 HTTP 共用端口, 路径固定为 /webdav, 无独立开关
// 返回码语义: 207 Multi-Status 为 WebDAV 正常响应 ;
//             401/403 表示端点存在但需认证或受限 ;
//             000 表示连接失败
function probe_webdav() {
	let uci = cursor();
	uci.load(UCI_PACKAGE);

	let port = uci.get(UCI_PACKAGE, 'main', 'port') ?? '8080';
	let cert = uci.get(UCI_PACKAGE, 'main', 'ssl_cert') ?? '';
	let key = uci.get(UCI_PACKAGE, 'main', 'ssl_key') ?? '';

	// 与 init 脚本保持一致: 证书与私钥同时存在才视为启用 HTTPS
	let scheme = (cert !== '' && key !== '') ? 'https' : 'http';

	let cmd = 'curl -s -o /dev/null -w "%{http_code}" -k --max-time 5 ' +
		'-X PROPFIND -H "Depth: 0" ' + scheme + '://127.0.0.1:' + port + '/webdav 2>/dev/null';

	let res = popen(cmd);
	let code = trim('' + (res.read('all') ?? ''));
	res.close();

	let available = (code in WEBDAV_OK_CODES);

	let out = {
		available,
		http_code: code,
		scheme,
		port: +port,
		url: scheme + '://<主机地址>:' + port + '/webdav'
	};

	if (!available) {
		if (code === '000' || code === '')
			out.msg = '无法连接, 请确认服务已启动且端口正确';
		else
			out.msg = 'WebDAV 端点返回异常状态码 ' + code;
	}
	else if (code === '401' || code === '403') {
		out.msg = '端点存在, 需使用有效账户认证后访问';
	}
	else {
		out.msg = 'WebDAV 端点响应正常';
	}

	if (scheme === 'https')
		out.tip = 'WebDAV 客户端通常不信任自签名证书, 建议使用受信任证书';

	return out;
}

// ---------------------------------------------------------------------------
// ubus 对象声明
// ---------------------------------------------------------------------------

return {
	luci: {
		chfs: {
			read_config: {
				call: function() { return read_config(); }
			},
			write_config: {
				args: { payload: {} },
				call: function(req) { return write_config(req.args.payload); }
			},
			init_action: {
				args: { action: '' },
				call: function(req) { return init_action(req.args.action); }
			},
			status: {
				call: function() { return service_status(); }
			},
			read_ini: {
				call: function() { return read_ini(); }
			},
			preview_ini: {
				args: { payload: {} },
				call: function(req) { return preview_ini(req.args.payload); }
			},
			probe_listen: {
				call: function() { return probe_listen(); }
			},
			probe_webdav: {
				call: function() { return probe_webdav(); }
			}
		}
	}
};
