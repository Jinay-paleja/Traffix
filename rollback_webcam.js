(() => {
  /** @type {Map<string, MediaStream>} */
  const streamsByDeviceId = new Map();
  /** @type {MediaStream|null} */
  let defaultStream = null;
  /** @type {Map<string, string>} */
  const networkUrlByLane = new Map();

  function hasActiveTracks(stream) {
    return !!stream && stream.getTracks().some((track) => track.readyState === "live");
  }

  function setStatus(el, msg, tone = "info") {
    if (!el) return;
    el.textContent = msg;
    el.dataset.tone = tone;
    el.style.display = msg ? "block" : "none";
  }

  async function getDefaultStream(constraints) {
    if (defaultStream && !hasActiveTracks(defaultStream)) {
      defaultStream = null;
    }
    if (defaultStream) return defaultStream;
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    defaultStream = stream;
    return stream;
  }

  function stopAllStreams() {
    if (defaultStream) {
      for (const track of defaultStream.getTracks()) track.stop();
      defaultStream = null;
    }
    for (const stream of streamsByDeviceId.values()) {
      for (const track of stream.getTracks()) track.stop();
    }
    streamsByDeviceId.clear();
  }

  async function listVideoInputs() {
    const devices = await navigator.mediaDevices.enumerateDevices();
    return devices.filter((d) => d.kind === "videoinput");
  }

  async function getStreamForDeviceId(deviceId, baseConstraints) {
    if (!deviceId) return getDefaultStream(baseConstraints);
    if (streamsByDeviceId.has(deviceId)) {
      const cached = streamsByDeviceId.get(deviceId);
      if (hasActiveTracks(cached)) return cached;
      streamsByDeviceId.delete(deviceId);
    }

    const constraints = {
      ...baseConstraints,
      video:
        baseConstraints?.video === true
          ? { deviceId: { exact: deviceId } }
          : typeof baseConstraints?.video === "object"
            ? { ...baseConstraints.video, deviceId: { exact: deviceId } }
            : { deviceId: { exact: deviceId } },
    };

    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    streamsByDeviceId.set(deviceId, stream);
    return stream;
  }

  function safeLabel(device, idx) {
    if (device?.label) return device.label;
    return `Camera ${idx + 1}`;
  }

  function storageKey(prefix, laneId) {
    return `${prefix}::${laneId}::deviceId`;
  }

  function storageKeyType(prefix, laneId) {
    return `${prefix}::${laneId}::sourceType`;
  }

  function storageKeyUrl(prefix, laneId) {
    return `${prefix}::${laneId}::networkUrl`;
  }

  async function populateCameraSelects({
    selectSelector = "select[data-webcam-select='1']",
    statusSelector = "[data-webcam-status='1']",
    storageKeyPrefix = "traffix:webcam",
    baseConstraints = { video: true, audio: false },
  } = {}) {
    const selects = Array.from(document.querySelectorAll(selectSelector));
    const statusEl = document.querySelector(statusSelector);
    if (!selects.length) return;

    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus(statusEl, "Webcam not supported in this browser.", "error");
      return;
    }

    try {
      // Request permission once so device labels show up
      setStatus(statusEl, "Requesting camera permission…", "info");
      await getDefaultStream(baseConstraints);

      const inputs = await listVideoInputs();

      selects.forEach((sel) => {
        const laneId = sel.getAttribute("data-lane-id") || "lane";
        const saved = localStorage.getItem(storageKey(storageKeyPrefix, laneId));

        // Rebuild options
        const currentValue = sel.value;
        sel.innerHTML = "";

        const autoOpt = document.createElement("option");
        autoOpt.value = "";
        autoOpt.textContent = "Auto (default camera)";
        sel.appendChild(autoOpt);

        inputs.forEach((dev, idx) => {
          const opt = document.createElement("option");
          opt.value = dev.deviceId;
          opt.textContent = safeLabel(dev, idx);
          sel.appendChild(opt);
        });

        // Restore selection
        const target = saved ?? currentValue ?? "";
        sel.value = target;
      });

      setStatus(statusEl, "Select a camera source per lane.", "success");
    } catch (err) {
      const msg =
        err?.name === "NotAllowedError"
          ? "Camera permission blocked. Allow camera access and refresh."
          : err?.name === "NotFoundError"
            ? "No camera found on this device."
            : `Webcam error: ${err?.message || String(err)}`;
      setStatus(statusEl, msg, "error");
    }
  }

  function applyNetworkUrlToLane(laneId, url) {
    if (!laneId) return;
    networkUrlByLane.set(laneId, url || "");
  }

  async function attachWebcamToVideos({
    videoSelector = "video[data-webcam='1']",
    selectSelector = "select[data-webcam-select='1']",
    networkImgSelector = "img[data-networkcam='1']",
    statusSelector = "[data-webcam-status='1']",
    constraints = { video: true, audio: false },
    storageKeyPrefix = "traffix:webcam",
  } = {}) {
    const videos = Array.from(document.querySelectorAll(videoSelector));
    const selects = Array.from(document.querySelectorAll(selectSelector));
    const networkImgs = Array.from(document.querySelectorAll(networkImgSelector));
    const statusEl = document.querySelector(statusSelector);

    if (!videos.length && !networkImgs.length) return;

    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus(statusEl, "Webcam not supported in this browser.", "error");
      return;
    }

    try {
      // Ensure selects are populated and labels are available
      await populateCameraSelects({
        selectSelector,
        statusSelector,
        storageKeyPrefix,
        baseConstraints: constraints,
      });

      setStatus(statusEl, "Connecting selected cameras…", "info");

      // Map laneId -> deviceId (from selects), fallback to default
      const deviceIdByLane = new Map();
      selects.forEach((sel) => {
        const laneId = sel.getAttribute("data-lane-id");
        if (!laneId) return;
        const val = sel.value || "";
        localStorage.setItem(storageKey(storageKeyPrefix, laneId), val);
        deviceIdByLane.set(laneId, val);
      });

      const deviceVideos = videos.filter((video) => {
        const laneId = video.getAttribute("data-lane-id");
        const sourceType = localStorage.getItem(storageKeyType(storageKeyPrefix, laneId)) || "device";
        return sourceType !== "network";
      });

      if (deviceVideos.length) {
        await getDefaultStream(constraints);
      }

      // Apply network URLs (if any)
      networkImgs.forEach((img) => {
        const laneId = img.getAttribute("data-lane-id");
        if (!laneId) return;
        const url = networkUrlByLane.get(laneId) || localStorage.getItem(storageKeyUrl(storageKeyPrefix, laneId)) || "";
        if (url) {
          // Cache-bust to avoid stale frames in some browsers
          const sep = url.includes("?") ? "&" : "?";
          img.src = `${url}${sep}t=${Date.now()}`;
        } else {
          img.removeAttribute("src");
        }
      });

      let attachedCount = 0;
      for (const v of videos) {
        const laneId = v.getAttribute("data-lane-id");
        if (!laneId) continue;

        const sourceType = localStorage.getItem(storageKeyType(storageKeyPrefix, laneId)) || "device";
        if (sourceType === "network") {
          // Don't attach a device stream if lane is set to network camera.
          v.srcObject = null;
          continue;
        }

        const deviceId = deviceIdByLane.get(laneId) || "";
        const stream = await getStreamForDeviceId(deviceId, constraints);
        v.srcObject = stream;
        v.muted = true;
        v.playsInline = true;
        try {
          await v.play?.();
          attachedCount += 1;
        } catch (playErr) {
          throw new Error(playErr?.message || "Video playback could not start.");
        }
      }

      if (!attachedCount && !networkImgs.some((img) => img.getAttribute("src"))) {
        setStatus(statusEl, "No active camera feeds available for this view.", "error");
        return;
      }

      setStatus(statusEl, "Cameras connected.", "success");
    } catch (err) {
      const msg =
        err?.name === "NotAllowedError"
          ? "Camera permission blocked. Allow camera access and refresh."
          : err?.name === "NotFoundError"
            ? "No camera found on this device."
            : `Webcam error: ${err?.message || String(err)}`;
      setStatus(statusEl, msg, "error");
    }
  }

  window.TraffixWebcam = {
    attachWebcamToVideos,
    populateCameraSelects,
    stopStream: stopAllStreams,
    applyNetworkUrlToLane,
    storageKeyType,
    storageKeyUrl,
  };
})();
