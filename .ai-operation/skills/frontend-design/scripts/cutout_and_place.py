# cutout_and_place.py —— 灌坑机:把组件图抠透明,按坑位清单装到对应位置,出预览。
# 不加任何阴影。干净组件 = 抠透明 + 直接装。
#
# 用法:
#   pip install "rembg[cpu]" pillow
#   python cutout_and_place.py <坑位清单.json> <组件图文件夹> <输出预览.png> [背景图.png]
#
# 坑位清单.json 形如(read_figma_positions.mjs 末尾会吐出这份):
#   { "frame": {"w":1334,"h":750},
#     "slots": [ {"name":"坑_主按钮","x":517,"y":630,"w":300,"h":90}, ... ] }
# 组件图文件夹:每个坑一张图,文件名 = 坑名(如 坑_主按钮.png)。缺图的坑自动跳过。
import sys, os, json
from PIL import Image
try:
    from rembg import remove, new_session
except Exception:
    print("缺 rembg。先装:pip install \"rembg[cpu]\""); sys.exit(1)

if len(sys.argv) < 4:
    print("用法: python cutout_and_place.py <坑位清单.json> <组件图文件夹> <输出预览.png> [背景图.png]")
    sys.exit(1)

slot_path, comp_dir, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
bg_path = sys.argv[4] if len(sys.argv) > 4 else None

data = json.load(open(slot_path, encoding="utf-8"))
fw, fh = data["frame"]["w"], data["frame"]["h"]
canvas = Image.open(bg_path).convert("RGBA").resize((fw, fh), Image.LANCZOS) if bg_path else Image.new("RGBA", (fw, fh), (0, 0, 0, 0))

sess = new_session("birefnet-general")  # 商用安全;玻璃发光边也保得住
placed, skipped = 0, []
for s in data["slots"]:
    # 找这个坑对应的组件图(按坑名)
    cand = [os.path.join(comp_dir, s["name"] + ext) for ext in (".png", ".jpg", ".jpeg", ".webp")]
    src = next((p for p in cand if os.path.exists(p)), None)
    if not src:
        skipped.append(s["name"]); continue
    img = Image.open(src).convert("RGBA")
    cut = remove(img, session=sess)            # 抠透明
    cut = cut.resize((s["w"], s["h"]), Image.LANCZOS)  # 缩到坑的确切尺寸
    canvas.alpha_composite(cut, (s["x"], s["y"]))      # 摆到确切位置,不加阴影
    placed += 1

canvas.convert("RGBA").save(out_path)
print(f"装好 {placed} 个坑 → {out_path}")
if skipped:
    print("没找到组件图、已跳过的坑:", "、".join(skipped))
