# Label audit: how to finish it

The vehicle labels (SUV, delivery_van, truck, bus; car on test) of the TRA 2026 train, val and
test splits were checked by two models:

- The first check was Codex, plus Opus 5.5 for the last 243 train boxes.
- Every box the first check disputed or was unsure of was then re-judged blind by Fable 5.1.

What is left is your decision on each disputed box, then the fix in Roboflow.

| Split | Disputed | Likely errors | Label looks right | Your call |
|---|---|---|---|---|
| Test | 141 | 24 | 16 | 101 |
| Val | 38 | 21 | 2 | 15 |
| Train | 402 | 164 | 22 | 216 |

The worst class is SUV: in train, about 120 of the 373 SUV boxes look wrong.

## 1. Review the boxes

Open `data/autolabel/audit/index.html` in your browser. It runs locally; no image leaves the
machine.

Work through the tabs in order: **Likely errors**, then **Unclear**, then **Label OK**. Each
card shows the enlarged box, the full frame, your label, and both models' answers.

| Key | Action |
|---|---|
| `1`–`9` | set the class (the number is on each button) |
| `0` | delete the box (not a road user, a reflection, a tram) |
| `B` | the class is fine but the box needs redrawing |
| `K` | keep your label |
| `Enter` | accept the suggestion (dashed button) |
| `←` `→` / `N` | move / next undecided |
| `⌫` | undo |

Decisions are saved in the browser as you go. When you are done, click **Export CSV**. It
saves `audit_decisions.csv` to your Downloads. Use **Import** to reload it, for example in
another browser.

## 2. Write the corrected labels (local)

```bash
.venv/bin/python -m training.apply_audit --decisions ~/Downloads/audit_decisions.csv
```

This writes corrected label files to `data/autolabel/audit/fixed/<split>/labels/`, plus a
`plan.csv` listing each image and its tags. `training/dataset` is not touched.

A warning of the form *"box N is not in the dataset labels"* means that box was added by the
pre-labeller, not by you. It is skipped.

## 3. Push to Roboflow

This step writes to the Roboflow project. The SDK installs its own OpenCV, so use a throwaway
environment. Try one image first:

```bash
uv venv /tmp/rf && uv pip install --python /tmp/rf/bin/python roboflow
export ROBOFLOW_API_KEY=...        # never commit it
/tmp/rf/bin/python -m training.apply_audit --decisions ~/Downloads/audit_decisions.csv --push --limit 1
```

Check that image in Roboflow: the labels should be changed and the tag added. Then run the same
command without `--limit 1`.

| Tag | Meaning |
|---|---|
| `audit-fixed` | a class was changed or a box deleted |
| `audit-box` | redraw the box by hand: filter by this tag in Roboflow |

## 4. Finish in Roboflow

1. Filter by `audit-box` and redraw those boxes.
2. Generate a **new dataset version**. Version 3, used in the paper, stays as it is.
3. Update `training/dataset` so it keeps the **same split**. Do **not** re-run
   `build_dataset --prepare`: the split is stratified by class, so changed labels could move
   images between train, val and test.

   The step-2 files (`data/autolabel/audit/fixed/<split>/labels/`) have the same names as the
   dataset files. They are copied over them, `split.json`'s label hashes are updated, and the
   change is committed as a new dataset. Ask Claude to do this step; no script for it exists
   yet.

## Files

| Path | What |
|---|---|
| `data/autolabel/audit/index.html`, `build.py` | review page; `build.py` rebuilds `data.js` |
| `data/autolabel/tra2026_<split>/adjudicate/adjudication.csv` | every disputed box with both models' answers |
| `data/autolabel/tra2026_<split>/boxes.csv` | every checked box and the first check's answer |
| `training/apply_audit.py` | steps 2 and 3 |

`data/` is gitignored, so these results exist only on this machine.
