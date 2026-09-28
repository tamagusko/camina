# Open data for the window-camera perspective: source report

2026-09-27. How the report was made: the searches across all sources and the reading of samples and licences were done by four Opus scouts, and I drafted this report on Opus. A separate Fable gate independently re-checked the top 8 candidates at their original source. It made the perspective, licence and tier rulings, the ranking, and the gaps and recommendation. The mechanical Sonnet pass was not run: the tables were assembled by hand from the scout and gate outputs. Nothing was downloaded beyond verification samples. Those samples are in the session scratchpad and are not kept.

## Perspective bar

The deployment reference is `videos/test.mov`. It is filmed from a 1st-floor window about 4–5 m up, with a pitch of about 25–30°. The view is oblique, across a two-way street: parked cars fill the near lane and pedestrians use the far footpath.

- **MATCH** means a camera at 3–6 m looking obliquely across or down an urban street.
- **NEAR** means a camera at 6–12 m, or a pitch of up to about 55°.
- **MISS** means pole/highway CCTV, dashcam, aerial, or street level.

Classes are taken from `configs/classes.yaml`: person, cyclist, car, e-scooter, SUV, motorcyclist, bus, delivery_van, truck.

## Bottom line

**No open dataset has the window perspective under a usable licence at any real volume.** Every MATCH-verified open source added together comes to under 0.3 h and under 1,000 frames:

- Murcia: about 11 min of staged campus footage.
- Wikimedia Commons: fewer than 50 stills.
- OTVision: 6 s of video.

None of them has e-scooter, delivery_van or SUV as a distinct class. The real supply is NEAR data from 6–10 m pole cameras. The window collection you shoot yourself is the primary MATCH set, not a supplement to it.

## Ranked sources (usable and conditional)

| # | Source | Content | Quantity | Perspective | Licence (read at source) → verdict | Tier | Acquisition |
|---|---|---|---|---|---|---|---|
| 1 | [Montreal traffic-camera annotated images](https://open.canada.ca/data/en/dataset/3c30b818-3cd9-4877-8273-600a2ee80b05) | City PTZ cameras, 2019, day and night. VOC boxes for vehicle, pedestrian, cyclist, bus and construction. | 10,008 JPEG, mostly 704×480, some 352×288 | NEAR, with a near-MATCH subset: residential streets with parked cars at 6–8 m, e.g. Rose-de-Lima/St-Jacques. Camera name and timestamp are burned into each image and must be masked. | "Creative Commons 4.0 Attribution (CC-BY) licence – Quebec" (`qc-cc-by`) → **USABLE** | 1 | Direct zip, 651 MB. "vehicle" must be split into car/SUV/van/truck. |
| 2 | [Transport for NSW live traffic cameras](https://opendata.transport.nsw.gov.au/dataset/live-traffic-cameras) | 241 cameras. The urban ones (Kent St, Broadway Glebe, …) are the useful subset. Left-hand traffic. | Live 800×600 stills, about 1 per minute, no archive | NEAR (urban poles at 6–8 m); highway cameras are MISS | "Creative Commons Attribution 4.0" (hub licence and dataset page). The API `rights` field is UNVERIFIED because it needs a key. → **USABLE** | 1 + 2 | Poll about 20 urban cameras every 2 min for 14 days: about 200k raw frames, 1–2 GB |
| 3 | [AAU RainSnow](https://www.kaggle.com/datasets/aalborguniversity/aau-rainsnow) | 7 Danish intersections in rain, snow and night; RGB + thermal | 22 × 5 min; 2,200 annotated frames with 13,297 objects | NEAR (about 6–8 m, intersections) | "Attribution 4.0 International (CC BY 4.0)" on the owner's Kaggle organisation page, which is the home the paper itself names → **USABLE** | 1 (weather) | Kaggle, 1.81 GB |
| 4 | [MERL Street Scene](https://zenodo.org/records/10870472) | One two-lane US street with bike lanes and sidewalks. Day only. Anomaly boxes only. | 202,545 frames, 1280×720 at 15 fps | NEAR: about 8–10 m, pitch about 50°, looking **along** the street. The "window view" description does not hold. | `cc-by-sa-4.0` (Zenodo API) → **CONDITIONAL** (share-alike) | 1 (weak) + 2 | Zenodo, 49.0 GB |
| 5 | [Murcia multi-perspective](https://zenodo.org/records/18375218) (Sci Data 2026) | Staged campus crosswalk: 7 pedestrians, 1 car | About 11 min of roadside-unit footage, 1080p at 60 fps | **MATCH** (tripod at 3 m, per the paper) | `cc-by-4.0` for the data; the article's CC BY-NC-ND covers only the paper → **USABLE** | 2 / 3 | Range-extract the roadside-unit files from the 10.07 GB zip, about 3 GB |
| 6 | [Wikimedia Commons: Views from windows](https://commons.wikimedia.org/wiki/Category:Views_from_windows) | Stills from 1st/2nd-floor windows over UK and EU streets | Fewer than about 50 usable | **MATCH** | CC BY-SA 2.0 / 4.0, per file → **CONDITIONAL** | 3 (+2) | Pick by hand, under 100 MB |
| 7 | [OpenTrafficCam OTVision](https://github.com/OpenTrafficCam/OTVision) test clips | German intersection | 2 × 3 s at 800×600 | **MATCH** (about 5 m) | GPL-3.0 → **CONDITIONAL**, reference only | 3 | GitHub, a few MB |
| 8 | [SEVD](https://github.com/eventbasedvision/SEVD) | CARLA fixed intersection cameras, 1280×960, day and night, 6 weather types | 27 h | NEAR (corner cameras, about 5–8 m) | The repo says "CC BY-SA 4.0" and the paper says CC BY 4.0. The repo governs. → **CONDITIONAL** | 3 | Google Form; size unknown |
| 9 | [CARLA](https://github.com/carla-simulator/carla) | Simulator with 8 of the 9 classes: no e-scooter, one bus model, no Dublin-style town | Unlimited | MATCH-capable (the camera can be placed anywhere) | Code MIT. Assets "CC-BY License", version not stated. What the Unreal Engine EULA says about rendered output is UNVERIFIED. → **USABLE** | 3 | Binary about 20 GB; 1–2 weeks to script a window view |
| 10 | [TfL JamCams](https://tfl.gov.uk/corporate/terms-and-conditions/transport-data-service) | 890 London cameras | Live, 352×288 | NEAR at best | OGL v2.0 with TfL amendments → **CONDITIONAL** | 2 at most | Skip while NSW exists |
| 11 | [MEVA](https://mevadata.org) | Training facility: parking lots and a roundabout, mostly indoor cameras | 328 h | Geometry NEAR, scene MISS | "CC BY-4.0" (mevadata.org and its licence file) → **USABLE** | 3 | AWS S3; skip for now |
| 12 | [VIRAT Ground 2.0](https://viratdata.org) | Parking lots filmed from 3–5 storeys | About 8.5 h | NEAR | Signed agreement allowing "research and commercial purposes", no redistribution → **CONDITIONAL** | 3 | Skip |

Generators for tier 3: FLUX.1-schnell (Apache-2.0) and SDXL (Open RAIL++-M, "Licensor claims no rights in the Output") are **USABLE**.

## Unusable but notable

| Source | Why it matters | Why it can't be used |
|---|---|---|
| TrainingDataPro "Electric Scooters Tracking" | Best geometric match seen: e-scooters at 4–6 m across an urban street | CC BY-NC-ND 4.0 vendor sample; only the paid set is offered |
| UrbanTracker Sherbrooke (Polytechnique Montréal) | About 4–5 m intersection, MATCH | No licence stated. Ask N. Saunier. |
| WindowSwap | Thousands of 10-min window clips | No licence or terms found. Only usable with permission. |
| NWPU Campus (CVPR 2023) | Campus roads at 3–6 m | Academic, non-commercial only |
| MOT17-03/04, MOT20-06/08 | Elevated street views | CC BY-NC-SA 3.0 (read from the search index; the site is offline) |
| MIO-TCD | Has `work_van` and `pickup_truck` | CC BY-NC-SA 4.0 |
| AI City / CityFlow | Traffic cameras | Non-commercial; forbids production use of trained models |
| Dublin City Council cameras | Local, left-hand traffic | The CC BY 4.0 covers the pole-location CSV, not the images. The sample is a MISS (8–10 m arterial). |
| Telraam / WeCount | Window-mounted cameras | No imagery is ever stored or released (counts only, Telraam CC BY-NC 4.0) |
| AMOS, Webcam Clip Art | Large webcam archives | No licence / non-commercial; mostly scenic views |
| Synthehicle, MOTSynth, VehicleX | Synthetic surveillance | No licence stated |
| JTA, SHIFT, SYNTHIA, VKITTI2, MetaUrban (BEDLAM/SynBody assets) | Synthetic | Non-commercial, research-only, or bans surveillance use |
| FLUX.1-dev | Generator | §4a forbids using its outputs for "surveillance, including any research or development relating to surveillance" |
| Pexels, Pixabay, Unsplash, SkylineWebcams, Windy | Stock footage and webcams | Their terms ban machine-learning use or frame capture |
| YouTube CC-BY | Many "traffic from my window" videos | The CC licence is valid, but YouTube's ToS forbids downloading. The only clean route is getting the file from the uploader. |
| UA-DETRAC re-uploads on HF, justjuu (CC0), Medellín, STREETS | Traffic CCTV | The uploaders re-license data they do not own |

Roboflow Universe could not be checked: Cloudflare blocked every automated request. Nothing from it is verified.

## Rulings that apply to all sources (from the Fable gate; practical, not legal advice)

1. **CC BY-SA data and AGPL weights.** It is unsettled whether trained weights count as "Adapted Material". Keep share-alike sources in a separate partition that stays at no more than 20% of the training mix. Never redistribute that partition, and attribute it in `models/*/PROVENANCE.md`. If anyone objects, retraining without it is cheap. Do not wait on this question to start work.
2. **GDPR.** Blur faces and plates when images are ingested. Never redistribute raw frames. Delete your own raw video after labelling. Keep a one-page DPIA note in `docs/`. Montreal and NSW fall outside GDPR, but the blur rule still applies because the project is privacy-first.
3. **NEAR data is worth pulling, with a cap on pitch.** Use data from 6–9 m with pitch ≤ 40° at full weight. Halve data from 9–12 m or with pitch of 40–55°. Use steeper or highway views only as tier-2 backgrounds. Always validate on `videos/test.counts.csv`.

## Gaps

- **Open data at the MATCH perspective:** under 1,000 frames in total, and none of it contains e-scooter, delivery_van or SUV as distinct classes.
- **Rare classes at any elevated perspective:** nothing open exists. Separating SUV from car and delivery_van from truck, and all e-scooter examples, must come from your own collection plus synthetic data.
- **Dublin / Irish streets:** no open imagery at all. NSW is the only left-hand-traffic source.
- **Consequence:** open tier-1 data teaches "elevated oblique urban traffic" in general. The window perspective and the rare classes have to be carried by tiers 2–3 and your own collection. Plan your own collection at ≥ 20 h across ≥ 5 Dublin windows. At 0.5 fps that gives about 36k frames, auto-labelled and then audited.

## Pull-first recommendation (on your go)

| # | Action | Size | Expected yield |
|---|---|---|---|
| 1 | Download the Montreal zip. Remap "vehicle" to car/SUV/van/truck with the current model and audit about 500 images. Flag the 6–8 m residential cameras. Mask the burned-in text. | 651 MB | Tier 1: about 10k images, about 6k of them urban-relevant, with boxes |
| 2 | Run an NSW poller: about 20 urban cameras, one still every 2 min, for 14 days. Remove near-duplicates by perceptual hash. | 1–2 GB | Tier 1: about 20–30k frames. Tier 2: about 5k empty or night frames. |
| 3 | AAU RainSnow, sampled at 1 fps | 1.81 GB | Tier 1: 2.2k labelled frames plus about 6.6k unlabelled, in rain, snow and night |
| 4 | Street Scene, only once the share-alike partition rule is adopted. Sample at 1 fps and crop out the steepest band. | 49 GB | Tier 1 (weak): about 13.5k frames. Tier 2: about 2k backgrounds. |
| 5 | Murcia roadside-unit files only | about 3 GB | Tier 2/3: about 650 frames at MATCH geometry |
| 6 | Emails, most likely to succeed first: N. Saunier (UrbanTracker licence); Dublin City Council (archive of camera stills + licence); OpenTrafficCam / TU Dresden (OTLabels images at about 5 m); WindowSwap (a research subset). Also submit the SEVD form. | — | MATCH tier 1 if OpenTrafficCam or WindowSwap says yes |

**Expected volume from the pull-first set:**

- **Tier 1:** about 40–55k frames, about 12k of them with existing boxes, all NEAR.
- **Tier 2:** about 7–8k backgrounds.
- **Tier 3:** fewer than 100 real stills, plus CARLA/SEVD as generators.
- **Real MATCH frames from open sources:** under 1k.

**Unverified:**

- The CARLA CC-BY version, and the Unreal Engine EULA's terms for rendered output.
- The NSW API `rights` field.
- WindowSwap's terms.
- The camera heights for Street Scene and AAU. The owners don't state them; the figures above are estimates from the images.

## Montreal feasibility check (2026-09-28, on the downloaded zip)

This check was run on the 651 MB zip downloaded to `~/Downloads`. The zip was extracted to the session scratchpad only.

- **Contents:** 9,998 JPEGs with Pascal VOC XML annotations. The splits are train 7,007, val 1,000 and test 991. There are also 1,000 `test_i` images, disjoint from `test`.
- **Resolution:**
  - 704×480: 5,672 images
  - 352×288: 2,373 images
  - 352×240: 1,953 images
- **Time of day:** about 71% day, 25% dusk or dim, and 4% dark (mean luminance on a 1-in-10 sample).
- **Labels:** 122,868 boxes in total. 413 images have no labels.

  | Label | Boxes |
  |---|---|
  | vehicle | 91,748 |
  | pedestrian | 15,728 |
  | construction | 12,763 |
  | bus | 1,445 |
  | cyclist | 1,184 |

  The `occluded` flag is always 0.
- **Cameras:** OCR of the burned-in camera names gives roughly 100–150 intersections, heavily skewed: the 10 largest cameras hold about 22% of the images. About 2.3k images have a near-duplicate.
- **Object scale:** at imgsz 640, the median box height is 19 px for vehicles and 32 px for pedestrians, and 17% of vehicle boxes are under 10 px. In `test.mov`, cars are about 150 px tall and pedestrians about 40 px. Montreal objects are 5–8× smaller than CAMINA's, so this data teaches far and small objects, not the near lane.
- **Label completeness:** YOLO11x, run on 300 images (conf ≥ 0.5), found only 64 confident objects with no ground-truth box, against about 3,600 ground-truth boxes. The labels look nearly complete, apart from the tiny objects.
- **Splitting "vehicle":**
  - YOLO11x matched 65% of vehicle boxes at IoU ≥ 0.5: 60% as car, 5% as truck, the rest as bus or motorcycle. The other 35% went unmatched, probably the tiny boxes (this is inferred, not measured).
  - SUV, delivery_van and e-scooter cannot be derived from a COCO model. They need the planned SAM 3 + VLM step or a human.
- **Tooling note:** the dev `.venv` has Ultralytics 8.3.123, under which `yolo26s.pt` detects nothing and `yolo26x.pt` almost nothing. The training env `.venv-train` (8.4.162) runs YOLO26 correctly, so the pipeline (#41, #42) is not affected. Run YOLO26 only from `.venv-train`.

## Montreal import: status and next steps (2026-09-28)

`training/import_montreal.py` has been run on the 5,672 images at 704×480. The output is `data/autolabel/montreal/` (gitignored): 76,731 boxes and a `boxes.csv` recording the source of each box.

| Class | Boxes |
|---|---|
| car | 60,324 (21.7k of them unmatched and set to car by default; median 11 px) |
| person | 11,582 |
| truck | 2,070 |
| bus | 1,182 |
| cyclist | 868 |
| delivery_van | 638 |
| motorcyclist | 65 |
| e-scooter | 2 |
| SUV | 0 |

Next steps:

1. **Verify before training.** Montreal SUVs are labelled `car`, which would train against the TRA 2026 SUV class. SAM 3 vans have a precision of about 0.40. Run `training.codex_check` on vehicle classes only: every truck, delivery_van and bus box, plus car boxes ≥ 30 px tall. That is about 18k crops; leave the tiny default cars unchecked.
2. **Export the reviewed set** to `data/montreal`, not `data/autolabel/montreal`. After `codex_check`, the latter also holds `review/` copies, so every image would be read twice.
3. **Ablation.** Train `training/experiments/yolo26n_tra2026_montreal.yaml` (Montreal in train only, capped at 1× the TRA training images) and compare it with `yolo26n_tra2026` via `training.evaluate`, on AP and on the `test.mov` count error. If 1× helps, try 2×.
