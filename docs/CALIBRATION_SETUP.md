# Speed calibration, per site

Stage S7b. The sensor times each road user between two lines across the road
and publishes, per class and 15-minute window, the mean speed
(`avg_speed_kmh`). This page is the site procedure. **Status: the code exists,
no site has been calibrated and no reference measurement has been made, so no
accuracy is claimed yet.**

## How it works

Two marks are made across the road a measured distance apart. In the camera
image a line is drawn on each mark (`line_a`, `line_b` in `sensor.yaml`). A
tracked road user whose box centre crosses one line and then the other gets

    speed = distance_m / (t_second - t_first)

with the times taken from the camera's capture timestamps, interpolated between
frames. A measurement is rejected (counted in the log, never published) when
the two lines are crossed in different directions or in an impossible order, or
when it is above `max_kmh` (150 by default). Code: `camina/core/speed.py`.

## What you need

- A measuring wheel or a 30 m tape.
- Chalk or temporary road-marking spray, and the landowner's or council's
  permission to mark.
- For validation: a radar speed gun, or a second person timing passes (see
  step 6).
- A laptop that can reach the Pi over SSH.

## Procedure

Plan for about an hour per site.

1. **Mount the camera** at its final height and angle first. Any later change of
   angle or zoom invalidates the calibration.
2. **Choose the stretch.** Straight, flat, fully in view, and away from where
   traffic stops (junctions, crossings, bus stops): the result is the mean speed
   over the stretch, stops included. Longer is better; 15 to 25 m is a good
   range. At 10 fps and 50 km/h a road user takes about 1.4 s to cover 20 m.
3. **Mark two lines across the road**, perpendicular to the direction of travel,
   and measure the distance between them along the road with the wheel. Measure
   twice, on each side of the road; if the two readings differ by more than
   0.2 m, re-mark. Record the mean as `distance_m`.
4. **Draw the lines in the image.** Take a still from the camera and read off
   each mark as two points `[x, y]` in fractions of the frame (0 to 1). Draw
   both lines in the same orientation (for example both from top to bottom);
   the sensor refuses lines drawn in opposite orientations or lines that touch.
   The count is made from the centre of each road user's box, which sits above
   the road surface. If the camera looks along the road rather than across it,
   place each line where the box centres are when a vehicle is over the mark,
   not on the paint itself: film a car driving slowly past the marks and use
   its box centre at each mark (`scripts/view_detections.py` draws the boxes).
5. **Set the config** in `/etc/camina/sensor.yaml` and restart the service:

   ```yaml
   speed:
     line_a: [[0.30, 0.20], [0.30, 0.90]]
     line_b: [[0.70, 0.20], [0.70, 0.90]]
     distance_m: 20.0
     max_kmh: 150
   ```

   `python -m camina --config /etc/camina/sensor.yaml --dry-run` checks the
   config before the restart.
6. **Validate on at least 20 road users.** Stop the service and run the sensor
   by hand with per-vehicle logging:

   ```bash
   sudo systemctl stop camina-sensor
   sudo -u camina /opt/camina/venv/bin/python -m camina \
       --config /etc/camina/sensor.yaml --log-level DEBUG 2>&1 | grep ' speed '
   ```

   Each timed road user prints one line, `speed car-17 42.3 km/h`, with the
   time. For every vehicle, write down the time, class, direction and the
   reference speed:

   - **Radar gun:** aim along the direction of travel, as close to parallel as
     safe, and read it as the vehicle crosses the stretch.
   - **Timed passes:** without a radar gun, time vehicles between the two marks
     with a stopwatch, or better, film them on a phone and count frames from the
     front wheel on the first mark to the front wheel on the second.

   Cover the classes the site carries (cars at least; cyclists if present) and
   both directions. Pair each reference with its log line by time and class.
   Restart the service afterwards (`sudo systemctl start camina-sensor`).
7. **Score and record.** Compute, over the paired vehicles, the mean absolute
   error and the 90th percentile of the absolute error. Commit the table
   (time, class, direction, reference km/h, sensor km/h) and the calibration
   (`distance_m`, both lines, camera height and angle, a photo of the marks)
   under `docs/benchmarks/` as `YYYY-MM-DD_speed_<site>.md`. The phone footage
   is only for timing: delete it once the table is written.

## Pass thresholds (proposed, confirm before S9)

On at least 20 vehicles with a reference speed:

| Measure | Pass |
|---|---|
| Mean absolute error | ≤ 5 km/h |
| 90th percentile of absolute error | ≤ 10 km/h |

A site that fails keeps `speed` out of its config (no speeds are published)
until it is re-marked and passes.

## Known limits

- The box centre is not the vehicle's ground point, so an oblique view biases
  the timing unless the lines are placed as in step 4.
- A stop between the lines (queue, red light) lowers that vehicle's speed; the
  window mean includes it.
- Frame rate bounds the precision: interpolation helps, but at low frame rates
  or on short stretches a one-frame error is a large fraction of the time.
- Speeds are averaged over the road users that crossed both lines, not over
  every counted road user. A class's speed is published only when at least
  k_min = 5 road users were timed in the window; the dashboard also hides
  speeds wherever the class count is below 5.
