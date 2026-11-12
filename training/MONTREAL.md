# Montreal images: selection by agreement

The Montreal traffic-camera set adds images from another city to CAMINA's training data. Its
labels are imported, not reviewed. This note says which images are used and why.

## Source

Ville de Montréal, *Images annotées de caméras de circulation* (open.canada.ca
3c30b818-3cd9-4877-8273-600a2ee80b05, CC BY 4.0). `training.import_montreal` keeps the
704×480 images: 5,672 images, 76,731 boxes in 5,466 of them. Its human boxes carry four
classes (vehicle, pedestrian, cyclist, bus). CAMINA's nine classes come from matching
each vehicle box to a YOLO26x or SAM 3 detection. An unmatched vehicle defaults to `car`.
Montreal has no SUV class, so SUVs arrive labelled `car`.

## Class check

`training.claude_check` showed each box to Claude Opus (alias `opus`, effort medium,
2026-09-29) as a crop with 40% context and the box outlined. Claude named its class from
the CAMINA class definitions, or answered `unsure`. Each checked box got a verdict:
`agree` (same class), `disagree` or `unsure`.

Checked were the boxes of the eight vehicle and rider classes with a shorter side of at
least 24 px. That is 22,733 boxes: 10,816 agree, 8,073 unsure, 3,844 disagree.
Smaller boxes and `person` boxes were not checked.

## Selection

An image is selected when at least one of its boxes was checked and every checked box
is `agree` (`training.select_agreed`). Boxes that were not checked keep their label.
Images are kept or dropped whole. Deleting single boxes would leave road users
unlabelled, which trains the model to treat them as background.

| Images | Count |
|---|---|
| Selected | 662 |
| Excluded: at least one box `unsure` or `disagree` | 4,055 |
| Excluded: no box checked | 749 |
| Excluded: no boxes | 206 |
| **Total** | **5,672** |

Boxes in the selected images:

| Class | Boxes | Agreed |
|---|---|---|
| car | 4,877 | 991 |
| person | 1,195 | 0 |
| truck | 174 | 126 |
| cyclist | 126 | 63 |
| bus | 104 | 71 |
| delivery_van | 51 | 42 |
| motorcyclist | 7 | 1 |

Claude confirmed 1,294 of the 6,534 boxes. The others have only the imported label.
The selection has no SUV or e-scooter box.

## Audit

The check cannot catch wrong classes on unchecked boxes or road users without a box. A
simple random sample of 60 selected images (seed 0) is reviewed in full. An image fails
if any box has the wrong class, any box is not a road user, or any identifiable road user
has no box. The selection is accepted if at most 2 images fail. With 2 failures, the
one-sided 95% Clopper–Pearson upper bound on the image failure rate is 10.1%. With 0
failures it is 4.9%.

Result: pending.

## Use

Training split only. Validation, test and count error stay on Dublin data. The images
are kept only if adding them does not worsen count error on the hand-counted clips.

## Reproduce

```bash
.venv/bin/python -m training.claude_check --run data/autolabel/montreal \
    --classes car,SUV,delivery_van,truck,bus,cyclist,motorcyclist,e-scooter \
    --min-side 24 --workers 3
.venv/bin/python -m training.select_agreed --run data/autolabel/montreal   # --audit 60 --seed 0
```

Outputs: `data/autolabel/montreal/tier_a/` (selection) and `tier_a_audit/` (sample),
each with `images/`, `labels/`, `data.yaml` and `images.txt`.
