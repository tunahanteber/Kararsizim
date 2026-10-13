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
})();
