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

### 4. Stima della trasmissione (DCP)

$$\tilde{t}(x) = 1 - \omega \, \min_{c} \left( \min_{y \in \Omega(x)} \frac{I^{c}(y)}{A^{c}} \right), \qquad \omega = 0{,}95$$

Applicando il dark channel all'immagine annebbiata (normalizzata per l'airlight) si ottiene la trasmissione grezza. Il fattore `ω < 1` lascia un filo di foschia nelle scene lontane, per un risultato più naturale.

- `ω` — fattore di "haze residua" (tipicamente 0,95)
- `A^c` — componente `c` dell'airlight
- `t̃(x)` — trasmissione grezza, da rifinire (passo 6)

### 5. Stima dell'airlight A

$$A^{c} = \max_{x \in \mathcal{P}} \; I^{c}(x), \qquad \mathcal{P} = \{\text{top } 0{,}1\%\ \text{dei pixel per } J^{\mathrm{dark}}\}$$

Si prendono i pixel col canale scuro più alto (le zone più "fitte" di foschia, di solito il cielo) e, tra questi, il valore più luminoso nell'immagine di partenza, per ciascun canale.

- `𝒫` — insieme dei pixel con canale scuro più alto (0,1% più luminoso)

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

### 7. Recupero della scena

$$J(x) = \frac{I(x) - A}{\max\bigl(t(x), t_0\bigr)} + A, \qquad t_0 = 0{,}1$$

Invertendo il modello si ottiene l'immagine ripulita. La soglia `t₀` evita la divisione per valori quasi nulli (dove la trasmissione è bassissima il rumore esploderebbe).

- `t(x)` — trasmissione rifinita (passo 6)
- `t_0` — soglia minima di trasmissione (tipicamente 0,1)

### 8. Post-processing (opzionale) — correzione gamma

$$s = c \cdot r^{\gamma}$$

Le immagini ripulite risultano spesso scure: una correzione di potenza ne schiarisce i toni.

- `r`, `s` — intensità in ingresso/uscita; `γ` — esponente (`γ<1` schiarisce); `c` — costante di scala

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
- `MAX` — massimo valore possibile (255 per 8 bit, o 1 se normalizzato)
- `μ`, `σ²`, `σ_xy` — media, varianza e covarianza locali (finestre scorrevoli)
- `C_1`, `C_2` — costanti di stabilizzazione; si media poi su tutte le finestre (Mean SSIM)

Per immagini reali **senza** ground truth si usano metriche no-reference (FADE, NIQE) e il confronto visivo.

## Struttura del repository

```
dehazing-project/
├── data/                  # dataset (NON versionati — vedi .gitignore)
│   ├── O-HAZE/  I-HAZE/  NH-HAZE/  SOTS-RESIDE/
├── document/              # i paper di riferimento (PDF)
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

# I-HAZE — 35 coppie indoor reali (~312 MB)
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

## Documenti di riferimento (cartella `document/`)

I PDF dei lavori su cui si basa il progetto, con un breve riassunto di cosa trattano. Nomi dei file nel formato autore-anno.

**`He2009_DarkChannelPrior.pdf`** — *Single Image Haze Removal Using Dark Channel Prior* (He, Sun, Tang — CVPR 2009, Best Paper).
Introduce il **Dark Channel Prior**, il metodo fondamentale del progetto: osserva che le immagini naturali senza foschia hanno, in quasi ogni patch, pixel molto scuri in almeno un canale; da questa statistica stima direttamente la trasmissione e recupera l'immagine pulita. Limite dichiarato: cade su cielo e superfici bianche.

**`He2010_GuidedImageFiltering.pdf`** — *Guided Image Filtering* (He, Sun, Tang — ECCV 2010 / TPAMI 2013).
Presenta il **Guided Filter**, filtro edge-preserving derivato da un modello lineare locale: liscia conservando i bordi, con comportamento migliore del filtro bilaterale e un algoritmo esatto a tempo lineare. Nel progetto rifinisce la trasmissione (al posto del soft matting, più lento).

**`Li2017_AOD-Net.pdf`** — *AOD-Net: All-in-One Dehazing Network* (Li et al. — ICCV 2017).
Metodo **deep learning**: riformula il modello di scattering per predire un'unica mappa `K(x)` con una CNN leggera, generando l'immagine pulita end-to-end (senza stimare `t` e `A` separatamente). Veloce e accurato; è il termine di confronto "moderno" per l'obiettivo opzionale.

**`Li2019_RESIDE_benchmark.pdf`** — *Benchmarking Single-Image Dehazing and Beyond (RESIDE)* (Li et al. — IEEE TIP 2019).
Definisce il **benchmark standard** del dehazing: cinque sottoinsiemi (ITS e OTS per il training sintetico, **SOTS** per il test oggettivo, HSTS soggettivo, RTTS reale con bounding box) e introduce, oltre a PSNR/SSIM, una valutazione task-driven (quanto il dehazing aiuta la detection).

**`Ancuti2018_O-HAZE.pdf`**, **`Ancuti2018_I-HAZE.pdf`**, **`Ancuti2020_NH-HAZE.pdf`** — dataset con nebbia **reale** (Ancuti et al., NTIRE 2018 e 2020).
Tre benchmark con coppie hazy/ground-truth ottenute con generatori di nebbia professionali: **O-HAZE** (45 scene outdoor), **I-HAZE** (35 scene indoor), **NH-HAZE** (55 scene a nebbia **non omogenea**). Servono a testare la generalizzazione su nebbia vera; NH-HAZE è il caso difficile per i metodi a trasmissione globale come il DCP.

**`Wang2004_SSIM.pdf`** — *Image Quality Assessment: From Error Visibility to Structural Similarity* (Wang et al. — IEEE TIP 2004).
Introduce la metrica **SSIM**: invece dell'errore pixel per pixel (MSE/PSNR), confronta la somiglianza strutturale combinando luminanza, contrasto e struttura locali, correlando meglio con la percezione umana. È la seconda metrica di valutazione del progetto.

## Riferimenti (citazioni complete)

- K. He, J. Sun, X. Tang — *Single Image Haze Removal Using Dark Channel Prior*, CVPR 2009 / IEEE TPAMI 2011.
- K. He, J. Sun, X. Tang — *Guided Image Filtering*, ECCV 2010 / IEEE TPAMI 2013.
- B. Li, X. Peng, Z. Wang, J. Xu, D. Feng — *AOD-Net: All-in-One Dehazing Network*, ICCV 2017.
- B. Li et al. — *Benchmarking Single-Image Dehazing and Beyond (RESIDE)*, IEEE TIP 2019.
- C. O. Ancuti et al. — *O-HAZE* / *I-HAZE*, NTIRE 2018 (CVPR Workshops); *NH-HAZE*, NTIRE 2020.
- Z. Wang, A. C. Bovik, H. R. Sheikh, E. P. Simoncelli — *Image Quality Assessment: From Error Visibility to Structural Similarity (SSIM)*, IEEE TIP 2004.

_Dataset e paper a solo uso accademico/di ricerca: citare le fonti nella relazione e non ridistribuirli._
