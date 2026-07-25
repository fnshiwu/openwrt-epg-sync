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
EPG_SOURCE_URL="[http://example.com/epg.xml](http://example.com/epg.xml)"

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

## 📜 许可证 | License

本项目采用 [MIT License](https://www.google.com/search?q=LICENSE) 开源许可证。

---

## 📡 作者 | Author

* GitHub: [@fnshiwu](https://github.com/fnshiwu)

