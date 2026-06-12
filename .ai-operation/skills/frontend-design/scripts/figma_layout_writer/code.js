// 排版写手 Layout Writer —— 在 Figma 里按"位置清单"画出一帧带名字的色块坑。
// 用法:在 Figma 桌面端 Plugins → Development → Import plugin from manifest 载入本插件,
//      把下面 SLOTS 换成本次第 1 步定好的位置清单,跑一次即可。
// 产物:一帧带名字的空骨架,供人手拖调整;之后用 read_figma_positions 读回坐标核对。
const F = figma;

// ↓↓↓ 把这份清单换成你本次的位置清单(单位:相对帧左上角的像素;颜色仅为肉眼区分)↓↓↓
const FRAME = { name: "排版试验", x: 0, y: 0, w: 1334, h: 750 }; // 帧的位置和尺寸,按目标屏比例
const SLOTS = [
  { name: "坑_返回",   x: 40,   y: 40,  w: 96,  h: 96,  c: [0.92, 0.45, 0.45] },
  { name: "坑_设置",   x: 1198, y: 40,  w: 96,  h: 96,  c: [0.92, 0.45, 0.45] },
  { name: "坑_标题",   x: 487,  y: 48,  w: 360, h: 96,  c: [0.95, 0.80, 0.35] },
  { name: "坑_主内容", x: 167,  y: 200, w: 1000,h: 400, c: [0.40, 0.65, 0.95] },
  { name: "坑_主按钮", x: 517,  y: 630, w: 300, h: 90,  c: [0.95, 0.55, 0.30] }
];
// ↑↑↑ 以上替换 ↑↑↑

(async () => {
  await F.loadFontAsync({ family: "Inter", style: "Bold" });
  const frame = F.createFrame();
  frame.name = FRAME.name;
  frame.resize(FRAME.w, FRAME.h);
  frame.x = FRAME.x; frame.y = FRAME.y;
  frame.fills = [{ type: "SOLID", color: { r: 0.12, g: 0.13, b: 0.18 } }];

  for (const s of SLOTS) {
    const rect = F.createRectangle();
    rect.name = s.name;
    rect.resize(s.w, s.h);
    rect.cornerRadius = 12;
    rect.fills = [{ type: "SOLID", color: { r: s.c[0], g: s.c[1], b: s.c[2] }, opacity: 0.65 }];
    frame.appendChild(rect);
    rect.x = s.x; rect.y = s.y;

    const label = F.createText();
    label.fontName = { family: "Inter", style: "Bold" };
    label.characters = s.name;
    label.fontSize = Math.max(14, Math.min(28, Math.floor(s.h / 4)));
    label.fills = [{ type: "SOLID", color: { r: 1, g: 1, b: 1 } }];
    frame.appendChild(label);
    label.x = s.x + 8; label.y = s.y + 8;
  }

  F.currentPage.appendChild(frame);
  F.viewport.scrollAndZoomIntoView([frame]);
  F.closePlugin(FRAME.name + " 已生成,可以开始拖拽调整");
})();
