# Single Image Dehazing — Dark Channel Prior + Guided Filter

Progetto per il corso **Elaborazione delle Immagini e Visione Artificiale (ELIVA)** — Università di Torino.

## Cosa fa questo progetto

In presenza di nebbia o foschia la luce viene diffusa dalle particelle in sospensione: l'immagine perde contrasto e assume una dominante biancastra. Questo progetto **rimuove la nebbia da una singola immagine** (single image dehazing), recuperando la scena "pulita" senza informazioni aggiuntive, a partire dal modello di scattering atmosferico:

```
I(x) = J(x)·t(x) + A·(1 − t(x))
```

dove `I` è l'immagine osservata, `J` la scena pulita da recuperare, `A` la luce atmosferica (airlight) e `t(x)` la trasmissione.

Il metodo principale implementato è quello classico basato sul **Dark Channel Prior** (He, Sun, Tang 2009), con rifinitura della trasmissione tramite **Guided Filter** (He et al. 2010). La pipeline:

1. **Canale scuro** — minimo sui canali RGB e su una finestra locale.
2. **Stima dell'airlight A** — dai pixel più luminosi del canale scuro.
3. **Trasmissione grezza** — dalla formula del DCP (`t = 1 − ω·min…`).
4. **Rifinitura** — Guided Filter per allineare i bordi della trasmissione all'immagine.
5. **Recupero della scena** — `J = (I − A) / max(t, t₀) + A`.

Come **valore aggiunto opzionale** è previsto il confronto con un metodo deep (**AOD-Net**), e la valutazione quantitativa con **PSNR** e **SSIM** su dataset con ground truth, più studi di ablazione (effetto di ω, della patch, di t₀; nebbia omogenea vs non omogenea).

## Struttura del repository

```
dehazing-project/
├── data/                  # dataset (NON versionati — vedi .gitignore)
│   ├── O-HAZE/  I-HAZE/  NH-HAZE/  SOTS-RESIDE/
├── src/
│   ├── dark_channel.py    # canale scuro, airlight, trasmissione
│   ├── guided_filter.py   # guided filter (o wrapper su cv2.ximgproc)
│   ├── dehaze.py          # pipeline DCP completa: dehaze(img) -> J
│   └── metrics.py         # PSNR, SSIM
├── scripts/
│   ├── run_single.py      # dehazing di una singola immagine
│   └── evaluate.py        # valutazione su un dataset -> tabella risultati
├── notebooks/             # esplorazione e figure per la relazione
├── results/               # immagini dehazed, tabelle, grafici
├── report/                # relazione
├── requirements.txt
├── dockerfile             # opzionale, per riproducibilità
└── readme.md
```

## Requisiti e installazione

Python 3.11+ consigliato. Da dentro la cartella del progetto:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

python -m pip install -r requirements.txt
```

Librerie principali: `numpy`, `opencv-contrib-python` (per `cv2.ximgproc.guidedFilter`), `scikit-image` (PSNR/SSIM), `matplotlib`, `tqdm`.

## Come scaricare i dataset

I dataset **non** sono inclusi nel repository (troppo pesanti, esclusi via `.gitignore`). Vanno scaricati ed estratti dentro le rispettive cartelle in `data/`. Tutti forniscono coppie immagine annebbiata / ground truth, necessarie per PSNR e SSIM.

### O-HAZE, I-HAZE, NH-HAZE (ETH Zürich — download diretto)

Benchmark reali delle sfide NTIRE, scaricabili senza registrazione. Da terminale, dalla cartella del progetto:

```bash
# O-HAZE — 45 coppie outdoor reali (~547 MB)
curl -L -o data/O-HAZE/O-HAZE.zip https://data.vision.ee.ethz.ch/cvl/ntire18/o-haze/O-HAZE.zip

# I-HAZE — 30 coppie indoor reali (~312 MB)
curl -L -o data/I-HAZE/I-HAZE.zip https://data.vision.ee.ethz.ch/cvl/ntire18/i-haze/I-HAZE.zip

# NH-HAZE — 55 coppie a nebbia NON omogenea (~316 MB)
curl -L -o data/NH-HAZE/NH-HAZE.zip https://data.vision.ee.ethz.ch/cvl/ntire20/nh-haze/files/NH-HAZE.zip
```

Poi estrai ciascun `.zip` nella sua cartella (su Windows: clic destro → *Estrai tutto*; da terminale: `unzip data/O-HAZE/O-HAZE.zip -d data/O-HAZE/`).

### SOTS — RESIDE (Kaggle — richiede account gratuito)

**SOTS** è il test set sintetico del benchmark **RESIDE** (serve per la valutazione sintetica e, con ITS/OTS, per l'eventuale addestramento della CNN). È ospitato su Kaggle e richiede un account gratuito:

1. Crea un account su [kaggle.com](https://www.kaggle.com), poi `Account → Create New API Token`: scarica `kaggle.json`.
2. Su Windows, mettilo in `C:\Users\<utente>\.kaggle\kaggle.json`.
3. Scarica ed estrai in `data/SOTS-RESIDE/`:

```bash
python -m pip install kaggle
kaggle datasets download -d balraj98/synthetic-objective-testing-set-sots-reside -p data/SOTS-RESIDE --unzip
```

In alternativa, download manuale dal sito ufficiale RESIDE: <https://sites.google.com/view/reside-dehaze-datasets> (sezione RESIDE-Standard → SOTS). Per la CNN servono anche ITS/OTS: `balraj98/indoor-training-set-its-residestandard` (indoor) e l'OTS outdoor.

## Come eseguire

```bash
# dehazing di una singola immagine
python scripts/run_single.py --input path/all_immagine_hazy.png --output results/

# valutazione su un dataset (PSNR/SSIM sulle coppie hazy/GT)
python scripts/evaluate.py --dataset data/O-HAZE
```

*(gli argomenti esatti dipendono dall'implementazione nei rispettivi script.)*

## Metriche

- **PSNR** = `10·log₁₀(MAX² / MSE)` — più alto è meglio.
- **SSIM** — confronta luminanza, contrasto e struttura; più vicino a 1 è meglio, correla meglio con la percezione umana.
- Per immagini reali senza ground truth: metriche no-reference (FADE, NIQE) e confronto visivo.

## Riferimenti

- K. He, J. Sun, X. Tang — *Single Image Haze Removal Using Dark Channel Prior*, CVPR 2009 / IEEE TPAMI 2011.
- K. He, J. Sun, X. Tang — *Guided Image Filtering*, ECCV 2010 / IEEE TPAMI 2013.
- B. Li et al. — *AOD-Net: All-in-One Dehazing Network*, ICCV 2017.
- B. Li et al. — *Benchmarking Single-Image Dehazing and Beyond (RESIDE)*, IEEE TIP 2019.
- C. O. Ancuti et al. — *O-HAZE* / *I-HAZE*, NTIRE 2018; *NH-HAZE*, NTIRE 2020.
- Z. Wang et al. — *Image Quality Assessment: From Error Visibility to Structural Similarity (SSIM)*, IEEE TIP 2004.

_Dataset a solo uso accademico/di ricerca: citare le fonti nella relazione e non ridistribuirli._
