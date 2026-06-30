# CTB to CSV

Toolkit per convertire file `.ctb` di AutoCAD in CSV editabili in Excel e ritorno.
Include una GUI desktop, comandi CLI, validazione e generazione di report HTML/PDF.

---

## Funzionalità

| Funzione | Descrizione |
|---|---|
| **CTB → CSV** | Esporta tutti i 255 stili di stampa ACI in un CSV apribile in Excel |
| **CSV → CTB** | Reimporta il CSV modificato in un file `.ctb` valido |
| **Validazione** | Controlla l'integrità del CSV con suggerimenti di correzione |
| **Report HTML** | Scheda di riferimento visuale degli stili attivi, ottimizzata per la stampa |
| **Report AI** | Come il report HTML, ma i raggruppamenti vengono inferiti da Claude AI |
| **GUI** | Interfaccia grafica con dialog espliciti per tutti i file di input/output |
| **EXE standalone** | `dist/ctb_gui.exe` — nessuna installazione Python richiesta |

---

## Avvio rapido

### Eseguibile standalone (nessuna installazione)

```
dist\ctb_gui.exe
```

Copiabile in qualsiasi cartella. Richiede Windows 10/11 a 64 bit.

### Con Python installato

```bash
pip install -e .
ctb-gui          # lancia la GUI
```

Oppure tramite batch (doppio clic):

```
ctb_gui.bat
```

---

## GUI

La GUI si articola in tre sezioni:

### CTB → CSV
1. **Sfoglia…** — seleziona il file `.ctb` sorgente
2. **Cambia…** — scegli dove salvare il CSV (default: stessa cartella del CTB)
3. **Converti CTB → CSV** — esegue la conversione
4. **Apri CSV ↗** — apre il CSV in Excel (disponibile dopo la conversione)

### Report HTML / PDF / AI
- **HTML** — genera la scheda penne e apre il browser
- **PDF** — come HTML ma esporta direttamente in PDF (richiede `pip install weasyprint`)
- **AI ✦** — usa Claude per inferire raggruppamenti funzionali (richiede `ANTHROPIC_API_KEY`)

### CSV → CTB
1. **Sfoglia…** — seleziona il CSV modificato
2. **Sfoglia…** — seleziona il CTB originale come template (struttura globale)
3. **Cambia…** — scegli dove salvare il CTB output
4. **Valida CSV** — controlla errori prima di convertire
5. **Converti CSV → CTB** — esegue la conversione (valida automaticamente)

---

## CLI

```bash
# CTB → CSV
ctb2csv input.ctb output.csv

# CSV → CTB
csv2ctb input.csv template.ctb output.ctb

# Validazione
validate input.csv

# Report HTML
ctb-csv report input.ctb output.html

# Report con AI
ctb-csv report input.ctb output.html --llm

# Report PDF (richiede weasyprint)
ctb-csv report input.ctb output.pdf --pdf
```

---

## Formato CSV

- Encoding: **UTF-8 BOM** (Excel lo apre senza import wizard)
- 255 righe dati, una per colore ACI (1–255)
- 23 colonne — i nomi corrispondono ai campi interni AutoCAD

Colonne principali:

| Colonna | Descrizione |
|---|---|
| `aci_color` | Numero ACI (1–255) |
| `description` | Descrizione dello stile |
| `color_policy` | 1=oggetto, 2=scala di grigi, 5=RGB specificato |
| `color_r/g/b` | Canali RGB del colore di stampa |
| `screen` | Retino 0–100% |
| `lineweight` | Indice spessore (0=da oggetto, 1–26 → tabella standard) |
| `lineweight_mm` | Spessore in mm (informativo, calcolato automaticamente) |

---

## Report HTML

Il report mostra solo le penne **attive** (che derogano dai default AutoCAD):
- `color_policy ≠ 1` — colore di stampa specificato
- `lineweight ≠ 0` — spessore esplicito
- `screen ≠ 100` — retino

Le penne sono raggruppate per colore di stampa, ordinate per numero ACI del primo elemento del gruppo. Le penne con retino < 100% formano il gruppo "Mezzitoni · Screening" in fondo.

Il report rileva automaticamente **anomalie nome ↔ spessore** (es. descrizione "sottile" con spessore 0.50 mm).

Per esportare in PDF: apri l'HTML nel browser e usa **Stampa → Salva come PDF**. I colori vengono preservati grazie a `print-color-adjust: exact`.

---

## Feature AI (raggruppamento inferenziale)

Richiede:
```bash
pip install anthropic
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

Usa `claude-opus-4-8` per analizzare le penne attive e inferire raggruppamenti funzionali con nomi e descrizioni in italiano (es. "Neri — Struttura", "Mezzitoni — Campiture").

---

## Installazione dipendenze opzionali

```bash
pip install ctb-csv[ai]    # solo AI (anthropic)
pip install ctb-csv[pdf]   # solo PDF (weasyprint)
pip install ctb-csv[all]   # AI + PDF
```

---

## Build eseguibile

```bash
pip install pyinstaller
pyinstaller ctb_gui.spec --noconfirm
# output: dist/ctb_gui.exe (~29 MB, include ezdxf e anthropic)
```

---

## Requisiti

- Python 3.10+
- `ezdxf >= 1.3`
- `click >= 8.1`
- Opzionale: `anthropic >= 0.40` (feature AI)
- Opzionale: `weasyprint` (export PDF diretto)
