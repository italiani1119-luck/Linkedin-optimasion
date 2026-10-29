(function () {
  "use strict";

  var MAX_TEXT = 3000;

  function formatCount(n) {
    try {
      return n.toLocaleString("id-ID");
    } catch (e) {
      return String(n);
    }
  }

  function bindCounter(textarea) {
    var out = document.getElementById(textarea.getAttribute("data-counter"));
    if (!out) return;
    function update() {
      var n = textarea.value.length;
      out.textContent = formatCount(n) + " / 3.000 karakter";
      out.classList.toggle("over", n > MAX_TEXT);
    }
    textarea.addEventListener("input", update);
    update();
  }

  function bindPreview(textarea) {
    var box = document.getElementById(textarea.getAttribute("data-preview"));
    if (!box) return;
    function update() {
      var value = textarea.value;
      box.textContent = value.trim() ? value : "Post masih kosong.";
      box.classList.toggle("empty", !value.trim());
    }
    textarea.addEventListener("input", update);
    update();
  }

  document.querySelectorAll("textarea[data-counter]").forEach(bindCounter);
  document.querySelectorAll("textarea[data-preview]").forEach(bindPreview);

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var temp = document.createElement("textarea");
      temp.value = text;
      temp.setAttribute("readonly", "");
      temp.style.position = "fixed";
      temp.style.top = "-1000px";
      document.body.appendChild(temp);
      temp.select();
      try {
        document.execCommand("copy");
        resolve();
      } catch (err) {
        reject(err);
      } finally {
        document.body.removeChild(temp);
      }
    });
  }

  document.querySelectorAll("[data-copy]").forEach(function (button) {
    button.addEventListener("click", function () {
      var target = document.getElementById(button.getAttribute("data-copy"));
      if (!target) return;
      var text = target.tagName === "TEXTAREA" ? target.value : target.textContent;
      var original = button.textContent;
      copyText(text)
        .then(function () {
          button.textContent = "Tersalin";
          setTimeout(function () { button.textContent = original; }, 1500);
        })
        .catch(function () {
          alert("Tidak bisa menyalin otomatis. Blok teksnya lalu tekan Ctrl+C.");
        });
    });
  });

  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.getAttribute("data-confirm"))) {
        event.preventDefault();
      }
    });
  });

  document.querySelectorAll("button[data-confirm]").forEach(function (button) {
    button.addEventListener("click", function (event) {
      if (!window.confirm(button.getAttribute("data-confirm"))) {
        event.preventDefault();
      }
    });
  });

  document.querySelectorAll("input[data-reveal]").forEach(function (box) {
    box.addEventListener("change", function () {
      var field = document.getElementById(box.getAttribute("data-reveal"));
      if (field) field.type = box.checked ? "text" : "password";
    });
  });

  var providerSelect = document.getElementById("llm_provider");
  if (providerSelect) {
    var providerBoxes = document.querySelectorAll("[data-provider]");
    var applyProvider = function () {
      providerBoxes.forEach(function (box) {
        box.style.display = box.getAttribute("data-provider") === providerSelect.value ? "" : "none";
      });
    };
    providerSelect.addEventListener("change", applyProvider);
    applyProvider();
  }

  var modeSelect = document.getElementById("gen_mode");
  if (modeSelect) {
    var fields = document.querySelectorAll("[data-mode]");
    function applyMode() {
      var mode = modeSelect.value;
      fields.forEach(function (field) {
        var modes = field.getAttribute("data-mode").split(",");
        field.style.display = modes.indexOf(mode) === -1 ? "none" : "";
      });
    }
    modeSelect.addEventListener("change", applyMode);
    applyMode();
  }
})();
