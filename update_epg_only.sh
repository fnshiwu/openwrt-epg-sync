#!/bin/sh
# ============================================================
# 多源 EPG 安全下载与调度脚本 (OpenWrt 无人值守版 v6.2.7)
# 定时任务: 30 4 * * * /root/iptv/update_epg_only.sh >> /root/iptv/epg_sync.log 2>&1
# ============================================================

# ================= 配置区 =================
PERSIST_DIR="/root/iptv"
OUTPUT_DIR="/mnt/sda1"
LOG_FILE="$PERSIST_DIR/epg_sync.log"
EPG_TARGET="$OUTPUT_DIR/epg_mini.xml"
WORKDIR="/tmp/epg_work"

# 阈值与安全策略常量
AGE_THRESHOLD_MIN=3000       # EPG 文件老化告警阈值（分钟，约 50 小时）
MIN_TMP_SPACE_KB=51200       # /tmp 目录最低可用空间预检（KB，约 50MB）
MAX_LOG_SIZE_BYTES=5242880   # 日志文件截断上限（Bytes，5MB）
PYTHON_TIMEOUT_SEC=300       # Python 脚本执行超时上限（秒）
# ==========================================

# 统一通过环境变量传递给 Python，消除双端路径分裂隐患
export WORKDIR PERSIST_DIR EPG_TARGET="$EPG_TARGET" TARGET_EPG_PATH="$EPG_TARGET"

log() { echo "[$(date '+%H:%M:%S')] $1"; }

LOCKFILE="/tmp/.epg_sync.lock"
exec 200>"$LOCKFILE"
if ! flock -n 200; then
    log "⚠️ 已有任务在运行，本次退出"
    exit 0
fi

mkdir -p "$WORKDIR" || exit 1
cd "$WORKDIR" || exit 1

[ -n "$WORKDIR" ] && rm -rf "${WORKDIR:?}"/* 2>/dev/null

if [ -f "$LOG_FILE" ]; then
    LOG_SIZE=$(wc -c < "$LOG_FILE")
    if [ -n "$LOG_SIZE" ] && [ "$LOG_SIZE" -gt "$MAX_LOG_SIZE_BYTES" ]; then
        tail -n 500 "$LOG_FILE" > "$LOG_FILE.tmp" && mv -f "$LOG_FILE.tmp" "$LOG_FILE"
    fi
fi

log "--------------------------------------------------"
log "📥 开始多源 EPG 同步流 (v6.2.7)..."
log "--------------------------------------------------"

_YEAR=$(date '+%Y')
if [ "$_YEAR" -lt "2025" ] || [ "$_YEAR" -gt "2030" ]; then
    log "❌ 系统时间异常 ($_YEAR)，跳过本次同步"; exit 1
fi

_TMP_AVAIL=$(df -k /tmp | awk 'NR==2{print $4}')
if [ -n "$_TMP_AVAIL" ] && [ "$_TMP_AVAIL" -lt "$MIN_TMP_SPACE_KB" ]; then
    log "❌ /tmp 空间不足 (${_TMP_AVAIL}K < ${MIN_TMP_SPACE_KB}K)，跳过本次同步"; exit 1
fi

if [ -f "$EPG_TARGET" ]; then
    _file_mtime=$(date -r "$EPG_TARGET" +%s 2>/dev/null || stat -c %Y "$EPG_TARGET" 2>/dev/null || echo 0)
    if [ "$_file_mtime" -gt 0 ]; then
        _AGE_MIN=$(( ( $(date +%s) - _file_mtime ) / 60 ))
        if [ "$_AGE_MIN" -gt "$AGE_THRESHOLD_MIN" ]; then
            log "⚠️ 警告: EPG 文件已 ${_AGE_MIN} 分钟未更新（超过 $((AGE_THRESHOLD_MIN / 60)) 小时）"
        fi
    fi
fi

for _cmd in curl gzip; do
    command -v "$_cmd" >/dev/null 2>&1 || { log "❌ 缺少必要依赖: $_cmd"; exit 1; }
done

PYTHON_CMD=""
for _py in python3 python; do
    if command -v "$_py" >/dev/null 2>&1; then
        PYTHON_CMD="$_py"
        break
    fi
done
[ -z "$PYTHON_CMD" ] && { log "❌ 未找到 Python 解释器"; exit 1; }

[ ! -d "$OUTPUT_DIR" ] && { log "❌ 输出目录 $OUTPUT_DIR 不存在"; exit 1; }

GITHUB_MIRRORS="https://gh-proxy.com/ https://ghproxy.net/ https://ghfile.geekertao.top/ https://gh.zwy.one/"

smart_download() {
    _url="$1"
    _target="$2"
    _min_size="${3:-1024}"
    _use_mirror="${4:-0}"
    _ua="OpenWrt-EPG-Sync/6.2.7"

    _url_list="$_url"
    if [ "$_use_mirror" -eq 1 ] && [ "${_url#https://}" != "$_url" ]; then
        for _m in $GITHUB_MIRRORS; do
            _url_list="$_url_list ${_m%/}/${_url#https://}"
        done
    fi

    for _try_url in $_url_list; do
        rm -f "${_target}.tmp"
        _domain="${_try_url#*://}"
        _domain="${_domain%%/*}"
        [ -z "$_domain" ] && _domain="直接连接"
        log "下载: $_target (来源: $_domain)..."

        if curl -sSLf --connect-timeout 15 --max-time 120 --retry 2 --retry-delay 5 \
             --user-agent "$_ua" -o "${_target}.tmp" "$_try_url"; then

            if [ -s "${_target}.tmp" ]; then
                _tmp_size=$(wc -c < "${_target}.tmp")
                if [ -n "$_tmp_size" ] && [ "$_tmp_size" -ge "$_min_size" ]; then
                    mv -f "${_target}.tmp" "$_target"
                    log "✅ $_target 更新完成 (${_tmp_size} B)"
                    return 0
                else
                    log "⚠️ 文件过小 (${_tmp_size} B < $_min_size B)，丢弃"
                fi
            else
                log "⚠️ 下载结果为空文件"
            fi
        else
            log "⚠️ 下载失败: $_domain"
        fi
        rm -f "${_target}.tmp"
    done

    log "❌ $_target 全部下载源均失败"
    rm -f "$_target" "${_target}.tmp"
    return 1
}

if smart_download "http://epg.112114.xyz/pp.xml.gz" "epg_src_a.xml.gz" 10240 0; then
    log "🔎 校验 epg_src_a.xml.gz 完整性..."
    if gzip -t "epg_src_a.xml.gz" 2>/dev/null; then
        log "✅ 校验通过，保留压缩包供 Python 流式读取"
    else
        log "❌ 压缩包损坏，清理废弃文件"
        rm -f "epg_src_a.xml.gz"
    fi
fi

smart_download "https://raw.githubusercontent.com/fanmingming/live/main/e.xml" "epg_b.xml" 51200 1
smart_download "https://raw.githubusercontent.com/CCSH/IPTV/refs/heads/main/e.xml" "epg_c.xml" 51200 1

log "🔄 调用 Python 进行融合提纯..."
_py_rc=0
if command -v timeout >/dev/null 2>&1; then
    if timeout "$PYTHON_TIMEOUT_SEC" "$PYTHON_CMD" "$PERSIST_DIR/clean_epg_only.py"; then
        _py_rc=0
    else
        _py_rc=$?
        [ $_py_rc -eq 124 ] && log "❌ Python 净化脚本执行超时 (超过 ${PYTHON_TIMEOUT_SEC} 秒)"
    fi
else
    log "ℹ️ 当前固件未内置 timeout，直接执行 Python..."
    "$PYTHON_CMD" "$PERSIST_DIR/clean_epg_only.py"
    _py_rc=$?
fi

if [ $_py_rc -eq 0 ] && [ -s "$EPG_TARGET" ]; then
    _out_size=$(wc -c < "$EPG_TARGET")
    log "✅ Python 处理成功，输出: ${_out_size} B"

    _pid=$(pidof rtp2httpd 2>/dev/null | awk '{print $1}')
    if [ -n "$_pid" ]; then
        kill -HUP "$_pid" 2>/dev/null && log "✅ 已成功向 rtp2httpd (PID: $_pid) 发送 SIGHUP 重载信号"
    fi
else
    log "❌ Python 执行异常或输出为空 (rc=$_py_rc)"
fi

log "🧹 清理内存临时空间..."
[ -n "$WORKDIR" ] && rm -rf "${WORKDIR:?}"/* 2>/dev/null

log "✅ [Multi-Source Sync v6.2.7] 流程完成"