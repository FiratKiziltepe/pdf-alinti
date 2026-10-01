# Alıntı — PDF not defteri

Makale yazarken PDF’lerde biriktirdiğiniz renkli vurguları, altı çizili cümleleri ve açıklamaları alıntı metniyle birlikte dışa aktaran Türkçe Streamlit uygulaması.

## Kurulum ve çalıştırma

Python 3.10 veya üzeri gerekir. ZIP arşivini açıp `pdf-alinti` klasöründe bir terminal açın.

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
source .venv/bin/activate
```

Ardından:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Tarayıcıda `http://localhost:8501` adresini açın. Sanal ortamı etkinleştiremiyorsanız Windows’ta `.venv\Scripts\python.exe`, macOS/Linux’ta `.venv/bin/python` kullanarak son iki komutu çalıştırabilirsiniz.

## Streamlit Community Cloud’da yayınlama

1. Proje dosyalarını GitHub deponuzun `main` dalına gönderin. `app.py`, `requirements.txt`, `pdf_notes/`, `assets/ornek-notlar.pdf` ve `.streamlit/config.toml` depoda bulunmalıdır.
2. [Streamlit Community Cloud](https://share.streamlit.io/) hesabınızda **Create app** seçeneğini açıp GitHub deposunu bağlayın.
3. **Repository** alanında deponuzu, **Branch** alanında `main`, **Main file path** alanında `app.py` seçin.
4. **Advanced settings** altında Python sürümünü **3.12** seçip **Deploy** düğmesine basın. Uygulama API anahtarı, veritabanı veya Secrets ayarı gerektirmez.

Yayın tamamlandığında Streamlit uygulamanın `https://…streamlit.app` adresini gösterir. `main` dalına gönderilen sonraki değişiklikler otomatik olarak yayına alınır. GitHub Actions, push ve pull request işlemlerinde Python 3.12 ile mevcut testleri çalıştırır. Yüklenen kişisel PDF’leri, dışa aktarılan belgeleri ve yerel `.env` dosyalarını depoya eklemeyin; örnek PDF sentetik içeriktir.

## Kullanım

1. Vurgu ve notları PDF okuyucunuzda **dosyaya kaydedin**. Okuyucunun kendi kütüphanesinde kalan açıklamaları varsa “açıklamalarla birlikte PDF’yi dışa aktar” seçeneğini kullanın.
2. Soldan PDF’lerinizi yükleyip **Alıntıları çıkar** düğmesine basın. Tek seferde en fazla 10 dosya, dosya başına 50 MB yüklenebilir. Parolalı belgeler için PDF parolasını girin. Her yeni işleme mevcut çalışma alanını değiştirir; farklı parolalı grupları ayrı işleyin.
3. Belge, renk ve işaret türüne göre filtreleyin; alıntı, not ve bağlam içinde arama yapın. Boş bırakılan filtre tüm kayıtları kapsar.
4. Kartlarda seçili alıntı ve eklenen yorumu birlikte okuyun. **İlgili paragraf** bölümünü açarak bağlamı, sağdaki önizlemeden kaynak sayfayı kontrol edin.
5. Word, Excel, Markdown, CSV veya JSON biçimini seçip **kayıtları indir** düğmesine basın. Dışa aktarma, liste sayfalamasından bağımsız olarak geçerli filtrelere uyan bütün kayıtları kapsar. Bağlamı arayüzde gizlemek indirme dosyasından kaldırmaz.

Dosya yüklemeden **Örnek PDF ile dene** düğmesine basabilirsiniz. İki sayfalık [örnek PDF](assets/ornek-notlar.pdf), gerçek PDF açıklamaları içerir; metni gösterim amacıyla üretilmiştir.

## Çıkarılan bilgiler

Her kayıtta kaynak PDF, belge başlığı, PDF sayfa numarası, işaret türü, renk adı ve özgün HEX rengi, seçili alıntı, paragraf bağlamı, açıklama, not yazarı ve PDF’de varsa tarihler bulunur. JSON ayrıca kayıt kimliği ve koordinatları korur. Aynı vurgudaki yorumlar ve bağlanabilen yanıtlar aynı kayıtta birleştirilir.

- **Vurgulama / alt çizgi / dalgalı çizgi / üstü çizili metin:** PDF’nin QuadPoints seçim geometrisinden karakterler çıkarılır. Böylece çok satırlı ve çok sütunlu metinde işaretin dışındaki cümlelerin karışması azaltılır.
- **Yapışkan not / serbest metin:** Açıklama korunur; en yakın metin bloğu ilgili paragraf olarak konumdan tahmin edilir. Bunlarda seçili bir metin aralığı olmadığı için alıntı alanı boş kalır. Paragraf, alıntıymış gibi sunulmaz.
- **Diğer şekiller:** Açıklama içeren çizgi, dikdörtgen, elips gibi notların yorumu ve yakın bağlamı çıkarılır. Ek dosya ve medya içerikleri aktarılmaz.

Renk adı yakın bir renk ailesidir; dosyadaki gerçek renk HEX koduyla korunur. Word alıntıları okunabilir bir renk tonuyla gösterir. Excel’de renk hücreleri özgün renkle boyanır. CSV Türkçe karakterlerin Excel’de açılabilmesi için UTF-8 BOM içerir. Excel’in hücre uzunluğu sınırını aşan metinler numaralı devam satırlarıyla saklanır; JSON metnin tamamını bölmeden korur.

## Bilinmesi gereken sınırlar

- Taranmış PDF’de OCR metin katmanı yoksa alıntı metni okunamaz; açıklamalar yine çıkarılabilir. Bu sürüm OCR yapmaz.
- PDF’ye birleştirilmiş (flattened) renkler/çizgiler ve görüntü olarak kaydedilmiş notlar standart PDF açıklaması değildir, ayrı kayıt olarak çıkarılamaz.
- Bağlam, PDF’nin metin bloklarına göre eşleştirilir. Bir blok her zaman tam bir paragraf değildir; kenar notlarında eşleşme tahminidir. Akademik alıntıyı kaynak sayfayla kontrol edin.
- Sayfa numarası PDF’nin fiziksel sayfasıdır; basılı makalenin üzerinde yazan numaradan farklı olabilir. PDF başlığı bibliyografik künye değildir; uygulama DOI, APA veya başka bir kaynakça uydurmaz.
- Satır sonları ve okunma sırası PDF metin katmanına bağlıdır. Bazı hatalı, alışılmadık veya özel okuyucu açıklamalarında seçili metin eksik olabilir; uygulama bunu okuma bilgisi olarak bildirir.

## Dosyaların işlenmesi

Yüklenen PDF’ler ve parolaları yalnızca kullanıcının Streamlit oturumunda, sunucu belleğinde tutulur. Uygulama dosyaları diske kaydetmez ve dış servise göndermez. PDF metinleri ortak `st.cache_data` önbelleğinde tutulmaz. **Oturumu temizle** düğmesi çalışma kayıtlarını, yüklemeleri, parolaları ve oluşturulan dışa aktarma/önizleme önbelleğini temizler. Streamlit bağlantısı koptuktan sonra oturum verisini kendi oturum yaşam döngüsüne göre kaldırır. Kendi bilgisayarınızda çalıştırıldığında sunucu da kendi bilgisayarınızdadır; uzak sunucuda çalıştırıldığında dosyalar o sunucuya yüklenir. Streamlit kullanım istatistikleri kapalıdır.

## Geliştirme ve test

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Çekirdek `pdf_notes/extract.py`, dışa aktarma `pdf_notes/exporters.py`, arayüz `app.py` dosyasındadır. Testler gerçek, programatik olarak oluşturulmuş PDF’lerle çalışır; parolalı dosyalar, seçim geometrisi, not/yanıt eşleştirmesi, Türkçe metin, dışa aktarılan belgelerin bütünlüğü ve Streamlit akışı kontrol edilir.

Örnek PDF’yi yeniden üretmek için:

```bash
python scripts/create_demo.py
```

Üretim betiği Türkçe destekli bir TTF arar; gerekirse `--font /yol/font.ttf` kullanın. Hazır örnek PDF yazı tipini içerir, çalıştırma sırasında sistem yazı tipi gerektirmez.
