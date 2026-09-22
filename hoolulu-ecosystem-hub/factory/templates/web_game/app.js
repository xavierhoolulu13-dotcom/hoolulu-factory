/* {{NAME}} — {{TAGLINE}}
   Plain JavaScript, no build step, no network requests. Works offline. */
(function () {
  "use strict";

  var CELLS = 20;              // board is CELLS x CELLS
  var BASE_SPEED = 140;        // ms per step at level 1
  var SPEEDUP = 8;             // ms shaved per food
  var MIN_SPEED = 70;

  var canvas = document.getElementById("board");
  var ctx = canvas.getContext("2d");
  var scoreEl = document.getElementById("score");
  var bestEl = document.getElementById("best");
  var levelEl = document.getElementById("level");
  var overlay = document.getElementById("overlay");
  var overlayTitle = document.getElementById("overlay-title");
  var overlayText = document.getElementById("overlay-text");
  var overlayBtn = document.getElementById("overlay-btn");
  var playBtn = document.getElementById("play");
  var restartBtn = document.getElementById("restart");
  var shareBtn = document.getElementById("share");

  var cell = canvas.width / CELLS;
  var snake, dir, nextDir, food, score, best, running, timer, started;

  best = Number(localStorage.getItem("{{SLUG}}-best") || 0);
  bestEl.textContent = best;

  function resize() {
    // keep the backing store sharp on high-DPI screens
    var size = Math.min(canvas.clientWidth || canvas.width, 480);
    var ratio = window.devicePixelRatio || 1;
    canvas.width = size * ratio;
    canvas.height = size * ratio;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    cell = size / CELLS;
    draw();
  }

  function reset() {
    snake = [{ x: 8, y: 10 }, { x: 7, y: 10 }, { x: 6, y: 10 }];
    dir = { x: 1, y: 0 };
    nextDir = dir;
    score = 0;
    started = false;
    running = false;
    placeFood();
    scoreEl.textContent = "0";
    levelEl.textContent = "1";
    playBtn.textContent = "Pause";
    showOverlay("Ready?", "Arrow keys or swipe. Press space to start.");
    draw();
  }

  function placeFood() {
    var free = [];
    for (var y = 0; y < CELLS; y++) {
      for (var x = 0; x < CELLS; x++) {
        if (!snake.some(function (s) { return s.x === x && s.y === y; })) free.push({ x: x, y: y });
      }
    }
    food = free[Math.floor(Math.random() * free.length)] || { x: 0, y: 0 };
  }

  function level() { return Math.floor(score / 5) + 1; }
  function speed() { return Math.max(MIN_SPEED, BASE_SPEED - score * SPEEDUP); }

  function step() {
    dir = nextDir;
    var head = { x: snake[0].x + dir.x, y: snake[0].y + dir.y };

    if (head.x < 0 || head.y < 0 || head.x >= CELLS || head.y >= CELLS ||
        snake.some(function (s) { return s.x === head.x && s.y === head.y; })) {
      return gameOver();
    }

    snake.unshift(head);
    if (head.x === food.x && head.y === food.y) {
      score += 1;
      scoreEl.textContent = String(score);
      levelEl.textContent = String(level());
      if (score > best) {
        best = score;
        bestEl.textContent = String(best);
        try { localStorage.setItem("{{SLUG}}-best", String(best)); } catch (e) { /* private mode */ }
      }
      placeFood();
      clearTimeout(timer);
      timer = setTimeout(loop, speed());
    } else {
      snake.pop();
    }
    draw();
  }

  function loop() {
    if (!running) return;
    step();
    if (running) timer = setTimeout(loop, speed());
  }

  function draw() {
    var size = cell * CELLS;
    ctx.clearRect(0, 0, size, size);

    // board grid
    ctx.fillStyle = "rgba(255,255,255,0.02)";
    for (var i = 0; i < CELLS; i++) {
      for (var j = 0; j < CELLS; j++) {
        if ((i + j) % 2 === 0) ctx.fillRect(i * cell, j * cell, cell, cell);
      }
    }

    // food
    ctx.fillStyle = "{{ACCENT}}";
    roundRect(food.x * cell + cell * 0.18, food.y * cell + cell * 0.18, cell * 0.64, cell * 0.64, cell * 0.22);

    // snake
    for (var k = snake.length - 1; k >= 0; k--) {
      var seg = snake[k];
      ctx.fillStyle = k === 0 ? "#8ef0d8" : "#2dd4bf";
      ctx.globalAlpha = k === 0 ? 1 : Math.max(0.45, 1 - k / (snake.length + 6));
      roundRect(seg.x * cell + cell * 0.08, seg.y * cell + cell * 0.08, cell * 0.84, cell * 0.84, cell * 0.26);
      ctx.globalAlpha = 1;
    }
  }

  function roundRect(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
    ctx.fill();
  }

  function gameOver() {
    running = false;
    clearTimeout(timer);
    showOverlay("Game over", "You scored " + score + ". Best is " + best + ".");
  }

  function showOverlay(title, text) {
    overlayTitle.textContent = title;
    overlayText.textContent = text;
    overlay.classList.remove("hidden");
  }

  function hideOverlay() { overlay.classList.add("hidden"); }

  function start() {
    if (running) return;
    running = true;
    started = true;
    hideOverlay();
    clearTimeout(timer);
    timer = setTimeout(loop, speed());
  }

  function pause() {
    running = false;
    clearTimeout(timer);
    playBtn.textContent = "Resume";
    showOverlay("Paused", "Press play or hit space to continue.");
  }

  function turn(x, y) {
    // no 180° turns: that is how you lose instantly
    if (dir.x === -x && dir.y === -y) return;
    nextDir = { x: x, y: y };
    if (!started) start();
  }

  // --- input --------------------------------------------------------------
  var KEYS = {
    ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0],
    w: [0, -1], s: [0, 1], a: [-1, 0], d: [1, 0], W: [0, -1], S: [0, 1], A: [-1, 0], D: [1, 0]
  };

  document.addEventListener("keydown", function (event) {
    if (event.key === " " || event.code === "Space") {
      event.preventDefault();
      running ? pause() : start();
      return;
    }
    var move = KEYS[event.key];
    if (move) {
      event.preventDefault();
      turn(move[0], move[1]);
    }
  });

  var touch = null;
  canvas.addEventListener("touchstart", function (event) {
    touch = event.touches[0];
  }, { passive: true });

  canvas.addEventListener("touchend", function (event) {
    if (!touch) return;
    var end = event.changedTouches[0];
    var dx = end.clientX - touch.clientX;
    var dy = end.clientY - touch.clientY;
    touch = null;
    if (Math.abs(dx) < 20 && Math.abs(dy) < 20) { running ? pause() : start(); return; }
    if (Math.abs(dx) > Math.abs(dy)) turn(dx > 0 ? 1 : -1, 0);
    else turn(0, dy > 0 ? 1 : -1);
  }, { passive: true });

  playBtn.addEventListener("click", function () { running ? pause() : start(); });
  restartBtn.addEventListener("click", function () { hideOverlay(); reset(); });
  overlayBtn.addEventListener("click", function () { hideOverlay(); reset(); start(); });

  shareBtn.addEventListener("click", function () {
    var url = location.origin + location.pathname + "?beat=" + best;
    var note = "I scored " + best + " in {{NAME}}. Beat that: " + url;
    var done = function () { shareBtn.textContent = "Copied!"; setTimeout(function () { shareBtn.textContent = "Copy challenge"; }, 1600); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(note).then(done, function () { prompt("Copy this:", note); });
    } else {
      prompt("Copy this:", note);
    }
  });

  window.addEventListener("resize", resize);

  // A challenge link shows the target before the first move.
  var params = new URLSearchParams(location.search);
  var beat = params.get("beat");
  if (beat) overlayText.textContent = "Beat " + beat + " to take the crown.";

  resize();
  reset();
})();
