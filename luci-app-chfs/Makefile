#
# Copyright (C) 2026 LianXia233
#
# This is free software, licensed under the Apache License, Version 2.0.
#

include $(TOPDIR)/rules.mk

LUCI_TITLE:=LuCI support for chfs (CuteHttpFileServer)
LUCI_DEPENDS:=+chfs +rpcd +rpcd-mod-ucode +ucode +ucode-mod-fs +ucode-mod-uci
LUCI_PKGARCH:=all
LUCI_DESCRIPTION:=chfs (CuteHttpFileServer) 的 LuCI 管理界面, 支持端口与共享目录配置、\
	账户权限与访问规则、IP 黑白名单、日志与开机自启管理.

PKG_NAME:=luci-app-chfs
PKG_VERSION:=1.0.0
PKG_RELEASE:=1

PKG_MAINTAINER:=LianXia233
PKG_LICENSE:=Apache-2.0

include $(INCLUDE_DIR)/package.mk
include $(TOPDIR)/feeds/luci/luci.mk

# 兼容 luci.mk 的两代调用签名:
#   - openwrt-21.02 及更早: $(eval $(call BuildPackage,$(PKG_NAME)))
#   - openwrt-22.03 及更新: $(eval $(call BuildPackage,luci-app-chfs))
# luci.mk 内部对两种写法均做了兼容处理, 此处沿用主流写法.
$(eval $(call BuildPackage,luci-app-chfs))
