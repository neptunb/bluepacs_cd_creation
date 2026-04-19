===============================================
  DICOM Medical Images Viewer
===============================================

This CD contains your medical images along with
a portable viewer that requires no installation.

HOW TO VIEW YOUR IMAGES:
-----------------------------------------------

  Windows:
    Double-click "windows_view.exe"

  macOS:
    Double-click "macos_view"
    (You may need to right-click > Open the first time)

  Linux:
    Open a terminal in this directory and run:
    ./linux_view

A web browser window will open automatically
showing your medical images.

CLOSING:
-----------------------------------------------
Simply close the browser tab, then close the
terminal/command window that appeared.

CONTENTS:
-----------------------------------------------
  DICOM/           - Your DICOM image files
  viewer/          - Image viewer application
  windows_view.exe - Windows launcher
  macos_view       - macOS launcher
  linux_view       - Linux launcher

===============================================
cd_template klasörünün tamamı GitHub’a gitmiyor; özellikle standalone görüntüleyici ikilileri bilinçli olarak repodan hariç tutulmuş. Sunucuya git clone/pull ile gelen şey, bu yüzden şablon iskeleti + dokümantasyon; macos_view gibi dosyalar gelmiyor.

Teknik olarak ne oluyor?
.gitignore içinde şu kural var:


.gitignore
Lines 36-42
# Standalone viewer binaries (large, built externally; see cd_template/standalone/README.md)
cd_template/standalone/*
!cd_template/standalone/.gitkeep
!cd_template/standalone/README.md
!cd_template/standalone/study/
cd_template/standalone/study/*
!cd_template/standalone/study/README.txt
Yani cd_template/standalone/ altındaki neredeyse her şey ignore; istisna olarak yalnızca .gitkeep, README.md ve study/README.txt gibi küçük/placeholder dosyalar takip ediliyor.

cd_template/standalone/README.md de bunu açık yazıyor: ikililer toplamda yaklaşık ~900 MB, git’e commit edilmiyor; OHIF Viewers reposunda build edilip sync_standalone.sh ile bu klasöre kopyalanması gerekiyor.

Özet
GitHub ile giden	GitHub ile gitmeyen
cd_template yapısı, README’ler, K-PACS şablonu vb. (ignore dışındaki her şey)
macos_view, linux_view, windows_view.exe (standalone OHIF paketleri)
Bu yüzden sunucu sadece GitHub’dan deploy aldıysa /app/cd_template/standalone içinde macos_view yok kalması normal; orayı sunucuda script veya manuel kopyayla doldurmanız gerekiyor.