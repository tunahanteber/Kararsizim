# kararsızım — Proje Spesifikasyonu ve Claude Code Yol Haritası

> Bu dosya, Claude Code'un projeyi faz faz geliştirmesi için tek doğruluk kaynağıdır.
> Repo köküne `CLAUDE.md` adıyla koyabilir ya da Claude Code'a `@KARARSIZIM.md` ile referans verebilirsin.
> **Kural:** Her oturumda yalnızca istenen fazı uygula. Bir faz bitmeden sonrakine geçme.

---

## 1. Ürün Özeti

**kararsızım**, kullanıcıların kararsız kaldıkları konularda topluluğa anket açarak fikir aldığı bir web uygulamasıdır.

- Örnek: *"Bu akşam sinemaya mı gitsem, restorana mı?"*
- Her ankette **en az 2, en fazla 5** seçenek vardır.
- **Takip / arkadaşlık mekanizması yoktur.** Herkes platformdaki tüm anketleri görür ve oylar.
- **Üye olmadan** anketler görüntülenir ve oylanır.
- **Anket oluşturmak için üyelik zorunludur.**
- Anketlerde oluşturanın **kullanıcı adı** görünür; **e-posta asla görünmez.**
- **Oy vermeden sonuçlar (yüzdeler/oy dağılımı) gizlidir.** Amaç sürü psikolojisini kırmak ve oy vermeyi teşvik etmek.

**İlk hedef: çalışan bir prototip.** Gereksiz karmaşıklık yok; sonradan adım adım geliştirilecek.

---

## 2. Teknoloji Yığını

| Katman | Seçim | Not |
|---|---|---|
| Dil | Python 3.12 | `.python-version` dosyasında sabitlenir |
| Framework | Django 5.2 LTS | Sunucu tarafı render (Django templates) |
| Veritabanı | Supabase (PostgreSQL) | Yalnızca Postgres olarak kullanılır; Supabase Auth / supabase-js **kullanılmaz** |
| DB sürücüsü | `psycopg[binary]` (psycopg 3) | |
| DB URL ayrıştırma | `dj-database-url` | |
| Ortam değişkenleri | `python-dotenv` | Yalnızca lokal |
| Statik dosya | Django staticfiles (+ lokal için `whitenoise`) | Vercel prod'da CDN'den sunar |
| Frontend | Saf HTML + CSS + vanilla JS | Framework, build adımı, npm **yok** |
| Deploy | Vercel (Python runtime, Django zero-config) | |

**Kullanılmayacaklar (prototip için):** React/Vue, Tailwind, DRF, Celery, Redis, Supabase Auth, Docker. Kimlik doğrulama Django'nun kendi auth sistemiyle yapılır.

### requirements.txt (başlangıç)

```
Django>=5.2,<6.0
psycopg[binary]>=3.2
dj-database-url>=2.2
python-dotenv>=1.0
whitenoise>=6.7
```

---

## 3. Repo Yapısı

```
kararsizim/
├── manage.py
├── requirements.txt
├── .python-version            # 3.12
├── vercel.json
├── .env.example               # gerçek değerler YOK
├── .gitignore                 # .env, .env.local, .venv, staticfiles/, __pycache__, db.sqlite3
├── KARARSIZIM.md              # bu dosya (veya CLAUDE.md)
├── config/                    # Django proje paketi
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── accounts/                  # özel kullanıcı modeli, kayıt/giriş
│   ├── models.py
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   └── admin.py
├── polls/                     # anket, seçenek, oy
│   ├── models.py
│   ├── forms.py
│   ├── views.py
│   ├── urls.py
│   ├── services.py            # oy verme, sonuç hesaplama, kod üretimi
│   ├── admin.py
│   └── templatetags/polls_extras.py
├── templates/
│   ├── base.html
│   ├── partials/              # poll_card.html, decision_bar.html, badge.html ...
│   ├── accounts/
│   └── polls/
└── static/
    ├── css/app.css
    ├── js/app.js
    └── img/                   # logo.svg, favicon
```

---

## 4. Veri Modeli

### 4.1 `accounts.User` (özel kullanıcı modeli — **ilk migration'dan ÖNCE** oluşturulmalı)

`AbstractUser`'dan türetilir.

| Alan | Tip | Kural |
|---|---|---|
| `email` | EmailField | unique, zorunlu, **giriş için kullanılır**, hiçbir sayfada gösterilmez |
| `username` | CharField(20) | unique (**büyük/küçük harf duyarsız**), zorunlu, herkese görünür |
| `password` | Django varsayılanı | Django parola doğrulayıcıları aktif |

- `USERNAME_FIELD = "email"`, `REQUIRED_FIELDS = ["username"]`
- Kullanıcı adı kuralı: `^[a-z0-9_.]{3,20}$` — kayıtta küçük harfe çevrilir. Türkçe karakter kabul edilmez (URL'de `/u/<username>/` olarak kullanılacağı için).
- Rezerve adlar reddedilir: `admin, yeni, giris, kayit, cikis, api, static, kararsizim, u, a`.
- DB seviyesinde: `UniqueConstraint(Lower("username"), name="uniq_username_ci")`.
- E-posta da küçük harfe normalize edilerek saklanır.
- `AUTH_USER_MODEL = "accounts.User"` settings'te en baştan tanımlı olmalı.

### 4.2 `polls.Poll`

| Alan | Tip | Kural |
|---|---|---|
| `id` | BigAutoField | **Sadece dahili.** URL'de veya HTML'de asla görünmez |
| `code` | CharField(12) | unique, index, URL'de kullanılan **rastgele 12 karakterlik kod** |
| `author` | FK → User | `on_delete=CASCADE` |
| `question` | CharField(160) | zorunlu, trim edilir, min 5 karakter |
| `details` | CharField(300) | opsiyonel kısa açıklama |
| `indecision_level` | PositiveSmallIntegerField | 1, 2, 3 (bkz. Kararsızlık Rozeti) |
| `created_at` | DateTimeField | `auto_now_add`, index |

### 4.3 `polls.Option`

| Alan | Tip | Kural |
|---|---|---|
| `poll` | FK → Poll | `related_name="options"`, CASCADE |
| `text` | CharField(80) | zorunlu, trim |
| `position` | PositiveSmallIntegerField | 0–4; seçenek rengi buna göre atanır |

- `UniqueConstraint(fields=["poll", "position"])`
- Bir ankette 2–5 seçenek; aynı ankette tekrar eden seçenek metni yasak (karşılaştırma `strip().casefold()` ile). Not: Türkçe `I/ı/İ/i` dönüşümleri `casefold` ile kusursuz değildir; prototip için kabul edilebilir.

### 4.4 `polls.Vote`

| Alan | Tip | Kural |
|---|---|---|
| `poll` | FK → Poll | CASCADE, `related_name="votes"` |
| `option` | FK → Option | CASCADE |
| `user` | FK → User, null | Giriş yapmış oy veren |
| `voter_hash` | CharField(64), null | Anonim oy veren için oturum anahtarından üretilen hash |
| `created_at` | DateTimeField | `auto_now_add` |

Kısıtlar (DB seviyesinde, race condition'a karşı asıl güvence bunlar):

```python
constraints = [
    models.UniqueConstraint(fields=["poll", "user"],
        condition=Q(user__isnull=False), name="uniq_vote_per_user"),
    models.UniqueConstraint(fields=["poll", "voter_hash"],
        condition=Q(voter_hash__isnull=False), name="uniq_vote_per_anon"),
    models.CheckConstraint(
        condition=(Q(user__isnull=False, voter_hash__isnull=True) |
                   Q(user__isnull=True, voter_hash__isnull=False)),
        name="vote_exactly_one_identity"),
]
```

> Django 5.2'de `CheckConstraint` için `condition=` parametresi kullanılır (`check=` eskidi).

- View/servis katmanında: `option.poll_id == poll.id` doğrulanır.
- Oy sayıları **denormalize edilmez**; `Count` ile hesaplanır (prototip için yeterli, race condition riski yok).
- Oy değiştirme / geri çekme **yok** (prototip).

---

## 5. Kritik İş Kuralları

### 5.1 Anket kodu (URL kimliği)

- Türkçe sorulardan slug üretmek sorunlu, sıralı ID ise anket sayısını dışarı sızdırır → **12 karakterlik rastgele kod**.
- Alfabe (karışabilecek `0 o 1 l i` hariç, sadece küçük harf + rakam):
  `23456789abcdefghjkmnpqrstuvwxyz` (31 karakter → 31¹² ≈ 7.9×10¹⁷ olasılık)
- Üretim `secrets.choice` ile yapılır (`random` modülü **kullanılmaz**).
- Çakışma ihtimali ihmal edilebilir ama yine de: kayıt sırasında `IntegrityError` alınırsa yeni kodla en fazla 5 kez tekrar dene.
- URL: `/a/<code>/` — URL pattern'ı kodu `[2-9a-hjkmnp-z]{12}` regex'iyle doğrular.

```python
# polls/services.py
import secrets
CODE_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"
CODE_LENGTH = 12

def generate_poll_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
```

### 5.2 Mükerrer oy engeli

- **Giriş yapmış kullanıcı:** `(poll, user)` benzersiz.
- **Anonim kullanıcı:** Django oturum anahtarından HMAC-SHA256 ile türetilen hash:
  ```python
  import hmac, hashlib
  from django.conf import settings

  def anon_voter_hash(request) -> str:
      if not request.session.session_key:
          request.session.save()          # oturum yoksa oluştur
      key = request.session.session_key.encode()
      return hmac.new(settings.SECRET_KEY.encode(), key, hashlib.sha256).hexdigest()
  ```
- Ham session key **asla** Vote tablosuna yazılmaz; yalnızca hash.
- Oy kaydı `transaction.atomic()` içinde yapılır; `IntegrityError` → "Zaten oy verdin" yanıtı + sonuçları göster.
- Oturum çerezi ömrü: `SESSION_COOKIE_AGE = 60 * 60 * 24 * 365` (1 yıl). Oturumlar Django'nun DB session backend'inde tutulur.

### 5.3 Sonuç gizliliği

- Kullanıcı o ankete oy vermediyse **sunucu, oy dağılımını HTML'e veya JSON'a hiç koymaz.** (CSS ile gizlemek yetmez — kaynak kodda görünür.)
- Oy vermeden önce gösterilebilenler: soru, seçenekler, yazar kullanıcı adı, tarih, **toplam oy sayısı** ("12 kişi oyladı" — merak uyandırır, dağılım sızdırmaz) ve yazarın kararsızlık rozeti.
- Oy verdikten sonra: her seçeneğin oy sayısı ve yüzdesi, karar çubuğu, sonuç etiketi.
- **Anket sahibi** kendi anketinin sonuçlarını oy vermeden de görür (kendi anketine de oy verebilir).
- Yüzdeler tam sayıya yuvarlanır; toplamın 100 olması için en büyük kalan yöntemi (largest remainder) kullanılır.

### 5.4 Yetkilendirme

| İşlem | Anonim | Üye |
|---|---|---|
| Akışı / anket detayını görme | ✅ | ✅ |
| Oy verme | ✅ | ✅ |
| Anket oluşturma | ❌ → giriş sayfasına `?next=` ile yönlendir | ✅ |
| Kendi anketini silme | ❌ | ✅ (sadece kendi) |
| Profil sayfası `/u/<username>/` görme | ✅ | ✅ |

---

## 6. Sayfalar ve URL'ler

URL'ler ASCII Türkçe kelimelerle:

| URL | Metot | Açıklama |
|---|---|---|
| `/` | GET | Akış: tüm anketler, en yeniden eskiye. `?sirala=populer` ile oy sayısına göre. Sayfa başı 20, `?sayfa=2` |
| `/a/<code>/` | GET | Anket detayı |
| `/a/<code>/oy/` | POST | Oy ver. `fetch` ile çağrılırsa JSON, normal form ise redirect (`Accept` header'ına göre) |
| `/a/<code>/sil/` | POST | Sahibi siler (onay JS `confirm` ile) |
| `/yeni/` | GET/POST | Anket oluştur (login required) |
| `/kayit/` | GET/POST | Kayıt: e-posta, kullanıcı adı, parola, parola tekrar |
| `/giris/` | GET/POST | Giriş: e-posta + parola |
| `/cikis/` | POST | Çıkış (GET ile çıkış yok) |
| `/u/<username>/` | GET | Kullanıcının açtığı anketler (e-posta yok, sadece kullanıcı adı + anketler) |
| `/admin/` | — | Django admin (geliştirme/moderasyon için) |

### Oy endpoint JSON yanıtı

```json
{
  "ok": true,
  "already_voted": false,
  "voted_option": 3,
  "total": 27,
  "results": [
    {"position": 0, "text": "Sinema", "count": 15, "percent": 56},
    {"position": 1, "text": "Restoran", "count": 12, "percent": 44}
  ],
  "verdict": {"key": "basa_bas", "label": "Başa baş"}
}
```

Hata durumları: geçersiz seçenek → 400; anket yok → 404; zaten oy verilmiş → 200 + `already_voted: true` + sonuçlar.

### Progresif geliştirme

Oy verme JS olmadan da çalışmalı (düz `<form method="post">`). JS varsa form `fetch` ile gönderilir, sayfa yenilenmeden karar çubuğu animasyonla açılır. CSRF token `fetch` isteğinde `X-CSRFToken` header'ı ile gönderilir.

---

## 7. Tasarım Sistemi

### 7.1 Genel his

- Hedef kitle: genç kullanıcılar. **Açık arka plan**, **canlı renkler**, yüzeylerde bu renklerin **açık tonları (tint)**, temiz ve ferah düzen.
- Mobil öncelikli (çoğu kullanıcı telefondan girecek). Maksimum içerik genişliği ~640px, tek kolon akış.
- Yuvarlak köşeler, kalın ama kısa gölgeler yerine renkli kenarlıklar ve hafif "sticker" hissi.
- Dil: samimi, kısa, "sen" diliyle. Örn. *"Oy ver, sonucu gör"*, *"Sen de kararsız mısın?"*

### 7.2 Renk token'ları (`static/css/app.css` içinde `:root`)

```css
:root {
  /* zemin ve metin */
  --bg:          #FFFAF3;   /* sıcak, kremsi açık zemin */
  --surface:     #FFFFFF;
  --ink:         #1B1530;   /* ana metin: koyu mürekkep moru */
  --ink-soft:    #5E5876;
  --line:        #ECE6F5;

  /* marka */
  --brand:       #6C3BFF;   /* elektrik moru */
  --brand-tint:  #EFE9FF;

  /* seçenek renkleri (position 0..4) + açık tonları */
  --opt-0: #6C3BFF;  --opt-0-tint: #EFE9FF;   /* mor */
  --opt-1: #FF5A5F;  --opt-1-tint: #FFE8E9;   /* mercan */
  --opt-2: #12B886;  --opt-2-tint: #E3F8F1;   /* nane */
  --opt-3: #FFB020;  --opt-3-tint: #FFF4DE;   /* güneş sarısı */
  --opt-4: #1C9CF0;  --opt-4-tint: #E3F3FE;   /* gök mavisi */

  --radius-lg: 20px;
  --radius-md: 14px;
  --radius-pill: 999px;
}
```

- Kontrast: renkli zemin üstündeki metinler WCAG AA'yı geçmeli; sarı (`--opt-3`) üstünde metin `--ink` olmalı, beyaz değil.
- Karanlık mod prototipte **yok** (sonraki faz).

### 7.3 Tipografi

- Google Fonts: başlıklar **Bricolage Grotesque** (700–800), metin **Plus Jakarta Sans** (400–600). İkisi de Türkçe karakterleri destekler.
- `font-display: swap`. Soru başlıkları büyük ve iddialı (mobilde ~22–24px).

### 7.4 Logo / wordmark

- Küçük harf **"kararsızım"** wordmark, `--ink` renginde; sondaki **"ı"** harfi `--brand` renginde ve hafif eğik. Hover'da "ı" sağa-sola küçük bir "kararsız sallanma" animasyonu yapar.
- SVG olarak `static/img/logo.svg`; favicon olarak tek "ı" + nokta yerine küçük bir soru işareti.

### 7.5 İMZA ÖĞESİ 1 — Karar Çubuğu

Ürünün görsel kimliği. Her anket kartında ve detay sayfasında bulunan **tek, yatay, segmentli bir çubuk.**

**Oy vermeden önce (kilitli durum):**
- Çubuk, seçenek sayısı kadar **eşit genişlikte** segmente bölünür.
- Segmentler renkli değil: `--line` zemin üzerinde ince çapraz çizgili (diagonal stripes) desen, ortada küçük bir 🔒 ya da `?` ikonu.
- Altında mikro metin: *"Oy ver, kararı gör"*.
- Bu durum **hiçbir gerçek oran bilgisi taşımaz** (eşit genişlik sabit).

**Oy verdikten sonra (açık durum):**
- Her segment kendi seçenek rengini (`--opt-N`) alır ve genişliği **yüzdesine** göre animasyonla (≈600ms, `cubic-bezier(.2,.8,.2,1)`) açılır.
- Kullanıcının seçtiği segmentin üstünde küçük ✓ rozeti.
- Lider segment hafif "nabız" efekti alır (bir kez).
- %0 olan seçenekler çubukta görünmez ama listede `%0` yazar.
- `prefers-reduced-motion` varsa animasyon yok, doğrudan son durum.

**Teknik:**
- `templates/partials/decision_bar.html` partial'ı; segment genişlikleri `style="--w: 56%"` şeklinde CSS değişkeni ile verilir, CSS `flex-basis: var(--w)` + `transition` ile animasyon.
- JS ile oy verildiğinde aynı partial'ın yapısı JSON'dan güncellenir (DOM'u yeniden üretmek yerine `--w` değerlerini değiştirmek yeterli).
- Erişilebilirlik: çubuk `role="img"` ve `aria-label="Sinema %56, Restoran %44"`; kilitliyken `aria-label="Sonuçlar oy verince görünür"`.

Seçenek satırları da aynı dili konuşur: oy sonrası her seçenek satırının arka planı soldan sağa kendi `--opt-N-tint` rengiyle yüzdesi kadar dolar.

### 7.6 İMZA ÖĞESİ 2 — Kararsızlık Rozeti

İki tür rozet var:

**a) Yazarın kararsızlık seviyesi** (anket açarken seçilir, her zaman görünür, sonuç sızdırmaz):

| Değer | Etiket | Emoji | Stil |
|---|---|---|---|
| 1 | Biraz kararsız | 🤔 | `--opt-3-tint` zemin |
| 2 | Çok kararsız | 😵‍💫 | `--opt-1-tint` zemin |
| 3 | Tam bir kararsız | 🌀 | `--brand` zemin, beyaz metin, hafif dönen 🌀 |

Oluşturma formunda üç büyük, tıklanabilir "sticker" kart olarak seçilir (radio input'lar görsel olarak gizlenir ama erişilebilir kalır). Varsayılan: 2.

**b) Sonuç etiketi** (sadece sonuçları görebilenlere gösterilir):

| Koşul (toplam ≥ 3 oy) | Anahtar | Etiket |
|---|---|---|
| İlk iki seçenek arası fark ≤ 5 puan | `kil_payi` | Kıl payı ⚖️ |
| Fark ≤ 15 puan | `basa_bas` | Başa baş 🔥 |
| Lider ≥ %70 | `net_karar` | Net karar ✅ |
| Diğer | `one_cikan` | Öne çıkan var 👀 |
| Toplam < 3 oy | `az_oy` | Henüz erken ⏳ |

Hesaplama `polls/services.py` içinde `compute_verdict(results)` fonksiyonunda; birim testi yazılmalı.

### 7.7 Bileşenler

- **Anket kartı (akışta):** yazar `@kullaniciadi` + göreli zaman ("3 dk önce", `django.contrib.humanize` `naturaltime`), kararsızlık rozeti, soru, seçenek "chip"leri (kendi tint renkleriyle), mini karar çubuğu, "X kişi oyladı", tüm kart detaya link.
- **Detay sayfası:** büyük soru, açıklama, seçenekler büyük dokunma alanlı butonlar (min 48px yükseklik), tam boy karar çubuğu, oy sonrası sonuç etiketi, "Paylaş" butonu (`navigator.share` varsa onu, yoksa linki panoya kopyala + küçük toast).
- **Oluşturma formu:** soru (karakter sayacı), opsiyonel açıklama, 2 seçenekle başlar; "+ Seçenek ekle" (5'te gizlenir), her seçeneğin yanında "×" (2'de gizlenir), seçenek kutularının solunda kendi renk noktası. Kararsızlık seviyesi sticker'ları. JS olmadan da 5 input göstererek çalışmalı (boş olanlar yok sayılır).
- **Üst bar:** logo, sağda giriş yoksa "Giriş" + belirgin "Anket aç" butonu (tıklanınca giriş sayfasına), giriş varsa "@kullaniciadi" + "Anket aç".
- **Boş durumlar:** "Henüz kimse kararsız değil… İlk sen ol." gibi esprili metinler.
- **Toast/mesajlar:** Django messages framework, sayfanın altından kayan küçük bildirim.

---

## 8. Django Ayarları (settings.py) — Önemli Noktalar

```python
import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")             # lokal; Vercel'de dosya yok, sorun değil

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]   # yoksa açıkça patlasın
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"

ALLOWED_HOSTS = ["localhost", "127.0.0.1", ".vercel.app"]
# özel domain eklenince buraya da eklenir
CSRF_TRUSTED_ORIGINS = ["https://*.vercel.app"]

AUTH_USER_MODEL = "accounts.User"
LANGUAGE_CODE = "tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True                              # DB'de UTC tutulur

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"     # Vercel collectstatic'i bunu görünce otomatik çalıştırır
STATICFILES_DIRS = [BASE_DIR / "static"]

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 365
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

LOGIN_URL = "/giris/"
LOGIN_REDIRECT_URL = "/"

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # SECURE_SSL_REDIRECT gerekmez, Vercel zaten HTTPS'e yönlendirir
```

DATABASES ayarı için **bkz. Bölüm 9.4** — burası en hassas kısım.

---

## 9. ⚠️ Vercel (Serverless) + Supabase Bağlantısı — DİKKATLİ OKU

Django'yu serverless ortamda çalıştırmak, klasik bir sunucuda çalıştırmaktan farklıdır. Yanlış ayar → "too many connections", rastgele "prepared statement does not exist" hataları, soğuk başlatmada zaman aşımı.

### 9.1 Vercel tarafı: nasıl çalışıyor?

- Vercel artık Django'yu **sıfır konfigürasyonla** destekliyor: repoda `manage.py`'yi bulur, `DJANGO_SETTINGS_MODULE`'ı ve `WSGI_APPLICATION`'ı okuyarak giriş noktasını belirler. **`api/` klasörüne, `vercel.json` içinde rewrite/builds tanımına gerek yok.** (Eski blog yazılarındaki `@vercel/python` + `builds` + `build_files.sh` yöntemini **kullanma**.)
- Tüm Django uygulaması **tek bir Vercel Function** olur ve varsayılan olarak **Fluid compute** üzerinde çalışır: bir fonksiyon örneği birden çok isteği işleyebilir ve istekler arasında "sıcak" kalabilir, ama her an yeni örnek açılabilir ya da kapanabilir.
- `STATIC_ROOT` tanımlıysa Vercel **build sırasında `collectstatic`'i kendisi çalıştırır** ve dosyaları CDN'den `STATIC_URL` altında sunar. Build script'ine `collectstatic` yazmaya gerek yok. WhiteNoise sadece lokalde aktif olur, sorun çıkarmaz.
- `collectstatic` build sırasında settings'i import eder → **`DJANGO_SECRET_KEY` build ortamında da tanımlı olmalı** (Vercel env var'ını Production + Preview için ekle). `collectstatic` DB'ye bağlanmaz; DB URL'si yoksa settings çökmemeli.
- Lokal test için `vercel dev` kullanılabilir (Vercel CLI ≥ 50.38).

**Çıkarımlar (Fluid compute + serverless):**
1. **Modül seviyesinde değiştirilebilir global state tutma.** İstekler arası paylaşılabilir ya da kaybolabilir.
2. **Dosya sistemine yazma** (SQLite, upload, log dosyası) prod'da kalıcı değildir. Prod'da SQLite asla kullanılmaz.
3. **In-memory cache** (LocMemCache) örnekler arası paylaşılmaz → rate limit vb. için güvenilmez.
4. **Arka plan işi yok**; her şey istek-yanıt içinde biter.
5. Bağımlılıkları az tut → soğuk başlatma hızlı olur.

### 9.2 `vercel.json`

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "regions": ["fra1"],
  "functions": {
    "config/wsgi.py": {
      "maxDuration": 15
    }
  }
}
```

- **`regions`: Supabase projesiyle aynı/yakın bölge seçilmeli.** Supabase'i **Frankfurt (eu-central-1)** bölgesinde aç, Vercel fonksiyonunu `fra1`'de çalıştır. Farklı kıtalarda olurlarsa her DB sorgusu 100ms+ gecikme ekler ve sayfa başına birden çok sorgu olduğu için sayfalar ağırlaşır. (İstanbul'daki kullanıcılar için Frankfurt da en yakın uygun seçenek.)
- `functions` anahtarı, çözümlenen entrypoint dosyasıdır (`config/wsgi.py`).

### 9.3 Supabase tarafı: hangi bağlantı dizesi?

Supabase panelinde **"Connect"** butonu üç tür bağlantı dizesi verir. Doğru seçim hayati:

| Tür | Host / Port | Ne zaman? |
|---|---|---|
| **Direct connection** | `db.<ref>.supabase.co:5432` | ❌ Vercel'de **kullanma.** Varsayılan olarak yalnızca IPv6; Vercel fonksiyonları IPv4 ile bağlanır → bağlantı kurulamaz. Ayrıca her fonksiyon örneği ayrı bağlantı açarak limiti hızla doldurur. |
| **Session pooler** (Supavisor, session mode) | `aws-?-<region>.pooler.supabase.com:5432` | ✅ **Lokalden migration çalıştırmak** için. IPv4 destekler, oturum boyunca aynı bağlantıyı tutar. |
| **Transaction pooler** (Supavisor, transaction mode) | `aws-?-<region>.pooler.supabase.com:6543` | ✅ **Vercel prod/preview için.** Serverless için tasarlanmıştır; bağlantı her transaction sonunda havuza döner. |

Kullanıcı adı formatı pooler'da `postgres.<project-ref>` şeklindedir (sadece `postgres` değil). Host'u **elle yazma, panelden kopyala** (bölgeye göre `aws-0-…` / `aws-1-…` değişebilir).

**Parola tuzağı:** Parolada `@ : / ? # %` gibi karakterler varsa URL içinde **percent-encode** edilmeli, yoksa `dj-database-url` yanlış ayrıştırır. En kolayı: Supabase'de yalnızca harf+rakamdan oluşan uzun bir DB parolası belirlemek.

### 9.4 Django `DATABASES` ayarı (transaction pooler uyumlu)

```python
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=0,            # her istekte bağlantıyı kapat → pooler yönetsin
            conn_health_checks=False,
            ssl_require=True,          # sslmode=require
        )
    }
    DATABASES["default"]["OPTIONS"] = {
        **DATABASES["default"].get("OPTIONS", {}),
        "prepare_threshold": None,     # psycopg3 prepared statement'larını KAPAT
    }
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
else:
    # Sadece lokal geliştirme için
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
```

Neden her biri?

- **`conn_max_age=0`**: Django kalıcı bağlantı tutmaz. Serverless'ta kalıcı bağlantılar donmuş/öldürülmüş fonksiyon örneklerinde sahipsiz kalır ve Supabase'in bağlantı limitini tüketir. Havuzlamayı Supavisor yapar; Django'nun yapmasına gerek yok.
- **`prepare_threshold: None`**: psycopg 3, aynı sorgu birkaç kez çalışınca otomatik olarak sunucu tarafı *prepared statement* oluşturur. Transaction mode'da bir sonraki sorgun **farklı bir arka uç bağlantısına** gidebileceği için bu statement orada yoktur → aralıklı `prepared statement "_pg3_x" does not exist` hataları. Kapatılmalı.
- **`DISABLE_SERVER_SIDE_CURSORS = True`**: `.iterator()` gibi işlemler sunucu tarafı imleç kullanır; imleçler transaction mode'da transaction'lar arası yaşayamaz.
- **`ssl_require=True`**: Supabase bağlantıları SSL üzerinden olmalı.
- **Oturum seviyesi `SET` komutları kullanma** (ör. `SET search_path`, `SET TIME ZONE`). Transaction mode'da kalıcı olmaz. Supabase DB saat dilimini **UTC** bırak; Django `USE_TZ=True` ile zaten UTC çalışır.
- `transaction.atomic()` blokları sorunsuzdur — transaction boyunca aynı arka uç bağlantısı tutulur.

### 9.5 Ortam değişkenleri

`.env.example` (repoda, değerler boş):

```
DJANGO_SECRET_KEY=
DJANGO_DEBUG=1
# Lokal: boş bırakırsan SQLite kullanılır.
# Migration için: Supabase SESSION pooler (port 5432)
DATABASE_URL=
```

| Değişken | Lokal `.env` | Vercel (Production + Preview) |
|---|---|---|
| `DJANGO_SECRET_KEY` | rastgele | **farklı**, güçlü rastgele değer |
| `DJANGO_DEBUG` | `1` | tanımlama (veya `0`) |
| `DATABASE_URL` | boş (SQLite) **veya** session pooler `:5432` | **transaction pooler `:6543`** |

- `.env` ve `.env.local` **asla commit edilmez**.
- SECRET_KEY değişirse: tüm oturumlar düşer **ve** anonim oy hash'leri değişir (bkz. Bilinen Sınırlar).

### 9.6 Migration stratejisi

- **Migration'lar Vercel build'inde çalıştırılmaz.** (Her preview deploy'da prod DB'ye migration atmak tehlikeli; build ortamından DB erişimi de güvenilir değil.)
- Migration'lar **lokalden**, `DATABASE_URL` geçici olarak **session pooler (5432)** dizesine ayarlanarak çalıştırılır:
  ```bash
  DATABASE_URL="postgresql://postgres.<ref>:<parola>@aws-?-eu-central-1.pooler.supabase.com:5432/postgres" \
    python manage.py migrate
  ```
- Sıra: migration'ı Supabase'e uygula → sonra kodu deploy et. Model değişiklikleri geriye uyumlu tutulmalı.
- Superuser da aynı yoldan oluşturulur: `python manage.py createsuperuser`.

### 9.7 Supabase güvenlik notu: Data API ve RLS

Supabase, `public` şemasındaki tabloları otomatik olarak **REST Data API** (PostgREST) üzerinden `anon` anahtarıyla erişilebilir yapar. Biz bu API'yi kullanmıyoruz ama tablolar oraya da açık kalır — Django'nun oluşturduğu `accounts_user` (parola hash'leri!) dahil.

Yapılacaklar (Faz 1'de):
1. Supabase Dashboard → Project Settings → **Data API**'yi kapat **veya** `public` şemasını exposed schemas listesinden çıkar.
2. Ek güvence olarak tüm tablolarda **RLS'i aç, policy ekleme**: Django `postgres` rolüyle bağlandığı için RLS'den etkilenmez; `anon`/`authenticated` rolleri hiçbir şey göremez. Bunu bir Django migration'ı (`RunSQL`) ile yap ki yeni tablolar için de unutulmasın:
   ```sql
   ALTER TABLE public.accounts_user ENABLE ROW LEVEL SECURITY;
   -- ... tüm tablolar için
   ```
3. Supabase Dashboard'daki **Security Advisor** uyarılarını kontrol et.

### 9.8 Diğer Supabase notları

- Ücretsiz plandaki projeler bir süre aktivite olmazsa **duraklatılır**; uygulama "bağlanamıyor" hatası verirse önce panelden projenin aktif olduğunu kontrol et.
- Bağlantı limiti plana göre değişir; transaction pooler sayesinde prototip trafiği için sorun olmaz.

### 9.9 Deploy kontrol listesi

- [ ] Supabase projesi `eu-central-1`, Vercel `regions: ["fra1"]`
- [ ] Vercel env: `DJANGO_SECRET_KEY`, `DATABASE_URL` (6543, transaction pooler) — Production **ve** Preview
- [ ] `DEBUG` prod'da kapalı
- [ ] `ALLOWED_HOSTS` ve `CSRF_TRUSTED_ORIGINS` doğru
- [ ] Migration'lar lokalden session pooler ile uygulandı
- [ ] Data API kapalı / RLS açık
- [ ] `python manage.py check --deploy` uyarıları gözden geçirildi
- [ ] Statik dosyalar CDN'den geliyor (CSS yükleniyor mu?)
- [ ] Prod'da: kayıt → giriş → anket aç → farklı tarayıcıdan anonim oy → sonuçlar görünüyor

---

## 10. Güvenlik ve Gizlilik

- E-posta hiçbir şablonda, JSON'da, profil sayfasında gösterilmez. Şablonlarda yazar için yalnızca `poll.author.username` kullanılır. (Test ile doğrula: HTML çıktısında e-posta geçmemeli.)
- Tüm POST formlarında CSRF aktif; `fetch` istekleri `X-CSRFToken` gönderir.
- Kullanıcı girdileri Django template auto-escape ile render edilir; `|safe` **kullanılmaz**.
- Çıkış sadece POST.
- Anket silme sadece sahibi, sadece POST.
- `Poll.id` hiçbir yerde dışarı verilmez; admin hariç.

---

## 11. Bilinen Sınırlar (Prototip)

Bunlar bilinçli kabul edilmiş sınırlardır, hata değildir:

1. **Anonim mükerrer oy:** Anonim oylar oturum anahtarından üretilen hash ile engellenir. **Çerezlerini temizleyen, gizli sekme açan veya farklı tarayıcı/cihaz kullanan biri tekrar oy verebilir.** Prototip için kabul edilebilir. İleride: IP + user-agent hash'i ile yumuşak sınır, rate limit, ya da Cloudflare Turnstile gibi bot koruması.
2. **Anonim → üye geçişi:** Django girişte oturum anahtarını yeniler. Bir kişi önce anonim oy verip sonra giriş yaparsa aynı ankete ikinci kez (üye olarak) oy verebilir.
3. **SECRET_KEY değişimi** tüm anonim oy hash'lerini geçersiz kılar (eski anonim oy verenler tekrar oy verebilir hale gelir) ve oturumları sonlandırır.
4. **Rate limit yok** (Faz 5'te DB tabanlı basit sınır eklenecek; serverless'ta in-memory sınır işe yaramaz).
5. **Oy değiştirme/geri çekme yok**, anket düzenleme yok (sadece silme).
6. **Moderasyon yok**; uygunsuz içerik yalnızca Django admin'den silinebilir.
7. **Arama, etiket/kategori, bildirim, e-posta doğrulama, parola sıfırlama yok.**
8. Oy sayıları her istekte `Count` ile hesaplanır; çok yüksek trafikte denormalize sayaç gerekebilir.
9. Seçenek metni tekrar kontrolü Türkçe `I/ı/İ/i` dönüşümlerinde kusursuz değildir.

---

## 12. Test Stratejisi

Django'nun yerleşik test runner'ı (`python manage.py test`), lokalde SQLite ile. Asgari testler:

- `generate_poll_code`: uzunluk 12, alfabe dışı karakter yok.
- Anket oluşturma: 1 seçenek → hata, 6 seçenek → hata, tekrar eden seçenek → hata, anonim kullanıcı → girişe yönlendirme.
- Oy: anonim aynı oturumla ikinci oy → `already_voted`; üye ikinci oy → `already_voted`; başka ankete ait `option` → 400.
- **Sonuç gizliliği:** oy vermemiş kullanıcının aldığı detay sayfası HTML'inde yüzde/oy sayısı dağılımı **yok**; oy verdikten sonra var; anket sahibi her zaman görüyor.
- **E-posta sızıntısı:** akış, detay ve profil sayfalarının HTML'inde yazarın e-postası geçmiyor.
- `compute_verdict` sınır değerleri ve yüzde yuvarlamanın toplamı 100 yapması.
- Kullanıcı adı: büyük/küçük harf farkıyla aynı ad ikinci kez alınamıyor; rezerve adlar reddediliyor.

---

## 13. Claude Code İçin Çalışma Kuralları

1. **Sadece istenen fazı uygula.** Faz sonunda "Kabul kriterleri"ni tek tek kontrol et ve özetle.
2. Bu dosyada belirtilmeyen yeni bağımlılık ekleme; gerekiyorsa önce sor.
3. Frontend için framework, npm, build aracı **ekleme**. Saf HTML/CSS/JS.
4. Bölüm 9'daki DB ayarlarını değiştirme (`conn_max_age=0`, `prepare_threshold: None`, `DISABLE_SERVER_SIDE_CURSORS`).
5. Migration'ları build sürecine ekleme.
6. Gizli bilgileri (anahtar, parola, bağlantı dizesi) koda veya commit'e yazma.
7. Kod ve değişken adları İngilizce; kullanıcıya görünen tüm metinler Türkçe.
8. İş mantığını (oy verme, sonuç hesaplama, kod üretme, verdict) `polls/services.py` içinde tut; view'lar ince kalsın.
9. Her fazın sonunda testleri çalıştır ve geçtiğini doğrula.

---

## 14. Fazlar

### Faz 0 — İskelet ve lokal çalışma

**Yapılacaklar**
- Django projesi (`config`), `accounts` ve `polls` uygulamaları, Bölüm 3'teki klasör yapısı.
- `requirements.txt`, `.python-version` (3.12), `.gitignore`, `.env.example`.
- **Özel kullanıcı modeli** (`accounts.User`, Bölüm 4.1) — **ilk `migrate`'ten önce.**
- `settings.py` Bölüm 8 ve 9.4'e göre (DATABASE_URL yoksa SQLite).
- `base.html`: Google Fonts, `app.css`, `app.js`, üst bar, wordmark; ana sayfada "yakında" yazan basit bir içerik.
- `app.css` içine Bölüm 7.2 token'ları.

**Kabul kriterleri**
- `python manage.py migrate` ve `runserver` hatasız; `/` sayfası açılıyor, font ve renkler yüklü.
- `/admin/` çalışıyor, superuser e-posta ile giriş yapabiliyor.

---

### Faz 1 — Supabase + Vercel ile erken deploy

> Serverless/DB sorunlarını özellik yazmadan **önce** yakalamak için iskeleti hemen yayına alıyoruz.

**Yapılacaklar**
- Supabase projesi (eu-central-1). Session ve transaction pooler dizelerini al.
- `vercel.json` (Bölüm 9.2).
- Lokalden session pooler ile `migrate` (Bölüm 9.6).
- RLS'i tüm tablolarda açan `RunSQL` migration'ı + Data API'yi kapatma (Bölüm 9.7).
- Vercel projesi, env değişkenleri (Bölüm 9.5), Git bağlantısı ile deploy.
- Basit bir sağlık kontrolü: `/saglik/` → DB'ye `SELECT 1` atıp `{"db": "ok"}` döner (sonra kaldırılabilir veya sadece admin'e açılır).

**Kabul kriterleri**
- Vercel URL'sinde ana sayfa CSS ile birlikte açılıyor.
- `/saglik/` prod'da `ok` dönüyor; ardışık 20 istekte "prepared statement" veya bağlantı hatası yok.
- `/admin/` prod'da çalışıyor, superuser giriş yapabiliyor (CSRF hatası yok).
- Supabase Security Advisor'da "RLS disabled" uyarısı yok.

---

### Faz 2 — Üyelik

**Yapılacaklar**
- `/kayit/`: e-posta, kullanıcı adı, parola, parola tekrar. Kullanıcı adı kuralları (Bölüm 4.1), anlık kural ipucu (JS ile, sunucu doğrulaması asıl).
- `/giris/` (e-posta + parola), `/cikis/` (POST).
- Kayıt sonrası otomatik giriş ve `next` parametresine yönlendirme.
- Üst bar giriş durumuna göre değişir.
- Türkçe hata mesajları.

**Kabul kriterleri**
- Aynı e-posta veya (harf büyüklüğü farkıyla) aynı kullanıcı adıyla ikinci kayıt reddediliyor.
- Rezerve adlar ve geçersiz karakterler reddediliyor.
- Testler geçiyor.

---

### Faz 3 — Anketler ve oylama (çekirdek)

**Yapılacaklar**
- `Poll`, `Option`, `Vote` modelleri ve kısıtları (Bölüm 4.2–4.4). RLS migration'ını yeni tablolar için güncelle.
- `services.py`: `generate_poll_code`, `create_poll`, `cast_vote`, `get_results` (yüzde + largest remainder), `compute_verdict`, `anon_voter_hash`, `can_see_results(request, poll)`.
- `/yeni/` oluşturma formu (2–5 seçenek, dinamik ekleme/silme, kararsızlık seviyesi).
- `/` akış (yeni / popüler, sayfalama), `/a/<code>/` detay, `/a/<code>/oy/` (form + JSON), `/a/<code>/sil/`, `/u/<username>/`.
- Sonuç gizliliği kuralları (Bölüm 5.3) — **sunucu tarafında.**
- Bu fazda arayüz basit/işlevsel olabilir; karar çubuğunun kilitli/açık durumları temel haliyle çalışmalı.
- Sorgu verimliliği: akışta `select_related("author")`, `prefetch_related("options")`, toplam oy için `annotate(Count("votes"))`; N+1 sorgu olmamalı.

**Kabul kriterleri**
- Bölüm 12'deki anket, oy, gizlilik ve e-posta sızıntısı testleri geçiyor.
- Prod'da: iki farklı tarayıcıdan anonim oy → toplam 2; aynı tarayıcıdan ikinci oy reddediliyor.
- Kaynak kodu görüntüle: oy vermeden önce yüzde/oy dağılımı HTML'de yok.

---

### Faz 4 — Tasarım ve imza öğeleri

**Yapılacaklar**
- Bölüm 7'nin tamamı: renk sistemi, tipografi, wordmark + "ı" animasyonu, anket kartı, detay sayfası.
- **Karar çubuğu** kilitli/açık durumlar, animasyon, erişilebilirlik (Bölüm 7.5).
- **Kararsızlık rozetleri** (yazar seviyesi + sonuç etiketi) (Bölüm 7.6).
- Oy verince sayfa yenilenmeden sonuç açılması (fetch + JSON).
- Oluşturma formunda sticker tarzı seviye seçici, renkli seçenek noktaları.
- Paylaş butonu, toast bildirimleri, boş durumlar, 404 ve 500 sayfaları (markaya uygun, esprili).
- Mobil (360px) ve masaüstü kontrolü; `prefers-reduced-motion`.

**Kabul kriterleri**
- 360px genişlikte yatay kaydırma yok, dokunma alanları ≥ 48px.
- JS kapalıyken oy verme ve anket oluşturma hâlâ çalışıyor.
- Lighthouse erişilebilirlik skoru ≥ 90.

---

### Faz 5 — Sağlamlaştırma (opsiyonel, prototip sonrası)

Öneriler (her biri ayrı küçük iş olarak ele alınabilir):
- DB tabanlı basit rate limit (Django `DatabaseCache` ile): IP başına dakikada N oy, saatte N anket.
- Anket sahibinin anketi "kapatması" (yeni oy almaz).
- Karanlık mod.
- Parola sıfırlama (e-posta servisi gerekir).
- Bot koruması (Cloudflare Turnstile) — anonim mükerrer oyu azaltmak için.
- Akışta "henüz oy vermediklerim" filtresi.
- Basit raporlama/şikâyet butonu.

---

## 15. Claude Code'a Verilecek Faz Promptları

Her yeni fazda Claude Code'a şunu yaz (faz numarasını değiştirerek):

```
@KARARSIZIM.md dosyasını baştan sona oku. Şimdi yalnızca "Faz 0 — İskelet ve lokal çalışma"
bölümünü uygula. Bölüm 13'teki çalışma kurallarına uy. Başlamadan önce kısa bir plan çıkar,
sonra uygula. Bitince kabul kriterlerini tek tek kontrol et, testleri çalıştır ve neyi
doğruladığını, neyi manuel olarak benim kontrol etmem gerektiğini özetle.
```

Faz 1 için ek not: Supabase ve Vercel panelinde yapılması gereken adımları (proje açma, bağlantı dizelerini kopyalama, env ekleme, Data API kapatma) **bana adım adım liste olarak ver**, kodla yapılabilenleri sen yap.
