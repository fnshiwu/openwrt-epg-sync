#!/usr/bin/env python3
"""
EPG 多源融合净化器 - OpenWrt 无人值守推荐版 v15.2.3
优化项:
  - 路径参数全面由 Shell 环境变量接管，消除硬编码分裂隐患
  - 修正流式解析内存表述为更严谨的“极低内存占用”
"""

import os
import sys
import re
import io
import json
import copy
import gzip
from xml.sax.saxutils import escape
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

# ================= 配置区（由 Shell 环境变量动态注入） =================
WORKDIR = os.environ.get("WORKDIR", "/tmp/epg_work")
PERSIST_DIR = os.environ.get("PERSIST_DIR", "/root/iptv")
TARGET_EPG_PATH = os.environ.get("TARGET_EPG_PATH", "/mnt/sda1/epg_mini.xml")

FILE_A = "epg_src_a.xml.gz"
BASE_SOURCE = "epg_b.xml"
SAFETY_PROGRAMME_THRESHOLD = 50
MAX_XML_SIZE = 500 * 1024 * 1024
CHANNELS_FILE = os.path.join(PERSIST_DIR, "channels.json")

DEFAULT_CHANNELS = {
    "needed": [
        "CCTV1", "CCTV2", "CCTV3", "CCTV4", "CCTV5", "CCTV5+", "CCTV6", "CCTV7", "CCTV8",
        "CCTV9", "CCTV10", "CCTV11", "CCTV12", "CCTV13", "CCTV14", "CCTV15", "CCTV16", "CCTV17",
        "CCTV 4K",
        "CETV1", "CETV2", "CETV4", "CGTN", "CGTN俄语", "CGTN法语", "CGTN西班牙语",
        "江苏卫视", "江苏城市", "江苏影视", "江苏新闻", "江苏综艺", "江苏体育休闲", "江苏国际", "江苏教育",
        "盐城1套", "盐城2套",
        "安徽卫视", "北京卫视", "兵团卫视", "重庆卫视", "东方卫视", "东南卫视", "甘肃卫视", "广东卫视",
        "广西卫视", "贵州卫视", "海南卫视", "河北卫视", "黑龙江卫视", "河南卫视", "湖北卫视", "湖南卫视",
        "江西卫视", "吉林卫视", "辽宁卫视", "内蒙古卫视", "宁夏卫视", "青海卫视", "三沙卫视", "陕西卫视",
        "山东卫视", "山西卫视", "深圳卫视", "四川卫视", "天津卫视", "厦门卫视", "新疆卫视", "西藏卫视",
        "云南卫视", "浙江卫视", "山东教育卫视",
        "优漫卡通", "卡酷少儿", "金鹰卡通", "金鹰纪实",
        "财富天下", "东方财经", "中国天气", "书画频道", "快乐垂钓", "文物宝库", "梨园", "武术世界",
        "法治天地", "生活时尚", "都市剧场"
    ]
}

TITLE_CLEAN_REGEX = re.compile(r'-?\d{4}-\d+\(?|-?\d{4,8}\(?')
SUFFIX_CLEAN_REGEX = re.compile(r'(?i)\s*4K|\s*HD|高清|超清|SDR|HDR|[\s\-_\[\]()（）]')
CCTV_CLEAN_REGEX = re.compile(r'^CCTV-?(\d{1,2})(\+|PLUS|＋)?', re.IGNORECASE)
GARBAGE_KWS = re.compile(r'片头|片尾|包装|广告|垫片|导视|台呼|测试|无节目|收台|串联')
GARBAGE_TITLES = frozenset({"111", "222", "333", "无", "暂无节目", "节目待定"})
_SHORT_KWS = frozenset({"新闻", "天气", "快讯", "简讯", "13点", "13:", "13："})
_LONG_KWS = frozenset({"电影", "剧场", "影院"})

_NON_DIGIT_TRANS = str.maketrans('', '', ''.join(chr(i) for i in range(256) if not chr(i).isdigit()))
# =======================================================================


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def strip_ns(tag: str) -> str:
    return tag.split('}', 1)[-1]


def load_config():
    config = {"channels": copy.deepcopy(DEFAULT_CHANNELS)}
    if os.path.exists(CHANNELS_FILE):
        try:
            with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                for key in DEFAULT_CHANNELS:
                    if key in loaded:
                        config["channels"][key] = loaded[key]
            log("[INFO] 已加载外部频道配置")
        except Exception as e:
            log(f"[WARN] 加载配置失败: {e}，使用默认配置")
    else:
        try:
            os.makedirs(os.path.dirname(CHANNELS_FILE), exist_ok=True)
            with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CHANNELS, f, ensure_ascii=False, indent=2)
            log(f"[INFO] 已创建默认配置: {CHANNELS_FILE}")
        except Exception as e:
            log(f"[WARN] 创建默认配置失败: {e}")
    return config

def clean_suffix(name_str: str) -> str:
    if not name_str:
        return ""
    name_str = name_str.strip()

    if re.search(r'^CCTV-?\s*4K', name_str, re.IGNORECASE):
        return "CCTV 4K"
    if re.search(r'^CCTV-?\s*8K', name_str, re.IGNORECASE):
        return "CCTV 8K"

    m = CCTV_CLEAN_REGEX.match(name_str)
    if m:
        return f"CCTV{m.group(1)}{'+' if m.group(2) else ''}"

    if "江苏体育" in name_str or "江苏休闲" in name_str or "江苏休息" in name_str:
        return "江苏体育休闲"

    return SUFFIX_CLEAN_REGEX.sub('', name_str).strip()

def parse_epg_time(time_str: str):
    if not time_str:
        return None

    digits = time_str.translate(_NON_DIGIT_TRANS)[:14]
    if len(digits) < 14:
        return None

    try:
        dt = datetime(
            int(digits[:4]), int(digits[4:6]), int(digits[6:8]),
            int(digits[8:10]), int(digits[10:12]), int(digits[12:14])
        )
    except ValueError:
        return None

    tz_match = re.search(r'([+-]\d{2}:?\d{2}|Z)$', time_str.strip().upper())
    if not tz_match:
        return dt

    tz_str = tz_match.group(1).replace(":", "")
    if tz_str == "Z":
        return dt + timedelta(hours=8)

    if len(tz_str) >= 5 and tz_str[0] in "+-":
        sign = 1 if tz_str[0] == "+" else -1
        try:
            src_h = int(tz_str[1:3])
            src_m = int(tz_str[3:5])
            src_offset = timedelta(hours=sign * src_h, minutes=sign * src_m)
            target_offset = timedelta(hours=8)
            return dt - src_offset + target_offset
        except ValueError:
            pass
    return dt


def get_repaired_xml_stream(file_path: str):
    """安全的尾部修复：读取有效内容到内存流，绝不修改源文件。"""
    if str(file_path).lower().endswith('.gz'):
        log(f"[INFO] 启用内存流式解压: {os.path.basename(file_path)}")
        return gzip.open(file_path, 'rb')

    file_size = os.path.getsize(file_path)
    if file_size == 0:
        return io.BytesIO(b"<tv></tv>")

    with open(file_path, 'rb') as f:
        read_size = min(4096, file_size)
        f.seek(-read_size, os.SEEK_END)
        tail = f.read()
        if b'</tv>' in tail:
            return open(file_path, 'rb')

    log(f"[WARN] 发现 {os.path.basename(file_path)} 结尾缺失，启动内存流修复...")
    scan_size = min(128 * 1024, file_size)
    with open(file_path, 'rb') as f:
        f.seek(-scan_size, os.SEEK_END)
        tail_data = f.read()

    last_prog = tail_data.rfind(b'</programme>')
    last_chan = tail_data.rfind(b'</channel>')
    valid_offset = max(
        last_prog + len(b'</programme>') if last_prog != -1 else -1,
        last_chan + len(b'</channel>') if last_chan != -1 else -1
    )

    if valid_offset > 0:
        cut_point = (file_size - scan_size) + valid_offset
        with open(file_path, 'rb') as f:
            valid_content = f.read(cut_point)
        return io.BytesIO(valid_content + b'\n</tv>')

    return io.BytesIO(b"<tv></tv>")


def process_source_file(filename: str, valid_dates_int: set, config: dict):
    path = os.path.join(WORKDIR, filename)
    if not os.path.exists(path):
        return {}

    try:
        size = os.path.getsize(path)
        if size == 0:
            log(f"[WARN] 文件为空，跳过: {filename}")
            return {}
        if size > MAX_XML_SIZE:
            log(f"[ERROR] 文件过大，跳过: {filename} ({size} B)")
            return {}
    except OSError as e:
        log(f"[ERROR] 无法访问 [{filename}]: {e}")
        return {}

    stream = get_repaired_xml_stream(path)
    needed_ch = frozenset(config["channels"]["needed"])

    is_a = (filename == FILE_A)
    is_b = (filename == BASE_SOURCE)

    local_map = {}
    pool = {}
    count_pr, valid_pr = 0, 0

    # ========== 极低内存占用的单遍流式解析 ==========
    try:
        for event, elem in ET.iterparse(stream, events=('end',)):
            tag = strip_ns(elem.tag)

            if tag == 'channel':
                ch_id = elem.get('id', '').strip()
                if ch_id:
                    disp = ch_id
                    for child in elem:
                        if strip_ns(child.tag) == 'display-name' and child.text:
                            disp = child.text.strip()
                            break
                    local_map[ch_id] = disp
                elem.clear()

            elif tag == 'programme':
                count_pr += 1
                ch_attr = elem.get('channel', '').strip()
                real_name = local_map.get(ch_attr, ch_attr)
                clean_id = clean_suffix(real_name)

                if clean_id in needed_ch:
                    dt_start = parse_epg_time(elem.get('start', ''))
                    if dt_start:
                        prog_date_int = dt_start.year * 10000 + dt_start.month * 100 + dt_start.day
                        if prog_date_int in valid_dates_int:
                            title = ''
                            for child in elem:
                                if strip_ns(child.tag) == 'title' and child.text:
                                    title = child.text.strip()
                                    break

                            title = TITLE_CLEAN_REGEX.sub('', title).strip()
                            if title and title not in GARBAGE_TITLES and not GARBAGE_KWS.search(title):
                                prio = 1 if is_b else (2 if is_a else 3)
                                pool.setdefault(clean_id, []).append({
                                    "start": dt_start,
                                    "stop": parse_epg_time(elem.get('stop', '')),
                                    "title": title,
                                    "prio": prio
                                })
                                valid_pr += 1
                elem.clear()

    except ET.ParseError as e:
        log(f"[ERROR] XML 解析失败 [{filename}]: {e}")
        return {}
    except Exception as e:
        log(f"[ERROR] 处理异常 [{filename}]: {e}")
        return {}
    finally:
        stream.close()

    log(f"[INFO] {filename} 解析完成 | 频道映射:{len(local_map)} 原始节目:{count_pr} 有效节目:{valid_pr}")
    return pool


def merge_pools(pools: list):
    if not pools:
        return {}

    merged = {}
    for pool in pools:
        for ch_id, progs in pool.items():
            merged.setdefault(ch_id, []).extend(progs)

    result = {}
    for ch_id, progs in merged.items():
        if not progs:
            result[ch_id] = []
            continue

        by_date = {}
        for p in progs:
            by_date.setdefault(p["start"].strftime("%Y%m%d"), []).append(p)

        filtered = []
        for day_progs in by_date.values():
            has_b = any(p["prio"] == 1 for p in day_progs)

            if has_b:
                target = [p for p in day_progs if p["prio"] == 1]
            else:
                min_prio = min(p["prio"] for p in day_progs)
                target = [p for p in day_progs if p["prio"] == min_prio]

            seen = set()
            for p in target:
                key = (p["start"].strftime("%Y%m%d%H%M%S"), p["title"])
                if key not in seen:
                    seen.add(key)
                    filtered.append(p)

        filtered.sort(key=lambda x: x["start"])
        result[ch_id] = filtered

    return result


def write_xml_atomic_stream(merged: dict, now_dt: datetime, target_path: str, needed_channels: list):
    ch_count = len(merged)
    real_prog_count = 0
    total_prog_count = 0
    base_start = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    tmp_path = target_path + ".tmp"

    safety_threshold = max(SAFETY_PROGRAMME_THRESHOLD, len(needed_channels) * 2)

    try:
        target_dir = os.path.dirname(target_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)

        sorted_ch = sorted(merged.keys())

        with open(tmp_path, 'w', encoding='utf-8', buffering=8192) as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<tv generator-info-name="EPG-Combiner v15.2.3" source-info-name="Multi-Source Fusion">\n')

            for ch_id in sorted_ch:
                safe_ch = escape(ch_id, entities={'"': "&quot;"})
                f.write(f'  <channel id="{safe_ch}">\n')
                f.write(f'    <display-name>{safe_ch}</display-name>\n')
                f.write('  </channel>\n')

            for ch_id in sorted_ch:
                progs = merged[ch_id]
                safe_ch = escape(ch_id, entities={'"': "&quot;"})

                if not progs:
                    for offset in (0, 1):
                        total_prog_count += 1
                        day_start = base_start + timedelta(days=offset)
                        day_stop = day_start.replace(hour=23, minute=59, second=59)
                        f.write(f'  <programme start="{day_start.strftime("%Y%m%d%H%M%S +0800")}" '
                                f'stop="{day_stop.strftime("%Y%m%d%H%M%S +0800")}" channel="{safe_ch}">\n')
                        f.write('    <title lang="zh">精彩节目</title>\n  </programme>\n')
                    continue

                n = len(progs)
                for i, p in enumerate(progs):
                    total_prog_count += 1
                    real_prog_count += 1
                    c_start = p["start"]
                    c_stop = p["stop"]

                    est_m = 15 if any(kw in p["title"] for kw in _SHORT_KWS) else \
                            90 if any(kw in p["title"] for kw in _LONG_KWS) else 45
                    est_stop = c_start + timedelta(minutes=est_m)

                    valid_orig = bool(c_stop and c_stop > c_start)
                    base_stop_time = c_stop if valid_orig else est_stop

                    if i < n - 1:
                        n_start = progs[i + 1]["start"]
                        if n_start > c_start:
                            final_stop = min(base_stop_time, n_start)
                            if final_stop <= c_start:
                                final_stop = c_start + timedelta(minutes=5)
                        else:
                            final_stop = c_start + timedelta(minutes=5)
                    else:
                        day_end = (c_start + timedelta(days=1)).replace(hour=6, minute=0, second=0)
                        final_stop = min(base_stop_time, day_end)
                        if final_stop <= c_start:
                            final_stop = c_start + timedelta(minutes=5)

                    safe_title = escape(p["title"])
                    f.write(f'  <programme start="{c_start.strftime("%Y%m%d%H%M%S +0800")}" '
                            f'stop="{final_stop.strftime("%Y%m%d%H%M%S +0800")}" channel="{safe_ch}">\n')
                    f.write(f'    <title lang="zh">{safe_title}</title>\n  </programme>\n')

            f.write('</tv>\n')
            f.flush()
            os.fsync(f.fileno())

        if real_prog_count < safety_threshold:
            log(f"[SECURITY] 熔断保护：真实节目 {real_prog_count} 低于动态阈值 {safety_threshold}，拒绝写入并清理碎片")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return False

        os.replace(tmp_path, target_path)
        log(f"[INFO] 输出成功: {target_path} ({ch_count}频道, 真实节目:{real_prog_count}, 总节点:{total_prog_count})")
        return True

    except Exception as e:
        log(f"[FATAL] 写入异常: {e}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False


def main():
    log("EPG 洗涤程序启动 (v15.2.3 无人值守推荐版)")

    now_dt = datetime.now()
    if now_dt.year < 2025 or now_dt.year > 2030:
        log(f"[FATAL] 系统时间异常: {now_dt}，拒绝执行以防止日期过滤错误")
        return 1

    config = load_config()
    needed_channels = config["channels"]["needed"]

    valid_dates_int = {
        int(now_dt.strftime("%Y%m%d")),
        int((now_dt + timedelta(days=1)).strftime("%Y%m%d"))
    }

    sources = [BASE_SOURCE, "epg_c.xml", FILE_A]
    pools = []
    for src in sources:
        pool = process_source_file(src, valid_dates_int, config)
        if pool:
            pools.append(pool)

    merged = merge_pools(pools)

    missing_channels = [ch for ch in needed_channels if ch not in merged or not merged[ch]]
    for ch in missing_channels:
        merged[ch] = []

    if missing_channels:
        log(f"[INFO] {len(missing_channels)} 个频道无有效节目，将生成默认占位")

    if write_xml_atomic_stream(merged, now_dt, TARGET_EPG_PATH, needed_channels):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())