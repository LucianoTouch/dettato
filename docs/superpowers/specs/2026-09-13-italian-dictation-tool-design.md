# Dictation Tool — Trascrizione vocale locale per Windows (Italiano)

**Data:** 2026-09-13
**Stato:** Approvato, pronto per implementazione

## Obiettivo

Tool desktop Windows che, tramite hotkey globale (default `Ctrl+Space`), registra audio dal microfono, lo trascrive in italiano usando un modello locale ad alta qualità, ripulisce il testo da filler words, e lo incolla automaticamente nel campo di testo attivo. Analogo locale di strumenti come Wispr Flow, ma senza costi API ricorrenti e senza dipendenza dalla rete dopo il setup iniziale.

## Non-goal (fuori scope per v1)

- Supporto multi-lingua (solo italiano)
- Comandi vocali, editing vocale, vocabolario personalizzato
- Pulizia del testo via LLM/cloud
- Packaging come installer distribuibile (`.exe` standalone) — v1 gira da ambiente Python locale
- Streaming/trascrizione in tempo reale mentre si parla (si trascrive solo al rilascio dell'hotkey)

## Valutazione modelli (riferimento)

Ricerca condotta il 2026-09-13. Sintesi:

- **Whisper large-v3** (locale, via `faster-whisper`/CTranslate2, CUDA): scelta per v1. ~3% WER su audio pulito in italiano, 99 lingue, ecosistema maturo, quantizzabile. Gira sub-secondo su RTX 3060 12GB.
- **NVIDIA Parakeet/Canary**: scartati — Parakeet è solo inglese, Canary supporta solo 4 lingue (no italiano).
- **FAMA** (Fondazione Bruno Kessler, modello italiano open-science): competitivo con large-v3 e più veloce, ma tooling/quantizzazione ancora immaturi. Da rivalutare in futuro, non usato in v1.
- **API cloud di frontiera** (ElevenLabs Scribe v2 ~2.2% WER, OpenAI gpt-4o-transcribe ~4% WER, Deepgram Nova-3 ~5.2% WER): leggermente più accurate di Whisper locale, ma comportano costo per minuto e dipendenza da rete. Il gap di qualità non giustifica il costo ricorrente per un uso quotidiano personale con hardware locale adeguato.

**Decisione:** Whisper `large-v3` locale, con `language="it"` forzato per evitare errori di rilevamento lingua. Nessuna integrazione cloud in v1.

## Architettura

App Python in background con icona nella system tray. Nessuna finestra principale in v1 (solo tray + eventuale finestra impostazioni).

```
[Hotkey listener] --toggle--> [Audio recorder] --buffer--> [STT engine] --testo grezzo--> [Post-processor] --testo pulito--> [Output handler] --> [campo attivo]
       |                            |                            |                                                              |
       v                            v                            v                                                              v
  [Tray icon: stato]                                                                                                    [Clipboard: save/restore]
```

### Componenti

**1. Hotkey listener**
- Libreria: `keyboard` (semplice, affidabile su Windows per combinazioni globali)
- Legge la combinazione da config (default `ctrl+space`)
- Su pressione: toggle stato registrazione (avvia se idle, ferma se recording)
- Deve funzionare anche se l'app non ha focus (system-wide hook)

**2. Audio recorder**
- Libreria: `sounddevice` + `numpy` per il buffering
- Cattura dal device di input di default (configurabile in futuro; v1 usa il default di sistema)
- Sample rate 16kHz mono (formato nativo atteso da Whisper), buffer in memoria (non file temporaneo, per latenza minima)
- Avvia cattura alla pressione hotkey, la ferma e restituisce il buffer alla seconda pressione

**3. STT engine**
- Libreria: `faster-whisper`
- Modello: `large-v3`, `device="cuda"`, `compute_type="float16"`
- Fallback automatico a `device="cpu"`, `compute_type="int8"` se CUDA non disponibile (con notifica tray "GPU non rilevata, modalità CPU più lenta")
- Parametri di trascrizione: `language="it"`, `vad_filter=True` (filtro VAD di faster-whisper per tagliare silenzi interni, migliora qualità e velocità)
- Primo avvio: il modello viene scaricato automaticamente da Hugging Face Hub (~3GB) e cachato localmente; da lì in poi funziona offline

**4. Post-processor (rule-based, locale)**
- Rimozione filler words italiani configurabili: lista default `["ehm", "uhm", "cioè cioè", "insomma insomma"]` (pattern ripetizioni + lista fissa)
- Normalizzazione spazi multipli e trim
- Nessuna chiamata di rete, nessuna dipendenza LLM

**5. Output handler**
- Salva il contenuto corrente della clipboard
- Scrive il testo trascritto nella clipboard (`pyperclip` o `win32clipboard`)
- Simula `Ctrl+V` nel campo attivo (`keyboard.send('ctrl+v')`)
- Ripristina la clipboard originale dopo un breve delay (~500ms, per dare tempo all'incolla di completarsi)
- Se il ripristino fallisce, fallisce silenziosamente (non bloccante) — logga ma non interrompe il flusso

**6. Tray UI**
- Libreria: `pystray` + `Pillow` per le icone
- Tre stati visivi: idle (grigio), recording (rosso), transcribing (giallo)
- Menu tray: "Impostazioni", "Avvio automatico con Windows" (toggle), "Esci"
- Notifiche di sistema per errori (mic non trovato, CUDA non disponibile, ecc.)

**7. Config**
- File `config.json` nella cartella utente dell'app (es. `%APPDATA%\dictation-tool\config.json`)
- Campi: `hotkey` (default `"ctrl+space"`), `model_size` (default `"large-v3"`), `device` (default `"auto"`), `filler_words` (lista), `auto_paste` (default `true`), `run_on_startup` (default `false`)
- Modificabile a mano o (fase successiva) da una piccola finestra impostazioni

## Flusso dati end-to-end

1. Utente preme `Ctrl+Space` → hotkey listener rileva → audio recorder inizia a bufferizzare → tray diventa rosso
2. Utente parla
3. Utente ripreme `Ctrl+Space` → audio recorder ferma, restituisce buffer numpy → tray diventa giallo
4. STT engine trascrive il buffer con Whisper large-v3, `language="it"`
5. Post-processor ripulisce il testo (filler words, spazi)
6. Output handler: salva clipboard corrente → scrive testo pulito in clipboard → simula Ctrl+V → ripristina clipboard originale dopo delay
7. Tray torna grigio, pronto per il prossimo ciclo

## Gestione errori

| Scenario | Comportamento |
|---|---|
| Microfono non trovato | Notifica tray, nessun crash, resta in idle |
| CUDA non disponibile | Fallback automatico a CPU (int8), notifica una tantum all'avvio |
| Modello non ancora scaricato | Download automatico al primo avvio con indicatore di progresso (log/notifica) |
| Hotkey già in uso da altra app | Log dell'errore, notifica tray con suggerimento di cambiare hotkey in config |
| Nessun parlato rilevato (buffer vuoto/silenzio) | Nessuna azione di paste, tray torna a idle senza errore |
| Ripristino clipboard fallito | Log silenzioso, non blocca il flusso principale |

## Testing / validazione

- Script di smoke-test standalone: carica un file audio italiano di esempio, esegue la pipeline STT + post-processing, stampa l'output — valida il motore prima di integrare hotkey/UI
- Test manuale end-to-end su almeno 3 applicazioni target (es. browser/campo di ricerca, editor di testo, client chat) per validare l'auto-paste
- Verifica manuale del fallback CPU disattivando temporaneamente CUDA
- Verifica manuale del ripristino clipboard (copia qualcosa, detta, controlla che la clipboard originale torni dopo il paste)

## Fasi di implementazione (macro)

1. **Core STT pipeline**: audio recorder + faster-whisper + smoke-test script (nessuna UI/hotkey ancora)
2. **Hotkey + output handler**: integrazione toggle recording, clipboard, auto-paste
3. **Tray UI + config**: icona di stato, menu, file di configurazione
4. **Post-processing + rifiniture**: filler words, gestione errori, avvio automatico con Windows
5. **Validazione end-to-end**: test manuali su app reali, tuning parametri (VAD, filler words list)

## Idee future (non in scope v1)

- Vocabolario personalizzato via initial prompt di Whisper (nomi propri, gergo tecnico)
- Comandi vocali ("nuova riga", "cancella ultima frase")
- Hotkey alternativo per modalità "solo clipboard" (senza auto-paste)
- Packaging come eseguibile standalone (PyInstaller) per distribuzione/comodità
- Rivalutazione di FAMA quando il tooling sarà più maturo
- Pulizia opzionale via LLM (con API key configurabile), se la qualità rule-based risultasse insufficiente in uso reale
