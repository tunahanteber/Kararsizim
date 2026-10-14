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
        r.querySelector("input").setAttribute("aria-label", "Seçenek " + (i + 1));
        r.querySelector("input").placeholder = "Seçenek " + (i + 1);
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

  // Toast yardımcısı
  function toast(message, kind) {
    var box = document.querySelector(".toasts");
    if (!box) {
      box = document.createElement("div");
      box.className = "toasts";
      box.setAttribute("aria-live", "polite");
      document.body.appendChild(box);
    }
    var t = document.createElement("div");
    t.className = "toast" + (kind ? " toast-" + kind : "");
    t.textContent = message;
    box.appendChild(t);
    setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, 4200);
  }

  // Paylaş: navigator.share varsa onu, yoksa linki panoya kopyala
  document.querySelectorAll("[data-share]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var url = btn.getAttribute("data-url"), title = btn.getAttribute("data-title");
      if (navigator.share) { navigator.share({ title: title, url: url }).catch(function () {}); return; }
      var done = function () { toast("Link kopyalandı 📋"); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(done, function () { toast("Link kopyalanamadı, adres çubuğundan kopyalayabilirsin.", "error"); });
      } else {
        var ta = document.createElement("textarea");
        ta.value = url; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.opacity = "0";
        document.body.appendChild(ta); ta.select();
        try { document.execCommand("copy"); done(); } catch (e) { toast("Link kopyalanamadı.", "error"); }
        document.body.removeChild(ta);
      }
    });
  });

  // Oy ver: sayfa yenilenmeden sonuçları aç (JS yoksa / hata olursa normal form gönderimi çalışır)
  var VERDICT_EMOJI = { kil_payi: "⚖️", basa_bas: "🔥", net_karar: "✅", one_cikan: "👀", az_oy: "⏳" };
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;  // textContent: kullanıcı metni asla HTML olarak yorumlanmaz
    return n;
  }
  function leaderPosition(results) {
    var best = null;
    results.forEach(function (r) { if (r.count > 0 && (best === null || r.count > best.count)) best = r; });
    return best ? best.position : null;
  }
  function buildBar(d) {
    var bar = el("div", "decision-bar");
    bar.setAttribute("role", "img");
    bar.setAttribute("aria-label", d.results.map(function (r) { return r.text + " %" + r.percent; }).join(", "));
    var lead = leaderPosition(d.results);
    d.results.forEach(function (r) {
      if (r.percent <= 0) return;  // %0 olan çubukta görünmez
      var seg = el("span", "seg opt-" + r.position + (r.position === lead ? " is-leader" : ""));
      seg.style.setProperty("--w", r.percent + "%");
      if (r.position === d.voted_option) {
        var check = el("span", "seg-check", "✓");
        check.setAttribute("aria-hidden", "true");
        seg.appendChild(check);
      }
      bar.appendChild(seg);
    });
    return bar;
  }
  function buildExtra(d) {
    var frag = document.createDocumentFragment();
    var v = el("p", "verdict");
    var emoji = el("span", null, VERDICT_EMOJI[d.verdict.key] || "");
    emoji.setAttribute("aria-hidden", "true");
    v.appendChild(emoji);
    v.appendChild(document.createTextNode(" " + d.verdict.label));
    frag.appendChild(v);
    var ul = el("ul", "result-list");
    d.results.forEach(function (r) {
      var li = el("li", "result-row opt-" + r.position + (r.position === d.voted_option ? " is-mine" : ""));
      li.style.setProperty("--w", r.percent + "%");
      var text = el("span", "result-text");
      if (r.position === d.voted_option) {
        text.appendChild(el("span", null, "✓")).setAttribute("aria-hidden", "true");
        text.appendChild(el("span", "sr-only", "Senin oyun: "));
        text.appendChild(document.createTextNode(" "));
      }
      text.appendChild(document.createTextNode(r.text));
      li.appendChild(text);
      li.appendChild(el("span", "result-num", r.count + " oy · %" + r.percent));
      ul.appendChild(li);
    });
    frag.appendChild(ul);
    return frag;
  }
  function showResults(root, d) {
    var bar = root.querySelector("[data-bar]"), extra = root.querySelector("[data-extra]");
    bar.textContent = "";
    bar.appendChild(buildBar(d));
    extra.textContent = "";
    extra.appendChild(buildExtra(d));
    var total = root.querySelector("[data-total]");
    if (total) total.textContent = d.total + " kişi oyladı";
    var form = root.querySelector("[data-vote-form]");
    if (form && form.parentNode) form.parentNode.removeChild(form);
    var note = root.querySelector("[data-owner-note]");
    if (note && note.parentNode) note.parentNode.removeChild(note);
  }
  document.querySelectorAll("[data-vote-form]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      var btn = e.submitter;
      if (!window.fetch || !window.FormData || !btn || !btn.name) return;  // normal gönderim
      e.preventDefault();
      var csrf = form.querySelector('[name="csrfmiddlewaretoken"]');
      var body = new FormData();
      body.append(btn.name, btn.value);
      form.classList.add("is-busy");
      fetch(form.action, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Accept": "application/json", "X-CSRFToken": csrf ? csrf.value : "" },
        body: body
      }).then(function (r) {
        if (r.status === 429 || r.status === 409) {
          // Bilinen, kullanıcıya söylenecek durumlar: formu normal akışa düşürme
          return r.json().then(function (d) {
            form.classList.remove("is-busy");
            toast(d.error || "İşlem yapılamadı.", "error");
            if (r.status === 409) setTimeout(function () { location.reload(); }, 1200);
            return null;
          });
        }
        if (!r.ok) throw new Error("http " + r.status);
        return r.json();
      }).then(function (d) {
        if (!d) return;
        var root = form.closest("[data-poll-detail]");
        showResults(root, d);
        toast(d.already_voted ? "Zaten oy verdin, işte sonuçlar." : "Oyun kaydedildi! 🎉");
      }).catch(function () {
        // Hata: normal form gönderimine dön (seçilen seçenek gizli alanla taşınır)
        var hidden = document.createElement("input");
        hidden.type = "hidden"; hidden.name = btn.name; hidden.value = btn.value;
        form.appendChild(hidden);
        form.submit();
      });
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
