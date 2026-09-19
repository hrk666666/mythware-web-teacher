#!/usr/bin/env python3
"""
极域电子教室第三方教师端 - Web版
Flask后端服务
"""
import os
import sys
import json
import time
import threading
from datetime import datetime
from flask import Flask, render_template, jsonify, request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import PacketBuilder, StudentDiscovery, CommandSender, parse_ip_range

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

discovery = StudentDiscovery()
sender = CommandSender()
operation_log = []


def add_log(action, detail, success=True):
    operation_log.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "action": action,
        "detail": detail,
        "success": success,
    })
    if len(operation_log) > 200:
        operation_log.pop(0)


@app.route('/')
def index():
    return render_template('index.html')


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

    return jsonify({
        "success": True,
        "results": results,
    })


@app.route('/api/message', methods=['POST'])
def api_message():
    data = request.get_json() or {}
    targets = data.get('targets', [])
    message = data.get('message', '')
    port = int(data.get('port', 7006))

    if not targets or not message:
        return jsonify({"success": False, "error": "缺少参数"})

    results = sender.send_message(targets, message, port=port)
    add_log("发送消息", f"[{message[:20]}...] -> {len(targets)}台")

    return jsonify({
        "success": True,
        "results": results,
    })


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

    return jsonify({
        "success": True,
        "results": results,
    })


@app.route('/api/log', methods=['GET'])
def api_log():
    return jsonify({"logs": list(reversed(operation_log))})


@app.route('/api/clear', methods=['POST'])
def api_clear():
    discovery.students.clear()
    return jsonify({"success": True})


if __name__ == '__main__':
    print("=" * 60)
    print("  极域电子教室第三方教师端 - Web版 v1.0")
    print("  安全研究用途，仅限自有机房测试")
    print("=" * 60)
    print()
    print("  访问地址: http://0.0.0.0:5000")
    print()
    app.run(host='0.0.0.0', port=5000, debug=False)
