# Dettato

Dettatura vocale in italiano per Windows, tutta in locale. Premi una scorciatoia
(`Ctrl+Spazio`) per iniziare a parlare e premila di nuovo per finire. Il testo viene
trascritto con Whisper `large-v3` (tramite `faster-whisper`, su GPU NVIDIA se c'è),
ripulito e incollato dove si trova il cursore. Né l'audio né il testo escono dal PC.

## Installazione

**Scarica l'ultima versione:**
[Dettato-Setup.exe](https://github.com/LucianoTouch/dettato/releases/latest/download/Dettato-Setup.exe)
(circa 1,3 GB), poi aprilo. Non servono permessi di amministratore né Python.

Il programma non è firmato digitalmente, quindi Windows può mostrare "Windows ha
protetto il PC". In quel caso clicca **Ulteriori informazioni** e poi **Esegui comunque**.

L'installer:

- installa Dettato in `%LOCALAPPDATA%\Programs\Dettato`;
- crea **Dettato** sul desktop e nel menu Start, più **Chiudi Dettato** nel menu Start;
- si può disinstallare da *Impostazioni → App → App installate → Dettato*;
- se c'è la vecchia installazione "Dictation Tool", la chiude e la rimuove.

Al primo avvio il modello Whisper viene scaricato da Internet: circa 3 GB con una GPU
NVIDIA (`large-v3`), 1,5 GB senza (`medium`). La finestra mostra l'avanzamento. Dopo
funziona offline.

### Aggiornamenti

Dettato controlla da solo se c'è una versione nuova, all'avvio e poi una volta al
giorno. Quando c'è, compare una notifica: dal menu dell'icona o dalla finestra scegli
**Aggiorna**. Di solito si scaricano pochi MB e Dettato si riavvia da solo. Puoi anche
controllare subito con *Controlla ora* nella scheda Generale.

## Uso

- **Icona Dettato** (desktop, menu Start o barra delle applicazioni, se la fissi): se
  Dettato è spento lo avvia, se è già acceso apre la sua finestra.
- **Icona microfono nella barra di sistema**, vicino all'orologio. Il colore indica lo
  stato:
  grigio = sta caricando, blu = pronto, rosso = sta registrando, giallo = sta trascrivendo.
  - clic sinistro: apre la finestra di Dettato
  - clic destro: Avvia/Ferma dettatura, Apri il log, Avvio automatico con Windows, Esci
- Un bip segnala l'inizio e la fine di ogni registrazione.

### Finestra di Dettato

Mostra lo stato e permette di cambiare:

- **Scorciatoia**: premi *Cambia…* e poi la nuova combinazione. Vale subito.
- **Modello**: `large-v3` è il più preciso, `large-v3-turbo` è molto più veloce con
  qualità simile. Serve un riavvio, che Dettato propone da solo.
- **Elaborazione**: automatica, GPU o CPU.
- **Parole da eliminare** (es. "ehm"), **incolla automatico**, **avvio con Windows**.

### Precisione

Nella scheda **Precisione** della finestra:

- **Vocabolario**: nomi, marchi e termini tecnici che usi spesso (uno per riga, es.
  `Meta Ads`, `Costruisci & Arreda`). Whisper li riceve come contesto e li scrive
  correttamente. È la cosa più efficace contro le parole sbagliate.
- **Correzioni**: per errori che si ripetono comunque, una riga `sbagliato = giusto`
  (es. `meta ed = Meta Ads`). Valgono solo su parole intere.
- **Modello**: se compaiono frasi inventate, prova `large-v2`.

Contro le frasi inventate ("Grazie a tutti.", "Sottotitoli a cura di…"), Dettato:

- taglia il silenzio all'inizio e alla fine, e non trascrive le registrazioni senza voce;
- scarta i segmenti che Whisper inventa di solito;
- salta il testo inventato nelle pause lunghe.

Per verificare: `.venv\Scripts\python scripts\accuracy_check.py --mic` (voce di sintesi
italiana più rumore reale del microfono, che resta in memoria e non viene salvato).

Le impostazioni sono in `%APPDATA%\Dettato\config.json` e il log in
`%APPDATA%\Dettato\dettato.log`.

## Sviluppo

```powershell
py -3 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py          # avvia dai sorgenti
.venv\Scripts\python main.py --stop   # chiude l'istanza in esecuzione
.venv\Scripts\python -m pytest        # test automatici
```

### Creare l'installer

Doppio clic su `build.bat`, oppure `.\build.ps1`. Lo script crea `.venv`, esegue i
test, genera `Dettato.exe` con PyInstaller (`dettato.spec`) e poi
`dist\Dettato-Setup.exe` con Inno Setup (`installer\dettato.iss`). Se Inno Setup
manca, lo installa con winget. Servono circa 6 GB liberi: le librerie CUDA da sole
pesano circa 2 GB.

### Pubblicare una nuova versione

```powershell
.\release.ps1 -Version 1.2.0 -Notes "Cosa cambia in questa versione"
```

Lo script porta `dettato\__init__.py` alla nuova versione, esegue test e build, crea il
pacchetto leggero (`Dettato-update.zip`, solo `Dettato.exe`) e `manifest.json`, fa
commit e tag, e pubblica la release su GitHub con i tre file. Serve GitHub CLI
collegata (`gh auth login`) e il lavoro già salvato in git.

Il manifest contiene un "runtime id", cioè l'impronta delle librerie incluse. Se non è
cambiata, chi ha Dettato installato scarica solo il pacchetto leggero; altrimenti
scarica l'installer completo.

L'icona si rigenera con `scripts\make_icon.py`. I file `scripts\manual_test_*.py`
servono per prove manuali con microfono, scorciatoia, tray e appunti veri.
