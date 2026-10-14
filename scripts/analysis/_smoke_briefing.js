// L2 无头 DOM 断言 —— 新加坡仿真成果看板
// 用法：NODE_PATH=<workspace>/node_modules node _smoke_briefing.js <page.html>
// 说明：页面为零 JS 的静态看板，故 L2 的「运行时错误」维度天然为空；
//       本脚本以 DOM 结构断言等价覆盖：容器非空 / 图表与表格计数 / 文案完整性 / 无模板残留。
const fs = require('fs');
const { JSDOM, VirtualConsole } = require('jsdom');

const html = fs.readFileSync(process.argv[2], 'utf8');
const errs = [];
const vc = new VirtualConsole();
vc.on('jsdomError', e => errs.push('jsdomError: ' + e.message));
vc.on('error', (...a) => errs.push('console.error: ' + a.join(' ')));

const dom = new JSDOM(html, { runScripts: 'dangerously', pretendToBeVisual: true, virtualConsole: vc });
const d = dom.window.document;
const text = d.body.textContent;

const fails = [];
let pass = 0;
function chk(name, cond, extra = '') {
  if (cond) { pass++; console.log(`  [OK]   ${name}${extra ? '  ' + extra : ''}`); }
  else { fails.push(name); console.log(`  [FAIL] ${name}${extra ? '  ' + extra : ''}`); }
}

console.log('L2 无头 DOM 断言 ｜ ' + process.argv[2]);

chk('页面无运行时错误', errs.length === 0, errs.slice(0, 3).join(' | '));
chk('title 非空', (d.title || '').length > 5, d.title);

const figs = d.querySelectorAll('figure');
chk('figure 计数 == 11', figs.length === 11, `实际 ${figs.length}`);

const imgs = [...d.querySelectorAll('img')];
chk('img 计数 == 11', imgs.length === 11, `实际 ${imgs.length}`);
chk('全部 img 为内嵌 base64（无外链/无 CDN）',
  imgs.every(i => (i.getAttribute('src') || '').startsWith('data:image/png;base64,')),
  '外链数 ' + imgs.filter(i => !(i.getAttribute('src') || '').startsWith('data:')).length);
chk('无 <script>（零 JS，离线自包含）', d.querySelectorAll('script').length === 0);
chk('无 <link rel=stylesheet> 外链', d.querySelectorAll('link[rel=stylesheet]').length === 0);

const tables = [...d.querySelectorAll('table.tbl')];
chk('表格计数 >= 8', tables.length >= 8, `实际 ${tables.length}`);
const emptyTables = tables.filter(t => t.querySelectorAll('tbody tr').length === 0);
chk('无空表（每表至少 1 行）', emptyTables.length === 0, `空表 ${emptyTables.length}`);
const noHead = tables.filter(t => t.querySelectorAll('thead th').length === 0);
chk('每表均有表头', noHead.length === 0);

const cards = d.querySelectorAll('.card');
chk('KPI 卡计数 == 12', cards.length === 12, `实际 ${cards.length}`);
chk('KPI 卡均有 值 与 说明',
  [...cards].every(c => c.querySelector('.v') && c.querySelector('.k') && c.querySelector('.s')));

// 文案完整性（关键结论必须出现在页面上，不得被截断/丢失）
const musts = ['D5 = FAIL', '1.0601', '66.0603', '不晋升 v1.1', 'EXECUTION_LEVEL_PARTIAL',
  'PIE+MCE', 'CANONICAL_MEDIAN', '6.64%', '16/17', '信任锚', '基线', 'FAIL'];
musts.forEach(m => chk(`文案存在「${m}」`, text.includes(m)));

// 模板残留
const ph = text.match(/__[A-Z0-9_]+__/g);
chk('无未替换占位符', !ph, ph ? [...new Set(ph)].join(',') : '');
const md = text.match(/\*\*[^*\n]{1,40}\*\*/g);
chk('无 markdown 粗体残留', !md, md ? md.slice(0, 3).join(' | ') : '');
chk('无 markdown 表格残留', !text.includes('| --- |'));

// 长表行数（与源数据规模相符）
// ★注意：标题与表格之间可能夹有 <p class="lead"> / <div class="note"> ⇒ 必须向后扫描若干兄弟节点
function rowsOf(titleFragment) {
  const h = [...d.querySelectorAll('h2,h3')].find(e => e.textContent.includes(titleFragment));
  if (!h) return -1;
  let n = h.nextElementSibling, hops = 0;
  while (n && hops++ < 6) {
    if (n.matches('table.tbl')) return n.querySelectorAll('tbody tr').length;
    const t = n.querySelector && n.querySelector('table.tbl');
    if (t) return t.querySelectorAll('tbody tr').length;
    n = n.nextElementSibling;
  }
  return -1;
}
const nCorr = rowsOf('走廊归因');
chk('走廊归因表行数 >= 8', nCorr >= 8, `实际 ${nCorr}`);
const nSec = rowsOf('断面标定明细');
chk('断面明细表行数 == 30', nSec === 30, `实际 ${nSec}`);
const nGate = rowsOf('执行级门禁');
chk('门禁表行数 >= 15', nGate >= 15, `实际 ${nGate}`);
const nRecon = rowsOf('看板自检');
chk('对账表行数 == 13', nRecon === 13, `实际 ${nRecon}`);

console.log(`\n结果：PASS ${pass} ｜ FAIL ${fails.length}` + (fails.length ? `  ⇒ ${fails.join('; ')}` : ''));
process.exit(fails.length ? 1 : 0);
