// kararsızım — vanilla JS
(function () {
  // Kayıt formu: kullanıcı adı kural ipucu (sunucu doğrulaması asıl olandır)
  var input = document.querySelector("[data-username-hint]");
  var hint = document.querySelector('[data-hint-for="username"]');
  if (input && hint) {
    var base = hint.textContent;
    var re = /^[a-z0-9_.]{3,20}$/;
    input.addEventListener("input", function () {
      var v = input.value.trim().toLowerCase();
      hint.classList.remove("is-ok", "is-bad");
      if (!v) { hint.textContent = base; return; }
      if (re.test(v)) { hint.textContent = "Güzel, bu olur."; hint.classList.add("is-ok"); }
      else { hint.textContent = base + " (Türkçe karakter ve boşluk olmaz.)"; hint.classList.add("is-bad"); }
    });
  }

  // Anket oluşturma: dinamik seçenek ekleme/silme (JS yoksa 5 input görünür)
  var form = document.querySelector("[data-poll-form]");
  if (form) {
    var rows = Array.prototype.slice.call(form.querySelectorAll("[data-option-row]"));
    var addBtn = form.querySelector("[data-add-option]");
    function domRows() { return Array.prototype.slice.call(form.querySelectorAll("[data-option-row]")); }
    function sync() {
      var visible = domRows().filter(function (r) { return !r.classList.contains("is-hidden"); });
      addBtn.hidden = visible.length >= 5;
      visible.forEach(function (r, i) {
        r.querySelector("[data-remove]").hidden = visible.length <= 2;
        r.className = "option-row opt-" + i;  // renk sırası DOM sırasını izler
        r.querySelector(".dot").className = "dot opt-" + i;
      });
    }
    form.addEventListener("submit", function () {
      // Sunucu option_0..4 alanlarını sırayla okur; görünür sıraya göre yeniden adlandır
      var n = 0;
      domRows().forEach(function (r) {
        var inp = r.querySelector("input");
        if (r.classList.contains("is-hidden")) { inp.disabled = true; }  // gönderilmesin
        else { inp.name = "option_" + n; n += 1; }
      });
    });
    rows.forEach(function (r, i) {
      var input = r.querySelector("input");
      if (i >= 2 && !input.value) r.classList.add("is-hidden");
      r.querySelector("[data-remove]").addEventListener("click", function () {
        input.value = "";
        r.classList.add("is-hidden");
        // gizli satırlar sona gitsin ki renk sırası bozulmasın
        r.parentNode.insertBefore(r, addBtn);
        sync();
      });
    });
    addBtn.addEventListener("click", function () {
      var next = domRows().filter(function (r) { return r.classList.contains("is-hidden"); })[0];
      if (next) { next.classList.remove("is-hidden"); next.querySelector("input").focus(); }
      sync();
    });
    sync();

    var q = form.querySelector('input[name="question"]');
    if (q) {
      var counter = document.createElement("p");
      counter.className = "counter";
      q.parentNode.appendChild(counter);
      var update = function () { counter.textContent = q.value.length + " / " + (q.maxLength > 0 ? q.maxLength : 160); };
      q.addEventListener("input", update);
      update();
    }
  }

  // Silme onayı
  document.querySelectorAll("form[data-confirm]").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      if (!window.confirm(f.getAttribute("data-confirm"))) e.preventDefault();
    });
  });

  // Paylaş
  document.querySelectorAll("[data-share]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var url = btn.getAttribute("data-url"), title = btn.getAttribute("data-title");
      if (navigator.share) { navigator.share({ title: title, url: url }).catch(function () {}); return; }
      if (navigator.clipboard) {
        navigator.clipboard.writeText(url).then(function () { btn.textContent = "Link kopyalandı ✓"; });
      }
    });
  });

  // Çift gönderimi engelle (giriş/kayıt): ikinci istek eski CSRF token'ıyla gelip 403 verirdi
  document.querySelectorAll("form[data-once]").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      if (f.dataset.submitted) { e.preventDefault(); return; }
      f.dataset.submitted = "1";
      var b = f.querySelector('button[type="submit"]');
      if (b) setTimeout(function () { b.disabled = true; }, 0);
    });
  });
})();
