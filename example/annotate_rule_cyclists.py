#!/usr/bin/env python3
"""
Detect 'person' and 'bicycle' with YOLO, then derive 'cyclist' if:
  - pedestrian box overlaps a cycle box, AND
  - the cycle is positioned lower in the image (its bottom y2 is below the person's y2).
For matched pairs, create a NEW UNION bounding box labeled 'cyclist'.
Keep unmatched pedestrians as 'pedestrian'. Ignore bicycles that don't form a cyclist.
Also detect and keep 'car', 'motorcycle', 'bus', and 'truck' as passthrough labels.

Input:
  images_in/   <-- put your .jpg/.jpeg/.png

Output:
  dataset_yolo/
    images/    (copied originals)
    labels/    (YOLO .txt with 'pedestrian', 'cyclist', 'car', 'motorcycle', 'bus', 'truck')
    preview/   (drawn boxes so you can SEE the rule worked)
    run.log    (per-image counts)
"""

from pathlib import Path
import shutil
import cv2
from PIL import Image
from ultralytics import YOLO

# =========================
# CONFIG (edit if needed)
# =========================
INPUT_DIR = "images_in"
OUTPUT_DIR = "dataset_yolo"
MODEL_WEIGHTS = "yolo11n.pt"      # n=speed, s/m for better accuracy
CONF_THRESH = 0.25                # detector confidence
IOU_THRESH  = 0.05                # min IoU (pedestrian ⨂ cycle) to consider pairing
LOWER_MARGIN_PX = 5               # cycle must be at least this many px lower than pedestrian (by bottom edge)
MIN_SIDE = 4                      # drop detector boxes smaller than this (px)
EXTENSIONS = {".jpg", ".jpeg", ".png"}
SAVE_PREVIEW = True
LOG_FILENAME = "run.log"

DETECTOR_CLASSES = {"person", "bicycle", "car", "motorcycle", "bus", "truck"}

# Final label schema (YOLO IDs are by order)
CLASSES = ["pedestrian", "cyclist", "car", "motorcycle", "bus", "truck"]

# Colors for preview (BGR)
COLORS = {
    "pedestrian": (0, 255, 255),  # yellow
    "cyclist":    (0, 165, 255),  # orange
    "car": (0, 255, 0),          # green
    "motorcycle": (255, 0, 255), # magenta
    "bus": (255, 0, 0),          # blue
    "truck": (0, 0, 255),        # red
}

# =========================
# Helpers
# =========================
def ensure_dirs(root: Path, save_preview: bool):
    (root / "images").mkdir(parents=True, exist_ok=True)
    (root / "labels").mkdir(parents=True, exist_ok=True)
    if save_preview:
        (root / "preview").mkdir(parents=True, exist_ok=True)

def iou_xyxy(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    areaA = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    areaB = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    return inter / (areaA + areaB - inter + 1e-9)

def union_box(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return [min(ax1, bx1), min(ay1, by1), max(ax2, bx2), max(ay2, by2)]

def xyxy_to_xywhn(xyxy, W, H):
    x1, y1, x2, y2 = xyxy
    w = max(1.0, x2 - x1); h = max(1.0, y2 - y1)
    cx = x1 + w / 2.0; cy = y1 + h / 2.0
    return cx / W, cy / H, w / W, h / H

def write_yolo_label(label_path: Path, objs, W, H, classes):
    # objs: [(cls_name, xyxy, conf), ...]
    lines = []
    for cls_name, xyxy, _ in objs:
        if cls_name not in classes:
            continue
        cls_id = classes.index(cls_name)
        cx, cy, w, h = xyxy_to_xywhn(xyxy, W, H)
        lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
    label_path.write_text("\n".join(lines))

def draw_preview(img_bgr, objs):
    for cls_name, xyxy, conf in objs:
        x1, y1, x2, y2 = [int(v) for v in xyxy]
        color = COLORS.get(cls_name, (0, 255, 0))
        cv2.rectangle(img_bgr, (x1, y1), (x2, y2), color, 2)
        label = f"{cls_name} {conf:.2f}" if conf is not None else cls_name
        (tw, th), bl = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(img_bgr, (x1, y1 - th - bl), (x1 + tw, y1), color, -1)
        cv2.putText(img_bgr, label, (x1, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)
    return img_bgr

def bottom_y(xyxy):
    return xyxy[3]

# =========================
# Pairing logic (greedy)
# =========================
def pair_ped_cycle_to_cyclist(ped_boxes, cyc_boxes):
    """
    Greedy match: for each pedestrian, pick the cycle with max IoU that:
      - overlaps above IOU_THRESH
      - has bottom y lower than the pedestrian bottom by >= LOWER_MARGIN_PX
    Return:
      matched_pairs: list of (p_idx, c_idx, union_xyxy, score)
      unmatched_peds: set of pedestrian indices not matched
    """
    used_cycles = set()
    matches = []

    for pi, p in enumerate(ped_boxes):
        best = None
        by_ped = bottom_y(p)
        for ci, c in enumerate(cyc_boxes):
            if ci in used_cycles:
                continue
            if bottom_y(c) < by_ped + LOWER_MARGIN_PX:
                # cycle not sufficiently lower than pedestrian
                continue
            score = iou_xyxy(p, c)
            if score >= IOU_THRESH and (best is None or score > best[3]):
                best = (pi, ci, union_box(p, c), score)
        if best is not None:
            matches.append(best)
            used_cycles.add(best[1])

    matched_peds = {pi for (pi, _, _, _) in matches}
    unmatched_peds = set(range(len(ped_boxes))) - matched_peds
    return matches, unmatched_peds

# =========================
# Pipeline
# =========================
def main():
    in_dir = Path(INPUT_DIR)
    out_root = Path(OUTPUT_DIR)
    ensure_dirs(out_root, SAVE_PREVIEW)

    imgs = sorted([p for p in in_dir.iterdir() if p.suffix.lower() in EXTENSIONS])
    if not imgs:
        raise SystemExit(f"No images found in {in_dir.resolve()} with extensions {sorted(EXTENSIONS)}")

    model = YOLO(MODEL_WEIGHTS)

    log_path = out_root / LOG_FILENAME
    with open(log_path, "w") as lf:
        lf.write("file,pedestrian_keep,cyclist_new,car,motorcycle,bus,truck,total_final\n")

    for img_path in imgs:
        # 1) Detect only person & bicycle & vehicles
        result = model.predict(source=str(img_path), conf=CONF_THRESH, verbose=False)[0]
        names = result.names

        dets = []
        if result.boxes is not None and len(result.boxes) > 0:
            xyxy = result.boxes.xyxy.cpu().numpy()
            cls = result.boxes.cls.cpu().numpy().astype(int)
            conf = result.boxes.conf.cpu().numpy()
            for b, c, s in zip(xyxy, cls, conf):
                name = names[c]
                if name not in DETECTOR_CLASSES:
                    continue
                x1, y1, x2, y2 = [float(v) for v in b]
                if (x2 - x1) < MIN_SIDE or (y2 - y1) < MIN_SIDE:
                    continue
                dets.append({"cls": name, "xyxy": [x1, y1, x2, y2], "conf": float(s)})

        # Split to pedestrians & cycles & vehicles
        peds = [d for d in dets if d["cls"] == "person"]
        cycs = [d for d in dets if d["cls"] == "bicycle"]

        cars  = [d for d in dets if d["cls"] == "car"]
        motos = [d for d in dets if d["cls"] == "motorcycle"]
        buses = [d for d in dets if d["cls"] == "bus"]
        trucks= [d for d in dets if d["cls"] == "truck"]

        ped_boxes = [d["xyxy"] for d in peds]
        cyc_boxes = [d["xyxy"] for d in cycs]

        # 2) Pair and derive cyclist unions
        matches, unmatched_peds = pair_ped_cycle_to_cyclist(ped_boxes, cyc_boxes)

        final_objs = []

        # Add derived cyclists (union boxes)
        for (pi, ci, union_xyxy, score) in matches:
            # confidence for preview: min of the two confs (optional)
            # conf = min(peds[pi]["conf"], cycs[ci]["conf"]) if peds and cycs else None
            conf = (peds[pi]["conf"] * cycs[ci]["conf"] * iou_xyxy(peds[pi]["xyxy"], cycs[ci]["xyxy"])) ** (1/3)
            final_objs.append(("cyclist", union_xyxy, conf))

        # Keep unmatched pedestrians
        for pi in unmatched_peds:
            final_objs.append(("pedestrian", peds[pi]["xyxy"], peds[pi]["conf"]))

        # Add vehicle boxes as-is
        for v in cars:
            final_objs.append(("car", v["xyxy"], v["conf"]))
        for v in motos:
            final_objs.append(("motorcycle", v["xyxy"], v["conf"]))
        for v in buses:
            final_objs.append(("bus", v["xyxy"], v["conf"]))
        for v in trucks:
            final_objs.append(("truck", v["xyxy"], v["conf"]))

        # Note: we intentionally DO NOT add standalone bicycles to final labels.

        # 3) Write YOLO + copy image
        dst_img = out_root / "images" / img_path.name
        shutil.copy2(img_path, dst_img)

        W, H = Image.open(img_path).size
        dst_lbl = out_root / "labels" / img_path.with_suffix(".txt").name
        write_yolo_label(dst_lbl, final_objs, W, H, CLASSES)

        # 4) Preview
        if SAVE_PREVIEW:
            img_bgr = cv2.imread(str(img_path))
            img_bgr = draw_preview(img_bgr, final_objs)
            cv2.imwrite(str(out_root / "preview" / img_path.name), img_bgr)

        # 5) Log
        n_ped = sum(1 for c, *_ in final_objs if c == "pedestrian")
        n_cyc = sum(1 for c, *_ in final_objs if c == "cyclist")
        n_car = sum(1 for c, *_ in final_objs if c == "car")
        n_mot = sum(1 for c, *_ in final_objs if c == "motorcycle")
        n_bus = sum(1 for c, *_ in final_objs if c == "bus")
        n_trk = sum(1 for c, *_ in final_objs if c == "truck")
        with open(log_path, "a") as lf:
            lf.write(f"{img_path.name},{n_ped},{n_cyc},{n_car},{n_mot},{n_bus},{n_trk},{len(final_objs)}\n")

    print(f"\n✅ Done. Output: {out_root.resolve()}")
    print("   - images/   (copied originals)")
    print("   - labels/   (YOLO .txt with 'pedestrian', 'cyclist', 'car', 'motorcycle', 'bus', 'truck')")
    print("   - preview/  (visual check of union-rule boxes)")
    print(f"   - {LOG_FILENAME}")
    print("\n👉 Zip this folder and upload to Roboflow (format: YOLO), then Annotate → Review.")

if __name__ == "__main__":
    main()