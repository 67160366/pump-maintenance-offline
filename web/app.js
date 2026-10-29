const $ = id => document.getElementById(id);
let state, currentPage = 'overview', returnPage = 'overview', historyRows = [], historyPage = 0;
let actionBusy = false, questionBusy = false, historyKey = '', disconnected = false;
const names = {
  'Type': ['ชนิดผลิตภัณฑ์', ''], 'Air temperature [K]': ['อุณหภูมิอากาศ', 'K'],
  'Process temperature [K]': ['อุณหภูมิกระบวนการ', 'K'],
  'Rotational speed [rpm]': ['ความเร็วรอบ', 'รอบ/นาที'], 'Torque [Nm]': ['แรงบิด', 'นิวตันเมตร'],
  'Tool wear [min]': ['เวลาใช้งานเครื่องมือ', 'นาที'], 'Temperature': ['อุณหภูมิ', 'หน่วยยังไม่ยืนยัน'],
  'Vibration': ['การสั่น', ''], 'Pressure': ['ความดัน', ''], 'Flow_Rate': ['อัตราการไหล', ''],
  'RPM': ['ความเร็วรอบ', ''], 'Operational_Hours': ['ชั่วโมงทำงาน', '']
};
const identity = event => event?.machine_id ? `ปั๊ม ${event.machine_id}` : `รายการที่ ${String(event?.row || 0).padStart(2, '0')}`;
const statusLabel = value => value === 1 ? 'ควรตรวจสอบเพิ่มเติม' : value === 0 ? 'ยังไม่พบสัญญาณเตือน' : 'ข้อมูลไม่พอประเมิน';
const score = value => value === null || value === undefined ? '—' : value.toFixed(3);
const localTime = value => value ? new Intl.DateTimeFormat('th-TH', {timeZone:'Asia/Bangkok', hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false}).format(new Date(value)) : 'ไม่ระบุ';
function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function readableSummary(text) {
  // Presentation only: keep the stored summary, model facts and LLM prompt intact.
  const phrases = [
    ['ยังไม่พบสัญญาณเครื่องเสียจากโมเดล', 'ยังไม่พบสัญญาณเตือนในรายการนี้'],
    ['ยังไม่พบสัญญาณให้ตรวจบำรุงรักษาจากโมเดล', 'ยังไม่พบสัญญาณเตือนในรายการนี้'],
    ['ควรตรวจบำรุงรักษา', 'ควรตรวจสอบเพิ่มเติม'],
    ['คะแนนโมเดล:', 'คะแนนประเมิน:'],
    ['ยังไม่ใช่โอกาสเสียที่ผ่าน calibration', 'คะแนนนี้ไม่ใช่เปอร์เซ็นต์โอกาสเสีย'],
    ['ไม่ใช่โอกาสเสียที่ยืนยันแล้ว', 'คะแนนนี้ไม่ใช่เปอร์เซ็นต์โอกาสเสีย'],
    ['เป็นผลจากข้อมูลสังเคราะห์ AI4I ไม่ระบุสาเหตุยืนยันหรือเวลาที่จะเสีย', 'ใช้ข้อมูลจำลอง ยังบอกสาเหตุหรือเวลาที่เครื่องจะเสียไม่ได้'],
    ['คำเตือน: โมเดลไม่ชนะ baseline ใช้สาธิตระบบเท่านั้น', 'ผลทำนายยังไม่น่าเชื่อถือเพียงพอ ใช้ทดลองเท่านั้น'],
    ['ควรตรวจสอบค่าที่วัดและคู่มือปั๊มก่อนตัดสินใจ ไม่สามารถระบุสาเหตุเสียหรือเวลาที่เหลือได้', 'ควรตรวจสอบค่าที่วัดและคู่มือปั๊มก่อนตัดสินใจ ยังบอกสาเหตุหรือเวลาที่เครื่องจะเสียไม่ได้']
  ];
  return text.split('\n').filter(line => !line.startsWith('ค่าที่วัด:')).map(line => {
    for (const [before, after] of phrases) line = line.replaceAll(before, after);
    return line;
  }).join('\n');
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
    const isKelvin = key === 'Air temperature [K]' || key === 'Process temperature [K]';
    const displayValue = isKelvin && typeof value === 'number' ? value-273.15 : value;
    const group = element('div', undefined, 'detail-reading');
    const reading = element('strong', displayValue === null ? 'ไม่มีค่า' : typeof displayValue === 'number' ? displayValue.toLocaleString('en-US', {maximumFractionDigits:isKelvin ? 1 : 2}) : displayValue);
    reading.append(element('small', ' '+(isKelvin ? '°C' : unit))); group.append(element('span', name), reading); return group;
  }));
  $('detail-time').textContent = `เวลาที่บันทึก ${localTime(event.at)} · เวลาที่วัดจริง ${event.measured_at ? localTime(event.measured_at) : 'ไม่มีในข้อมูลตัวอย่าง'}`;
  $('detail-method').textContent = event.summary_method === 'local_llm_validated' ? 'AI ช่วยเลือกข้อความ' : event.summary_method === 'pending' ? 'กำลังสรุปผล' : event.summary_method === 'template' ? 'ข้อความมาตรฐาน' : event.summary_method === 'template_missing_data' ? 'ข้อมูลยังไม่ครบ' : 'ใช้ข้อความมาตรฐานแทน AI';
  $('detail-summary').textContent = event.summary ? readableSummary(event.summary) : 'ประเมินข้อมูลแล้ว กำลังเตรียมสรุปผล…';
  $('detail-facts').textContent = JSON.stringify({method:event.summary_method, classifier_ms:event.inference_seconds*1000, llm_seconds:event.llm_seconds, ...event.handoff}, null, 2);
  navigate('detail');
}
$('open-latest').addEventListener('click', () => detail(state?.current));
function render(data) {
  const wasDisconnected = disconnected;
  disconnected = false; state = data;
  if (wasDisconnected && !data.error) showError('');
  const meta = data.metadata, event = data.current;
  $('connection').textContent = 'ระบบพร้อมใช้งาน'; $('connection-dot').className = 'dot online';
  $('source').textContent = meta.dataset === 'ai4i' ? 'ข้อมูลจำลองสำหรับทดลองใช้งาน' : 'ข้อมูลปั๊มจากไฟล์ตัวอย่าง';
  $('context-note').textContent = meta.dataset === 'ai4i' ? 'ไม่ได้วัดจากปั๊มจริง' : 'ผลทำนายยังใช้ยืนยันกับปั๊มจริงไม่ได้';
  $('position').textContent = `ดูแล้ว ${data.position} / ${meta.rows} รายการ`;
  $('alert-count').textContent = data.stored.alerts; $('normal-count').textContent = data.stored.normal; $('total-count').textContent = data.stored.total;
  $('play').textContent = data.running ? 'Ⅱ พักการอ่าน' : '▶ ดูอัตโนมัติ';
  $('play').disabled = (!data.running && data.position >= meta.rows) || data.ask_busy || !!data.error;
  $('step').disabled = data.running || data.busy || data.ask_busy || data.position >= meta.rows || !!data.error;
  $('reset').disabled = data.busy || data.ask_busy;
  $('run-state').textContent = data.ask_busy ? 'กำลังตอบคำถาม' : data.busy ? 'กำลังประเมินข้อมูล' : data.running ? 'กำลังดูอัตโนมัติ' : data.position >= meta.rows ? 'ดูครบแล้ว เริ่มรอบใหม่ได้' : 'พร้อมดูรายการถัดไป';
  if (data.error) showError(data.error);
  $('status').textContent = event ? statusLabel(event.status) : 'พร้อมดูข้อมูลตัวอย่าง';
  $('status').className = 'status '+(!event || event.status === null ? 'idle' : event.status === 1 ? 'alert' : '');
  $('score').textContent = score(event?.score);
  $('latest-identity').textContent = event ? identity(event) : 'รอข้อมูล';
  $('latest-note').textContent = event ? `คะแนนตั้งแต่ ${meta.threshold.toFixed(3)} ขึ้นไป = ควรตรวจสอบ` : 'กด “ดูรายการถัดไป” เพื่อเริ่ม';
  $('score').title = 'คะแนนที่ระบบใช้ประเมิน ไม่ใช่เปอร์เซ็นต์โอกาสเสีย';
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
    if (!alerts.length) $('attention-list').append(element('p', data.position ? 'ยังไม่มีรายการที่ควรตรวจสอบในรอบนี้' : 'เริ่มดูข้อมูล แล้วรายการที่ควรตรวจสอบจะแสดงที่นี่', 'empty'));
    if (currentPage === 'history' && $('history-scope').value === 'session') loadHistory();
  }
  $('ask-method').textContent = data.question_llm_enabled ? 'ผู้ช่วยภาษา AI ช่วยอ่านคำถาม' : 'ตอบจากข้อมูลที่บันทึกไว้';
  $('ask-note').textContent = data.running ? 'กด “พักการอ่าน” ก่อนถาม' : data.busy ? 'รอให้ดูรายการนี้เสร็จ แล้วถามได้เลย' : 'เปิดดูรายการประกอบคำตอบได้';
  $('send-question').disabled = questionBusy || data.running || data.busy || data.ask_busy;
  document.querySelectorAll('[data-question]').forEach(button => button.disabled = questionBusy || data.running || data.busy || data.ask_busy);
  $('system-warning').textContent = meta.dataset === 'ai4i' ? 'ตอนนี้ใช้ข้อมูลจำลองสำหรับทดลอง ยังไม่ได้เชื่อมต่อหรือยืนยันผลกับปั๊มจริง' : 'ผลทำนายของชุดปั๊มนี้ยังไม่ดีกว่าการทายพื้นฐานอย่างชัดเจน ใช้ทดลองเท่านั้น';
  const values = {'ชนิดเครื่อง':data.resources.machine, 'หน่วยความจำของโปรแกรม':`${(data.resources.process_tree_rss_bytes/1024**2).toFixed(0)} MiB`, 'หน่วยความจำที่เครื่องใช้':`${(data.resources.system_used_bytes/1024**3).toFixed(2)} GiB`, 'อุณหภูมิตัวประมวลผล': data.resources.temperature_c === null ? 'เครื่องนี้ยังอ่านค่าไม่ได้' : `${data.resources.temperature_c.toFixed(1)} °C`, 'แบบจำลองที่ใช้ประเมิน':meta.model, 'ผู้ช่วยภาษา AI':meta.llm_configured ? 'ตั้งค่าแล้ว' : 'ไม่ได้เปิด ใช้ข้อความมาตรฐาน'};
  $('system-values').replaceChildren(...Object.entries(values).map(([key,value]) => { const row = element('div'); row.append(element('dt',key),element('dd',value)); return row; }));
}
async function request(url, options) {
  const response = await fetch(url, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `ระบบยังตอบกลับไม่ได้ ลองอีกครั้ง (รหัส ${response.status})`);
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
    $('history-context').textContent = `${result.stats.total} รายการ · แสดงล่าสุดไม่เกิน 100 รายการ · เวลาแสดงเป็นเวลาที่บันทึกตัวอย่าง`;
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
  if (!historyRows.length) $('record-list').append(element('p','ยังไม่มีรายการในช่วงนี้ ไปที่ “ภาพรวม” แล้วเริ่มดูข้อมูลก่อนได้เลย','empty'));
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
    const note = result.display_limit ? 'เปิดดูข้อมูลประกอบได้สูงสุด 3 รายการ • '+result.caveat : result.caveat;
    pending.append(element('span',note,'message-footnote'));
    const method = result.method==='local_llm_intent_validated' ? 'ผู้ช่วยภาษา AI ช่วยอ่านคำถาม • คำตอบคำนวณจากบันทึก' : result.method==='local_data_query' ? 'คำตอบคำนวณจากข้อมูลที่บันทึกไว้' : 'ผู้ช่วยภาษา AI ยังตอบไม่ได้ • ใช้ข้อมูลที่บันทึกไว้ตอบแทน';
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
    showError('ติดต่อระบบไม่ได้ กำลังลองเชื่อมต่อใหม่…');
  } finally { setTimeout(poll,1000); }
}
poll();
