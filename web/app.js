const $ = id => document.getElementById(id);
let state, currentPage = 'overview', returnPage = 'overview', historyRows = [], historyPage = 0;
let actionBusy = false, questionBusy = false, historyKey = '', disconnected = false;
const names = {
  'Type': ['ชนิดผลิตภัณฑ์', ''], 'Air temperature [K]': ['อุณหภูมิอากาศ', 'K'],
  'Process temperature [K]': ['อุณหภูมิกระบวนการ', 'K'],
  'Rotational speed [rpm]': ['ความเร็วรอบ', 'rpm'], 'Torque [Nm]': ['แรงบิด', 'Nm'],
  'Tool wear [min]': ['เวลาสึกหรอเครื่องมือ', 'min'], 'Temperature': ['อุณหภูมิ', 'หน่วยไม่ยืนยัน'],
  'Vibration': ['การสั่น', ''], 'Pressure': ['ความดัน', ''], 'Flow_Rate': ['อัตราการไหล', ''],
  'RPM': ['ความเร็วรอบ', ''], 'Operational_Hours': ['ชั่วโมงทำงาน', '']
};
const identity = event => event?.machine_id ? `ปั๊ม ${event.machine_id}` : `Snapshot ${String(event?.row || 0).padStart(2, '0')}`;
const statusLabel = value => value === 1 ? 'ควรตรวจบำรุงรักษา' : value === 0 ? 'ยังไม่พบสัญญาณจากโมเดล' : 'ประเมินไม่ได้';
const score = value => value === null || value === undefined ? '—' : value.toFixed(3);
const ms = value => `${(value * 1000).toFixed(1)} ms`;
const localTime = value => value ? new Intl.DateTimeFormat('th-TH', {timeZone:'Asia/Bangkok', hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false}).format(new Date(value)) : 'ไม่ระบุ';
function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function showError(message) { $('error').textContent = message || ''; $('error').hidden = !message; }
$('error').addEventListener('click', () => showError(''));
function navigate(page) {
  if (page !== 'detail' && page !== 'system') returnPage = page;
  currentPage = page;
  for (const item of ['overview', 'history', 'ask', 'detail', 'system']) $('page-'+item).hidden = item !== page;
  document.querySelectorAll('[data-page]').forEach(button => {
    const active = button.dataset.page === (page === 'detail' || page === 'system' ? returnPage : page);
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
  });
  if (page === 'history') loadHistory();
}
document.querySelectorAll('[data-page]').forEach(button => button.addEventListener('click', () => navigate(button.dataset.page)));
$('device-info').addEventListener('click', () => navigate('system'));
$('back-system').addEventListener('click', () => navigate(returnPage));
$('back-detail').addEventListener('click', () => navigate(returnPage));
function detail(event) {
  if (!event) return;
  $('detail-title').textContent = identity(event);
  $('detail-reference').textContent = event.record_id ? `บันทึก #${event.record_id}` : 'กำลังประมวลผล';
  $('detail-readings').replaceChildren(...Object.entries(event.readings).map(([key, value]) => {
    const [name, unit] = names[key] || [key, ''];
    const group = element('div', undefined, 'detail-reading');
    const reading = element('strong', value === null ? 'ไม่มีค่า' : typeof value === 'number' ? value.toLocaleString('en-US', {maximumFractionDigits:2}) : value);
    reading.append(element('small', ' '+unit)); group.append(element('span', name), reading); return group;
  }));
  $('detail-time').textContent = `บันทึก ${localTime(event.at)} · เวลาวัด ${event.measured_at ? localTime(event.measured_at) : 'ไม่มีใน CSV'}`;
  $('detail-method').textContent = event.summary_method === 'local_llm_validated' ? 'LLM ตรวจแล้ว' : event.summary_method === 'pending' ? 'กำลังสรุป' : event.summary_method === 'template' ? 'Template' : 'Fallback';
  $('detail-summary').textContent = event.summary || 'ได้ผล ML แล้ว กำลังรอสรุปในเครื่อง…';
  $('detail-facts').textContent = JSON.stringify({method:event.summary_method, classifier_ms:event.inference_seconds*1000, llm_seconds:event.llm_seconds, ...event.handoff}, null, 2);
  navigate('detail');
}
$('open-latest').addEventListener('click', () => detail(state?.current));
function render(data) {
  const wasDisconnected = disconnected;
  disconnected = false; state = data;
  if (wasDisconnected && !data.error) showError('');
  const meta = data.metadata, event = data.current;
  $('connection').textContent = 'เชื่อมต่อเครื่อง'; $('connection-dot').className = 'dot online';
  $('source').textContent = meta.dataset === 'ai4i' ? 'CSV REPLAY / AI4I สังเคราะห์' : 'CSV REPLAY / ชุดปั๊มเดิม';
  $('context-note').textContent = meta.dataset === 'ai4i' ? 'Snapshot สาธิต • ไม่มีรหัสเครื่องจริง' : 'สาธิตเท่านั้น • ยังไม่ชนะ baseline';
  $('position').textContent = `${data.position} / ${meta.rows} แถว`;
  $('alert-count').textContent = data.stored.alerts; $('normal-count').textContent = data.stored.normal; $('total-count').textContent = data.stored.total;
  $('play').textContent = data.running ? 'Ⅱ หยุดพัก' : '▶ เล่นเดโม';
  $('play').disabled = (!data.running && data.position >= meta.rows) || data.ask_busy || !!data.error;
  $('step').disabled = data.running || data.busy || data.ask_busy || data.position >= meta.rows || !!data.error;
  $('reset').disabled = data.busy || data.ask_busy;
  $('run-state').textContent = data.ask_busy ? 'กำลังตอบคำถาม' : data.busy ? 'กำลังประมวลผล' : data.running ? 'กำลังเล่น' : data.position >= meta.rows ? 'เล่นครบแล้ว' : 'พร้อมอ่าน';
  if (data.error) showError(data.error);
  $('status').textContent = event ? statusLabel(event.status) : 'พร้อมอ่านข้อมูล';
  $('status').className = 'status '+(!event || event.status === null ? 'idle' : event.status === 1 ? 'alert' : '');
  $('score').textContent = score(event?.score);
  $('latest-identity').textContent = event ? identity(event) : 'รอข้อมูล';
  $('latest-note').textContent = event ? `Threshold ${meta.threshold.toFixed(3)} · ${ms(event.inference_seconds)}` : 'กดอ่านถัดไปเพื่อเริ่ม';
  $('open-latest').disabled = !event;
  const temp = event?.readings[meta.dataset === 'ai4i' ? 'Process temperature [K]' : 'Temperature'];
  $('temperature-label').textContent = meta.dataset === 'ai4i' ? 'อุณหภูมิกระบวนการ' : 'อุณหภูมิ (หน่วยไม่ยืนยัน)';
  $('latest-temperature').replaceChildren(document.createTextNode(temp === null || temp === undefined ? '—' : (meta.dataset === 'ai4i' ? temp-273.15 : temp).toFixed(1)));
  if (meta.dataset === 'ai4i' && temp !== null && temp !== undefined) $('latest-temperature').append(element('small', ' °C'));
  const nextHistoryKey = data.session+':'+data.position;
  if (historyKey !== nextHistoryKey) {
    historyKey = nextHistoryKey;
    const alerts = [...data.history].filter(row => row.status === 1).reverse().slice(0, 3);
    $('attention-list').replaceChildren(...alerts.map(row => {
      const button = element('button', undefined, 'attention-item');
      const label = element('span', identity(row)); label.append(element('small', ` · #${row.record_id}`));
      button.append(label, element('span', score(row.score)+' →')); button.addEventListener('click', () => detail(row)); return button;
    }));
    if (!alerts.length) $('attention-list').append(element('p', data.position ? 'ยังไม่มีรายการเตือนในรอบนี้' : 'อ่านข้อมูลเพื่อดูรายการที่ควรตรวจ', 'empty'));
    if (currentPage === 'history' && $('history-scope').value === 'session') loadHistory();
  }
  $('ask-method').textContent = data.question_llm_enabled ? 'LLM ในเครื่องช่วยเลือกคำถาม' : 'คำนวณจากข้อมูล • LLM ยังไม่เปิด';
  $('ask-note').textContent = data.running || data.busy ? 'หยุดเดโมก่อนถาม' : 'อ้างอิงบันทึกในเครื่อง';
  $('send-question').disabled = questionBusy || data.running || data.busy || data.ask_busy;
  document.querySelectorAll('[data-question]').forEach(button => button.disabled = questionBusy || data.running || data.busy || data.ask_busy);
  $('system-warning').textContent = meta.warning;
  const values = {'สถาปัตยกรรม':data.resources.machine, 'RAM โปรแกรม + LLM':`${(data.resources.process_tree_rss_bytes/1024**2).toFixed(0)} MiB`, 'RAM ระบบ':`${(data.resources.system_used_bytes/1024**3).toFixed(2)} GiB`, 'CPU': data.resources.temperature_c === null ? 'อ่านไม่ได้บนเครื่องนี้' : `${data.resources.temperature_c.toFixed(1)} °C`, 'โมเดล':meta.model, 'LLM สรุปแถว':meta.llm_configured ? 'ตั้งค่าแล้ว' : 'Template'};
  $('system-values').replaceChildren(...Object.entries(values).map(([key,value]) => { const row = element('div'); row.append(element('dt',key),element('dd',value)); return row; }));
}
async function request(url, options) {
  const response = await fetch(url, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
  return result;
}
async function action(value) {
  if (actionBusy) return;
  actionBusy = true; showError('');
  try { await request('/api/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:value})}); }
  catch (error) { showError(error.message); } finally { actionBusy = false; }
}
$('play').addEventListener('click', () => action(state?.running ? 'pause' : 'start'));
$('step').addEventListener('click', () => action('step'));
$('reset').addEventListener('click', () => action('reset'));
async function loadHistory() {
  try {
    const result = await request('/api/records?scope='+$('history-scope').value);
    historyRows = result.records;
    historyPage = Math.min(historyPage, Math.max(0, Math.ceil(historyRows.length/4)-1));
    $('history-context').textContent = `${result.stats.total} บันทึก · แสดงล่าสุดไม่เกิน 100 · เวลาแสดงเป็นเวลาบันทึก replay`;
    renderHistory();
  } catch (error) { showError(error.message); }
}
function renderHistory() {
  $('record-list').replaceChildren(...historyRows.slice(historyPage*4, historyPage*4+4).map(event => {
    const row = element('button', undefined, 'record-row');
    const title = element('span', undefined, 'record-identity'); title.append(element('span',identity(event)),element('small',`บันทึก #${event.record_id}`));
    row.append(title, element('span',statusLabel(event.status), 'record-status '+(event.status===1?'alert':'')),element('span',score(event.score),'record-number'),element('span',localTime(event.at),'record-time'));
    row.addEventListener('click', () => detail(event)); return row;
  }));
  if (!historyRows.length) $('record-list').append(element('p','ยังไม่มีข้อมูลที่บันทึก กดอ่านข้อมูลจากหน้าภาพรวมก่อน','empty'));
  $('page-number').textContent = `${historyPage+1} / ${Math.max(1,Math.ceil(historyRows.length/4))}`;
  $('previous-page').disabled = historyPage===0; $('next-page').disabled = (historyPage+1)*4>=historyRows.length;
}
$('history-scope').addEventListener('change', () => { historyPage=0; loadHistory(); });
$('previous-page').addEventListener('click', () => { historyPage--; renderHistory(); });
$('next-page').addEventListener('click', () => { historyPage++; renderHistory(); });
async function ask(question) {
  if (!question.trim() || questionBusy) return;
  questionBusy = true;
  const log = $('chat-log'); log.querySelector('.welcome')?.remove();
  log.append(element('div',question,'message user'));
  const pending = element('div','กำลังอ่านข้อมูลที่บันทึก…','message answer'); log.append(pending); log.scrollTop=log.scrollHeight;
  $('question').value=''; $('send-question').disabled=true;
  try {
    const result = await request('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question,scope:$('ask-scope').value})});
    pending.replaceChildren(element('span',result.scope_label,'message-label'),element('span',result.answer));
    const citations = element('div',undefined,'citations');
    for (const citation of result.citations) {
      const button=element('button',`ดูบันทึก #${citation.record_id}`);
      button.addEventListener('click',()=>detail(citation.event)); citations.append(button);
    }
    pending.append(citations);
    const note = result.display_limit ? 'หลักฐานสูงสุด 3 รายการ • '+result.caveat : result.caveat;
    pending.append(element('span',note,'message-footnote'));
    const method = result.method==='local_llm_intent_validated' ? `LLM เลือกคำถาม · คำนวณจากข้อมูล · ${result.llm_seconds.toFixed(1)} s` : result.method==='local_data_query' ? 'คำตอบจากฐานข้อมูล · ไม่ได้เรียก LLM' : 'LLM ไม่ผ่าน/ไม่พร้อม · ใช้ตัวค้นข้อมูลในเครื่อง';
    pending.append(element('span',method,'message-footnote'));
    while (log.children.length>16) log.firstElementChild.remove();
  } catch (error) { pending.textContent=error.message; }
  finally { questionBusy=false; $('send-question').disabled=false; log.scrollTop=pending.offsetTop-log.offsetTop; }
}
$('question-form').addEventListener('submit', event => { event.preventDefault(); ask($('question').value); });
document.querySelectorAll('[data-question]').forEach(button=>button.addEventListener('click',()=>ask(button.dataset.question)));
async function poll() {
  try { render(await request('/api/state',{cache:'no-store'})); }
  catch(error) {
    disconnected=true; $('connection').textContent='ขาดการเชื่อมต่อ'; $('connection-dot').className='dot offline';
    for(const id of ['play','step','reset','send-question']) $(id).disabled=true;
    showError('อ่านข้อมูลไม่ได้: '+error.message);
  } finally { setTimeout(poll,1000); }
}
poll();
