// read_figma_positions.mjs —— 用只读钥匙读 Figma 里每个控件写死的位置宽高。
// 钥匙绝不写进文件,运行时当环境变量传:
//   FIGMA_TOKEN=<只读钥匙> node read_figma_positions.mjs <文件编号> [帧名]
// 文件编号 = 分享链接里 /design/<这一段>/ 的那段。
// 不传帧名:列出所有帧 + 各自整体位置;传帧名:钻进该帧,列出每个控件相对帧左上角的位置。
// 需要 Node ≥ 18(自带 fetch)。

const TOKEN = process.env.FIGMA_TOKEN;
const KEY = process.argv[2];
const FRAME = process.argv[3];

if (!TOKEN || !KEY) {
  console.error('用法: FIGMA_TOKEN=<只读钥匙> node read_figma_positions.mjs <文件编号> [帧名]');
  process.exit(1);
}
const H = { 'X-Figma-Token': TOKEN };

async function get(url) {
  const r = await fetch(url, { headers: H });
  if (!r.ok) { console.error('Figma 接口报错', r.status, await r.text()); process.exit(1); }
  return r.json();
}

const file = await get(`https://api.figma.com/v1/files/${KEY}?depth=2`);

if (!FRAME) {
  console.log('文件:', file.name);
  for (const page of file.document.children || []) {
    console.log('页:', page.name);
    for (const f of page.children || []) {
      const b = f.absoluteBoundingBox;
      if (b) console.log(`  - ${f.name} [${f.type}]  x=${Math.round(b.x)} y=${Math.round(b.y)} 宽=${Math.round(b.width)} 高=${Math.round(b.height)}`);
    }
  }
  console.log('\n（要看某帧里每个控件的位置,在命令后面加上帧名）');
  process.exit(0);
}

// 找到目标帧,钻进去读相对位置
let target = null;
for (const page of file.document.children || [])
  for (const f of page.children || [])
    if (f.name === FRAME) target = f;
if (!target) { console.error('没找到帧:', FRAME); process.exit(1); }

const b0 = target.absoluteBoundingBox;
const nodes = await get(`https://api.figma.com/v1/files/${KEY}/nodes?ids=${encodeURIComponent(target.id)}&depth=2`);
const doc = nodes.nodes[target.id].document;
console.log(`帧[${FRAME}] 整体 x=${Math.round(b0.x)} y=${Math.round(b0.y)} 宽=${Math.round(b0.width)} 高=${Math.round(b0.height)}`);
console.log('--- 帧内各控件(相对该帧左上角)---');
const out = [];
for (const c of doc.children || []) {
  const b = c.absoluteBoundingBox;
  if (!b) continue;
  const row = { name: c.name, type: c.type, x: Math.round(b.x - b0.x), y: Math.round(b.y - b0.y), w: Math.round(b.width), h: Math.round(b.height) };
  out.push(row);
  console.log(`  - ${row.name} [${row.type}]  左${row.x} 上${row.y}  宽${row.w} 高${row.h}`);
}
// 同时吐一份位置清单(可直接喂给 cutout_and_place.py)
console.log('\nSLOT_MAP_JSON:');
console.log(JSON.stringify({ frame: { w: Math.round(b0.width), h: Math.round(b0.height) }, slots: out }, null, 2));
