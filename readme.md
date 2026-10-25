# Single Image Dehazing — Dark Channel Prior + Guided Filter

Progetto per il corso **Elaborazione delle Immagini e Visione Artificiale (ELIVA)** — Università di Torino.

## Cosa fa questo progetto

In presenza di nebbia o foschia la luce viene diffusa dalle particelle in sospensione: l'immagine perde contrasto e assume una dominante biancastra. Questo progetto **rimuove la nebbia da una singola immagine** (single image dehazing), recuperando la scena "pulita" senza informazioni aggiuntive, a partire dal modello di scattering atmosferico:

```text
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

## Risultati in breve

Configurazione di default (patch 15, ω = 0,95, t₀ = 0,1, guided filter r = 60, ε = 1e−3), immagini ridotte a lato massimo 1024 px. "Hazy" è la baseline senza dehazing; valori medi sul dataset.

| Dataset | Nebbia | N | PSNR hazy → DCP (dB) | SSIM hazy → DCP | Immagini migliorate |
| --- | --- | --: | --: | --: | --: |
| SOTS indoor | sintetica | 500 | 11,97 → **19,82** | 0,693 → **0,859** | 96% |
| SOTS outdoor | sintetica | 500 | 15,92 → **17,05** | 0,814 → **0,859** | 58% |
| O-HAZE | reale, omogenea | 45 | 13,79 → **16,01** | 0,612 → **0,680** | 78% |
| I-HAZE | reale, omogenea | 30 | **14,31** → 12,35 | **0,702** → 0,630 | 27% |
| NH-HAZE | reale, non omogenea | 55 | 11,52 → **12,29** | 0,448 → **0,478** | 58% |

Il DCP funziona molto bene sulla nebbia sintetica e su O-HAZE, aiuta poco sulla nebbia non omogenea (NH-HAZE) e **peggiora** le scene indoor di I-HAZE: le ampie pareti bianche hanno un canale scuro alto anche senza nebbia, quindi violano il prior. È il limite dichiarato da He et al.

La discussione completa è nella relazione di progetto, [`report/Relazione_Dehazing.pdf`](report/Relazione_Dehazing.pdf). Il report con statistiche per dataset, immagini migliori e peggiori, figure qualitative e ablazioni è in [`report/risultati.md`](report/risultati.md), generato da `scripts/make_report.py`.

## Formule utilizzate

Tutte le formule su cui si basa il progetto, con descrizione e significato dei simboli. _(La notazione LaTeX viene resa automaticamente su GitHub; in VS Code serve un'estensione per l'anteprima matematica.)_

### 1. Modello di formazione dell'immagine annebbiata

$$I(x) = J(x)\,t(x) + A\,\bigl(1 - t(x)\bigr)$$

È il modello di scattering atmosferico, base di tutto il progetto. L'immagine osservata è la somma di due contributi: l'**attenuazione diretta** `J(x)·t(x)` (la scena pulita indebolita dalla diffusione) e l'**airlight** `A·(1−t(x))` (il velo biancastro dovuto alla luce ambientale diffusa verso la camera).

- `I(x)` — intensità osservata nel pixel `x` (per ogni canale RGB)
- `J(x)` — radianza della scena "pulita" da recuperare
- `A` — luce atmosferica globale (airlight), costante sull'immagine
- `t(x)` — trasmissione: frazione di luce che raggiunge la camera senza essere diffusa, `t ∈ [0,1]`

### 2. Trasmissione e profondità

$$t(x) = e^{-\beta d(x)}$$

In atmosfera omogenea la trasmissione decade esponenzialmente con la distanza: più un oggetto è lontano, più nebbia lo copre.

- `β` — coefficiente di scattering dell'atmosfera (densità della nebbia)
- `d(x)` — profondità della scena nel pixel `x`

### 3. Canale scuro (Dark Channel)

$$J^{\mathrm{dark}}(x) = \min_{c \in \{r,g,b\}} \left( \min_{y \in \Omega(x)} J^{c}(y) \right)$$

Il **prior**: in un'immagine naturale senza foschia, il canale scuro tende a zero, perché in quasi ogni patch esiste un pixel molto scuro in almeno un canale. Dove invece è alto, quell'intensità è dovuta all'airlight — da cui si stima la trasmissione.

- `Ω(x)` — finestra locale centrata in `x` (tipicamente 15×15)
- `J^c(y)` — valore del canale `c` nel pixel `y`
- il doppio minimo = minimo sui canali, poi sulla finestra

Nel codice: `src/dark_channel.py` → `dark_channel()`. Il minimo sulla finestra è calcolato come erosione morfologica (`cv2.erode`), che è equivalente ma molto più veloce di un ciclo.

### 4. Stima della trasmissione (DCP)

$$\tilde{t}(x) = 1 - \omega \, \min_{c} \left( \min_{y \in \Omega(x)} \frac{I^{c}(y)}{A^{c}} \right), \qquad \omega = 0{,}95$$

Applicando il dark channel all'immagine annebbiata (normalizzata per l'airlight) si ottiene la trasmissione grezza. Il fattore `ω < 1` lascia un filo di foschia nelle scene lontane, per un risultato più naturale.

- `ω` — fattore di "haze residua" (tipicamente 0,95)
- `A^c` — componente `c` dell'airlight
- `t̃(x)` — trasmissione grezza, da rifinire (formula 6)

Nel codice: `src/dark_channel.py` → `transmission_raw()`.

### 5. Stima dell'airlight A

$$\mathcal{P} = \{\text{top } 0{,}1\%\ \text{dei pixel per } I^{\mathrm{dark}}\}, \qquad x^{*} = \arg\max_{x \in \mathcal{P}} \sum_{c} I^{c}(x), \qquad A = I(x^{*})$$

Si prendono i pixel col canale scuro più alto (le zone più "fitte" di foschia, di solito il cielo) e, tra questi, si sceglie **il singolo pixel più luminoso** nell'immagine di partenza: il suo colore è l'airlight. È la scelta del paper di He et al.

- `𝒫` — insieme dei pixel con canale scuro più alto (0,1% del totale)
- `x*` — il pixel più luminoso tra i candidati

Nel codice: `src/dark_channel.py` → `estimate_atmospheric_light()`. Per l'ablazione sono disponibili anche altre due varianti (`--airlight`): `max_per_channel` (massimo indipendente per ciascun canale, $A^{c} = \max_{x \in \mathcal{P}} I^{c}(x)$) e `mean` (media dei candidati, più robusta a lampade e riflessi).

### 6. Rifinitura della trasmissione — Guided Filter

La trasmissione grezza è a blocchi; il Guided Filter la rende liscia conservando i bordi dell'immagine. Si assume un **modello lineare locale** tra uscita `q` e immagine guida `I` in ogni finestra `ω_k`:

$$q_i = a_k \, I_i + b_k, \qquad \forall\, i \in \omega_k$$

con i coefficienti ottenuti per minimi quadrati:

$$a_k = \frac{\frac{1}{|\omega|}\sum_{i \in \omega_k} I_i\,p_i - \mu_k\,\bar{p}_k}{\sigma_k^{2} + \varepsilon}, \qquad b_k = \bar{p}_k - a_k\,\mu_k$$

- `p` — input da filtrare (la trasmissione grezza `t̃`); `I` — immagine guida (grigio/RGB)
- `μ_k`, `σ_k²` — media e varianza della guida nella finestra `ω_k`
- `p̄_k` — media dell'input nella finestra; `|ω|` — numero di pixel della finestra
- `ε` — regolarizzazione (ε grande → più liscio; valori tipici ~1e−3)
- costo **O(N)**, indipendente dalla dimensione della finestra

Nel codice: `src/guided_filter.py`, con guida in grigio (`guided_filter_gray`), guida a colori con matrice di covarianza 3×3 per pixel (`guided_filter_color`) e la versione di OpenCV come riferimento (`guided_filter_opencv`).

### 7. Recupero della scena

$$J(x) = \frac{I(x) - A}{\max\bigl(t(x), t_0\bigr)} + A, \qquad t_0 = 0{,}1$$

Invertendo il modello si ottiene l'immagine ripulita. La soglia `t₀` evita la divisione per valori quasi nulli (dove la trasmissione è bassissima il rumore esploderebbe).

- `t(x)` — trasmissione rifinita (formula 6)
- `t_0` — soglia minima di trasmissione (tipicamente 0,1)

Nel codice: `src/dehaze.py` → `recover_scene()`.

### 8. Post-processing (opzionale) — correzione gamma

$$s = c \cdot r^{\gamma}$$

Le immagini ripulite risultano spesso scure: una correzione di potenza ne schiarisce i toni.

- `r`, `s` — intensità in ingresso/uscita; `γ` — esponente (`γ<1` schiarisce); `c` — costante di scala (nel codice `c = 1`, opzione `--gamma`)

### 9. Confronto deep learning (opzionale) — AOD-Net

$$J(x) = K(x)\,I(x) - K(x) + b$$

AOD-Net riformula il modello: invece di stimare `t` e `A` separatamente, una CNN leggera predice un'unica mappa `K(x)` che li ingloba, generando direttamente l'immagine pulita (end-to-end).

- `K(x)` — mappa appresa che racchiude trasmissione e airlight
- `b` — costante (bias), fissata nel paper a 1

### 10. Metriche di valutazione

**Errore quadratico medio (MSE):**

$$\mathrm{MSE} = \frac{1}{MN}\sum_{x=1}^{M}\sum_{y=1}^{N}\bigl[J(x,y) - \hat{J}(x,y)\bigr]^{2}$$

**PSNR** (Peak Signal-to-Noise Ratio), in decibel — più alto è meglio:

$$\mathrm{PSNR} = 10 \, \log_{10}\frac{\mathrm{MAX}^{2}}{\mathrm{MSE}}$$

**SSIM** (Structural Similarity) — confronta luminanza, contrasto e struttura; `∈ [0,1]`, più vicino a 1 è meglio, correla meglio con la percezione umana:

$$\mathrm{SSIM}(x,y) = \frac{(2\mu_x\mu_y + C_1)(2\sigma_{xy} + C_2)}{(\mu_x^{2} + \mu_y^{2} + C_1)(\sigma_x^{2} + \sigma_y^{2} + C_2)}$$

- `J`, `Ĵ` — immagine ricostruita e ground truth; `M×N` — numero di pixel
- `MAX` — massimo valore possibile (255 per 8 bit, o 1 se normalizzato; nel progetto si usa 1)
- `μ`, `σ²`, `σ_xy` — media, varianza e covarianza locali (finestre scorrevoli)
- `C_1`, `C_2` — costanti di stabilizzazione; si media poi su tutte le finestre (Mean SSIM)

Nel codice: `src/metrics.py` (scikit-image). La SSIM è calcolata **per canale e poi mediata**: alcuni articoli la calcolano solo sulla luminanza, quindi i numeri non sono sempre confrontabili alla lettera.

Per immagini reali **senza** ground truth si usano metriche no-reference (FADE, NIQE) e il confronto visivo.

## Struttura del repository

```text
dehazing-project/
├── data/                  # dataset (NON versionati — vedi .gitignore)
│   ├── O-HAZE/  I-HAZE/  NH-HAZE/  SOTS-RESIDE/
├── document/              # paper di riferimento in PDF (NON versionati — copyright)
├── src/                   # la "libreria": tutta la logica
│   ├── __init__.py        # rende src un pacchetto importabile
│   ├── io_utils.py        # lettura/scrittura immagini + abbinamento hazy/GT dei 5 dataset
│   ├── dark_channel.py    # canale scuro, airlight, trasmissione grezza (passi 1-3)
│   ├── guided_filter.py   # guided filter grigio / colori / OpenCV (passo 4)
│   ├── dehaze.py          # pipeline completa: dehaze(img) -> J (passi 1-6)
│   ├── metrics.py         # MSE, PSNR, SSIM
│   └── cli.py             # argomenti da riga di comando condivisi dagli script
├── scripts/               # i comandi da lanciare
│   ├── run_single.py      # dehazing di una singola immagine (+ mappe intermedie)
│   ├── evaluate.py        # valutazione su un dataset -> results/<esperimento>/
│   └── make_report.py     # results/ -> report/ (tabelle, grafici, confronti)
├── tests/
│   └── test_pipeline.py   # test automatici (pytest)
├── notebooks/             # esplorazione e figure per la relazione
├── results/               # output di evaluate.py (NON versionato)
├── report/                # relazione + report generato
│   ├── Relazione_Dehazing.pdf   # relazione di progetto (da consegnare)
│   ├── Relazione_Dehazing.docx  # versione Word modificabile (NON versionata)
│   ├── risultati.md       # report dei risultati (generato)
│   ├── summary.csv        # una riga per esperimento (generato)
│   └── figures/           # grafici e confronti qualitativi (generati)
├── pytest.ini             # configurazione dei test
├── requirements.txt       # dipendenze della pipeline classica
├── requirements-dl.txt    # dipendenze extra per la parte deep (AOD-Net)
├── Dockerfile             # ambiente riproducibile
├── .dockerignore          # esclude dataset e risultati dal build Docker
└── readme.md
```

Convenzione usata in tutto il codice: le immagini sono array NumPy `float32`, canali in ordine **BGR** (quello di OpenCV), valori in **[0, 1]**.

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

Librerie principali: `numpy`, `opencv-contrib-python` (per `cv2.ximgproc.guidedFilter`; non installarla insieme a `opencv-python`, vanno in conflitto), `scikit-image` (PSNR/SSIM), `matplotlib`, `tqdm`, `pytest`.

Per la parte deep (AOD-Net), solo quando serve:

```bash
python -m pip install -r requirements-dl.txt
```

PyTorch conviene installarlo con il comando generato da <https://pytorch.org/get-started/locally/>, che sceglie la build giusta (CPU o CUDA).

> **Nota per Windows:** OpenCV non legge né scrive file il cui percorso contiene caratteri accentati (es. `università`): `cv2.imread` restituisce `None` senza errore. Per questo `src/io_utils.py` usa `np.fromfile` + `cv2.imdecode` e `cv2.imencode` + `tofile`.

## Come scaricare i dataset

I dataset **non** sono inclusi nel repository (troppo pesanti, esclusi via `.gitignore`). Vanno scaricati ed estratti dentro le rispettive cartelle in `data/`. Tutti forniscono coppie immagine annebbiata / ground truth, necessarie per PSNR e SSIM.

### O-HAZE, I-HAZE, NH-HAZE (ETH Zürich — download diretto)

Benchmark reali delle sfide NTIRE, scaricabili senza registrazione. Da terminale, dalla cartella del progetto:

```bash
# O-HAZE — 45 coppie outdoor reali (~547 MB)
curl -L -o data/O-HAZE/O-HAZE.zip https://data.vision.ee.ethz.ch/cvl/ntire18/o-haze/O-HAZE.zip

# I-HAZE — 30 coppie indoor reali con GT (01–25 e 31–35) (~312 MB)
curl -L -o data/I-HAZE/I-HAZE.zip https://data.vision.ee.ethz.ch/cvl/ntire18/i-haze/I-HAZE.zip

# NH-HAZE — 55 coppie a nebbia NON omogenea (~316 MB)
curl -L -o data/NH-HAZE/NH-HAZE.zip https://data.vision.ee.ethz.ch/cvl/ntire20/nh-haze/files/NH-HAZE.zip
```

Poi estrai ciascun `.zip` nella sua cartella (su Windows: clic destro → _Estrai tutto_; da terminale: `unzip data/O-HAZE/O-HAZE.zip -d data/O-HAZE/`).

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

### Struttura attesa e controllo

Non serve rinominare nulla dopo l'estrazione: `src/io_utils.py` trova da solo le sottocartelle (anche `# O-HAZY NTIRE 2018/`) e ignora maiuscole/minuscole nelle estensioni (`.jpg` / `.JPG`).

| Dataset | Abbinamento hazy ↔ GT | Coppie attese |
| --- | --- | --: |
| O-HAZE | `hazy/01_outdoor_hazy.jpg` ↔ `GT/01_outdoor_GT.jpg` | 45 |
| I-HAZE | `hazy/01_indoor_hazy.jpg` ↔ `GT/01_indoor_GT.jpg` | 30 |
| NH-HAZE | `01_hazy.png` ↔ `01_GT.png` (stessa cartella) | 55 |
| SOTS indoor | `hazy/1400_3.png` ↔ `clear/1400.png` (50 GT × 10 livelli di nebbia) | 500 |
| SOTS outdoor | `hazy/0001_0.8_0.2.jpg` ↔ `clear/0001.png` (500 hazy su 492 GT) | 500 |

Per verificare che tutto sia al suo posto:

```bash
python -c "from src.io_utils import list_pairs; [print(n, len(list_pairs(n))) for n in ['o-haze','i-haze','nh-haze','sots-indoor','sots-outdoor']]"
```

## Come eseguire

```bash
# 1. test automatici (meno di un secondo)
python -m pytest

# 2. dehazing di una singola immagine, salvando anche canale scuro e trasmissioni
python scripts/run_single.py --input data/NH-HAZE/NH-HAZE/01_hazy.png --save-maps

# 3. valutazione su un dataset (PSNR/SSIM + tempi) -> results/<esperimento>/
python scripts/evaluate.py --dataset sots-indoor --max-side 1024
python scripts/evaluate.py --dataset o-haze --max-side 1024 --save-images

# 4. report: tabelle, grafici e confronti qualitativi -> report/
python scripts/make_report.py --qualitative
```

Dataset disponibili per `--dataset`: `sots-indoor`, `sots-outdoor`, `o-haze`, `i-haze`, `nh-haze`. Opzioni utili:

| Opzione | Default | A cosa serve |
| --- | --- | --- |
| `--max-side N` | 0 (originale) | riduce le immagini enormi di O-HAZE / I-HAZE (fino a 4657 px) |
| `--limit N` | 0 (tutte) | usa solo le prime N coppie, per prove veloci |
| `--save-images` | no | salva anche le immagini ripulite |
| `--patch`, `--omega`, `--t0` | 15, 0.95, 0.1 | parametri del DCP |
| `--airlight` | `brightest` | `brightest`, `max_per_channel` o `mean` |
| `--refine` | `guided` | `guided`, `guided_color`, `guided_cv`, `bilateral`, `none` |
| `--radius`, `--eps` | 60, 0.001 | parametri del guided filter |
| `--gamma` | nessuna | correzione gamma finale (es. 0.8) |

Ogni esecuzione di `evaluate.py` crea una cartella con un nome che descrive i parametri (es. `results/sots-indoor_p15_w0.95_t0.1_guided_brightest/`), con `metrics.csv` (una riga per immagine) e `params.json`. Per un'ablazione basta lanciare più valutazioni e poi rigenerare il report, che le confronta da solo (esempio in PowerShell):

```powershell
foreach ($w in 0.8, 0.85, 0.9, 1.0) { python scripts/evaluate.py --dataset sots-indoor --max-side 1024 --omega $w }
python scripts/make_report.py --qualitative
```

## Docker (opzionale)

L'immagine contiene solo codice e dipendenze; dataset e risultati vengono montati come volumi al momento dell'esecuzione (PowerShell):

```powershell
docker build -t dehazing .
docker run --rm -v "${PWD}/data:/app/data:ro" -v "${PWD}/results:/app/results" dehazing scripts/evaluate.py --dataset sots-indoor --limit 20
```

## Documenti di riferimento

I lavori su cui si basa il progetto, con un breve riassunto di cosa trattano. I PDF **non sono inclusi nel repository** per motivi di copyright (la cartella `document/` è esclusa via `.gitignore`): si trovano tramite le citazioni complete in fondo. I nomi dei file indicati sono quelli usati localmente, nel formato autore-anno.

**`He2009_DarkChannelPrior.pdf`** — _Single Image Haze Removal Using Dark Channel Prior_ (He, Sun, Tang — CVPR 2009, Best Paper).
Introduce il **Dark Channel Prior**, il metodo fondamentale del progetto: osserva che le immagini naturali senza foschia hanno, in quasi ogni patch, pixel molto scuri in almeno un canale; da questa statistica stima direttamente la trasmissione e recupera l'immagine pulita. Limite dichiarato: cade su cielo e superfici bianche.

**`He2010_GuidedImageFiltering.pdf`** — _Guided Image Filtering_ (He, Sun, Tang — ECCV 2010 / TPAMI 2013).
Presenta il **Guided Filter**, filtro edge-preserving derivato da un modello lineare locale: liscia conservando i bordi, con comportamento migliore del filtro bilaterale e un algoritmo esatto a tempo lineare. Nel progetto rifinisce la trasmissione (al posto del soft matting, più lento).

**`Li2017_AOD-Net.pdf`** — _AOD-Net: All-in-One Dehazing Network_ (Li et al. — ICCV 2017).
Metodo **deep learning**: riformula il modello di scattering per predire un'unica mappa `K(x)` con una CNN leggera, generando l'immagine pulita end-to-end (senza stimare `t` e `A` separatamente). Veloce e accurato; è il termine di confronto "moderno" per l'obiettivo opzionale.

**`Li2019_RESIDE_benchmark.pdf`** — _Benchmarking Single-Image Dehazing and Beyond (RESIDE)_ (Li et al. — IEEE TIP 2019).
Definisce il **benchmark standard** del dehazing: cinque sottoinsiemi (ITS e OTS per il training sintetico, **SOTS** per il test oggettivo, HSTS soggettivo, RTTS reale con bounding box) e introduce, oltre a PSNR/SSIM, una valutazione task-driven (quanto il dehazing aiuta la detection).

**`Ancuti2018_O-HAZE.pdf`**, **`Ancuti2018_I-HAZE.pdf`**, **`Ancuti2020_NH-HAZE.pdf`** — dataset con nebbia **reale** (Ancuti et al., NTIRE 2018 e 2020).
Tre benchmark con coppie hazy/ground-truth ottenute con generatori di nebbia professionali: **O-HAZE** (45 scene outdoor), **I-HAZE** (35 scene indoor, di cui 30 con ground truth pubblica), **NH-HAZE** (55 scene a nebbia **non omogenea**). Servono a testare la generalizzazione su nebbia vera; NH-HAZE è il caso difficile per i metodi a trasmissione globale come il DCP.

**`Wang2004_SSIM.pdf`** — _Image Quality Assessment: From Error Visibility to Structural Similarity_ (Wang et al. — IEEE TIP 2004).
Introduce la metrica **SSIM**: invece dell'errore pixel per pixel (MSE/PSNR), confronta la somiglianza strutturale combinando luminanza, contrasto e struttura locali, correlando meglio con la percezione umana. È la seconda metrica di valutazione del progetto.

## Riferimenti (citazioni complete)

- K. He, J. Sun, X. Tang — _Single Image Haze Removal Using Dark Channel Prior_, CVPR 2009 / IEEE TPAMI 2011.
- K. He, J. Sun, X. Tang — _Guided Image Filtering_, ECCV 2010 / IEEE TPAMI 2013.
- B. Li, X. Peng, Z. Wang, J. Xu, D. Feng — _AOD-Net: All-in-One Dehazing Network_, ICCV 2017.
- B. Li et al. — _Benchmarking Single-Image Dehazing and Beyond (RESIDE)_, IEEE TIP 2019.
- C. O. Ancuti et al. — _O-HAZE_ / _I-HAZE_, NTIRE 2018 (CVPR Workshops); _NH-HAZE_, NTIRE 2020.
- Z. Wang, A. C. Bovik, H. R. Sheikh, E. P. Simoncelli — _Image Quality Assessment: From Error Visibility to Structural Similarity (SSIM)_, IEEE TIP 2004.

_Dataset e paper a solo uso accademico/di ricerca: citare le fonti nella relazione e non ridistribuirli._
