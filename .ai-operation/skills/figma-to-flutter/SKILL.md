# figma-to-flutter — Figma 设计稿(.fig)解析 → Flutter 界面还原 → 装机

> **触发词**: figma, .fig, 解析设计稿, 设计稿装机, UI 还原, 还原设计, 把设计做成页面
>
> **能力**: 把 Figma `.fig` 文件本地解码成节点树(位置/尺寸/颜色/文字/图片),
> 按图片哈希精确提取美术素材,再 1:1 还原为 Flutter 界面并装机验证。
> **不依赖 Figma 客户端、不需手动导出 PNG。**

---

## 0. 物理边界(先认清,别白干)

- `.fig` 里**只有长相,没有行为**:记录"按钮在哪、什么色、贴哪张图",**不记录**点击跳哪、业务逻辑、数据。
- 所以"解析 → 自动变成能玩的产品"**不可能全自动**。能自动的是:① 提取素材 ② 还原静态界面装机看。
- **推荐策略**:不要从 .fig 生成一堆死界面再苦哈哈接线。**保留现有能跑的界面 + 逻辑,用设计的素材/配色/排版换皮**;或新页先做静态壳,再单独按现有逻辑接跳转。

---

## 1. `.fig` 文件结构

`.fig` 是一个 **ZIP 包**(魔数 `50 4b 03 04`)。解压得到:
- `canvas.fig` — 设计数据,**fig-kiwi 二进制容器**(核心)
- `meta.json` — 文件名/缩略图/导出时间
- `images/<40位sha1>` — 所有美术图(**无扩展名**,按内容哈希命名;PNG/JPG 看魔数)

---

## 2. 解码 canvas.fig(fig-kiwi 容器)

容器结构:`"fig-kiwi"(8B magic) + version(uint32 LE) + 多个块`,每块 = `uint32 LE 长度 + 压缩字节`。
- **块0 = Kiwi schema**(自带!),用 **deflate(raw)** 压缩 → `zlib.inflateRawSync`
- **块1+ = 数据消息**(root 类型 `Message`),**新版 Figma 用 ZSTD 压缩**(魔数 `28 b5 2f fd`)→ `zlib.zstdDecompressSync`(Node ≥22)

> ⚠️ **头号大坑(本项目踩过)**:数据块是 **zstd 不是 deflate**。若只 `inflateRaw` 且失败后 fallback 保留原字节,会把**压缩数据当解压结果**喂进解码器 → 全是乱码 / 在某个类型上崩。**必须按魔数判断 zstd**。

> ⚠️ 二号坑:`kiwi-schema` 的严格生成解码器会在某个较新类型(如 `ClientRenderedMetadata`)抛 "invalid message"。用**通用容错解码器**(本 skill 的 `decode_fig.js`):root 层逐字段读,遇错就停——要的 `nodeChanges`(field id 4)在前面,早读到了。

依赖:`npm install kiwi-schema`(可信,Figma 联创 Evan Wallace 出品)。

**用法**:
```
node decode_fig.js <path-to.fig>
# 产出:nodes.json(全部节点)、frames.txt(画面清单:FRAME 名/尺寸)
```

---

## 3. 节点树 → 界面蓝图

`nodes.json` 是 `nodeChanges` 数组,每个节点常用字段:
- `guid {sessionID,localID}`、`parentIndex.guid`(父)、`parentIndex.position`(排序)
- `type`:FRAME / TEXT / ROUNDED_RECTANGLE / ELLIPSE / VECTOR / INSTANCE / SYMBOL …
- `name`、`size {x,y}`、`transform {m00..m12}`(m02=x, m12=y,相对父)
- `fillPaints[]`:`{type:'SOLID', color:{r,g,b}, opacity}` 或 `{type:'IMAGE', image:{hash}}`(hash 转 hex = images/ 文件名)或 `GRADIENT_*`
- `cornerRadius`、`textData.characters`(文字内容)、`fontSize`

**步骤**:用 `guid→node` 和 `parent→children[]` 建树;按 `name` 找目标画面(如 `主界面`);递归导出子树,每个节点记 `type/name/x/y/w/h/fill/text/radius` → 实现蓝图。
脚本:`extract_frame.js <frameName>` 打印该画面整棵子树。

---

## 4. 精确提取素材

IMAGE 填充的 `image.hash`(hex)**就是 `images/` 里的文件名前缀**。收集目标画面用到的所有 hash → 从 zip 提取对应 `images/<hash>` → 按魔数补 `.png/.jpg`。
脚本:`extract_images.js <frameName> <outDir>`。
> INSTANCE/SYMBOL(组件实例,如图标)的图不在自身 fillPaints,要顺着 symbol 定义再取一层(进阶,首版可先占位)。

---

## 5. 还原为 Flutter

- 用 `Stack` + `Positioned(left,top,width,height)`,坐标尺寸**直接用设计像素**(子节点相对父 frame)。
- 整张包一层 `FittedBox` 缩放到设备:
  - **比例一致** → `BoxFit.contain` / `fitWidth`,无失真。
  - **比例不一致**(如设计 4:3 vs 设备 16:10):`contain` 会留边(非满屏);要满屏又不裁切按钮只能 `BoxFit.fill`(轻微拉伸)。**先跟用户确认满屏 vs 不失真。**
- 映射:TEXT→`Text`(用实测 fontSize/color);ROUNDED_RECTANGLE→`Container`(color/borderRadius);IMAGE→`Image.asset`;GRADIENT→`LinearGradient`;VECTOR→难,先用近似形状/占位;INSTANCE→symbol 图或占位。
- 颜色:`color.r/g/b` 是 0~1,×255;`opacity` 单独乘。

---

## 6. 接逻辑 & 装机

- 纯视觉壳先做出来,**入口先占位**(toast),装机验版式。
- 再按**现有代码逻辑**逐个接跳转(新页指向现有 Screen / 新建逻辑)。设计无行为,这步是人工。
- 装机:`flutter build apk --debug` → `adb install -r` → `adb shell monkey -p <pkg> -c android.intent.category.LAUNCHER 1` → `adb exec-out screencap`(注意:PowerShell `>` 会损坏二进制,用 `adb shell screencap -p /sdcard/x.png` + `adb pull`)→ 截图比对设计。

---

## 7. 标准流程(每次按这个做)

1. 确认 .fig 路径 → 解压看结构(`canvas.fig`/`meta.json`/`images/`)
2. `npm install kiwi-schema`(若没装)→ `node decode_fig.js <fig>` → 得 nodes.json + frames.txt
3. 跟用户对齐:**做哪个画面**、**满屏 vs 不失真**、**入口怎么接**(先占位还是接现有页)
4. `extract_frame.js <画面名>` 出蓝图 → `extract_images.js <画面名>` 出素材入 `assets/`
5. 走项目 taskSpec 流程([提需]→propose→submit→approve)→ 写 Flutter 界面
6. build + install + 截图验收 → 提交 → [存档]

> 复用脚本在本 skill 的 `scripts/` 下。决策点(满屏/接线/画面范围)必须问用户,别替他定。
