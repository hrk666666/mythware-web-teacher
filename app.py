#!/usr/bin/env python3
"""
极域电子教室第三方教师端 - Web版 v2.0
Flask后端服务
"""
import os
import sys
import io
import time
import base64
import threading
from datetime import datetime
from collections import defaultdict
from flask import Flask, render_template, jsonify, request, Response

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import PacketBuilder, StudentDiscovery, CommandSender, parse_ip_range

# PyInstaller打包后资源路径处理
if getattr(sys, 'frozen', False):
    # 打包后运行
    bundle_dir = sys._MEIPASS
    template_dir = os.path.join(bundle_dir, 'templates')
    static_dir = os.path.join(bundle_dir, 'static')
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
else:
    # 开发模式运行
    app = Flask(__name__)

app.config['JSON_AS_ASCII'] = False
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB

discovery = StudentDiscovery()
sender = CommandSender()
operation_log = []

# 屏幕监控数据存储
screen_cache = defaultdict(dict)  # ip -> {screenshot, timestamp, hostname}
# 屏幕广播状态
broadcast_state = {
    "active": False,
    "frame": None,
    "timestamp": 0,
    "teacher_ip": "",
}


def add_log(action, detail, success=True):
    operation_log.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "action": action,
        "detail": detail,
        "success": success,
    })
    if len(operation_log) > 300:
        operation_log.pop(0)


# ============ 页面路由 ============

@app.route('/')
def index():
    return render_template('index.html')


# ============ 学生端发现 ============

@app.route('/api/scan', methods=['POST'])
def api_scan():
    data = request.get_json() or {}
    subnet = data.get('subnet', '192.168.1.0/24')
    timeout = float(data.get('timeout', 0.2))
    found = discovery.scan_network(subnet, timeout=timeout)
    add_log("扫描", f"网段: {subnet}, 发现: {len(found)}台")
    return jsonify({
        "success": True,
        "found": len(found),
        "students": [s.to_dict() for s in discovery.get_all()],
    })


@app.route('/api/students', methods=['GET'])
def api_students():
    return jsonify({
        "students": [s.to_dict() for s in discovery.get_all()],
        "online_count": len(discovery.get_online()),
        "total_count": len(discovery.get_all()),
    })


# ============ 极域控制命令 ============

@app.route('/api/exec', methods=['POST'])
def api_exec():
    data = request.get_json() or {}
    targets = data.get('targets', [])
    command = data.get('command', '')
    params = data.get('params', '')
    port = int(data.get('port', 4705))
    if not targets or not command:
        return jsonify({"success": False, "error": "缺少参数"})
    results = sender.exec_command(targets, command, params, port=port)
    add_log("远程执行", f"{command} -> {len(targets)}台, 成功{results['success']}")
    return jsonify({"success": True, "results": results})


@app.route('/api/message', methods=['POST'])
def api_message():
    data = request.get_json() or {}
    targets = data.get('targets', [])
    message = data.get('message', '')
    port = int(data.get('port', 7006))
    if not targets or not message:
        return jsonify({"success": False, "error": "缺少参数"})
    results = sender.send_message(targets, message, port=port)
    add_log("发送消息", f"[{message[:20]}] -> {len(targets)}台")
    return jsonify({"success": True, "results": results})


@app.route('/api/shutdown', methods=['POST'])
def api_shutdown():
    data = request.get_json() or {}
    targets = data.get('targets', [])
    reboot = data.get('reboot', False)
    port = int(data.get('port', 7005))
    if not targets:
        return jsonify({"success": False, "error": "缺少目标"})
    results = sender.shutdown(targets, reboot=reboot, port=port)
    action = "重启" if reboot else "关机"
    add_log(action, f"-> {len(targets)}台, 成功{results['success']}")
    return jsonify({"success": True, "results": results})


# ============ 屏幕监控 ============

@app.route('/api/screen/upload', methods=['POST'])
def api_screen_upload():
    """学生端代理上传屏幕截图"""
    data = request.get_json() or {}
    ip = data.get('ip', request.remote_addr)
    screenshot = data.get('screenshot', '')
    hostname = data.get('hostname', '')
    if screenshot:
        screen_cache[ip] = {
            "screenshot": screenshot,
            "hostname": hostname,
            "timestamp": time.time(),
        }
    return jsonify({"success": True})


@app.route('/api/screen/list', methods=['GET'])
def api_screen_list():
    """获取所有学生屏幕列表"""
    result = []
    now = time.time()
    for ip, info in screen_cache.items():
        age = now - info["timestamp"]
        if age < 30:  # 30秒内活跃
            result.append({
                "ip": ip,
                "hostname": info.get("hostname", ip),
                "age": int(age),
                "has_screen": bool(info.get("screenshot")),
            })
    return jsonify({"screens": result, "count": len(result)})


@app.route('/api/screen/<ip>', methods=['GET'])
def api_screen_get(ip):
    """获取指定学生的屏幕截图"""
    info = screen_cache.get(ip)
    if info and info.get("screenshot"):
        return jsonify({
            "success": True,
            "screenshot": info["screenshot"],
            "hostname": info.get("hostname", ip),
            "timestamp": info["timestamp"],
        })
    return jsonify({"success": False, "error": "无屏幕数据"})


# ============ 屏幕广播 ============

@app.route('/api/broadcast/start', methods=['POST'])
def api_broadcast_start():
    """开始屏幕广播"""
    global broadcast_state
    data = request.get_json() or {}
    broadcast_state = {
        "active": True,
        "frame": None,
        "timestamp": time.time(),
        "teacher_ip": data.get("teacher_ip", request.remote_addr),
    }
    add_log("屏幕广播", "开始广播")
    return jsonify({"success": True, "message": "广播已开始"})


@app.route('/api/broadcast/frame', methods=['POST'])
def api_broadcast_frame():
    """教师端推送广播帧"""
    global broadcast_state
    data = request.get_json() or {}
    frame = data.get("frame", "")
    if frame:
        broadcast_state["frame"] = frame
        broadcast_state["timestamp"] = time.time()
    return jsonify({"success": True})


@app.route('/api/broadcast/stop', methods=['POST'])
def api_broadcast_stop():
    """停止屏幕广播"""
    global broadcast_state
    broadcast_state["active"] = False
    broadcast_state["frame"] = None
    add_log("屏幕广播", "停止广播")
    return jsonify({"success": True, "message": "广播已停止"})


@app.route('/api/broadcast/status', methods=['GET'])
def api_broadcast_status():
    """获取广播状态（学生端轮询）"""
    return jsonify({
        "active": broadcast_state["active"],
        "has_frame": bool(broadcast_state.get("frame")),
        "timestamp": broadcast_state.get("timestamp", 0),
    })


@app.route('/api/broadcast/frame/latest', methods=['GET'])
def api_broadcast_latest():
    """学生端获取最新广播帧"""
    if broadcast_state["active"] and broadcast_state.get("frame"):
        return jsonify({
            "success": True,
            "frame": broadcast_state["frame"],
            "timestamp": broadcast_state["timestamp"],
        })
    return jsonify({"success": False, "active": broadcast_state["active"]})


# ============ 日志和工具 ============

@app.route('/api/log', methods=['GET'])
def api_log():
    return jsonify({"logs": list(reversed(operation_log))})


@app.route('/api/clear', methods=['POST'])
def api_clear():
    discovery.students.clear()
    return jsonify({"success": True})


if __name__ == '__main__':
    print("=" * 60)
    print("  极域电子教室第三方教师端 - Web版 v2.0")
    print("  功能: 学生发现 | 远程执行 | 屏幕监控 | 屏幕广播")
    print("  安全研究用途，仅限自有机房测试")
    print("=" * 60)
    print()
    print("  访问地址: http://0.0.0.0:5000")
    print()
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
