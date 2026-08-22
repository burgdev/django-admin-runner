/**
 * django-admin-runner — xterm.js terminal output widget
 *
 * Renders captured stdout/stderr in a real terminal emulator so ANSI
 * control sequences (colors, cursor movement, line erase) display exactly
 * as they would in a terminal — progress bars render as a single updating
 * line instead of one line per redraw frame.
 *
 * Storage is append-only output parts (≤512 KB each):
 * - Sealed parts are fetched whole from the part endpoint; the server marks
 *   them immutable, so repeat opens hit the browser cache.
 * - The active (last) part and new output are read via the cursor delta
 *   endpoint, polled every 250 ms while the command runs.
 * - Initial replay writes in ~64 KB slices with yields so the page stays
 *   responsive; a progress bar shows loaded parts vs. total.
 * - On `reset` (retention pruning dropped parts before our cursor) the
 *   terminal is cleared and the retained output replayed, with a
 *   truncation notice.
 * - Shows a running timer and a status bar when the command finishes.
 */
(function () {
  "use strict";

  var DEFAULT_POLL_INTERVAL = 500; // ms fallback; per-command value comes
  // from the page config (matches flush cadence)
  var SCROLL_THRESHOLD = 50; // px from bottom to still auto-scroll
  var WRITE_SLICE = 64 * 1024; // chars per term.write() during replay
  var PROGRESS_PART_THRESHOLD = 3; // show progress bar above this many parts

  function isNearBottom(el) {
    return el.scrollHeight - el.scrollTop - el.clientHeight < SCROLL_THRESHOLD;
  }

  function formatDuration(seconds) {
    if (seconds < 60) {
      return Math.floor(seconds) + "s";
    }
    var m = Math.floor(seconds / 60);
    var s = Math.floor(seconds % 60);
    return m + "m " + s + "s";
  }

  function formatBytes(n) {
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
    return (n / (1024 * 1024)).toFixed(1) + " MB";
  }

  function startTimer(startedAt, container) {
    if (!startedAt || !container) return null;
    var start = new Date(startedAt).getTime();
    if (isNaN(start)) return null;

    var wrapper = document.createElement("div");
    wrapper.className = "dar-timer";
    wrapper.style.cssText =
      "margin-bottom: 8px; font-size: 13px; color: #888; display: flex; align-items: center; gap: 6px;";

    var clockIcon = document.createElement("span");
    clockIcon.innerHTML =
      '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" style="flex-shrink:0;"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>';

    var calIcon = document.createElement("span");
    calIcon.innerHTML =
      '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" style="flex-shrink:0;"><path d="M19 3h-1V1h-2v2H8V1H6v2H5c-1.11 0-1.99.9-1.99 2L3 19c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V8h14v11zM7 10h5v5H7z"/></svg>';

    var startTime = document.createElement("span");
    startTime.textContent = new Date(startedAt).toLocaleString();
    startTime.style.opacity = "0.7";

    var arrow = document.createElement("span");
    arrow.textContent = "→";
    arrow.style.opacity = "0.5";

    var elapsed = document.createElement("span");
    elapsed.style.fontFamily = "monospace";

    function tick() {
      var secs = (Date.now() - start) / 1000;
      if (secs < 0) secs = 0;
      elapsed.textContent = formatDuration(secs);
    }

    tick();
    wrapper.appendChild(calIcon);
    wrapper.appendChild(startTime);
    wrapper.appendChild(arrow);
    wrapper.appendChild(clockIcon);
    wrapper.appendChild(elapsed);
    container.insertBefore(wrapper, container.firstChild);
    var intervalId = setInterval(tick, 1000);
    return { badge: elapsed, intervalId: intervalId };
  }

  function makeDivider() {
    var sep = document.createElement("span");
    sep.textContent = "|";
    sep.style.color = "#ccc";
    return sep;
  }

  function makeLink(text, url, color) {
    var a = document.createElement("a");
    a.textContent = text;
    a.href = url;
    a.style.color = color;
    a.style.textDecoration = "underline";
    return a;
  }

  function buildStatusBar(
    status,
    stdoutUrl,
    stderrUrl,
    elapsedText,
    hasStdout,
    hasStderr,
  ) {
    var container =
      document.querySelector(".dar-output-container") ||
      document.querySelector(".dar-terminal-group");
    if (!container) return;

    var existing = container.querySelector(".dar-status-bar");
    if (existing) existing.remove();

    var bar = document.createElement("div");
    bar.className = "dar-status-bar";
    bar.style.cssText =
      "padding: 0.75em 1em; border-top: 1px solid #e5e7eb; display: flex; align-items: center; gap: 1em; font-size: 13px;";

    var statusEl = document.createElement("span");
    if (status === "SUCCESS") {
      statusEl.textContent = "Successfully finished";
      statusEl.style.cssText = "color: #28a745; font-weight: 600;";
    } else {
      statusEl.textContent = "Failed";
      statusEl.style.cssText = "color: #dc3545; font-weight: 600;";
    }
    bar.appendChild(statusEl);

    if (elapsedText) {
      bar.appendChild(makeDivider());
      var dur = document.createElement("span");
      dur.textContent = elapsedText;
      dur.style.color = "#888";
      bar.appendChild(dur);
    }
    if (hasStderr && status === "FAILED") {
      bar.appendChild(makeDivider());
      bar.appendChild(makeLink("View stderr", stderrUrl, "#dc3545"));
    }
    if (hasStdout && status === "FAILED") {
      bar.appendChild(makeDivider());
      bar.appendChild(makeLink("View stdout", stdoutUrl, "#0d6efd"));
    }

    container.appendChild(bar);
  }

  /**
   * A single terminal bound to one output field of one execution.
   */
  function TerminalField(config, el) {
    this.config = config;
    this.field = el.dataset.darField;
    this.pollInterval = config.pollInterval || DEFAULT_POLL_INTERVAL;
    this.el = el;
    this.cursor = ""; // opaque "<seq>:<offset>" delta cursor
    this.term = new window.Terminal({
      cols: config.cols,
      rows: config.rows,
      scrollback: 5000,
      disableStdin: true,
      // Django command output uses plain "\n" line endings; a bare LF
      // does not return the cursor to column 0 in a terminal.
      convertEol: true,
      theme: { background: "#1e1e1e" },
    });
    this.term.open(el);
    // WebGL renderer: GPU-accelerated, drastically reduces flicker on
    // rapidly redrawn lines (progress bars). Falls back to the default
    // renderer when WebGL is unavailable or the addon fails to activate.
    try {
      if (window.WebglAddon) {
        this.webglAddon = new window.WebglAddon();
        this.webglAddon.onContextLoss(
          function () {
            if (this.webglAddon) {
              this.webglAddon.dispose();
              this.webglAddon = null;
            }
          }.bind(this),
        );
        this.term.loadAddon(this.webglAddon);
      }
    } catch (e) {
      // Renderer stays on the default (DOM/canvas) implementation.
      this.webglAddon = null;
      console.warn("django-admin-runner: WebGL renderer unavailable:", e);
    }
    this.viewport = el.querySelector(".xterm-viewport");
    this.term.scrollToBottom();

    this.progress = null;
    this.bytesWritten = 0;
    this.noticeShown = false;
  }

  TerminalField.prototype.partUrl = function (seq) {
    return (
      this.config.partUrl.replace(/\/part\/0\/$/, "/part/" + seq + "/") +
      "?field=" +
      this.field
    );
  };

  TerminalField.prototype.deltaUrl = function () {
    var sep = this.config.outputUrl.indexOf("?") === -1 ? "?" : "&";
    return (
      this.config.outputUrl +
      sep +
      "field=" +
      this.field +
      "&cursor=" +
      encodeURIComponent(this.cursor)
    );
  };

  TerminalField.prototype.showNotice = function () {
    if (this.noticeShown) return;
    this.noticeShown = true;
    var notice = document.createElement("div");
    notice.className = "dar-truncated-notice";
    notice.style.cssText =
      "padding: 4px 8px; margin-bottom: 4px; font-size: 12px; color: #856404; " +
      "background: #fff3cd; border: 1px solid #ffeeba; border-radius: 4px;";
    notice.textContent =
      "Older output was pruned (retention cap ADMIN_RUNNER_MAX_OUTPUT) — " +
      "showing the retained tail.";
    this.el.parentElement.insertBefore(notice, this.el);
  };

  TerminalField.prototype.showProgress = function (loaded, total) {
    if (total <= PROGRESS_PART_THRESHOLD) return;
    if (!this.progress) {
      var wrap = document.createElement("div");
      wrap.className = "dar-replay-progress";
      wrap.style.cssText =
        "margin-bottom: 4px; font-size: 12px; color: #888; font-family: monospace;";
      var bar = document.createElement("div");
      bar.style.cssText =
        "height: 4px; background: #e5e7eb; border-radius: 2px; overflow: hidden; margin-bottom: 2px;";
      var fill = document.createElement("div");
      fill.style.cssText =
        "height: 100%; width: 0%; background: #0d6efd; transition: width 0.1s;";
      bar.appendChild(fill);
      var label = document.createElement("div");
      wrap.appendChild(bar);
      wrap.appendChild(label);
      this.el.parentElement.insertBefore(wrap, this.el);
      this.progress = { wrap: wrap, fill: fill, label: label };
    }
    var pct = total ? Math.round((loaded / total) * 100) : 0;
    this.progress.fill.style.width = pct + "%";
    this.progress.label.textContent =
      "Loading output… " +
      loaded +
      "/" +
      total +
      " parts (" +
      formatBytes(this.bytesWritten) +
      ")";
  };

  TerminalField.prototype.hideProgress = function () {
    if (this.progress) {
      this.progress.wrap.remove();
      this.progress = null;
    }
  };

  /**
   * Write text in ~64 KB slices, yielding between slices so the page
   * stays responsive during large replays.
   */
  TerminalField.prototype.writeChunked = function (text) {
    var self = this;
    this.bytesWritten += text.length;
    return new Promise(function (resolve) {
      var pos = 0;
      function step() {
        var nearBottom = self.viewport ? isNearBottom(self.viewport) : true;
        var slice = text.slice(pos, pos + WRITE_SLICE);
        if (slice) self.term.write(slice);
        pos += WRITE_SLICE;
        if (nearBottom && self.viewport) self.term.scrollToBottom();
        if (pos < text.length) {
          setTimeout(step, 0);
        } else {
          resolve();
        }
      }
      step();
    });
  };

  /**
   * Sequential replay: fetch parts 0, 1, 2, … until a 404 marks the end
   * of stored parts.  Sealed parts are immutable and browser-cached.
   * Resolves once caught up; leaves this.cursor at the replay position.
   */
  TerminalField.prototype.replay = function () {
    var self = this;
    var seq = 0;

    function fetchPart() {
      return fetch(self.partUrl(seq), {
        headers: { "X-Requested-With": "XMLHttpRequest" },
      }).then(function (r) {
        if (r.status === 404) return null;
        if (!r.ok) throw new Error("part fetch failed: " + r.status);
        var total = parseInt(r.headers.get("X-Dar-Total-Parts") || "0", 10);
        return r.text().then(function (text) {
          return { text: text, total: total };
        });
      });
    }

    function next() {
      return fetchPart().then(function (part) {
        if (part === null) {
          // Caught up: no (more) parts stored.
          self.hideProgress();
          return;
        }
        self.showProgress(seq + 1, part.total || seq + 1);
        return self.writeChunked(part.text).then(function () {
          self.cursor = seq + ":" + part.text.length;
          seq += 1;
          return next();
        });
      });
    }

    return next().catch(function (e) {
      console.error("django-admin-runner: replay failed:", e);
    });
  };

  /**
   * Fetch a delta from the cursor endpoint. Handles `reset` by clearing
   * the terminal and replaying the served retained output.
   */
  TerminalField.prototype.fetchDelta = function () {
    var self = this;
    return fetch(self.deltaUrl(), {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
      .then(function (r) {
        return r.ok ? r.json() : null;
      })
      .then(function (data) {
        if (!data) return null;
        if (data.reset) {
          self.showNotice();
          self.term.reset();
          self.bytesWritten = 0;
          self.cursor = data.cursor;
          return self.writeChunked(data.chunk);
        }
        if (data.chunk) {
          return self.writeChunked(data.chunk);
        }
        self.cursor = data.cursor;
        return data;
      });
  };

  function init() {
    var configEl = document.getElementById("dar-terminal-config");
    if (!configEl || !window.Terminal) return;

    var config;
    try {
      config = JSON.parse(configEl.textContent);
    } catch (e) {
      return;
    }

    var placeholders = Array.prototype.slice.call(
      document.querySelectorAll(".dar-terminal"),
    );
    if (!placeholders.length) return;

    var fields = placeholders.map(function (el) {
      return new TerminalField(config, el);
    });

    var running = config.status === "PENDING" || config.status === "RUNNING";

    var timer = null;
    if (running) {
      var outputContainer =
        document.querySelector(".dar-output-container") ||
        placeholders[0].closest(".module, .dar-terminal-group, form") ||
        document.body;
      timer = startTimer(config.startedAt, outputContainer);
    }

    var stopped = false;

    function fetchAll() {
      return Promise.all(
        fields.map(function (f) {
          return f.fetchDelta();
        }),
      );
    }

    function stopPolling(finalStatus) {
      if (stopped) return;
      stopped = true;
      // One final fetch catches output flushed after finished_at
      fetchAll().then(function () {
        var elapsedText = timer ? timer.badge.textContent : "";
        if (timer) clearInterval(timer.intervalId);
        buildStatusBar(
          finalStatus,
          config.stdoutUrl,
          config.stderrUrl,
          elapsedText,
          fields.some(function (f) {
            return f.field === "stdout";
          }),
          fields.some(function (f) {
            return f.field === "stderr";
          }),
        );
        // Reload to refresh all admin fields (status, timing, etc.)
        setTimeout(function () {
          window.location.reload();
        }, 1000);
      });
    }

    // Initial chunked replay from the beginning, THEN delta polling.
    // Polling must not start before replay resolves: the replay loop
    // writes whole parts and advances/regresses the cursor itself, so a
    // concurrent delta poll would fetch overlapping content and duplicate
    // output (repeated progress-bar frames, flickering last line).
    Promise.all(
      fields.map(function (f) {
        return f.replay();
      }),
    )
      .then(function () {
        if (!running || stopped) return;
        return fetchAll().then(function (results) {
          var data = results && results[0];
          if (data && data.finished) {
            stopPolling(data.status);
          }
        });
      })
      .then(function () {
        if (!running || stopped) return;
        setTimeout(poll, config.pollInterval || DEFAULT_POLL_INTERVAL);
      });

    function poll() {
      if (stopped) return;
      fetchAll()
        .then(function (results) {
          var data = results && results[0];
          if (data && data.finished) {
            stopPolling(data.status);
          }
        })
        .catch(function (e) {
          console.error("django-admin-runner: terminal output poll failed:", e);
        })
        .finally(function () {
          if (!stopped) {
            setTimeout(poll, config.pollInterval || DEFAULT_POLL_INTERVAL);
          }
        });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
