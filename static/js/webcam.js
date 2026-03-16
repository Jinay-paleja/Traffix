(() => {
  let activeStream = null;

  function setStatus(el, msg, tone = "info") {
    if (!el) return;
    el.textContent = msg;
    el.dataset.tone = tone;
    el.style.display = msg ? "block" : "none";
  }

  async function getStream(constraints) {
    if (activeStream) return activeStream;
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    activeStream = stream;
    return stream;
  }

  function stopStream() {
    if (!activeStream) return;
    for (const track of activeStream.getTracks()) track.stop();
    activeStream = null;
  }

  async function attachWebcamToVideos({
    videoSelector = "video[data-webcam='1']",
    statusSelector = "[data-webcam-status='1']",
    constraints = { video: { width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false },
  } = {}) {
    const videos = Array.from(document.querySelectorAll(videoSelector));
    const statusEl = document.querySelector(statusSelector);

    if (!videos.length) return;

    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus(statusEl, "Webcam not supported in this browser.", "error");
      return;
    }

    try {
      setStatus(statusEl, "Requesting camera permission…", "info");
      const stream = await getStream(constraints);
      for (const v of videos) {
        v.srcObject = stream;
        v.muted = true;
        v.playsInline = true;
        // Autoplay can still be blocked; play() helps in some browsers.
        v.play?.().catch(() => {});
      }
      setStatus(statusEl, "Webcam connected (same feed shown for all lanes).", "success");
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
    stopStream,
  };
})();

