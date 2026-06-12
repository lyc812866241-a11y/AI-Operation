// 提取某画面用到的所有 IMAGE 填充素材到指定目录(按图片哈希精确取)
// 用法: node extract_images.js <frameName> <figPath> <outDir> [nodes.json]
const fs = require('fs');
const { execSync } = require('child_process');
const frameName = process.argv[2], figPath = process.argv[3], outDir = process.argv[4] || 'extracted_imgs';
const nc = JSON.parse(fs.readFileSync(process.argv[5] || 'nodes.json'));
if (!frameName || !figPath) { console.error('用法: node extract_images.js <frameName> <figPath> <outDir>'); process.exit(1); }

const key = g => g ? `${g.sessionID}:${g.localID}` : null;
const childrenOf = new Map();
for (const n of nc) { const p = n.parentIndex && key(n.parentIndex.guid); if (!p) continue; (childrenOf.get(p) || childrenOf.set(p, []).get(p)).push(n); }
const root = nc.find(n => n.name === frameName);
if (!root) { console.error('未找到画面:', frameName); process.exit(1); }

const hashes = new Set();
const hex = h => h ? Buffer.from(h).toString('hex') : null;
(function walk(n){for(const p of (n.fillPaints||[]))if(p.type==='IMAGE'&&p.image&&p.image.hash){const h=hex(p.image.hash);if(h)hashes.add(h);}for(const c of (childrenOf.get(key(n.guid))||[]))walk(c);})(root);

fs.mkdirSync(outDir, { recursive: true });
const oDir = outDir.replace(/\\/g, '\\\\');
const fPath = figPath.replace(/\\/g, '\\\\');
const py = `import zipfile,os
z=zipfile.ZipFile(r'''${figPath}''')
names=set(n.split('/')[-1] for n in z.namelist() if n.startswith('images/'))
out=r'''${outDir}'''
for h in ${JSON.stringify([...hashes])}:
    if h in names:
        b=z.read('images/'+h)
        ext='png' if b[:2]==b'\\x89P' else ('jpg' if b[:2]==b'\\xff\\xd8' else 'bin')
        open(os.path.join(out,h[:12]+'.'+ext),'wb').write(b); print('OK',h[:12],ext,len(b))
    else:
        print('MISSING',h)
`;
fs.writeFileSync('_extract_tmp.py', py);
console.log('图片 hash 数:', hashes.size);
console.log(execSync('python _extract_tmp.py', { encoding: 'utf8' }));
fs.unlinkSync('_extract_tmp.py');
