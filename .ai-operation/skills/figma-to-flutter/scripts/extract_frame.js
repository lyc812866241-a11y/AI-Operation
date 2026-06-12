// 打印某画面(FRAME)整棵子树蓝图(位置/尺寸/颜色/文字/图片哈希/圆角)
// 用法: node extract_frame.js <frameName> [nodes.json]
const fs = require('fs');
const frameName = process.argv[2];
const nc = JSON.parse(fs.readFileSync(process.argv[3] || 'nodes.json'));
if (!frameName) { console.error('用法: node extract_frame.js <frameName>'); process.exit(1); }

const key = g => g ? `${g.sessionID}:${g.localID}` : null;
const childrenOf = new Map();
for (const n of nc) { const p = n.parentIndex && key(n.parentIndex.guid); if (!p) continue; if (!childrenOf.has(p)) childrenOf.set(p, []); childrenOf.get(p).push(n); }
for (const a of childrenOf.values()) a.sort((x, y) => (x.parentIndex.position || '').localeCompare(y.parentIndex.position || ''));

const root = nc.find(n => n.name === frameName);
if (!root) { console.error('未找到画面:', frameName); process.exit(1); }

const hex = h => h ? Buffer.from(h).toString('hex') : '';
function fill(n){return (n.fillPaints||[]).map(p=>{
  if(p.type==='SOLID'){const c=p.color||{};return `SOLID rgba(${(c.r*255|0)},${(c.g*255|0)},${(c.b*255|0)},${(p.opacity??1)})`;}
  if(p.type==='IMAGE')return `IMAGE ${hex(p.image&&p.image.hash).slice(0,16)}`;
  return p.type;}).join(' | ');}
const sz=n=>n.size?`${Math.round(n.size.x)}x${Math.round(n.size.y)}`:'';
const tx=n=>n.transform?`(${Math.round(n.transform.m02)},${Math.round(n.transform.m12)})`:'';
const txt=n=>n.type==='TEXT'?` TEXT="${((n.textData&&n.textData.characters)||'').replace(/\n/g,'\\n').slice(0,40)}" fs=${n.fontSize||''}`:'';

const out=[];
(function walk(n,d){out.push(`${'  '.repeat(d)}${n.type} "${(n.name||'').slice(0,28)}" ${sz(n)} @${tx(n)}${n.cornerRadius?` r=${n.cornerRadius}`:''} ${fill(n)}${txt(n)}`);for(const c of (childrenOf.get(key(n.guid))||[]))walk(c,d+1);})(root,0);
fs.writeFileSync('frame_tree.txt', out.join('\n'));
console.log(out.join('\n'));
console.error('\n共 ' + out.length + ' 个节点 -> frame_tree.txt');
