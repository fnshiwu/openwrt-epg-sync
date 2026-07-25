# OpenWrt 多源 EPG 自动同步与融合清洗工具

针对 OpenWrt / BusyBox 精简固件设计的高效 EPG（电子节目单）多源融合与净化脚本。支持内存流式解压、智能去重、多源互补与断路保护。

## 特性
- **极低内存占用**：采用 Python `iterparse` 流式解析，完美适配软路由内存环境。
- **多源融合容灾**：支持主备多源自动拼接与优先级调度。
- **智能净化**：自动清洗节目名称中的冗余后缀、日期和垃圾关键词。
- **安全兜底**：具备原子文件写入、熔断保护及动态占位机制。

## 文件说明
- `update_epg_only.sh`：Shell 调度与下载脚本（支持空间预检、老化告警、服务重载）。
- `clean_epg_only.py`：Python 核心清洗与融合脚本。

## 快速部署
1. 将脚本放置于软路由的持久化目录（如 `/root/iptv/`）。
2. 配置 crontab 定时任务自动执行：
   ```bash
   30 4 * * * /root/iptv/update_epg_only.sh >> /root/iptv/epg_sync.log 2>&1