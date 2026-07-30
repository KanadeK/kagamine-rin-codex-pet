# Kagamine Rin look mechanics

## Registration and identity locks

- Keep both boot soles, pelvis, and lower torso registered to the approved idle
  baseline. Look direction must not translate, rotate, skew, or resize the
  whole sprite.
- Preserve the same head-to-body ratio, blonde bob silhouette, large white bow,
  cyan irises, sailor collar, yellow neckerchief, dark warmers, and palette in
  every direction.
- The asymmetric belt pouch remains on the same viewer-right side used by the
  approved frontal identity. Hair clips and garment details must not swap sides
  or disappear.
- There is no gaze prop. Do not add arrows, degree labels, motion marks,
  highlights outside the silhouette, or replacement eyes.

## Natural gaze hierarchy

1. The cyan pupils and irises lead the direction inside the existing eye
   construction. Keep both eyes readable and keep their size stable.
2. The face follows with a small pitch or yaw: nose tip, mouth center, cheek
   exposure, and bangs move coherently with the pupils.
3. The neck and upper torso may follow by a few pixels, while hips, legs, and
   feet stay anchored.
4. Side hair tips and the large bow follow the head with a smaller, softer
   displacement. They never become independent props or change size.

The mechanism is a gaze and subtle head turn, not sixteen rotated copies of
the complete character.

## Cardinal anchors

### 000 — up / top edge

- Face remains broadly frontal.
- Both pupils sit unmistakably high inside the cyan irises.
- Chin lifts slightly and the face center rises a little under the bangs.
- More lower iris is visible than upper iris; eyes must not become closed or
  surprised.
- Bow and hair follow upward only subtly; feet and hips do not move.

### 090 — screen-right

- Both pupils move to the screen-right side of their eye openings.
- Nose tip and mouth center move to the screen-right of the head center.
- The screen-right cheek/hair edge compresses slightly while the opposite side
  opens, creating a real shallow yaw rather than eye-only sliding.
- Keep both eyes visible, keep the belt pouch viewer-right, and do not mirror
  the sprite.

### 180 — down / bottom edge

- Face remains broadly frontal.
- Both pupils sit unmistakably low inside the irises.
- Chin tucks slightly; bangs and face center descend a little while eyes remain
  open and readable.
- The pose must read as looking down, not sadness, sleep, or a failure state.
- Bow, hips, and feet remain registered.

### 270 — screen-left

- Apply the inverse facial landmark movement of 090.
- Both pupils, nose tip, and mouth center move toward the screen-left edge.
- Screen-left cheek/hair compresses slightly and the opposite side opens.
- Preserve all asymmetric identity details on their approved sides; do not use
  a horizontal pixel mirror.

## Diagonal interpolation and continuity

- Rows 9 and 10 form one clockwise loop:
  `000 → 022.5 → … → 337.5 → 000`.
- Each diagonal advances pupils, nose, face plane, hair, and bow monotonically
  between its two approved cardinal anchors. No diagonal may reverse or repeat
  the previous direction.
- The 157.5 to 180 join, 337.5 to 000 loop closure, and the row boundary
  between 157.5 and 180 must have the same scale, baseline, and gradual
  displacement as every other neighbor.
- Keep motion small enough for a 192×208 cell but large enough that an
  unlabeled blind reviewer can distinguish all four cardinals and the clockwise
  ordering.
