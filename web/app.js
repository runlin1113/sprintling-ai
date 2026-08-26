/* =============================================================
   SprintLing 部署配置：静态托管 + 远程后端跨域访问
   -------------------------------------------------------------
   使用场景：
   1) 本地/一体化部署：前端与 Flask 后端同源（默认）-> API_BASE_URL = ''
   2) 静态托管 CDN (GitHub Pages/Netlify/Vercel/OSS/COS) + 远程 Flask API：
        在浏览器 URL 栏追加 ?api=https://your-backend.example.com 临时切换，
        或直接修改下方 API_BASE_URL_DEFAULT 写死后端地址即可一次打包到处运行。
   ============================================================= */
(function _initDeployConfig() {
    // ① 写死的默认后端地址（静态托管 CDN 时改成你的公网 Flask 域名即可）
    //    例：https://sprintling-api.example.com  或  http://1.2.3.4:5000
    const API_BASE_URL_DEFAULT = '';

    const urlParams = new URLSearchParams(window.location.search);
    const fromQuery = urlParams.get('api') || '';
    const fromStorage = (typeof localStorage !== 'undefined') ? (localStorage.getItem('sprintling_api_base') || '') : '';

    let base = fromQuery || fromStorage || API_BASE_URL_DEFAULT;
    // 规范化：去掉末尾斜杠，避免 /api//xxx 双斜杠问题
    base = base.replace(/\/+$/, '');
    if (base && typeof localStorage !== 'undefined' && !fromQuery) {
        // 非临时切换 -> 记住选择
        try { localStorage.setItem('sprintling_api_base', base); } catch (e) { /* ignore */ }
    }
    // 暴露到全局
    window.__SPRINTLING_API_BASE__ = base;
    // 控制台提示，方便排错
    if (window.console && window.console.info) {
        window.console.info('%c[SprintLing Deploy] API_BASE =', 'color:#FF6B35;font-weight:700', base || '(同源 / same-origin)');
    }
})();

/**
 * 拼接后端 API 完整 URL：
 *   apiUrl('/api/history')               -> 同源: '/api/history'   跨域: 'https://xx/api/history'
 *   apiUrl('/api/serve/xxx/chart.png')   -> 支持图片/视频资源路径
 */
function apiUrl(path) {
    const base = window.__SPRINTLING_API_BASE__ || '';
    if (!base) return path; // 同源部署 -> 直接返回相对路径
    // 绝对路径 (http/https://...) 直接透传
    if (/^https?:\/\//i.test(path)) return path;
    // 保证 path 以 "/" 开头，避免 base/api/xxx 变成 baseapi/xxx
    const cleanPath = path.startsWith('/') ? path : '/' + path;
    return base + cleanPath;
}

let state = {
    athlete: null,
    selectedRecord: null,
    startFile: null,
    maxvelFile: null,
    currentTimestamp: null,
    statusPollingTimer: null
};

document.addEventListener('DOMContentLoaded', function () {
    initApp();
});

function initApp() {
    setupFileUploaders();
    loadHistory();
    setupRegistrationForm();
}

/* ====== Landing / App Navigation ====== */

function enterApp() {
    const landing = document.getElementById('landing-page');
    const app = document.getElementById('app');
    if (landing) landing.classList.remove('active');
    if (app) {
        app.style.display = 'flex';
        // Slight delay to ensure display is set before view logic runs
        setTimeout(() => {
            // Reset to registration view when entering app from landing
            document.getElementById('dashboard-view').classList.remove('active');
            document.getElementById('registration-view').classList.add('active');
            document.getElementById('sidebar-user-section').style.display = 'block';
            stopStatusPolling();
            state.selectedRecord = null;
            state.currentTimestamp = null;
            document.getElementById('results-section').style.display = 'none';
            document.getElementById('processing-section').style.display = 'none';
            document.getElementById('selected-record-section').style.display = 'none';
            // Reset AI Protocol tab state
            if (document.getElementById('report-empty')) document.getElementById('report-empty').style.display = 'block';
            if (document.getElementById('report-section')) document.getElementById('report-section').style.display = 'none';
            if (document.getElementById('regenerate-report-btn')) document.getElementById('regenerate-report-btn').style.display = 'none';
            resetUploads();
            loadHistory();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }, 50);
    }
}

function goToLanding() {
    const landing = document.getElementById('landing-page');
    const app = document.getElementById('app');
    if (app) app.style.display = 'none';
    if (landing) {
        landing.classList.add('active');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function setupRegistrationForm() {
    const form = document.getElementById('registration-form');
    form.addEventListener('submit', async function (e) {
        e.preventDefault();
        const name = document.getElementById('name').value.trim();
        const event = document.getElementById('event').value;
        const pb = document.getElementById('pb').value.trim();
        const goal = document.getElementById('goal').value.trim();

        if (!name) {
            alert('Please enter a name or choose to skip. | 请输入姓名或选择跳过。');
            return;
        }

        const response = await fetch(apiUrl('/api/register'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, event, pb, goal })
        });

        const data = await response.json();
        if (data.success) {
            state.athlete = { name, event, pb, goal };
            enterDashboard();
        } else {
            alert(data.message || 'Registration failed');
        }
    });
}

function skipRegistration() {
    state.athlete = {};
    enterDashboard();
}

function enterDashboard() {
    document.getElementById('registration-view').classList.remove('active');
    document.getElementById('dashboard-view').classList.add('active');

    if (state.athlete && state.athlete.name) {
        document.getElementById('welcome-title').textContent = `前进吧！${state.athlete.name}! 🏃`;
        document.getElementById('welcome-subtitle').textContent =
            `Current Target: ${state.athlete.event} | PB: ${state.athlete.pb}s`;
    } else {
        document.getElementById('welcome-title').textContent = 'SprintLing Analytics AI | 短跨力学分析系统';
        document.getElementById('welcome-subtitle').textContent = '';
    }

    document.getElementById('sidebar-user-section').style.display = 'block';
    loadHistory();
}

function backToRegistration() {
    stopStatusPolling();
    state.selectedRecord = null;
    state.currentTimestamp = null;
    document.getElementById('dashboard-view').classList.remove('active');
    document.getElementById('registration-view').classList.add('active');
    document.getElementById('results-section').style.display = 'none';
    document.getElementById('processing-section').style.display = 'none';
    document.getElementById('selected-record-section').style.display = 'none';
    resetUploads();
}

function setupFileUploaders() {
    setupSingleUploader('start');
    setupSingleUploader('maxvel');
}

function setupSingleUploader(type) {
    const uploadArea = document.getElementById(`${type}-upload-area`);
    const fileInput = document.getElementById(`${type}-video`);
    const fileInfo = document.getElementById(`${type}-file-info`);
    const fileName = document.getElementById(`${type}-file-name`);

    fileInput.addEventListener('change', function (e) {
        if (e.target.files.length > 0) {
            handleFileSelect(type, e.target.files[0]);
        }
    });

    uploadArea.addEventListener('dragover', function (e) {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', function () {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', function (e) {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            handleFileSelect(type, e.dataTransfer.files[0]);
        }
    });
}

function handleFileSelect(type, file) {
    if (!file.type.startsWith('video/')) {
        alert('Please upload a video file.');
        return;
    }

    const uploadArea = document.getElementById(`${type}-upload-area`);
    const fileInfo = document.getElementById(`${type}-file-info`);
    const fileName = document.getElementById(`${type}-file-name`);
    const placeholder = uploadArea.querySelector('.upload-placeholder');

    state[`${type}File`] = file;
    fileName.textContent = file.name;
    placeholder.style.display = 'none';
    fileInfo.style.display = 'flex';
    uploadArea.classList.add('has-file');
}

function removeFile(type) {
    state[`${type}File`] = null;
    const uploadArea = document.getElementById(`${type}-upload-area`);
    const fileInput = document.getElementById(`${type}-video`);
    const fileInfo = document.getElementById(`${type}-file-info`);
    const placeholder = uploadArea.querySelector('.upload-placeholder');

    fileInput.value = '';
    placeholder.style.display = 'block';
    fileInfo.style.display = 'none';
    uploadArea.classList.remove('has-file');
}

function resetUploads() {
    removeFile('start');
    removeFile('maxvel');
}

async function loadHistory() {
    try {
        const response = await fetch(apiUrl('/api/history'));
        const data = await response.json();
        const listEl = document.getElementById('history-list');

        if (!data.records || data.records.length === 0) {
            listEl.innerHTML = '<p class="empty-state">No records yet</p>';
            return;
        }

        listEl.innerHTML = data.records.map(record => {
            const activeClass = state.selectedRecord === record ? 'active' : '';
            return `<button class="history-item ${activeClass}" onclick="selectRecord('${record}')">RECORD: ${record}</button>`;
        }).join('');
    } catch (e) {
        console.error('Failed to load history:', e);
    }
}

async function selectRecord(timestamp) {
    state.selectedRecord = timestamp;
    document.getElementById('selected-record-name').textContent = timestamp;
    document.getElementById('selected-record-section').style.display = 'block';

    await loadHistory();
    await loadRecordResults(timestamp);
}

async function deleteSelectedRecord() {
    if (!state.selectedRecord) return;

    if (!confirm(`Delete record ${state.selectedRecord}? This cannot be undone.`)) return;

    try {
        const response = await fetch(apiUrl(`/api/history/${state.selectedRecord}`), { method: 'DELETE' });
        const data = await response.json();

        if (data.success) {
            alert('Record deleted successfully.');
            state.selectedRecord = null;
            document.getElementById('selected-record-section').style.display = 'none';
            document.getElementById('results-section').style.display = 'none';
            loadHistory();
        }
    } catch (e) {
        alert('Failed to delete record.');
    }
}

async function startAnalysis() {
    if (!state.startFile && !state.maxvelFile) {
        alert('Please upload at least one video file (Start or Max Velocity).');
        return;
    }

    const btn = document.getElementById('analyze-btn');
    btn.disabled = true;
    btn.textContent = '🔄 Processing...';

    const formData = new FormData();
    if (state.startFile) formData.append('start_video', state.startFile);
    if (state.maxvelFile) formData.append('maxvel_video', state.maxvelFile);
    formData.append('athlete_info', JSON.stringify(state.athlete || {}));

    try {
        const response = await fetch(apiUrl('/api/process'), {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            state.currentTimestamp = data.timestamp;
            startStatusPolling(data.timestamp);
        } else {
            alert(data.message || 'Processing failed');
        }
    } catch (e) {
        alert('Error uploading videos: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '🔬 Initialize Biomechanical Engine | 启动分析';
    }
}

function startStatusPolling(timestamp) {
    document.getElementById('processing-section').style.display = 'block';
    document.getElementById('progress-fill').style.width = '5%';
    document.getElementById('progress-stage').textContent = 'Initializing...';

    if (state.statusPollingTimer) {
        clearInterval(state.statusPollingTimer);
    }

    state.statusPollingTimer = setInterval(async () => {
        try {
            const response = await fetch(apiUrl(`/api/status/${timestamp}`));
            const data = await response.json();

            updateProgress(data);

            if (data.done) {
                stopStatusPolling();
                onProcessingComplete(timestamp);
            }
            if (data.error) {
                stopStatusPolling();
                alert('Processing error: ' + data.stage);
                document.getElementById('processing-section').style.display = 'none';
            }
        } catch (e) {
            console.error('Status check failed:', e);
        }
    }, 1000);
}

function stopStatusPolling() {
    if (state.statusPollingTimer) {
        clearInterval(state.statusPollingTimer);
        state.statusPollingTimer = null;
    }
}

function updateProgress(data) {
    const fill = document.getElementById('progress-fill');
    const stage = document.getElementById('progress-stage');
    fill.style.width = data.progress + '%';
    stage.textContent = data.stage || 'Processing...';
}

async function onProcessingComplete(timestamp) {
    document.getElementById('progress-fill').style.width = '100%';
    document.getElementById('progress-stage').textContent = '✅ Complete!';

    await loadHistory();
    await loadRecordResults(timestamp);

    setTimeout(() => {
        document.getElementById('processing-section').style.display = 'none';
    }, 1500);
}

async function loadRecordResults(timestamp) {
    state.selectedRecord = timestamp;
    document.getElementById('selected-record-name').textContent = timestamp;
    document.getElementById('selected-record-section').style.display = 'block';

    try {
        const response = await fetch(apiUrl(`/api/history/${timestamp}/files`));
        const data = await response.json();

        if (data.success) {
            renderResults(timestamp, data.files);
        }
    } catch (e) {
        console.error('Failed to load results:', e);
    }
}

function renderResults(timestamp, files) {
    document.getElementById('results-section').style.display = 'block';

    // Videos
    if (files['proc_start.webm']) {
        document.getElementById('start-video-card').style.display = 'block';
        document.getElementById('start-video-player').src = apiUrl(`/api/serve/${timestamp}/proc_start.webm`);
    } else {
        document.getElementById('start-video-card').style.display = 'none';
    }

    if (files['proc_maxvel.webm']) {
        document.getElementById('maxvel-video-card').style.display = 'block';
        document.getElementById('maxvel-video-player').src = apiUrl(`/api/serve/${timestamp}/proc_maxvel.webm`);
    } else {
        document.getElementById('maxvel-video-card').style.display = 'none';
    }

    // Payload
    if (files['payload.json']) {
        document.getElementById('payload-section').style.display = 'block';
        fetch(apiUrl(`/api/serve/${timestamp}/payload.json`))
            .then(r => r.json())
            .then(data => {
                document.getElementById('payload-data').textContent = JSON.stringify(data, null, 2);
            });
    } else {
        document.getElementById('payload-section').style.display = 'none';
    }

    // Chart
    if (files['chart.png']) {
        document.getElementById('chart-section').style.display = 'block';
        document.getElementById('chart-img').src = apiUrl(`/api/serve/${timestamp}/chart.png`);
    } else {
        document.getElementById('chart-section').style.display = 'none';
    }

    // --- AI Report (with missing report + auto-regenerate) ---
    const reportEmptyEl = document.getElementById('report-empty');
    const reportSectionEl = document.getElementById('report-section');
    const regenerateBtn = document.getElementById('regenerate-report-btn');
    const emptyReasonEl = document.getElementById('report-empty-reason');
    const downloadSectionEl = document.getElementById('download-section');

    if (files['report.md']) {
        // 正常情况：报告存在，显示内容
        reportEmptyEl.style.display = 'none';
        reportSectionEl.style.display = 'block';
        fetch(apiUrl(`/api/serve/${timestamp}/report.md`))
            .then(r => r.text())
            .then(text => {
                document.getElementById('report-content').innerHTML = markdownToHTML(text);
            });
    } else {
        // 异常情况：报告缺失
        reportSectionEl.style.display = 'none';
        reportEmptyEl.style.display = 'block';

        if (files['payload.json']) {
            // 有 payload 但无 report → 是旧记录丢失报告，提示可重生成
            emptyReasonEl.innerHTML = `
                该分析记录已完成生物力学计算（检测到有效 payload.json），
                但 AI 教练诊断报告缺失（可能由旧版本 API 调用失败导致）。
                <br/><strong>Click the button below to regenerate using the current DeepSeek AI engine.</strong>
                <br/>点击下方按钮，使用当前的 DeepSeek AI 引擎重新生成诊断报告。
            `;
            regenerateBtn.style.display = 'inline-block';
            regenerateBtn.disabled = false;
            regenerateBtn.classList.remove('loading');
        } else {
            // 无 payload 也无 report → 纯新用户，流程还没走到AI
            emptyReasonEl.innerHTML = `
                请先完成视频分析流程，AI 教练会自动生成训练处方。
                <br/>Please upload videos and click "Start Analysis" first.
            `;
            regenerateBtn.style.display = 'none';
        }
    }

    // Download Word
    if (files['report.docx']) {
        downloadSectionEl.style.display = 'block';
    } else {
        downloadSectionEl.style.display = 'none';
    }

    // Switch to tracking tab
    switchTab('tracking');
}

/* 重新生成缺失的 AI 报告 (针对历史旧记录) */
async function regenerateMissingReport() {
    if (!state.selectedRecord) {
        alert('Please select a record first.');
        return;
    }

    const btn = document.getElementById('regenerate-report-btn');
    btn.disabled = true;
    btn.classList.add('loading');

    try {
        const response = await fetch(apiUrl(`/api/history/${state.selectedRecord}/regenerate_report`), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ athlete_info: state.athlete || {} })
        });

        const data = await response.json();

        if (data.success) {
            alert('✅ AI Coach report regenerated successfully!\n教练分析报告重新生成成功！');
            // 重新加载结果
            await loadRecordResults(state.selectedRecord);
            // 自动切到 AI Protocol tab
            switchTab('protocol');
        } else {
            alert('❌ Failed: ' + (data.message || 'Unknown error'));
        }
    } catch (e) {
        alert('❌ Error during regeneration: ' + e.message);
        console.error(e);
    } finally {
        btn.classList.remove('loading');
        btn.disabled = false;
    }
}

function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `tab-${tabName}`);
    });
}

function downloadWordReport() {
    if (!state.selectedRecord) return;
    window.location.href = apiUrl(`/api/download/${state.selectedRecord}/report.docx`);
}

function downloadVideo(filename) {
    if (!state.selectedRecord) return;
    window.location.href = apiUrl(`/api/download/${state.selectedRecord}/${filename}`);
}

/**
 * 完整 Markdown → HTML 解析器
 * 支持：标题 / 围栏代码块 / 引用块 / 表格(含对齐行) / 水平分隔线
 *       / 无序列表 / 有序列表 / 粗体 / 斜体 / 删除线 / 行内代码 / 链接
 */
function markdownToHTML(md) {
    if (!md) return '';

    // ----- 工具函数：行内格式化（纯文本 → 富文本内联元素） -----
    function inlineFormat(text) {
        if (!text) return '';
        // 先处理行内代码（保护其内容不被后续正则破坏）
        const codeTokens = [];
        text = text.replace(/`([^`]+?)`/g, (_, code) => {
            codeTokens.push(code);
            return `\x00CODE${codeTokens.length - 1}\x00`;
        });
        // 转义安全（避免 XSS，但是保留纯文本中的空格）
        text = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        // 链接 [text](url)
        text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
        // 删除线 ~~text~~
        text = text.replace(/~~([^~]+)~~/g, '<del>$1</del>');
        // 粗体 **text** 或 __text__
        text = text.replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>');
        text = text.replace(/__([^_]+?)__/g, '<strong>$1</strong>');
        // 斜体 *text* 或 _text_ (避免破坏 <em> 已嵌套的)
        text = text.replace(/(^|[^*])\*([^*\n]+?)\*(?!\*)/g, '$1<em>$2</em>');
        text = text.replace(/(^|[^_])_([^_\n]+?)_(?!_)/g, '$1<em>$2</em>');
        // 还原行内代码
        text = text.replace(/\x00CODE(\d+)\x00/g, (_, idx) => {
            const raw = codeTokens[parseInt(idx, 10)];
            const escaped = raw
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
            return `<code>${escaped}</code>`;
        });
        return text;
    }

    // ----- 表格解析辅助 -----
    function isTableLine(line) {
        const t = line.trim();
        return t.startsWith('|') && t.includes('|') && t.length > 2;
    }
    function parseTableRow(line) {
        let t = line.trim();
        if (t.startsWith('|')) t = t.slice(1);
        if (t.endsWith('|')) t = t.slice(0, -1);
        return t.split('|').map(cell => cell.trim());
    }
    function isTableAlignRow(cells) {
        return cells.length > 0 && cells.every(c => /^:?-{3,}:?$/.test(c));
    }
    function parseAlignments(cells) {
        return cells.map(c => {
            const left = c.startsWith(':');
            const right = c.endsWith(':');
            if (left && right) return 'center';
            if (right) return 'right';
            return 'left';
        });
    }
    function renderTable(rows) {
        if (rows.length === 0) return '';
        const header = parseTableRow(rows[0]);
        let idx = 1;
        let aligns = new Array(header.length).fill('left');
        if (rows.length > 1) {
            const row1 = parseTableRow(rows[1]);
            if (isTableAlignRow(row1)) {
                aligns = parseAlignments(row1);
                idx = 2;
            }
        }
        // 对齐 padding to header length (防止数据比 header 多/少)
        while (aligns.length < header.length) aligns.push('left');

        const theadCells = header.map((h, i) =>
            `<th style="text-align:${aligns[i]}">${inlineFormat(h)}</th>`
        ).join('');

        const bodyRows = rows.slice(idx).map(r => {
            const cells = parseTableRow(r);
            // 按最小长度配对，避免越界
            const tdHtml = [];
            for (let i = 0; i < Math.max(cells.length, header.length); i++) {
                const cell = cells[i] != null ? cells[i] : '';
                const align = aligns[i] || 'left';
                tdHtml.push(`<td style="text-align:${align}">${inlineFormat(cell)}</td>`);
            }
            return `<tr>${tdHtml.join('')}</tr>`;
        }).join('');

        return `<div class="md-table-wrapper"><table class="md-table"><thead><tr>${theadCells}</tr></thead><tbody>${bodyRows}</tbody></table></div>`;
    }

    // ===== 主解析流程（有限状态机） =====
    const rawLines = md.replace(/\r\n?/g, '\n').split('\n');
    let i = 0;
    const n = rawLines.length;
    let out = '';

    function flushPara(paraBuf) {
        if (paraBuf.length === 0) return;
        const text = paraBuf.join('\n');
        out += `<p>${inlineFormat(text)}</p>`;
        paraBuf.length = 0;
    }
    function flushUl(buf) {
        if (buf.length === 0) return;
        out += '<ul>' + buf.map(li => `<li>${inlineFormat(li)}</li>`).join('') + '</ul>';
        buf.length = 0;
    }
    function flushOl(buf) {
        if (buf.length === 0) return;
        out += '<ol>' + buf.map(li => `<li>${inlineFormat(li)}</li>`).join('') + '</ol>';
        buf.length = 0;
    }
    function flushBq(buf) {
        if (buf.length === 0) return;
        const inner = markdownToHTML(buf.join('\n')); // 递归支持引用中嵌套格式
        out += `<blockquote>${inner}</blockquote>`;
        buf.length = 0;
    }

    let paraBuf = [];
    let ulBuf = [];
    let olBuf = [];
    let bqBuf = [];

    while (i < n) {
        let line = rawLines[i];
        const trimmed = line.trim();

        // --- 1. 围栏代码块 ``` ---
        const fenceMatch = trimmed.match(/^```([\w-]*)\s*$/);
        if (fenceMatch) {
            flushPara(paraBuf); flushUl(ulBuf); flushOl(olBuf); flushBq(bqBuf);
            const lang = fenceMatch[1] || '';
            const codeLines = [];
            i++;
            while (i < n) {
                const ln = rawLines[i];
                if (/^```\s*$/.test(ln.trim())) break;
                codeLines.push(ln);
                i++;
            }
            i++; // skip closing fence
            const codeHtml = codeLines.join('\n')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
            out += `<pre class="md-code"><code class="language-${lang}">${codeHtml}\n</code></pre>`;
            continue;
        }

        // --- 2. 水平分隔线 --- /--- 或 *** 或 ___ ---
        if (/^-{3,}\s*$/.test(trimmed) ||
            /^\*{3,}\s*$/.test(trimmed) ||
            /^_{3,}\s*$/.test(trimmed)) {
            flushPara(paraBuf); flushUl(ulBuf); flushOl(olBuf); flushBq(bqBuf);
            out += '<hr class="md-hr"/>';
            i++;
            continue;
        }

        // --- 3. 表格（连续 |...| 行，首行后可跟对齐行 + 数据行） ---
        if (isTableLine(line) && ulBuf.length === 0 && olBuf.length === 0) {
            flushPara(paraBuf); flushBq(bqBuf);
            const tableRows = [line];
            i++;
            while (i < n && isTableLine(rawLines[i])) {
                tableRows.push(rawLines[i]);
                i++;
            }
            out += renderTable(tableRows);
            continue;
        }

        // --- 4. 标题 #, ##, ###, #### ---
        const hMatch = trimmed.match(/^(#{1,4})\s+(.*)$/);
        if (hMatch) {
            flushPara(paraBuf); flushUl(ulBuf); flushOl(olBuf); flushBq(bqBuf);
            const level = hMatch[1].length;
            out += `<h${level}>${inlineFormat(hMatch[2])}</h${level}>`;
            i++;
            continue;
        }

        // --- 5. 引用块 > text ---
        if (/^>\s?/.test(line)) {
            flushPara(paraBuf); flushUl(ulBuf); flushOl(olBuf);
            bqBuf.push(line.replace(/^>\s?/, ''));
            i++;
            continue;
        } else {
            flushBq(bqBuf);
        }

        // --- 6. 无序列表 -, *, + ---
        const ulMatch = trimmed.match(/^[-*+]\s+(.*)$/);
        if (ulMatch) {
            flushPara(paraBuf); flushOl(olBuf); flushBq(bqBuf);
            ulBuf.push(ulMatch[1]);
            i++;
            continue;
        } else {
            flushUl(ulBuf);
        }

        // --- 7. 有序列表 1. 2) 等 ---
        const olMatch = trimmed.match(/^\d+[\.)]\s+(.*)$/);
        if (olMatch) {
            flushPara(paraBuf); flushUl(ulBuf); flushBq(bqBuf);
            olBuf.push(olMatch[1]);
            i++;
            continue;
        } else {
            flushOl(olBuf);
        }

        // --- 8. 空行 → flush ---
        if (trimmed === '') {
            flushPara(paraBuf);
            i++;
            continue;
        }

        // --- 9. 普通段落（合并连续非空非列表行） ---
        paraBuf.push(trimmed);
        i++;
    }
    // 末尾 flush
    flushPara(paraBuf); flushUl(ulBuf); flushOl(olBuf); flushBq(bqBuf);

    return out;
}
