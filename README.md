# openwrt-epg-sync

一个专为 OpenWrt 系统设计的 IPTV EPG（电子节目指南）自动同步与更新工具。  
*An automated EPG (Electronic Program Guide) synchronization tool designed for OpenWrt.*

[![License](https://img.shields.io/badge/license-MIT-green.svg?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-OpenWrt-blue.svg?style=flat-square)](https://openwrt.org/)

---

## 📌 项目简介 | Overview

**openwrt-epg-sync** 旨在解决 OpenWrt 路由环境中 IPTV / Live TV 系统的 EPG 节目单同步问题。通过轻量级脚本，自动抓取、解析并更新最新的 EPG 数据，确保家庭网内电视或播放终端能够获取实时节目信息。

> **openwrt-epg-sync** is a lightweight utility designed to fetch, parse, and update IPTV EPG data automatically on OpenWrt routers.

---

## ✨ 功能特性 | Features

* 🚀 **轻量高效**：专为路由嵌入式环境优化，资源占用极低。
* ⏰ **定时同步**：支持配合 OpenWrt `crontab` 实现无感后台自动更新。
* 🛠️ **易于集成**：可轻松对接 xTeVe、Threadfin、IPTV Checker 等前端或播放器。
* 🧹 **自动清理**：内置过期日志与缓存清理逻辑，防止占用闪存空间。

---

## 🧱 系统要求 | Requirements

* **OpenWrt** 19.07 或更高版本
* `curl` 或 `wget`（带有 SSL 支持）
* `bash` / `sh` 脚本执行环境
* `cron`（用于定时任务）

---

## 🚀 安装方法 | Installation

可以通过 SSH 登录到 OpenWrt 终端，执行以下命令进行安装：

```bash
# 切换到临时目录
cd /tmp

# 下载项目源码
git clone https://github.com/fnshiwu/openwrt-epg-sync.git

# 进入目录并赋予执行权限
cd openwrt-epg-sync
chmod +x *.sh

```

---

## ⚙️ 配置说明 | Configuration

主要配置文件位于 `/etc/openwrt-epg-sync/config.conf`（或根据你实际的项目路径）：

```ini

# EPG 数据源链接 / EPG Source URL
EPG_SOURCE_URL="http://example.com/epg.xml"

# 输出保存路径 / Output Path
OUTPUT_PATH="/www/epg.xml"

# 日志保留天数 / Log Retention Days
LOG_RETENTION_DAYS=7

```

---

## ⏰ 定时任务设置 | Automated Cron Job

为了保证 EPG 数据保持最新，建议在 OpenWrt 的计划任务（Crontab）中添加定时执行命令。

在 OpenWrt Web 界面（LuCI -> 系统 -> 计划任务）或编辑 `/etc/crontabs/root` 添加以下内容：

```bash
# 每天凌晨 3:00 自动同步一次 EPG 数据
0 3 * * * /usr/bin/openwrt-epg-sync.sh >/dev/null 2>&1

```

---

## 🧪 手动测试 | Manual Testing

直接在终端运行主脚本以测试同步是否正常：

```bash
/usr/bin/openwrt-epg-sync.sh --test

```

---


## 🛠️ 常见问题与可选依赖 | Troubleshooting & Optional Dependencies

### 1. 提示 `当前固件未内置 timeout，直接执行 Python...`

* **原因**：OpenWrt 默认的 BusyBox 可能未内置 `timeout` 命令。虽然脚本可以正常运行，但在无人值守（Cron）模式下，若遇到异常文件导致 Python 解析卡死，缺乏超时保护可能会占用系统资源。
* **解决方法**：建议安装 `coreutils-timeout` 以启用进程超时保护：

  ```bash
  opkg update
  opkg install coreutils-timeout

### 2. Cron 定时任务无法按时触发？

  * 请确保 OpenWrt 的 `cron` 服务已开启并随系统自启：

  ```bash
  /etc/init.d/cron enable
  /etc/init.d/cron start

```

---

## 🙏 鸣谢 | Acknowledgements

本项目本身不托管、不修改、不分发任何受版权保护的电视节目流或 EPG 数据。核心功能仅为提供一个自动化的同步与数据转换环境。

特别感谢以下开源/免费的 EPG 数据源提供者，没有他们的无私奉献，本项目将无法正常运作：

* **112114 EPG** ([epg.112114.xyz](https://epg.112114.xyz/)) - 提供高质量、高精度的中文 EPG 节目单数据。
* **Fanmingming EPG** ([GitHub Raw](https://raw.githubusercontent.com/fanmingming/live)) - 提供丰富且持续维护的 Live/EPG 规则与列表。
* **Yang-1989 EPG** ([GitHub Raw](https://raw.githubusercontent.com/Yang-1989/m3u)) - 提供全面且实用的 IPTV EPG 资源支持。

> **⚠️ 免责声明 (Disclaimer)**：请用户在使用本项目时，务必遵守所在国家/地区的法律法规以及对应数据源的使用条款。本项目对由于滥用第三方接口导致的 IP 封禁或版权纠纷不承担任何责任。
---

## 📜 许可证 | License

本项目采用 [MIT License](https://www.google.com/search?q=LICENSE) 开源许可证。

---

## 📡 作者 | Author

* GitHub: [@fnshiwu](https://github.com/fnshiwu)

