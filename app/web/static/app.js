const form = document.getElementById('upload-form');
const fileInput = document.getElementById('files');
const customFileBtn = document.getElementById('custom-file-btn');
const fileHint = document.getElementById('file-hint');
const dryRunInput = document.getElementById('dry-run');
const manualInput = document.getElementById('manual-records-json');
const submitBtn = document.getElementById('submit-btn');
const resetBtn = document.getElementById('reset-btn');

const statusPanel = document.getElementById('status-panel');
const statusText = document.getElementById('status-text');
const summaryPanel = document.getElementById('summary-panel');
const tablesPanel = document.getElementById('tables-panel');
const summaryCards = document.getElementById('summary-cards');

const validTableBody = document.querySelector('#valid-table tbody');
const reviewTableBody = document.querySelector('#review-table tbody');
const errorTableBody = document.querySelector('#error-table tbody');
const parseErrorBlock = document.getElementById('parse-error-block');
const parseErrorTableBody = document.querySelector('#parse-error-table tbody');

customFileBtn.addEventListener('click', () => {
  fileInput.click();
});

fileInput.addEventListener('change', () => {
  if (!fileInput.files || fileInput.files.length === 0) {
    fileHint.textContent = '尚未选择文件';
    return;
  }
  const count = fileInput.files.length;
  fileHint.textContent = `已选择 ${count} 个文件`;
});

resetBtn.addEventListener('click', () => {
  form.reset();
  fileHint.textContent = '尚未选择文件';
  clearResult();
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();

  const hasFiles = fileInput.files && fileInput.files.length > 0;
  const manualText = manualInput.value.trim();
  if (!hasFiles && !manualText) {
    showStatus('请至少上传1张图片，或填写手动输入记录', true);
    return;
  }

  const data = new FormData();
  if (hasFiles) {
    for (const file of fileInput.files) {
      data.append('files', file);
    }
  }

  data.append('dry_run', dryRunInput.checked ? 'true' : 'false');
  if (manualText) {
    data.append('manual_records_json', manualText);
  }

  setLoading(true);
  showStatus('任务处理中，请稍候...', false);

  try {
    const resp = await fetch('/api/v1/inventory/parse-sync', {
      method: 'POST',
      body: data,
    });

    const result = await resp.json();
    if (!resp.ok) {
      const detail = result.detail || '请求失败';
      showStatus(`处理失败: ${detail}`, true);
      return;
    }

    renderResult(result);
    showStatus(`任务完成: ${result.summary.status}，任务ID: ${result.task_id}`, false);
  } catch (error) {
    showStatus(`请求异常: ${error.message}`, true);
  } finally {
    setLoading(false);
  }
});

function setLoading(loading) {
  submitBtn.disabled = loading;
  submitBtn.textContent = loading ? '处理中...' : '开始处理';
}

function clearResult() {
  summaryPanel.classList.add('hidden');
  tablesPanel.classList.add('hidden');
  statusPanel.classList.add('hidden');

  summaryCards.innerHTML = '';
  validTableBody.innerHTML = '';
  reviewTableBody.innerHTML = '';
  errorTableBody.innerHTML = '';
  parseErrorBlock.classList.add('hidden');
  parseErrorTableBody.innerHTML = '';
}

function showStatus(message, isError) {
  statusPanel.classList.remove('hidden');
  statusText.textContent = message;
  statusText.classList.toggle('error', Boolean(isError));
}

function renderResult(result) {
  summaryPanel.classList.remove('hidden');
  tablesPanel.classList.remove('hidden');

  renderSummary(result.summary, result.task_id);
  renderValid(result.valid_records || []);
  renderReview(result.review_records || []);
  renderErrors(result.error_summary || []);
  renderParseErrors(result.debug?.parse_errors || []);
}

function renderSummary(summary, taskId) {
  const fields = [
    ['任务ID', taskId],
    ['状态', summary.status],
    ['图片数', summary.image_count],
    ['解析总数', summary.parsed_total],
    ['有效记录', summary.valid_total],
    ['待复核', summary.review_total],
    ['写入成功', summary.write_success],
    ['写入失败', summary.write_failed],
  ];

  summaryCards.innerHTML = fields
    .map(
      ([label, value]) => `
      <article class="summary-card">
        <div class="label">${escapeHtml(String(label))}</div>
        <div class="value">${escapeHtml(String(value))}</div>
      </article>
    `
    )
    .join('');
}

function renderValid(records) {
  if (records.length === 0) {
    validTableBody.innerHTML = '<tr><td colspan="5">无数据</td></tr>';
    return;
  }

  validTableBody.innerHTML = records
    .map(
      (r) => `
      <tr>
        <td>${escapeHtml(r.品类 || '')}</td>
        <td>${escapeHtml(r.型号 || '')}</td>
        <td>${escapeHtml(r.颜色 || '')}</td>
        <td>${escapeHtml(r.尺码 || '')}</td>
        <td>${escapeHtml(String(r.数量 ?? ''))}</td>
      </tr>
    `
    )
    .join('');
}

function renderReview(records) {
  if (records.length === 0) {
    reviewTableBody.innerHTML = '<tr><td colspan="6">无数据</td></tr>';
    return;
  }

  reviewTableBody.innerHTML = records
    .map(
      (r) => `
      <tr>
        <td>${escapeHtml(r.品类 || '')}</td>
        <td>${escapeHtml(r.型号 || '')}</td>
        <td>${escapeHtml(r.颜色 || '')}</td>
        <td>${escapeHtml(r.尺码 || '')}</td>
        <td>${escapeHtml(String(r.数量 ?? ''))}</td>
        <td>${escapeHtml(r.异常原因 || '')}</td>
      </tr>
    `
    )
    .join('');
}

function renderErrors(items) {
  if (items.length === 0) {
    errorTableBody.innerHTML = '<tr><td colspan="2">无数据</td></tr>';
    return;
  }

  errorTableBody.innerHTML = items
    .map(
      (e) => `
      <tr>
        <td>${escapeHtml(e.type || '')}</td>
        <td>${escapeHtml(String(e.count ?? ''))}</td>
      </tr>
    `
    )
    .join('');
}

function renderParseErrors(errors) {
  if (!errors || errors.length === 0) {
    parseErrorBlock.classList.add('hidden');
    return;
  }

  parseErrorBlock.classList.remove('hidden');
  parseErrorTableBody.innerHTML = errors
    .map(
      (e) => `
      <tr>
        <td class="error-cell">${escapeHtml(e.filename || '')}</td>
        <td class="error-cell">${escapeHtml(e.error || '')}</td>
      </tr>
    `
    )
    .join('');
}

function escapeHtml(input) {
  return input
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}
