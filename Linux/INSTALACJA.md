# Watermark Tool — Instalacja na Linux

## Wymagania

| Pakiet | Minimalna wersja | Uwagi |
|--------|-----------------|-------|
| Python | 3.8+ | zwykle już zainstalowany |
| tkinter | — | interfejs graficzny |
| Pillow | 9.0+ | przetwarzanie zdjęć |

---

## Instalacja krok po kroku

### 1. Sprawdź czy Python jest zainstalowany

```bash
python3 --version
```

Jeśli polecenie nie działa, zainstaluj Python:

```bash
# Ubuntu / Debian / Linux Mint
sudo apt install python3

# Fedora
sudo dnf install python3

# Arch Linux
sudo pacman -S python
```

---

### 2. Zainstaluj tkinter

tkinter nie jest zawsze instalowany razem z Pythonem:

```bash
# Ubuntu / Debian / Linux Mint
sudo apt install python3-tk

# Fedora
sudo dnf install python3-tkinter

# Arch Linux
sudo pacman -S tk
```

Sprawdź czy działa:
```bash
python3 -c "import tkinter; print('tkinter OK')"
```

---

### 3. Zainstaluj Pillow

```bash
pip3 install Pillow
```

Lub przez menedżer pakietów:
```bash
# Ubuntu / Debian
sudo apt install python3-pil python3-pil.imagetk

# Fedora
sudo dnf install python3-pillow python3-pillow-tk
```

Sprawdź czy działa:
```bash
python3 -c "from PIL import Image; print('Pillow OK')"
```

---

### 4. Czcionki (opcjonalnie)

Program automatycznie wykrywa czcionki zainstalowane w systemie.
Dla najlepszego wyboru czcionek warto mieć zainstalowane fonty Liberation lub DejaVu:

```bash
# Ubuntu / Debian
sudo apt install fonts-liberation fonts-dejavu

# Fedora
sudo dnf install liberation-fonts dejavu-fonts-all
```

Czcionki DejaVu Sans są zazwyczaj już zainstalowane w większości dystrybucji.

---

## Uruchomienie programu

Skopiuj plik `watermark_tool_linux_v1.0.py` oraz `profiles.json` (jeśli istnieje)
do wybranego folderu, a następnie uruchom:

```bash
python3 watermark_tool_linux_v1.0.py
```

Lub nadaj prawa wykonywania i uruchom bezpośrednio:

```bash
chmod +x watermark_tool_linux_v1.0.py
./watermark_tool_linux_v1.0.py
```

---

## Tworzenie skrótu na pulpicie (opcjonalnie)

Utwórz plik `watermark_tool.desktop` w folderze `~/.local/share/applications/`:

```ini
[Desktop Entry]
Name=Watermark Tool
Comment=Nakładanie znaku wodnego na zdjęcia
Exec=python3 /SCIEZKA/DO/watermark_tool_linux_v1.0.py
Icon=image-x-generic
Terminal=false
Type=Application
Categories=Graphics;Photography;
```

Zastąp `/SCIEZKA/DO/` rzeczywistą ścieżką do pliku, np. `/home/uzytkownik/watermark/`.

---

## Rozwiązywanie problemów

**Błąd: `No module named 'tkinter'`**
→ Zainstaluj `python3-tk` (patrz krok 2)

**Błąd: `No module named 'PIL'`**
→ Zainstaluj Pillow (patrz krok 3)

**Brak czcionek na liście**
→ Zainstaluj pakiety `fonts-liberation` lub `fonts-dejavu` (patrz sekcja Czcionki)

**Błąd uprawnień przy uruchamianiu**
→ Uruchom przez `python3 watermark_tool_linux_v1.0.py` zamiast bezpośrednio
