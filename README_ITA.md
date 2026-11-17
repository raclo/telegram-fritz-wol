[English](README.md) | [Italiano](README_ITA.md)

# telegram-fritz-wol

Bot Telegram leggero per accendere i computer configurati attraverso un FRITZ!Box
tramite TR-064. Usa long polling, non richiede porte pubbliche o webhook e non
utilizza database. Repository: [raclo/telegram-fritz-wol](https://github.com/raclo/telegram-fritz-wol).

Il deployment può essere gestito con **Docker Compose** oppure **Portainer su
Docker Standalone**. L'applicazione è la stessa: scegliere un solo gestore per
il deployment ed eseguire una sola istanza per token Telegram. Impostare
`BOT_LANGUAGE=en` oppure `BOT_LANGUAGE=it` per tutti i messaggi e pulsanti del bot.
La lingua predefinita è **inglese** (`en`); vale per l'intera istanza e non segue
la lingua Telegram del singolo utente.

## Funzionalità e comandi

- Allowlist esplicita di user ID Telegram, controllata per comandi e callback inline.
- Accesso solo in chat privata; appartenenza a gruppi e username non autorizzano.
- Configurazione dispositivi in JSON esterno, con pulsanti Accendi e Stato.
- Chiamate TR-064 autenticate, timeout HTTP limitati e messaggi di errore sicuri.
- Container non root, filesystem in sola lettura, nessuna porta pubblicata,
  nessuna capability Linux e nessun accesso al socket Docker.

| Comando | Azione |
| --- | --- |
| `/start`, `/help` | Istruzioni e pulsanti dei dispositivi |
| `/list` | Elenco dispositivi con pulsanti Accendi e Stato |
| `/wol [id]` | Richiede WoL per un dispositivo oppure mostra la selezione |
| `/status [id]` | Legge la segnalazione del router oppure mostra la selezione |

Dopo aver configurato gli ID di esempio, usare `/wol desktop-pc` o `/status desktop-pc`.
Il bot accetta solo gli ID configurati, mai MAC arbitrari ricevuti da Telegram.

### Indicatore di attività Telegram

Per una richiesta `/wol` o `/status` autorizzata e relativa a un dispositivo
configurato, il bot invia una sola azione nativa Telegram `typing` prima
dell'operazione. I pulsanti inline fanno lo stesso, dopo aver confermato la
callback come prima. Selezioni non valide e richieste non autorizzate non lo
attivano. Non vengono inviati, modificati o cancellati messaggi temporanei;
se l'azione fallisce, l'operazione prosegue comunque.

Telegram mostra l'indicatore per **circa cinque secondi al massimo**, oppure fino
a un messaggio del bot che lo rimuove. Il bot non lo rinnova. Se il router impiega
più tempo, l'indicatore può scomparire mentre la richiesta è ancora in corso:
attendere la risposta finale. È un segnale di attività, non una misura di
avanzamento o una conferma del successo del WoL. Timeout TR-064, serializzazione
e intervallo minimo fra tentativi restano invariati.

### Significato di WoL e stato

WoL invoca `Hosts1 / X_AVM-DE_WakeOnLANByMACAddress` con `NewMACAddress`.
Il successo significa che il FRITZ!Box ha accettato la richiesta, **non che il
computer sia acceso**. La risposta può andare persa dopo l'invio: l'applicazione
non ritenta automaticamente il WoL. Ogni dispositivo ha un intervallo minimo di
10 secondi fra i tentativi, anche dopo errori; il limite è in memoria e si azzera
al riavvio del bot.

`/status` invoca `Hosts1 / GetSpecificHostEntry` solo per il MAC selezionato:

| Risultato | Significato |
| --- | --- |
| `NewActive=true` | Attivo secondo il router, potenzialmente raggiungibile |
| `NewActive=false` | Inattivo secondo il router, raggiungibilità non rilevata |
| SOAP fault 714 o stato non interpretabile | Sconosciuto, senza dedurre che sia offline |
| Errore di connessione, timeout o autenticazione | Errore del router, non stato di accensione del computer |

La segnalazione può essere ritardata. Non vengono eseguiti ping, controlli TCP o
scansioni della LAN; lo stato non conferma accensione, spegnimento o disponibilità
del sistema operativo. Per tale conferma verificare un servizio sul computer.

## Requisiti

- FRITZ!Box con TR-064 abilitato e WoL già funzionante per i dispositivi previsti.
- Credenziali FRITZ!Box autorizzate alle azioni necessarie. Preferire un utente
  dedicato con i permessi richiesti dalla propria versione FRITZ!OS; il bot non
  crea utenti e non modifica le impostazioni del router.
- Token Telegram da BotFather e user ID numerici verificati da autorizzare.
- Docker e, per il percorso CLI, Docker Compose **2.30 o successivo** per
  `env_file` raw. Per il percorso GUI, Portainer con Docker Standalone.
  Queste istruzioni non dichiarano supporto per Docker Swarm.
- Accesso in uscita al router sulla TCP `49000`, DNS e HTTPS verso
  `api.telegram.org:443`. Non esporre TR-064 su Internet.
- Host sempre acceso. Un bot ospitato sul computer che viene spento non può
  riaccendere quello stesso host mentre è spento.

Il Dockerfile usa Python 3.13 su `python:3.13-slim-bookworm`. Le dipendenze dirette
sono `python-telegram-bot==22.8` e `fritzconnection==1.15.1`;
[requirements.txt](requirements.txt) fissa anche le dipendenze transitive. Il tag
dell'immagine base può cambiare: la build non è vincolata al suo digest.

## Configurazione comune

Scaricare i sorgenti e lavorare dalla radice del repository. I comandi seguenti
sono per **nuove installazioni**; durante gli aggiornamenti conservare i file
esistenti.

```sh
git clone https://github.com/raclo/telegram-fritz-wol.git
cd telegram-fritz-wol
mkdir -p secrets
cp config/devices.example.json secrets/devices.json
```

Sostituire ogni placeholder MAC in `secrets/devices.json` con il MAC reale
dell'interfaccia che supporta WoL. L'esempio non può superare la validazione
finché non viene compilato. Non aggiungere il file compilato a Git.

`desktop-pc` / `Desktop PC` e `home-server` / `Home Server` sono esempi generici.
Scegliere ID e nomi propri prima del primo deployment. Su un deployment esistente
mantenere invariato il JSON privato: rinominare gli esempi non richiede migrazioni
e non cambia i payload delle callback dei dispositivi configurati. Il bot legge
gli ID dal JSON, senza fissarli nel codice. `.env.example` usa placeholder per
indirizzo del router, user ID Telegram e credenziali: sostituirli privatamente
con i valori della propria rete. L'indirizzo nella tabella seguente è il default
dell'applicazione, non un indirizzo obbligatorio o una descrizione della rete
del manutentore.

Ogni dispositivo deve contenere esattamente `id`, `name` e `mac`. Sono ammessi
1–32 dispositivi. Gli ID sono univoci, lunghi 1–24 caratteri, iniziano con una
lettera minuscola o una cifra e contengono solo `a-z`, cifre, `_` o `-`. I nomi
hanno 1–32 caratteri stampabili senza spazi iniziali o finali. I MAC devono essere
unicast non nulli, con sei coppie separate da `:`; MAC, ID o chiavi JSON duplicati
vengono rifiutati. Vedere [config/devices.example.json](config/devices.example.json).

| Variabile | Significato | Default / obbligatorietà |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | Token BotFather | Obbligatorio |
| `TELEGRAM_ALLOWED_USER_IDS` | User ID numerici separati da virgole | Obbligatori |
| `FRITZ_ADDRESS` | IPv4 privato del router | Default app: `192.168.178.1`; obbligatorio nello YAML Portainer |
| `FRITZ_USERNAME` | Utente FRITZ!Box | Obbligatorio |
| `FRITZ_PASSWORD` | Password FRITZ!Box | Obbligatoria |
| `FRITZ_TIMEOUT_SECONDS` | Timeout per richiesta HTTP, 1–15 secondi | Opzionale; `5` in entrambi i percorsi |
| `BOT_LANGUAGE` | Lingua dell'istanza: `en` oppure `it` | Opzionale; `en` |
| `DEVICES_FILE` | Percorso JSON nel processo | Entrambi gli YAML impostano `/app/config/devices.json` |

Usare **user ID**, non username o ID di gruppi. Non inserire credenziali in issue,
README, screenshot o YAML versionati. La configurazione viene caricata all'avvio.
Sono ammessi solo i codici esatti `en` e `it`; gli altri vengono rifiutati
all'avvio con un errore sicuro che non riporta il valore ricevuto. Comandi,
ID dei dispositivi e payload delle callback non cambiano con la lingua.

### Permessi del bind mount JSON

L'immagine usa **UID/GID `10001:10001`**. Il JSON deve esistere sull'host Docker ed
essere leggibile da tale identità. Viene montato in sola lettura; Docker non crea
il percorso sorgente mancante. In una tipica installazione Docker rootful:

```sh
sudo chgrp 10001 secrets secrets/devices.json
sudo chmod 0750 secrets
sudo chmod 0640 secrets/devices.json
```

I comandi mantengono il proprietario attuale e concedono l'accesso al gruppo
`10001`. Il daemon Docker deve poter attraversare il percorso host. Con Docker
rootless o rimappatura degli user namespace verificare prima gli ID host
corrispondenti; questi comandi non dimostrano compatibilità con tali modalità.
Evitare configurazioni leggibili da tutti e modifiche ricorsive estese ai permessi.

## Deployment con Docker Compose

### 1. Configurare le variabili d'ambiente

Per una nuova installazione CLI:

```sh
cp .env.example .env
chmod 0600 .env
```

Inserire in `.env` token, user ID e credenziali reali del router. Il servizio lo
legge con `format: raw`: non racchiudere i valori fra virgolette, non aggiungere
commenti inline e non eseguire `source .env`. Caratteri come `$` e `#` sono
letterali. `.env` e `secrets/` sono già esclusi da Git.
Per l'italiano impostare `BOT_LANGUAGE=it`; per l'inglese mantenere
`BOT_LANGUAGE=en` dell'esempio. Il timeout d'esempio resta `FRITZ_TIMEOUT_SECONDS=5`.

I comandi seguenti usano `--env-file .env.example` per l'interpolazione di Compose,
mentre il servizio carica comunque il proprio ambiente reale da `.env`. Si evita
così che Compose interpreti implicitamente il file delle credenziali per
l'interpolazione. `BOT_ENV_FILE` seleziona un file sul lato host ed è usato solo
nella validazione dell'esempio seguente; lasciarlo non impostato nel deployment
CLI normale.

### 2. Validare lo YAML senza avviare servizi

```sh
BOT_ENV_FILE=.env.example docker compose --env-file .env.example -f compose.yaml config --quiet
```

Il controllo valida la struttura con placeholder; non verifica credenziali,
MAC, permessi del mount o connettività.

### 3. Costruire e avviare

```sh
docker compose --env-file .env.example -f compose.yaml up -d --build
```

`compose.yaml` costruisce dai sorgenti locali e monta `./secrets/devices.json`.
Non occorrono un'immagine applicativa precompilata o un account su un registry.

### 4. Controllare e arrestare

```sh
docker compose --env-file .env.example -f compose.yaml ps
docker compose --env-file .env.example -f compose.yaml logs --tail=100 -f bot
docker compose --env-file .env.example -f compose.yaml stop
```

L'arresto interrompe il bot: eseguirlo solo quando previsto. Dopo l'avvio provare
il bot da una chat Telegram privata autorizzata. Un container in esecuzione non
dimostra da solo la connettività con Telegram o TR-064.

## Deployment con Portainer

### 1. Costruire l'immagine locale sull'host Docker di destinazione

Dalla directory dei sorgenti sull'**host Docker gestito dall'ambiente Portainer
selezionato**, costruire il tag esatto indicato da
[compose.portainer.yaml](compose.portainer.yaml):

```sh
docker build -t telegram-fritz-wol:local .
```

Il comando costruisce l'immagine e non avvia il bot. Il tag è locale, non
un'immagine pubblicata su Docker Hub. Costruirla sul portatile o sul server
Portainer non basta se l'endpoint Docker scelto è un altro host. Questo file
stack non contiene `build:`, quindi Portainer non costruisce l'applicazione.

### 2. Preparare il percorso JSON sull'host

Lo YAML distribuito usa questo percorso sorgente assoluto:

```text
/srv/docker/telegram-fritz-wol/secrets/devices.json
```

Collocare il JSON compilato lì sull'**host Docker di destinazione**, applicando i
permessi UID/GID comuni descritti sopra. Se il checkout è altrove, adattare
`volumes.source` nella definizione dello stack da distribuire. Il percorso è un
esempio di deployment, non una directory di installazione obbligatoria. Non è un
percorso nel container Portainer o nel computer da cui si usa il browser.

### 3. Inserire le variabili nella GUI Portainer

Selezionare l'ambiente Docker Standalone, aprire **Stacks → Add stack**, chiamare
lo stack `telegram-fritz-wol`, scegliere **Web editor** e incollare il contenuto di
`compose.portainer.yaml`. Nella sezione **Environment variables** configurare le
seguenti sette variabili: cinque obbligatorie e due con valore predefinito:

| Variabile | Obbligatoria nella GUI | Valore / default |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | Sì | Token del bot |
| `TELEGRAM_ALLOWED_USER_IDS` | Sì | User ID numerici autorizzati, separati da virgole |
| `FRITZ_ADDRESS` | Sì | IPv4 privato del router |
| `FRITZ_USERNAME` | Sì | Utente FRITZ!Box |
| `FRITZ_PASSWORD` | Sì | Password FRITZ!Box |
| `FRITZ_TIMEOUT_SECONDS` | No | `5`; intervallo ammesso 1–15 secondi |
| `BOT_LANGUAGE` | No | `en`; impostare `it` per l'italiano |

`DEVICES_FILE` è già fissata nello YAML. Non aggiungerla nella GUI.
Tutte le cinque sostituzioni `${...:?required}` devono essere valorizzate.
Inserire i valori direttamente, senza assegnazioni shell o virgolette esterne.

In alternativa, selezionare **Load variables from .env file** nella stessa sezione
GUI e caricare un file d'ambiente compilato privatamente dal computer del browser.
Usare `.env.example` come modello, sostituire i placeholder in privato e mantenere
solo le sette chiavi elencate. L'operazione importa i valori in Portainer: non
legge un percorso `.env` arbitrario sull'host Docker. Controllare privatamente i
valori importati, soprattutto password con caratteri speciali: l'importazione
GUI non usa il lettore `format: raw` del servizio CLI. Non versionare o condividere
il file compilato e non sovrascrivere credenziali esistenti con valori d'esempio.

Nel deployment Portainer reale non ha funzionato l'uso diretto di un `env_file`
con percorso host; questa variante usa invece variabili della GUI sostituite in
voci `environment` esplicite. Seguire questo percorso senza aggiungere `.env`
come `env_file` con percorso host. Per questo deployment Portainer non serve il
file `.env` usato dalla CLI. Inserimento singolo e importazione GUI usano le
stesse voci `environment` esplicite nello YAML. Vedere la
[documentazione degli stack Portainer](https://docs.portainer.io/user/docker/stacks/add).

Lo YAML Portainer ora inoltra entrambe le impostazioni opzionali e usa
`FRITZ_TIMEOUT_SECONDS=5` e `BOT_LANGUAGE=en` se omesse o vuote. I valori di lingua
esplicitamente non supportati vengono rifiutati dall'applicazione. Il file raw
della CLI inoltra invece i valori letteralmente: un `BOT_LANGUAGE=` esplicitamente
vuoto è quindi invalido; omettere la chiave per usare il default applicativo.

### 4. Distribuire e controllare

Selezionare **Deploy the stack**. Lasciare disabilitata l'opzione di riscaricare
l'immagine dal registry per il tag locale. Controllare il container del bot nello
stack e la sua vista **Logs**, quindi provare da una chat privata autorizzata.
Per arrestarlo usare l'azione di stop dello stack. Non avviare una seconda istanza
gestita dalla CLI con lo stesso token.

## Aggiornamenti e modifiche alla configurazione

Effettuare prima il backup. Esaminare le modifiche a monte e ottenere la revisione
desiderata; con checkout non modificato, `git pull --ff-only` aggiorna senza
riscrivere la cronologia. Risolvere le modifiche locali prima dell'aggiornamento.
Cambiare i sorgenti non sostituisce da solo il container in esecuzione.

Prima della nuova build conservare l'immagine attualmente usata dal bot. Per i
deployment CLI, sullo stesso host Docker:

```sh
wol_previous_image=$(docker compose --env-file .env.example -f compose.yaml images --quiet bot)
docker image tag "$wol_previous_image" telegram-fritz-wol:rollback
```

Per Portainer, individuare l'ID immagine del bot attivo nei dettagli del container,
poi eseguire sull'endpoint Docker scelto, sostituendo il placeholder:

```sh
docker image tag REPLACE_WITH_RUNNING_IMAGE_ID telegram-fritz-wol:rollback
```

Conservare privatamente anche revisione dei sorgenti e configurazione
corrispondenti. Mantenere l'immagine di rollback fino alla verifica
dell'aggiornamento; non eliminarla con operazioni di pulizia e non sovrascrivere
il tag se quella versione serve ancora.

**Docker Compose:** ricostruire e ricreare il bot dalla radice del repository:

```sh
docker compose --env-file .env.example -f compose.yaml up -d --build --force-recreate bot
```

**Portainer:** ricostruire `telegram-fritz-wol:local` sullo stesso endpoint Docker:

```sh
docker build -t telegram-fritz-wol:local .
```

Aprire poi **Editor** nello stack esistente, conservare variabili d'ambiente e
percorso host e selezionare **Update the stack** senza riscaricare dal registry.
Verificare che il container venga ricreato con la nuova immagine. Per una modifica
al solo JSON, usare l'azione Portainer di ricreazione del container se
l'aggiornamento dello stack lo lascia invariato. Gestire gli aggiornamenti
successivi tramite lo stesso stack.

### Aggiornare un deployment esistente mantenendo l'italiano

Il bot precedente rispondeva in italiano; la nuova immagine senza `BOT_LANGUAGE`
usa l'inglese. Per mantenere l'italiano impostare **`BOT_LANGUAGE=it`** prima
della ricreazione:

1. Conservare JSON e credenziali attuali. Non copiare `.env.example` sopra un
   `.env` esistente e non importare placeholder sopra uno stack Portainer attivo.
2. Per la CLI, aggiungere o aggiornare solo `BOT_LANGUAGE=it` nel `.env` esistente,
   conservando credenziali e timeout correnti.
3. Per Portainer, aggiornare la definizione dello stack esistente da
   `compose.portainer.yaml` conservando l'eventuale percorso host personalizzato.
   Mantenere i cinque valori GUI obbligatori, aggiungere `BOT_LANGUAGE=it` e
   impostare `FRITZ_TIMEOUT_SECONDS` solo se si desidera un timeout diverso dal
   default. Per questo aggiornamento preferire la modifica manuale dei campi
   opzionali nella GUI. Se si importa un file, includere i valori obbligatori
   esistenti corretti e verificare ogni campo prima di applicare la modifica.
4. **Le modifiche al codice richiedono una nuova build e la ricreazione del
   container.** Usare il percorso di ricostruzione e deployment descritto sopra:
   un riavvio mantiene immagine e ambiente precedenti. Dopo il deployment
   pianificato controllare log e lingua del bot.

Entrambi i percorsi rileggono la configurazione solo in un nuovo processo.
Cambiare variabili richiede la ricreazione, non il semplice riavvio del container
esistente. Ricreare anche dopo modifiche al JSON: un editor che sostituisce il
file può lasciare il bind mount sul vecchio inode. A ogni avvio del bot vengono
scartati gli aggiornamenti Telegram in attesa, evitando comandi accodati durante
la fermata.

### Rollback dell'immagine Docker

Se un aggiornamento fallisce, usare l'immagine conservata invece di ricostruire
vecchi sorgenti con un'immagine base potenzialmente cambiata. Per Docker Compose,
questo override temporaneo seleziona l'immagine locale salvata e disabilita
esplicitamente build e pull:

```sh
docker compose --env-file .env.example -f compose.yaml -f - up -d --no-build --pull never --force-recreate bot <<'YAML'
services:
  bot:
    image: telegram-fritz-wol:rollback
YAML
```

Per Portainer, cambiare solo `image` nello stack in `telegram-fritz-wol:rollback`,
lasciare disabilitato il nuovo download dal registry, conservare ambiente e bind
mount e aggiornare lo stack esistente per ricreare il bot. Ripristinare la
configurazione privata corrispondente se il formato è cambiato, senza azzerare
le credenziali. Dopo il rollback controllare log e Telegram. Prima di un nuovo
aggiornamento ripristinare la selezione abituale dell'immagine
(`telegram-fritz-wol:local` per Portainer) e usare la revisione desiderata dei
sorgenti. Queste operazioni sostituiscono il container del bot e causano una breve
interruzione; non vengono eseguite automaticamente.

## Log e arresto

Per i log CLI usare il comando Compose precedente. In Portainer aprire
**Containers**, selezionare il bot dello stack, poi **Logs**. I log contengono
messaggi controllati e categorie di errore, senza URL con token, corpi SOAP,
credenziali o traceback delle eccezioni. Controllare gli export prima di
condividerli: i metadati Docker/Portainer possono esporre variabili d'ambiente.

Entrambi gli YAML ruotano i log JSON a 5 MB con tre file, usano il riavvio
`unless-stopped` e concedono 120 secondi all'arresto. `SIGINT`/`SIGTERM`
interrompono il polling e chiudono la sessione del router. I timeout TR-064 sono
per singola richiesta HTTP; la discovery iniziale può includere più richieste e
rendere lento il primo comando. Non è configurato un healthcheck: l'esistenza del
processo non è una verifica significativa della connettività end-to-end.

## Backup della configurazione e ripristino

Non ci sono database o volumi di stato applicativo. Salvare JSON compilato,
YAML scelto e revisione dei sorgenti, più `.env` della CLI oppure i valori delle
variabili Portainer. Conservare copie private, preferibilmente cifrate, con
permessi restrittivi. Non versionare backup o esportazioni dei dati Portainer.

Per il percorso CLI, questo esempio crea un archivio protetto nella directory
`secrets/`, già ignorata:

```sh
mkdir -p secrets/backups
chmod 0700 secrets/backups
(umask 077; tar -czf "secrets/backups/config-$(date +%Y%m%d-%H%M%S).tar.gz" .env secrets/devices.json)
```

L'archivio **non è cifrato**: trasferirlo in un archivio di backup protetto. Il
comando presuppone che esista `.env` della CLI. Per un deployment solo GUI,
salvare il JSON e conservare i valori Portainer configurati, inclusi lingua e
timeout, in un gestore di segreti
protetto; salvare separatamente anche la definizione dello stack distribuito.

Per ripristinare o migrare, riposizionare i file sull'host Docker di destinazione,
riapplicare l'accesso UID/GID, ripristinare le variabili con il gestore scelto,
costruire l'immagine su quell'host e distribuire una sola istanza. Ricostruire per
una nuova architettura CPU. Il progetto non ha verificato l'esecuzione su ARM o
Raspberry Pi: l'immagine base multiarch non dimostra da sola la compatibilità.

## Troubleshooting

| Sintomo | Controlli |
| --- | --- |
| Configurazione non valida o riavvii continui | Sostituire i placeholder, verificare JSON e variabili richieste. Errori di configurazione: codice `2`; errori fatali: `1`. |
| Accesso negato su Telegram | Verificare user ID numerico del mittente, allowlist e chat privata; gli stessi controlli valgono per le callback. |
| Conflitto Telegram / altra istanza di polling | Arrestare l'istanza duplicata con quel token. Usare un solo gestore del deployment. |
| Variabile obbligatoria mancante in Portainer | Compilare tutti i cinque campi GUI; non affidarsi a un `env_file` con percorso host. |
| Lingua errata o `BOT_LANGUAGE` non supportata | Usare esattamente `en` o `it`; il default è `en`. Impostare `it` per mantenere le risposte italiane precedenti e ricreare il container con la nuova immagine. |
| Pull dell'immagine Portainer fallito | Costruire `telegram-fritz-wol:local` sull'endpoint selezionato e disabilitare il nuovo download dal registry. |
| JSON mancante o non leggibile nel mount | Controllare percorso sull'host Docker, file esistente, GID `10001`, permessi `0640` ed eventuali user namespace. Ricreare dopo la sostituzione del file. |
| Errore di autenticazione/autorizzazione del router | Verificare localmente utente, password e permessi TR-064; non inserirli in log o issue. |
| Timeout / router indisponibile | Controllare indirizzo configurato, percorso LAN e TCP `49000`. La discovery iniziale può richiedere più timeout HTTP. |
| WoL accettato ma computer spento | Controllare alimentazione, interfaccia, impostazioni WoL di firmware/sistema operativo e MAC. L'accettazione non conferma l'avvio. |
| Stato inattivo o sconosciuto | La segnalazione del router può essere ritardata; il fault 714 indica una voce sconosciuta. Verificare separatamente un servizio sul dispositivo. |
| Nessuna risposta dopo lo spegnimento dell'host | Spostare il bot su un host sempre acceso. Non può riaccendere l'host spento su cui risiede. |

Non abilitare dump HTTP per diagnosticare credenziali: gli URL Telegram contengono
il token. Revocare o sostituire le credenziali divulgate prima di aprire una issue.

## Verifiche e sviluppo

I risultati seguenti rappresentano evidenze di tipo diverso:

| Verifica | Ambito e risultato |
| --- | --- |
| **71 test unitari** | Superati il 2026-11-17: i 63 test della revisione i18n più otto test dell'indicatore di attività. Mock offline e connessioni di rete bloccate; nessuna chiamata reale a router o Telegram. |
| **Collaudo manuale end-to-end precedente a questa revisione** | Il manutentore conferma il funzionamento in produzione in italiano e inglese tramite Telegram e TR-064, in Docker gestito da Portainer. Vedere l'hardware collaudato sotto. Il nuovo indicatore non è stato distribuito o collaudato dal vivo durante questa modifica. |

### Hardware effettivamente collaudato

Il manutentore riferisce un collaudo WoL end-to-end con **FRITZ!Box 5530 Fiber**,
un desktop configurato come destinazione e un host Docker gestito da Portainer.
Nomi host, MAC, ID Telegram personali e dettagli effettivi della rete di deployment
non servono per riprodurre la configurazione e sono intenzionalmente omessi.

Il collaudo reale non dimostra che ogni percorso di errore sia stato provato
sull'hardware. Altri modelli FRITZ!Box, ARM/Raspberry Pi e Docker Swarm non sono
stati verificati. Il percorso CLI è documentato a partire dal Compose fornito;
l'evidenza end-to-end dichiarata riguarda Portainer.

Riprodurre i controlli automatici dalla radice del repository senza pacchetti globali:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --no-cache-dir -r requirements.txt
.venv/bin/python -m unittest discover -v
.venv/bin/python -m compileall -q telegram_fritz_wol tests
.venv/bin/python -m pip check
BOT_ENV_FILE=.env.example docker compose --env-file .env.example -f compose.yaml config --quiet
docker compose --env-file .env.example -f compose.portainer.yaml config --quiet
```

I due controlli YAML usano valori di esempio non segreti e non avviano servizi.
I test coprono autorizzazioni, callback manipolate, configurazione, selezione WoL,
intervallo minimo, messaggi sullo stato, chiusura delle risorse ed errori. I test
SOAP usano il parser di `fritzconnection==1.15.1`: il 714 diventa `FritzLookUpError`,
produce stato sconosciuto per `/status` e resta un errore sicuro per WoL. Gli altri
fault, compreso il 606 di autorizzazione, restano errori. Token, ID e MAC dei test
sono sintetici.
I test delle lingue coprono completezza delle chiavi e dei placeholder nominati,
rendering, entrambe le lingue, rifiuto sicuro di codici non supportati, messaggi,
pulsanti ed errori tradotti, payload delle callback invariati, autorizzazioni,
WoL e intervallo minimo invariati.
I test di attività verificano typing prima di TR-064, ordine di conferma delle
callback, richieste non autorizzate/non valide, tolleranza agli errori dell'azione
Telegram ed entrambe le lingue.

Per validare offline le impostazioni reali, eseguire
`python -m telegram_fritz_wol --check-config` con le variabili già nell'ambiente
del processo e `DEVICES_FILE` diretto al JSON locale. L'entrypoint Python non
legge automaticamente `.env`. Il controllo verifica solo la configurazione,
non l'accettazione delle credenziali da parte dei servizi remoti.

## Architettura e sicurezza

| Modulo | Responsabilità |
| --- | --- |
| `config.py` | Validazione offline di ambiente e dispositivi |
| `i18n.py` | Dizionari italiano/inglese e rendering con placeholder nominati |
| `bot.py` | Handler Telegram asincroni, autorizzazioni e pulsanti inline |
| `service.py` | Allowlist dispositivi, intervallo minimo e messaggi sicuri |
| `router.py` | Adattatore TR-064 autenticato e classificazione degli errori |
| `__main__.py` | Logging, controllo configurazione e ciclo di polling |

Le operazioni TR-064 bloccanti usano `asyncio.to_thread`. Aggiornamenti e chiamate
al router sono serializzati; il client viene creato al primo utilizzo e riusato.
Vengono richiesti solo aggiornamenti `message` e `callback_query`.

Telegram usa HTTPS verificato. TR-064 usa **HTTP Digest sulla LAN**: autentica
le richieste, ma HTTP non cifra il traffico e non verifica il router con un
certificato. Usare una LAN fidata o un percorso di rete protetto. Il progetto
non abilita la modalità TLS della libreria, che in questa versione disabilita
la verifica del certificato del router.

I segreti sono esclusi da Git e dal contesto di build Docker. Gli amministratori
Docker e Portainer possono comunque leggere le variabili del container: non sono
un archivio segreti. Entrambi i deployment usano `no-new-privileges`, rimuovono
tutte le capability e non richiedono host networking o modalità privilegiata.

## Licenza e riferimenti

[Licenza MIT](LICENSE). Copyright (c) 2026 Carlo Catapano.

- [FRITZ! TR-064: azioni Hosts](https://fritz.support/resources/TR-064_Hosts.pdf)
- [FRITZ! TR-064: autenticazione](https://fritz.support/resources/TR-064_Authentication.pdf)
- [python-telegram-bot 22.8: ciclo di vita](https://docs.python-telegram-bot.org/en/v22.8/telegram.ext.application.html)
- [Documentazione API fritzconnection](https://fritzconnection.readthedocs.io/en/1.15.0/sources/fritzconnection_api.html)
- [Docker Compose: file d'ambiente](https://docs.docker.com/reference/compose-file/services/#env_file)
- [Portainer: creazione stack e variabili](https://docs.portainer.io/user/docker/stacks/add)
- [Portainer: modifica e aggiornamento stack](https://docs.portainer.io/user/docker/stacks/edit)
- [Portainer: log dei container](https://docs.portainer.io/user/docker/containers/logs)
