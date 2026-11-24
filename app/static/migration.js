import {element, request, pretty} from './client.js';

const form = document.querySelector('#migration-source');
const file = document.querySelector('#migration-file');
const profile = document.querySelector('#migration-profile');
const notice = document.querySelector('#m-notice');
const detail = document.querySelector('#m-review');
const evidence = document.querySelector('#m-evidence');
let report, batch, busy = false;

function announce(text, failure = false) {
  notice.textContent = text;
  notice.dataset.failure = String(failure);
}

function payload() {
  const data = new FormData();
  if (file.files.length) data.append('file', file.files[0]);
  else data.append('sample', profile.value);
  return data;
}

function table(id, headers, rows, empty) {
  const node = document.querySelector(id);
  node.replaceChildren();
  const head = element('tr');
  head.append(...headers.map(title => element('th', title, {scope: 'col'})));
  node.createTHead().append(head);
  const body = node.createTBody();
  if (!rows.length) body.insertRow().insertCell().textContent = empty;
  for (const row of rows) {
    const tr = body.insertRow();
    tr.append(...row.map(value => element('td', value === null || value === undefined ? '—' : value)));
  }
}

function kpi(node, count, cents) {
  document.querySelector(node).textContent = `${count} 笔 / ${cents} 分`;
}

function draw() {
  if (!report) return;
  const b = report.balance;
  kpi('#m-kpi-source', b.source.count, b.source.cents);
  kpi('#m-kpi-attributed', b.attributed.count, b.attributed.cents);
  kpi('#m-kpi-pending', b.pending.count, b.pending.cents);
  document.querySelector('#m-kpi-isolated').textContent =
    `${b.isolated} 行（重放 ${b.replay}）`;
  document.querySelector('#m-sign-flag').textContent =
    `${b.balanced ? '已对平' : '未对平'} · ${b.signable ? '可签发' : '不可签发'}`;

  table('#m-ledger', ['新客户编号', '已归金额(分)'],
    Object.entries(report.ledger), '暂无已归客户金额');
  table('#m-attributed', ['源交易', '原签约客户', '新客户', '状态', '金额(分)'],
    report.attributed.map(r => [r.record, r.old_customer, r.new_customer, r.status, r.cents]),
    '暂无直接归属交易');
  table('#m-pending', ['源交易', '原签约客户', '新客户', '状态', '金额(分)'],
    report.pending.map(r => [r.record, r.old_customer, r.new_customer, r.status, r.cents]),
    '没有新旧编号同时命中的待核交易');
  table('#m-isolation', ['源行', '记录键', '客户编号', '原因码'],
    report.isolation.map(r => [r.line, r.record, r.customer, r.reason]),
    '当前文件没有隔离行');

  document.querySelector('#m-detail').textContent = pretty({
    对账: {
      行数守恒: b.line_conservation,
      笔数守恒: b.count_conservation,
      金额守恒: b.cents_conservation,
      台账守恒: b.ledger_conservation,
    },
    待核依据: report.pending.map(r => ({record: r.record, basis: r.basis})),
    隔离原因: b.issues,
  });

  detail.hidden = !batch;
  if (batch) {
    document.querySelector('#m-run-status').textContent =
      `${batch.id.slice(0, 10)} · ${batch.status} · r${batch.revision}`;
    const signable = batch.report.balance.signable;
    detail.querySelector('[value="APPROVED"]').disabled =
      !signable || batch.status === 'APPROVED';
    detail.querySelector('[value="HELD"]').disabled = batch.status === 'APPROVED';
    evidence.href = `/api/migrations/runs/${batch.id}/evidence`;
  }
}

function show(payload, committed = false) {
  batch = committed ? payload : null;
  report = committed ? payload.report : payload;
  detail.elements.note.value = batch?.note || '';
  draw();
}

async function refresh() {
  const data = await request('/api/migrations/runs');
  const target = document.querySelector('#m-history');
  target.replaceChildren();
  for (const item of data.items) {
    const li = element('li');
    li.append(
      element('button', item.id.slice(0, 10), {type: 'button', 'data-run': item.id}),
      element('span', item.status, {class: 'badge', 'data-result': item.status})
    );
    target.append(li);
  }
  if (!data.items.length) target.append(element('li', '尚无迁移批次'));
}

async function guard(action) {
  if (busy) return;
  busy = true;
  document.body.setAttribute('aria-busy', 'true');
  try { await action(); }
  catch (error) { announce(error.message, true); }
  finally { busy = false; document.body.removeAttribute('aria-busy'); }
}

document.querySelector('#migration-preview').addEventListener('click', () => guard(async () => {
  show(await request('/api/migrations/preview', {method: 'POST', body: payload()}));
  announce('迁移预览已更新（未入库）');
}));

form.addEventListener('submit', event => guard(async () => {
  event.preventDefault();
  const result = await request('/api/migrations/runs', {method: 'POST', body: payload()});
  show(result, true);
  announce('迁移批次已保存');
  await refresh();
}));

profile.addEventListener('change', () => { file.value = ''; });
file.addEventListener('change', () => {
  document.querySelector('#migration-file-name').textContent = file.files[0]?.name || '';
});

document.querySelector('#m-history').addEventListener('click', event => {
  const button = event.target.closest('[data-run]');
  if (!button) return;
  guard(async () => {
    show(await request(`/api/migrations/runs/${button.dataset.run}`), true);
    announce('已载入历史迁移批次');
  });
});

detail.addEventListener('submit', event => guard(async () => {
  event.preventDefault();
  const body = {
    status: event.submitter.value,
    revision: batch.revision,
    note: detail.elements.note.value,
  };
  const result = await request(`/api/migrations/runs/${batch.id}`, {
    method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  show(result, true);
  announce(result.status === 'APPROVED' ? '迁移批次已签发' : '迁移批次已暂缓');
  await refresh();
}));

guard(async () => {
  show(await request('/api/migrations/preview', {method: 'POST', body: payload()}));
  announce('迁移预览已更新（未入库）');
  await refresh();
});
