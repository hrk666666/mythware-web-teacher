let students = [];

// 页面加载完成
document.addEventListener('DOMContentLoaded', function() {
    refreshStudents();
    setInterval(refreshStudents, 5000);
});

// API请求封装
async function api(url, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: { 'Content-Type': 'application/json' }
    };
    if (data) {
        options.body = JSON.stringify(data);
    }
    try {
        const resp = await fetch(url, options);
        return await resp.json();
    } catch (e) {
        showModal('错误', '请求失败: ' + e.message);
        return { success: false };
    }
}

// 扫描学生端
async function scanNetwork() {
    const subnet = document.getElementById('subnetInput').value;
    const btn = event.target;
    btn.innerHTML = '<span class="loading"></span> 扫描中...';
    btn.disabled = true;

    const result = await api('/api/scan', 'POST', { subnet: subnet, timeout: 0.2 });

    btn.innerHTML = '🔍 扫描学生端';
    btn.disabled = false;

    if (result.success) {
        addLog('扫描完成', `发现 ${result.found} 台学生端`);
        refreshStudents();
    }
}

// 刷新学生列表
async function refreshStudents() {
    const result = await api('/api/students');
    if (result.success) {
        students = result.students;
        renderStudents();
        document.getElementById('onlineCount').textContent = result.online_count;
        document.getElementById('totalCount').textContent = result.total_count;
    }
}

// 渲染学生列表
function renderStudents() {
    const tbody = document.getElementById('studentList');
    if (students.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty-tip">暂无学生端，请先扫描</td></tr>';
        return;
    }

    tbody.innerHTML = students.map((s, i) => `
        <tr>
            <td><input type="checkbox" class="student-check" data-ip="${s.ip}" ${s.checked ? 'checked' : ''}></td>
            <td>${s.ip}</td>
            <td>${s.hostname}</td>
            <td>
                <span class="status-dot ${s.online ? 'status-online' : 'status-offline'}"></span>
                ${s.online ? '在线' : '离线'}
            </td>
            <td>${s.last_seen}</td>
        </tr>
    `).join('');
}

// 全选
function toggleSelectAll() {
    const checked = document.getElementById('checkAll').checked;
    document.querySelectorAll('.student-check').forEach(cb => {
        cb.checked = checked;
    });
}

function selectAll() {
    document.getElementById('checkAll').checked = true;
    document.querySelectorAll('.student-check').forEach(cb => cb.checked = true);
}

function selectOnline() {
    document.querySelectorAll('.student-check').forEach((cb, i) => {
        cb.checked = students[i] && students[i].online;
    });
}

function selectNone() {
    document.getElementById('checkAll').checked = false;
    document.querySelectorAll('.student-check').forEach(cb => cb.checked = false);
}

// 获取选中的IP
function getSelectedIPs() {
    const ips = [];
    document.querySelectorAll('.student-check:checked').forEach(cb => {
        ips.push(cb.dataset.ip);
    });
    return ips;
}

// 执行命令
async function execCommand() {
    const targets = getSelectedIPs();
    if (targets.length === 0) {
        showModal('提示', '请先选择学生端');
        return;
    }
    const command = document.getElementById('execCmd').value;
    const params = document.getElementById('execParams').value;
    if (!command) {
        showModal('提示', '请输入要执行的命令');
        return;
    }

    const result = await api('/api/exec', 'POST', {
        targets: targets,
        command: command,
        params: params
    });

    if (result.success) {
        const r = result.results;
        showModal('执行完成', `
            <p>总计: ${r.total} 台</p>
            <p style="color:#52c41a">成功: ${r.success} 台</p>
            <p style="color:#f5222d">失败: ${r.failed} 台</p>
        `);
        addLog('远程执行', `${command} -> ${targets.length}台, 成功${r.success}台`);
    }
}

// 发送消息
async function sendMessage() {
    const targets = getSelectedIPs();
    if (targets.length === 0) {
        showModal('提示', '请先选择学生端');
        return;
    }
    const message = document.getElementById('msgText').value;
    if (!message) {
        showModal('提示', '请输入消息内容');
        return;
    }

    const result = await api('/api/message', 'POST', {
        targets: targets,
        message: message
    });

    if (result.success) {
        const r = result.results;
        showModal('发送完成', `
            <p>总计: ${r.total} 台</p>
            <p style="color:#52c41a">成功: ${r.success} 台</p>
        `);
        addLog('发送消息', `"${message}" -> ${targets.length}台`);
    }
}

// 电源控制
async function powerControl(reboot) {
    const targets = getSelectedIPs();
    if (targets.length === 0) {
        showModal('提示', '请先选择学生端');
        return;
    }
    const action = reboot ? '重启' : '关机';
    if (!confirm(`确认要对选中的 ${targets.length} 台机器执行${action}吗？`)) {
        return;
    }

    const result = await api('/api/shutdown', 'POST', {
        targets: targets,
        reboot: reboot
    });

    if (result.success) {
        const r = result.results;
        showModal(`${action}完成`, `
            <p>总计: ${r.total} 台</p>
            <p style="color:#52c41a">成功: ${r.success} 台</p>
        `);
        addLog(action, `-> ${targets.length}台, 成功${r.success}台`);
    }
}

// 清空列表
async function clearStudents() {
    await api('/api/clear', 'POST');
    refreshStudents();
    addLog('清空', '学生端列表已清空');
}

// 添加日志
function addLog(action, detail) {
    const container = document.getElementById('logContainer');
    const now = new Date().toLocaleTimeString();
    const item = document.createElement('div');
    item.className = 'log-item';
    item.innerHTML = `<span class="log-time">[${now}]</span> <span class="log-action">${action}</span> <span class="log-success">${detail}</span>`;
    container.prepend(item);
}

// 弹窗
function showModal(title, body) {
    document.getElementById('modalTitle').textContent = title;
    document.getElementById('modalBody').innerHTML = body;
    document.getElementById('resultModal').classList.add('show');
}

function closeModal() {
    document.getElementById('resultModal').classList.remove('show');
}
