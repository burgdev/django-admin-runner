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
    } else if (status === "CANCELLED") {
      statusEl.textContent = "Cancelled";
      statusEl.style.cssText = "color: #d97706; font-weight: 600;";
    } else if (status === "TIMEOUT") {
      statusEl.textContent = "Timed out";
      statusEl.style.cssText = "color: #dc2626; font-weight: 600;";
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
    // Fit to the container (full-output page, config.fit): the terminal
    // fills the available width/height instead of the recorded cols/rows.
    // Re-fit after webfonts load — xterm measures character cells, and the
    // first measurement can happen before the font is applied.
    // The vendored addon bundles are UMD builds whose factory returns the
    // module namespace ({FitAddon: class}) — unwrap that; older builds
    // assigned the constructor itself to the global.
    var FitCtor =
      typeof window.FitAddon === "function"
        ? window.FitAddon
        : window.FitAddon && window.FitAddon.FitAddon;
    if (config.fit && FitCtor) {
      var self0 = this;
      var applyFit = function () {
        if (!self0.fitAddon || !self0.term.element) return;
        try {
          self0.fitAddon.fit();
        } catch (e) {
          /* noop */
        }
      };
      try {
        this.fitAddon = new FitCtor();
        this.term.loadAddon(this.fitAddon);
        applyFit();
        // xterm measures character cells; the first measurement can happen
        // before the webfont is applied — re-fit once fonts are ready.
        if (document.fonts && document.fonts.ready) {
          document.fonts.ready.then(function () {
            applyFit();
          });
        }
        // Late layout / tab panes switching from display:none.
        if (typeof ResizeObserver !== "undefined") {
          this.fitObserver = new ResizeObserver(applyFit);
          this.fitObserver.observe(el);
        }
      } catch (e) {
        this.fitAddon = null;
      }
    }
    // WebGL renderer: GPU-accelerated, drastically reduces flicker on
    // rapidly redrawn lines (progress bars). Falls back to the default
    // renderer when WebGL is unavailable or the addon fails to activate.
    try {
      var WebglCtor =
        typeof window.WebglAddon === "function"
          ? window.WebglAddon
          : window.WebglAddon && window.WebglAddon.WebglAddon;
      if (WebglCtor) {
        this.webglAddon = new WebglCtor();
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
          // CRITICAL: advance the cursor AFTER the chunk is written.
          // Without this, every poll re-requested the same growing delta
          // and re-wrote it — duplicated lines in the terminal view.
          return self.writeChunked(data.chunk).then(function () {
            self.cursor = data.cursor;
            return data;
          });
        }
        self.cursor = data.cursor;
        return data;
      });
  };

  /**
   * Live-update the status badge (#dar-status-badge) from the poll.
   * Markup mirrors the server-side badge in admin.py (_status_badge) —
   * keep icons/colors in sync when changing either side.
   */
  var BADGE_STYLES = {
    PENDING: {
      color: "#6b7280",
      tint: "rgba(107, 114, 128, 0.14)",
      icon:
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">' +
        '<path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8' +
        ' 8 8 0 0 1-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>',
    },
    RUNNING: {
      color: "#2563eb",
      tint: "rgba(37, 99, 235, 0.14)",
      icon:
        '<svg class="dar-spin" width="12" height="12" viewBox="0 0 24 24" ' +
        'fill="none" stroke="currentColor" stroke-width="3" ' +
        'stroke-linecap="round"><path d="M12 3a9 9 0 1 0 9 9"/></svg>',
    },
    SUCCESS: {
      color: "#16a34a",
      tint: "rgba(22, 163, 74, 0.14)",
      icon:
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" ' +
        'stroke="currentColor" stroke-width="3" stroke-linecap="round" ' +
        'stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
    },
    FAILED: {
      color: "#dc2626",
      tint: "rgba(220, 38, 38, 0.14)",
      icon:
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" ' +
        'stroke="currentColor" stroke-width="3" stroke-linecap="round">' +
        '<path d="M18 6 6 18M6 6l12 12"/></svg>',
    },
    CANCELLED: {
      color: "#d97706",
      tint: "rgba(217, 119, 6, 0.14)",
      icon:
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" ' +
        'stroke="currentColor" stroke-width="3" stroke-linecap="round">' +
        '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/></svg>',
    },
    TIMEOUT: {
      color: "#dc2626",
      tint: "rgba(220, 38, 38, 0.12)",
      icon:
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" ' +
        'stroke="currentColor" stroke-width="3" stroke-linecap="round">' +
        '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>',
    },
  };
  var BADGE_LABELS = {
    PENDING: "Pending",
    RUNNING: "Running",
    SUCCESS: "Success",
    FAILED: "Failed",
    CANCELLED: "Cancelled",
    TIMEOUT: "Timed out",
  };

  function updateStatusBadge(status) {
    var badge = document.getElementById("dar-status-badge");
    if (!badge || !status || badge.dataset.status === status) return;
    var style = BADGE_STYLES[status];
    if (!style) return;
    badge.dataset.status = status;
    badge.style.color = style.color;
    badge.style.background = style.tint;
    badge.innerHTML = style.icon + (BADGE_LABELS[status] || status);
  }

  /**
   * Live Stop / Force Stop control (container `#dar-stop-control`).
   *
   * The server renders the control only when the page loads with the
   * execution already RUNNING — an execution that starts out PENDING gets
   * its button inserted here when the poll first reports RUNNING (and the
   * label flips to "Force Stop" once a stop was requested). ``stop`` is
   * null once the execution leaves RUNNING: the control is removed.
   */
  function updateStopControl(stop) {
    var control = document.getElementById("dar-stop-control");
    if (!control) return;
    var state = stop ? (stop.force ? "force" : "stop") : "none";
    if (control.dataset.stopState === state) return;
    control.dataset.stopState = state;
    if (!stop) {
      control.innerHTML = "";
      return;
    }
    var button = document.createElement("button");
    button.type = "button";
    button.textContent = stop.force ? "Force Stop" : "Stop";
    if (stop.force) {
      // Filled red — unmistakably the last resort.
      button.style.cssText =
        "background:#dc3545;color:#fff;border:0;" +
        "border-radius:4px;padding:6px 12px;font-size:11px;font-weight:600;" +
        "cursor:pointer;white-space:nowrap;";
    } else {
      // Outlined red for the graceful stop.
      button.style.cssText =
        "background:rgba(220,53,69,0.08);color:#dc3545;" +
        "border:2px solid rgba(220,53,69,0.55);border-radius:4px;" +
        "padding:6px 12px;font-size:11px;font-weight:600;" +
        "cursor:pointer;white-space:nowrap;";
    }
    button.addEventListener("click", function () {
      button.disabled = true;
      var body = new URLSearchParams();
      if (stop.force) body.set("force", "1");
      var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
      fetch(stop.url, {
        method: "POST",
        headers: {
          "X-CSRFToken": match ? decodeURIComponent(match[1]) : "",
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: body.toString(),
        credentials: "same-origin",
      })
        .then(function () {
          window.location.reload();
        })
        .catch(function () {
          button.disabled = false;
        });
    });
    control.innerHTML = "";
    control.appendChild(button);
  }

  function init() {
    if (window.__darTerminalInit) return; // never double-init
    window.__darTerminalInit = true;
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
          if (data && data.status) updateStatusBadge(data.status);
          if (data) updateStopControl(data.stop);
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
          var any =
            results &&
            results.filter(function (r) {
              return r;
            })[0];
          if (any && any.status) updateStatusBadge(any.status);
          updateStopControl(any && any.stop);
          var data =
            results &&
            results.filter(function (r) {
              return r && r.finished;
            })[0];
          if (data) {
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

    // Re-fit terminals when the window resizes (full-output page only).
    window.addEventListener("resize", function () {
      fields.forEach(function (f) {
        if (f.fitAddon) {
          try {
            f.fitAddon.fit();
          } catch (e) {
            /* noop */
          }
        }
      });
    });
  }

  // Changelist Stop / Force Stop links: the stop endpoint is POST-only
  // and the changelist wraps rows in a form (no nested forms allowed),
  // so the link is turned into a fetch POST here. Registered at module
  // scope — pages without terminals (the changelist) skip init() early.
  document.addEventListener("click", function (ev) {
    var link = ev.target.closest ? ev.target.closest("a.dar-stop-post") : null;
    if (!link) return;
    ev.preventDefault();
    if (link.dataset.stopPosted) return;
    link.dataset.stopPosted = "1";
    var body = new URLSearchParams();
    if (link.dataset.force === "1") body.set("force", "1");
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    fetch(link.href, {
      method: "POST",
      headers: {
        "X-CSRFToken": match ? decodeURIComponent(match[1]) : "",
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: body.toString(),
      credentials: "same-origin",
    })
      .then(function () {
        window.location.reload();
      })
      .catch(function () {
        delete link.dataset.stopPosted;
      });
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
