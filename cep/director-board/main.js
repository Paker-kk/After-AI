(function () {
  var canvas = document.getElementById("board");
  var ctx = canvas.getContext("2d");
  var statusBox = document.getElementById("status");
  var resultsBox = document.getElementById("results");
  var shotPromptEl = document.getElementById("shotPrompt");
  var audioPromptEl = document.getElementById("audioPrompt");
  var imageProviderEl = document.getElementById("imageProvider");
  var audioProviderEl = document.getElementById("audioProvider");
  var audioDurationEl = document.getElementById("audioDuration");
  var removeBgFileEl = document.getElementById("removeBgFile");

  var BOARD_STATE = {
    zoom: 1,
    panX: 0,
    panY: 0,
    dragging: false,
    dragStartX: 0,
    dragStartY: 0,
    nodes: []
  };

  var ASSETS = [];
  var SERVER_BASE = "http://localhost:8000";

  function setStatus(text) {
    statusBox.textContent = text;
  }

  function resizeCanvas() {
    canvas.width = canvas.clientWidth;
    canvas.height = canvas.clientHeight;
    drawBoard();
  }

  function worldToScreen(x, y) {
    return {
      x: x * BOARD_STATE.zoom + BOARD_STATE.panX,
      y: y * BOARD_STATE.zoom + BOARD_STATE.panY
    };
  }

  function screenToWorld(x, y) {
    return {
      x: (x - BOARD_STATE.panX) / BOARD_STATE.zoom,
      y: (y - BOARD_STATE.panY) / BOARD_STATE.zoom
    };
  }

  function drawGrid() {
    var step = 64 * BOARD_STATE.zoom;
    var minStep = 24;
    if (step < minStep) {
      step = minStep;
    }
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "#252525";
    ctx.lineWidth = 1;
    for (var x = BOARD_STATE.panX % step; x < canvas.width; x += step) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.stroke();
    }
    for (var y = BOARD_STATE.panY % step; y < canvas.height; y += step) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }
  }

  function drawNode(node) {
    var p = worldToScreen(node.x, node.y);
    var w = node.w * BOARD_STATE.zoom;
    var h = node.h * BOARD_STATE.zoom;
    ctx.fillStyle = "#202020";
    ctx.strokeStyle = "#5a5a5a";
    ctx.lineWidth = 1;
    roundRect(ctx, p.x, p.y, w, h, 8);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#f2f2f2";
    ctx.font = Math.max(10, 12 * BOARD_STATE.zoom) + "px Arial";
    ctx.fillText(node.title, p.x + 12, p.y + 22);
    ctx.fillStyle = "#9d9d9d";
    var line = (node.subtitle || "").slice(0, 70);
    ctx.fillText(line, p.x + 12, p.y + 42);
  }

  function roundRect(context, x, y, w, h, r) {
    context.beginPath();
    context.moveTo(x + r, y);
    context.arcTo(x + w, y, x + w, y + h, r);
    context.arcTo(x + w, y + h, x, y + h, r);
    context.arcTo(x, y + h, x, y, r);
    context.arcTo(x, y, x + w, y, r);
    context.closePath();
  }

  function drawBoard() {
    drawGrid();
    for (var i = 0; i < BOARD_STATE.nodes.length; i++) {
      drawNode(BOARD_STATE.nodes[i]);
    }
  }

  function addNode(title, subtitle) {
    var worldCenter = screenToWorld(canvas.width * 0.5, canvas.height * 0.5);
    BOARD_STATE.nodes.push({
      id: "node_" + Date.now(),
      x: worldCenter.x - 140,
      y: worldCenter.y - 60,
      w: 280,
      h: 120,
      title: title,
      subtitle: subtitle || ""
    });
    drawBoard();
  }

  function bindCanvasEvents() {
    canvas.addEventListener("mousedown", function (evt) {
      BOARD_STATE.dragging = true;
      BOARD_STATE.dragStartX = evt.clientX;
      BOARD_STATE.dragStartY = evt.clientY;
    });
    window.addEventListener("mouseup", function () {
      BOARD_STATE.dragging = false;
    });
    window.addEventListener("mousemove", function (evt) {
      if (!BOARD_STATE.dragging) {
        return;
      }
      var dx = evt.clientX - BOARD_STATE.dragStartX;
      var dy = evt.clientY - BOARD_STATE.dragStartY;
      BOARD_STATE.dragStartX = evt.clientX;
      BOARD_STATE.dragStartY = evt.clientY;
      BOARD_STATE.panX += dx;
      BOARD_STATE.panY += dy;
      drawBoard();
    });
    canvas.addEventListener("wheel", function (evt) {
      evt.preventDefault();
      var direction = evt.deltaY > 0 ? -1 : 1;
      var factor = direction > 0 ? 1.08 : 0.92;
      var oldZoom = BOARD_STATE.zoom;
      var newZoom = Math.max(0.2, Math.min(3, oldZoom * factor));
      var mouseX = evt.offsetX;
      var mouseY = evt.offsetY;
      var world = screenToWorld(mouseX, mouseY);
      BOARD_STATE.zoom = newZoom;
      BOARD_STATE.panX = mouseX - world.x * newZoom;
      BOARD_STATE.panY = mouseY - world.y * newZoom;
      drawBoard();
    }, { passive: false });
  }

  async function callApi(path, payload) {
    var resp = await fetch(SERVER_BASE + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {})
    });
    if (!resp.ok) {
      throw new Error("API " + path + " failed: " + resp.status);
    }
    return resp.json();
  }

  function renderAssets() {
    resultsBox.innerHTML = "";
    for (var i = ASSETS.length - 1; i >= 0; i--) {
      var asset = ASSETS[i];
      var wrapper = document.createElement("div");
      wrapper.className = "asset";

      if (asset.preview_url) {
        var img = document.createElement("img");
        img.src = asset.preview_url;
        wrapper.appendChild(img);
      }

      var meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = (asset.type || "asset") + " | " + (asset.local_path || "remote");
      wrapper.appendChild(meta);

      var btnRow = document.createElement("div");
      btnRow.className = "row";

      if (asset.type === "image" && asset.local_path) {
        var importImgBtn = document.createElement("button");
        importImgBtn.textContent = "导入 AE(当前帧)";
        importImgBtn.onclick = function (path) {
          return function () {
            importImageToAE(path);
          };
        }(asset.local_path);
        btnRow.appendChild(importImgBtn);
      }

      if (asset.type === "audio" && asset.local_path) {
        var importAudioBtn = document.createElement("button");
        importAudioBtn.className = "success";
        importAudioBtn.textContent = "导入音频到 AE";
        importAudioBtn.onclick = function (path) {
          return function () {
            importAudioToAE(path);
          };
        }(asset.local_path);
        btnRow.appendChild(importAudioBtn);
      }

      wrapper.appendChild(btnRow);
      resultsBox.appendChild(wrapper);
    }
  }

  function pushAsset(asset) {
    ASSETS.push(asset);
    renderAssets();
  }

  function importImageToAE(localPath) {
    try {
      var cs = new CSInterface();
      var escapedPath = localPath.replace(/\\/g, "\\\\");
      var frame = 0;
      var script = 'com.AESD.cep.initialize();com.AESD.cep.importImageAtFrame("' + escapedPath + '",' + frame + ');';
      cs.evalScript(script, function (res) {
        setStatus("AE 图像导入结果: " + (res || "done"));
      });
    } catch (err) {
      setStatus("导入失败，请确认在 AE 中运行: " + err.message);
    }
  }

  function importAudioToAE(localPath) {
    try {
      var cs = new CSInterface();
      var escapedPath = localPath.replace(/\\/g, "\\\\");
      var script = 'com.AESD.cep.importAudioAtFrame("' + escapedPath + '",0);';
      cs.evalScript(script, function (res) {
        setStatus("AE 音频导入结果: " + (res || "done"));
      });
    } catch (err) {
      setStatus("导入失败，请确认在 AE 中运行: " + err.message);
    }
  }

  function bindUiEvents() {
    document.getElementById("refinePrompt").addEventListener("click", async function () {
      var text = (shotPromptEl.value || "").trim();
      if (!text) {
        setStatus("请先输入镜头描述");
        return;
      }
      setStatus("Gemini 正在优化提示词...");
      try {
        var result = await callApi("/ai/refine_prompt", {
          text: text,
          target: "image"
        });
        if (result && result.prompt) {
          shotPromptEl.value = result.prompt;
          addNode("Prompt Refined", result.prompt);
          setStatus("提示词优化完成");
        } else {
          setStatus("提示词优化返回为空");
        }
      } catch (err) {
        setStatus("优化失败: " + err.message);
      }
    });

    document.getElementById("genImage").addEventListener("click", async function () {
      var prompt = (shotPromptEl.value || "").trim();
      if (!prompt) {
        setStatus("请先输入镜头描述");
        return;
      }
      setStatus("正在生成画面...");
      try {
        var result = await callApi("/generate/image", {
          provider: imageProviderEl.value,
          prompt: prompt
        });
        pushAsset({
          type: "image",
          local_path: result.local_path || "",
          preview_url: result.preview_url || "",
          provider: result.provider || imageProviderEl.value
        });
        addNode("Image Generated", prompt);
        setStatus("画面生成完成");
      } catch (err) {
        setStatus("画面生成失败: " + err.message);
      }
    });

    document.getElementById("genAudio").addEventListener("click", async function () {
      var prompt = (audioPromptEl.value || "").trim();
      if (!prompt) {
        setStatus("请先输入音频描述");
        return;
      }
      setStatus("正在生成音频...");
      try {
        var result = await callApi("/generate/audio", {
          provider: audioProviderEl.value,
          prompt: prompt,
          duration: Number(audioDurationEl.value || 30)
        });
        pushAsset({
          type: "audio",
          local_path: result.local_path || "",
          preview_url: "",
          provider: result.provider || audioProviderEl.value
        });
        addNode("Audio Generated", prompt);
        setStatus("音频生成完成");
      } catch (err) {
        setStatus("音频生成失败: " + err.message);
      }
    });

    document.getElementById("removeBg").addEventListener("click", async function () {
      var file = removeBgFileEl.files && removeBgFileEl.files[0];
      if (!file) {
        setStatus("请先选择图片文件");
        return;
      }
      setStatus("正在上传并抠图...");
      try {
        var b64 = await fileToBase64(file);
        var result = await callApi("/api/remove-bg", {
          filename: file.name,
          image_base64: b64
        });
        pushAsset({
          type: "image",
          local_path: result.local_path || "",
          preview_url: result.preview_url || ""
        });
        addNode("BG Removed", file.name);
        setStatus("抠图完成");
      } catch (err) {
        setStatus("抠图失败: " + err.message);
      }
    });
  }

  function fileToBase64(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () {
        var value = String(reader.result || "");
        var idx = value.indexOf(",");
        resolve(idx >= 0 ? value.slice(idx + 1) : value);
      };
      reader.onerror = function () {
        reject(new Error("读取文件失败"));
      };
      reader.readAsDataURL(file);
    });
  }

  function init() {
    resizeCanvas();
    bindCanvasEvents();
    bindUiEvents();
    addNode("Director Board", "Infinite Canvas Ready");
    setStatus("Director Board 已就绪。");
  }

  window.addEventListener("resize", resizeCanvas);
  init();
})();
