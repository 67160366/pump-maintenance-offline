const $ = id => document.getElementById(id);
let state;
let requesting = false;
let lastHistory = '';
const names = {
  'Type': ['ชนิดผลิตภัณฑ์', ''], 'Air temperature [K]': ['อุณหภูมิอากาศ', 'K'],
  'Process temperature [K]': ['อุณหภูมิกระบวนการ', 'K'],
  'Rotational speed [rpm]': ['ความเร็วรอบ', 'rpm'], 'Torque [Nm]': ['แรงบิด', 'Nm'],
  'Tool wear [min]': ['เวลาสึกหรอเครื่องมือ', 'min'], 'Temperature': ['อุณหภูมิ', ''],
  'Vibration': ['การสั่น', ''], 'Pressure': ['ความดัน', ''], 'Flow_Rate': ['อัตราการไหล', ''],
  'RPM': ['ความเร็วรอบ', ''], 'Operational_Hours': ['ชั่วโมงทำงาน', '']
};
const label = s => s === 1 ? 'ควรตรวจบำรุงรักษา' : s === 0 ? 'ยังไม่พบสัญญาณจากโมเดล' : 'ประเมินไม่ได้';
const ms = n => (n * 1000).toFixed(1) + ' ms';
const memory = n => (n / 1024 ** 2).toFixed(0) + ' MiB';
function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function showError(message) { $('error').textContent = message || ''; $('error').hidden = !message; }
function drawChart(history, threshold) {
  const svg = $('chart'); svg.replaceChildren();
  function shape(tag, attrs) {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    svg.append(node);
  }
  const y = n => 92 - n * 84;
  shape('line', { x1: 0, x2: 400, y1: y(threshold), y2: y(threshold), stroke: '#c5a15d', 'stroke-dasharray': '5 5' });
  // Break lines at unavailable rows rather than connecting across missing data.
  let segment = [];
  const flush = () => { if (segment.length) shape('polyline', { points: segment.join(' '), fill: 'none', stroke: '#1b7965', 'stroke-width': 2 }); segment = []; };
  history.forEach((event, index) => {
    if (event.score === null) return flush();
    const x = 8 + index * (384 / Math.max(history.length - 1, 1));
    segment.push(`${x},${y(event.score)}`);
    shape('circle', { cx: x, cy: y(event.score), r: 3, fill: event.status ? '#b77c2e' : '#1b7965' });
  }); flush();
}
function render(data) {
  state = data;
  const meta = data.metadata, event = data.current;
  $('connection').textContent = 'เชื่อมต่อเซิร์ฟเวอร์ในเครื่อง'; $('connection-dot').className = 'dot online';
  $('dataset').textContent = meta.dataset === 'ai4i' ? 'AI4I 2020 / Synthetic' : 'Industrial Pump / Demo';
  $('warning').textContent = meta.warning;
  $('llm-config').textContent = meta.llm_configured ? 'ตั้งค่า LLM แล้ว • ดูผลจริงในวิธีสรุป' : 'โหมด Template • ไม่ได้เปิด LLM';
  $('position').textContent = `${data.position} / ${meta.rows} แถว`;
  $('run-state').textContent = data.busy ? 'กำลังประมวลผลแถวปัจจุบัน' : data.running ? 'กำลังเล่นอัตโนมัติ' : data.position >= meta.rows ? 'เล่นครบแล้ว' : 'พร้อมอ่านข้อมูล';
  $('start').disabled = data.running || data.position >= meta.rows || !!data.error;
  $('step').disabled = data.running || data.busy || data.position >= meta.rows || !!data.error;
  $('reset').disabled = data.busy; $('pause').disabled = !data.running;
  if (data.error) showError(data.error);
  $('threshold').textContent = meta.threshold.toFixed(3);
  $('sensor-note').textContent = meta.dataset === 'ai4i' ? 'หน่วยจาก AI4I • อุณหภูมิเป็น Kelvin' : 'หน่วยของชุดปั๊มเดิมยังไม่ยืนยัน';
  for (const id of ['input', 'model', 'bridge', 'summary']) $('stage-' + id).classList.toggle('active', !!event);
  $('model-info').textContent = JSON.stringify({ model: meta.model, split: meta.split, threshold: meta.threshold, test_metrics: meta.test_metrics, hardware_acceptance_verified: false }, null, 2);
  if (event) {
    $('row-number').textContent = `แถว ${event.row}`;
    $('readings').replaceChildren(...Object.entries(event.readings).map(([key, value]) => {
      const [name, unit] = names[key] || [key, ''];
      const row = element('div', undefined, 'reading');
      const content = element('span', value === null ? 'ไม่มีค่า' : typeof value === 'number' ? value.toLocaleString('en-US', { maximumFractionDigits: 2 }) : value, 'reading-value');
      content.append(element('small', unit)); row.append(element('span', name, 'reading-label'), content); return row;
    }));
    $('status').textContent = label(event.status); $('status').className = 'status ' + (event.status === 1 ? 'alert' : event.status === null ? 'idle' : '');
    $('score').textContent = event.score === null ? '—' : event.score.toFixed(3);
    $('score-bar').value = event.score || 0; $('inference-time').textContent = ms(event.inference_seconds);
    $('summary').textContent = event.summary || (meta.llm_configured ? 'ได้ผลจาก ML แล้ว กำลังรอ LLM ในเครื่อง… (ไม่เกิน 30 วินาที)' : 'กำลังจัดข้อความจากข้อเท็จจริง…');
    $('summary-method').textContent = event.summary_method;
    $('summary-stage').textContent = event.summary_method === 'local_llm_validated' ? 'LLM ตอบและผ่านการตรวจแล้ว' : event.stage !== 'complete' ? 'กำลังจัดสรุป' : event.summary_method === 'template' ? 'ข้อความจาก Template' : 'Fallback → Template';
    $('llm-time').textContent = `เวลา LLM ${event.llm_seconds.toFixed(2)} s`;
    $('handoff').textContent = JSON.stringify(event.handoff, null, 2);
  } else {
    $('row-number').textContent = 'รอข้อมูล'; $('readings').replaceChildren(element('p', 'กดอ่านแถวถัดไปเพื่อเริ่มเดโม', 'muted'));
    $('status').textContent = 'รอประมวลผล'; $('status').className = 'status idle'; $('score').textContent = '—';
    $('score-bar').value = 0; $('inference-time').textContent = '— ms'; $('summary-method').textContent = 'ยังไม่มีสรุป';
    $('summary').textContent = 'เมื่ออ่านข้อมูล ระบบจะแสดงข้อเท็จจริงและข้อความไทยที่นี่';
    $('llm-time').textContent = 'เวลา LLM —'; $('summary-stage').textContent = 'Template / LLM ในเครื่อง'; $('handoff').textContent = 'ยังไม่มีข้อมูล';
  }
  const historyKey = JSON.stringify(data.history.map(e => [e.at, e.score]));
  if (historyKey !== lastHistory) {
    lastHistory = historyKey;
    const rows = [...data.history].reverse().map(e => {
      const row = element('tr');
      for (const text of [e.row, label(e.status), e.score === null ? '—' : e.score.toFixed(3), ms(e.inference_seconds), e.summary_method]) row.append(element('td', text));
      return row;
    });
    if (!rows.length) { const row = element('tr'), cell = element('td', 'ยังไม่มีผลประเมิน', 'muted'); cell.colSpan = 5; row.append(cell); rows.push(row); }
    $('history').replaceChildren(...rows); drawChart(data.history, meta.threshold);
  }
  $('machine').textContent = data.resources.machine; $('rss').textContent = memory(data.resources.process_tree_rss_bytes);
  $('system-memory').textContent = memory(data.resources.system_used_bytes);
  $('temperature').textContent = data.resources.temperature_c === null ? 'อ่านไม่ได้บนเครื่องนี้' : data.resources.temperature_c.toFixed(1) + ' °C';
}
async function poll() {
  try {
    const response = await fetch('/api/state', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
  } catch (error) {
    $('connection').textContent = 'ขาดการเชื่อมต่อเซิร์ฟเวอร์'; $('connection-dot').className = 'dot offline';
    for (const id of ['start', 'step', 'pause', 'reset']) $(id).disabled = true;
    showError('อ่านข้อมูลไม่ได้: ' + error.message);
  } finally { setTimeout(poll, 700); }
}
for (const action of ['start', 'pause', 'step', 'reset']) $(action).addEventListener('click', async () => {
  if (requesting) return;
  requesting = true; showError('');
  try {
    const response = await fetch('/api/action', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action }) });
    const result = await response.json(); if (!response.ok) throw new Error(result.error);
  } catch (error) { showError(error.message); } finally { requesting = false; }
});
poll();
