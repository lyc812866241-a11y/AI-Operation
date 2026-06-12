// 解码 Figma .fig -> nodes.json + frames.txt
// 用法: node decode_fig.js <path-to .fig 或 canvas.fig>
// 依赖: npm install kiwi-schema ; Node>=22(自带 zstd); 解 .fig 需 python(zipfile)
const fs = require('fs');
const zlib = require('zlib');
const path = require('path');
const { execSync } = require('child_process');
const kiwi = require('kiwi-schema');

const input = process.argv[2];
if (!input) { console.error('用法: node decode_fig.js <.fig 或 canvas.fig>'); process.exit(1); }

// 拿到 canvas.fig 字节(.fig 是 zip,用 python 取;直接给 canvas.fig 则直读)
let canvas;
if (input.toLowerCase().endsWith('.fig') && !path.basename(input).startsWith('canvas')) {
  // 可能是整包 .fig(zip)或就是 canvas.fig;先按 zip 试
  const head = fs.readFileSync(input).subarray(0, 8);
  if (head[0] === 0x50 && head[1] === 0x4b) {
    const tmp = path.join(process.cwd(), '_canvas_tmp.fig');
    execSync(`python -c "import zipfile,sys; open(r'${tmp}','wb').write(zipfile.ZipFile(r'${input}').read('canvas.fig'))"`);
    canvas = fs.readFileSync(tmp); fs.unlinkSync(tmp);
  } else {
    canvas = fs.readFileSync(input); // 本身就是 canvas.fig
  }
} else {
  canvas = fs.readFileSync(input);
}

if (canvas.toString('ascii', 0, 8) !== 'fig-kiwi') throw new Error('不是 fig-kiwi 容器');
let off = 8; const version = canvas.readUInt32LE(off); off += 4;
const blocks = [];
while (off + 4 <= canvas.length) {
  const len = canvas.readUInt32LE(off); off += 4;
  if (!len || off + len > canvas.length) break;
  const c = canvas.subarray(off, off + len); off += len;
  let r;
  if (c[0] === 0x28 && c[1] === 0xb5 && c[2] === 0x2f && c[3] === 0xfd) r = zlib.zstdDecompressSync(c); // ★ 数据块=zstd
  else { try { r = zlib.inflateRawSync(c); } catch { try { r = zlib.inflateSync(c); } catch { r = c; } } }
  blocks.push(r);
}
console.log('version', version, 'blocks', blocks.length, blocks.map(b => b.length).join(','));

const schema = kiwi.decodeBinarySchema(blocks[0]);
const defs = Object.fromEntries(schema.definitions.map(d => [d.name, d]));
const data = blocks.length === 2 ? blocks[1] : Buffer.concat(blocks.slice(1));
const bb = new kiwi.ByteBuffer(data);

function readBuiltin(t){switch(t){case 'bool':return !!bb.readByte();case 'byte':return bb.readByte();case 'int':return bb.readVarInt();case 'uint':return bb.readVarUint();case 'float':return bb.readVarFloat();case 'string':return bb.readString();case 'int64':return bb.readVarInt64();case 'uint64':return bb.readVarUint64();default:return undefined;}}
function readValue(type){const v=readBuiltin(type);if(v!==undefined)return v;const d=defs[type];if(!d)throw new Error('unknown type '+type);if(d.kind==='ENUM'){const n=bb.readVarUint();const f=d.fields.find(x=>x.value===n);return f?f.name:n;}if(d.kind==='STRUCT'){const o={};for(const f of d.fields)o[f.name]=f.isArray?readArray(f.type):readValue(f.type);return o;}return readMessage(d);}
function readArray(type){const n=bb.readVarUint();const a=new Array(n);for(let i=0;i<n;i++)a[i]=readValue(type);return a;}
function readMessage(d){const o={};while(true){const id=bb.readVarUint();if(id===0)break;const f=d.fields.find(x=>x.value===id);if(!f)throw new Error('unknown field '+id+' in '+d.name);o[f.name]=f.isArray?readArray(f.type):readValue(f.type);}return o;}

const root = defs['Message']; const msg = {}; let stoppedAt = null;
try {
  while (true) {
    const id = bb.readVarUint(); if (id === 0) break;
    const f = root.fields.find(x => x.value === id);
    if (!f) { stoppedAt = 'unknown root field ' + id; break; }
    try { msg[f.name] = f.isArray ? readArray(f.type) : readValue(f.type); }
    catch (e) { stoppedAt = f.name + ': ' + e.message; break; } // ★ root 容错:停在出错字段(nodeChanges 在前已读到)
  }
} catch (e) { stoppedAt = 'root: ' + e.message; }

const nc = msg.nodeChanges || [];
fs.writeFileSync('nodes.json', JSON.stringify(nc));
const frames = nc.filter(n => n.type === 'FRAME' && n.name)
  .map(n => `${n.name}\t${n.size ? Math.round(n.size.x) + 'x' + Math.round(n.size.y) : '?'}`);
fs.writeFileSync('frames.txt', frames.join('\n'));
console.log('stoppedAt:', stoppedAt, '| nodeChanges:', nc.length, '| FRAMEs:', frames.length);
console.log('已写 nodes.json / frames.txt');
