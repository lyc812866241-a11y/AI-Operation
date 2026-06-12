# check_overlap.py —— 坑位重叠自检:位置定好后、灌皮前跑一遍,看有没有两个坑压在一起。
# 这是 AI 能自己闭的一致性检查(纯几何);重叠未必是错(图标叠在按钮上、角标叠在头像上是故意的),
# 所以它只"报告 + 让用户确认哪些是故意叠的",不硬性判错。
#
# 用法:
#   python check_overlap.py <坑位清单.json> [可容忍重叠比例,默认0]
# 坑位清单.json 形如:
#   { "frame": {"w":1334,"h":750},
#     "slots": [ {"name":"坑_主按钮","x":517,"y":630,"w":300,"h":90}, ... ] }
import sys, json

if len(sys.argv) < 2:
    print("用法: python check_overlap.py <坑位清单.json> [可容忍重叠比例,默认0]")
    sys.exit(1)

data = json.load(open(sys.argv[1], encoding="utf-8"))
tol = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0  # 0~1,小于这个比例的轻微重叠不报
slots = data["slots"]
fw = data.get("frame", {}).get("w")
fh = data.get("frame", {}).get("h")

def rect(s):
    return s["x"], s["y"], s["x"] + s["w"], s["y"] + s["h"]

def overlap_area(a, b):
    ax0, ay0, ax1, ay1 = rect(a); bx0, by0, bx1, by1 = rect(b)
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0
    return (ix1 - ix0) * (iy1 - iy0)

reports = []
for i in range(len(slots)):
    for j in range(i + 1, len(slots)):
        a, b = slots[i], slots[j]
        area = overlap_area(a, b)
        if area <= 0:
            continue
        small = min(a["w"] * a["h"], b["w"] * b["h"])
        frac = area / small if small else 1.0
        if frac > tol:
            reports.append((frac, a["name"], b["name"]))

# 顺带提醒越界(坑跑到画面外)
out_of_frame = []
if fw and fh:
    for s in slots:
        x0, y0, x1, y1 = rect(s)
        if x0 < 0 or y0 < 0 or x1 > fw or y1 > fh:
            out_of_frame.append(s["name"])

print("=== 坑位重叠自检 ===")
if not reports:
    print("✓ 没有重叠的坑。")
else:
    print(f"⚠ 发现 {len(reports)} 对重叠,请逐一确认是不是故意叠的(图标叠按钮、角标叠头像=正常;否则要挪):")
    for frac, n1, n2 in sorted(reports, reverse=True):
        print(f"  - {n1}  ×  {n2}  → 重叠占较小那个的 {round(frac*100)}%")
if out_of_frame:
    print("⚠ 跑到画面外的坑(位置或尺寸要收一下):", "、".join(out_of_frame))

sys.exit(0)
