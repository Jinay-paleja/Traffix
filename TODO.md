# Traffix Enhancement: Road Name Edit + Live Camera Feed

## Plan Steps (Approved)

### 1. Update Backend (app.py)
- Add `update_intersection(intersection_id, name, location)` function
- Add `@app.route("/intersection/update/<intersection_id>", methods=["POST"])` route
- Ensure `add_intersection` and `toggle_camera` add `stream_url` to each camera

### 2. Update Frontend (templates/intersection_detail.html)
- Add edit form in page-header for name/location
- Add 'View Live' button in each lane-card (if active)
- Add modal for live video feed with JS show/hide

### 3. Test Changes
- Restart server (`python app.py`)
- Create/edit intersection name
- Toggle camera + view live feed

### 4. Verify & Complete
- Check data/intersections.json updates
- Test modal/video placeholder

**Current Progress:** ✅ Step 1 complete (app.py), ✅ Step 2 complete (intersection_detail.html: edit form + live modal)

**Next:** Step 3 - Test changes (run `python app.py`, create/edit intersection, test live feed)

