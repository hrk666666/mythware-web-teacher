#!/usr/bin/env python3
"""
极域电子教室第三方教师端 - Web版 v3.0
学生端运行官方极域，教师端通过原生协议控制
"""
import os
import sys
import time
from datetime import datetime
from flask import Flask, render_template, jsonify, request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import (
    PacketBuilder, StudentDiscovery, CommandSender,
    ScreenBroadcaster, get_broadcaster, parse_ip_range
)

# PyInstaller打包后资源路径处理
if getattr(sys, 'frozen', False):
    bundle_dir = sys._MEIPASS
    template_dir = os.path.join(bundle_dir, 'templates')
    static_dir = os.path.join(bundle_dir, 'static')
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
else:
    app = Flask(__name__)

app.config['JSON_AS_ASCII'] = False

discovery = StudentDiscovery()
sender = CommandSender()
broadcaster = get_broadcaster()
operation_log = []


def add_log(action, detail):
    operation_log.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "action": action,
        "detail": detail,
    })
    if len(operation_log) > 300:
        operation_log.pop(0)


# ============ 页面 ============

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
    add_log("扫描", f"网段 {subnet}，发现 {len(found)} 台")
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


# ============ 控制命令 ============

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
    add_log("远程执行", f"{command} -> {len(targets)} 台，成功 {results['success']}")
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
    add_log("发送消息", f'"{message[:20]}" -> {len(targets)} 台')
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
    add_log(action, f"-> {len(targets)} 台，成功 {results['success']}")
    return jsonify({"success": True, "results": results})


# ============ 屏幕广播（原生极域协议） ============

@app.route('/api/broadcast/start', methods=['POST'])
def api_broadcast_start():
    data = request.get_json() or {}
    targets = data.get('targets', [])
    fps = int(data.get('fps', 5))
    quality = int(data.get('quality', 60))

    if not targets:
        return jsonify({"success": False, "error": "请先选择学生端"})

    ok = broadcaster.start(targets, fps=fps, quality=quality)
    if ok:
        add_log("屏幕广播", f"开始广播，目标 {len(targets)} 台，{fps}fps")
        return jsonify({"success": True, "message": "广播已开始"})
    else:
        return jsonify({"success": False, "error": "广播已在运行中"})


@app.route('/api/broadcast/stop', methods=['POST'])
def api_broadcast_stop():
    broadcaster.stop()
    add_log("屏幕广播", "停止广播")
    return jsonify({"success": True, "message": "广播已停止"})


@app.route('/api/broadcast/status', methods=['GET'])
def api_broadcast_status():
    return jsonify({
        "running": broadcaster.is_running(),
        "teacher_ip": broadcaster.teacher_ip,
        "multicast_group": "225.2.2.11",
        "target_count": len(broadcaster.target_students),
    })


# ============ 屏幕监控（通过TCP 7001请求学生端屏幕） ============

@app.route('/api/monitor/request', methods=['POST'])
def api_monitor_request():
    """向指定学生端发送屏幕监控请求（TCP 7001）"""
    data = request.get_json() or {}
    targets = data.get('targets', [])
    if not targets:
        return jsonify({"success": False, "error": "请先选择学生端"})

    results = {"total": len(targets), "success": 0, "failed": 0}
    for ip in targets:
        if broadcaster.send_handshake(ip):
            results["success"] += 1
        else:
            results["failed"] += 1

    add_log("屏幕监控", f"请求 {len(targets)} 台，成功 {results['success']}")
    return jsonify({"success": True, "results": results})


# ============ 日志 ============

@app.route('/api/log', methods=['GET'])
def api_log():
    return jsonify({"logs": list(reversed(operation_log))})


@app.route('/api/clear', methods=['POST'])
def api_clear():
    discovery.students.clear()
    return jsonify({"success": True})


if __name__ == '__main__':
    print("=" * 60)
    print("  极域电子教室第三方教师端 - Web版 v3.0")
    print("  学生端: 官方极域 | 教师端: 本工具")
    print("  协议: DMOC UDP + TCP 7001 + 组播 225.2.2.11")
    print("=" * 60)
    print()
    print("  访问地址: http://0.0.0.0:5000")
    print()
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
