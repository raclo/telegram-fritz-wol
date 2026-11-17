"""Instance-wide translations. Templates use named placeholders only."""

MESSAGES = {
    "en": {
        "help": (
            "Wake-on-LAN through your FRITZ!Box.\n"
            "/start or /help — instructions\n"
            "/list — devices and buttons\n"
            "/wol [id] — request WoL or select a device\n"
            "/status [id] — router-reported status or device selection\n"
            "WoL does not confirm power-on. Router information may be out of date."
        ),
        "access_denied": "Access denied: unauthorized user or non-private chat.",
        "button_wol": "Wake {name}",
        "button_status": "Status {name}",
        "device_entry": "{id} — {name}",
        "device_list": "Configured devices:\n{devices}",
        "select_device": "Select a device:",
        "command_usage": "Usage: /{action} [id]. See /list.",
        "message_unavailable": "Message unavailable. Use /list.",
        "invalid_selection": "Invalid selection. Use /list.",
        "unknown_command": "Unknown command. Use /help.",
        "operation_failed": "Operation incomplete. Outcome unconfirmed; try again later.",
        "not_configured": "Device or action not configured. Use /list.",
        "cooldown": "Wait 10 seconds between WoL attempts for the same device.",
        "wol_accepted": (
            "{name}: WoL request accepted by the FRITZ!Box. Power-on has not been verified. "
            "Check /status or a service on the computer."
        ),
        "wol_error": "{error} WoL outcome unconfirmed; the command may have been sent.",
        "error_authentication": "FRITZ!Box authentication failed: check username, password and TR-064 permissions.",
        "error_timeout": "FRITZ!Box request timed out.",
        "error_connection": "FRITZ!Box unreachable.",
        "error_unknown_host": "The FRITZ!Box does not recognize this device.",
        "error_router": "TR-064 request rejected or service unavailable.",
        "status_active": "active, potentially reachable",
        "status_inactive": "inactive, reachability not detected",
        "status_unknown": "unknown, reachability undetermined",
        "status_result": (
            "{name}: router-reported status: {state}. Router information may be out of date. "
            "Power-on or power-off has not been verified. No direct reachability test was performed."
        ),
        "config_language": "Unsupported BOT_LANGUAGE. Use en or it.",
        "config_required": "Set {variable} to a real value.",
        "config_duplicate_key": "Duplicate JSON key in the devices file.",
        "config_file_size": "Devices file too large (maximum 64 KiB).",
        "config_file_invalid": "Devices file unreadable or invalid JSON.",
        "config_devices_key": "JSON must contain only the devices list.",
        "config_device_count": "Configure between 1 and 32 devices.",
        "config_device_fields": "Each device requires only id, name and mac.",
        "config_device_id": "Invalid device ID: use 1-24 characters from a-z, 0-9, _ or -; start with a letter or digit.",
        "config_device_name": "Invalid device name: use 1-32 printable characters without surrounding spaces.",
        "config_device_mac": "Invalid MAC: replace placeholders with real colon-separated MAC addresses.",
        "config_mac_unicast": "MAC must identify a nonzero unicast device.",
        "config_duplicate_device": "Duplicate device ID or MAC.",
        "config_token": "Invalid TELEGRAM_BOT_TOKEN format.",
        "config_user_ids": "TELEGRAM_ALLOWED_USER_IDS requires numeric IDs separated by commas.",
        "config_user_id_range": "TELEGRAM_ALLOWED_USER_IDS contains an out-of-range ID.",
        "config_address": "FRITZ_ADDRESS requires the router's IPv4 address.",
        "config_address_private": "FRITZ_ADDRESS must be a private LAN IPv4 address.",
        "config_timeout_numeric": "FRITZ_TIMEOUT_SECONDS must be numeric.",
        "config_timeout_range": "FRITZ_TIMEOUT_SECONDS must be between 1 and 15.",
    },
    "it": {
        "help": (
            "Wake-on-LAN tramite FRITZ!Box.\n"
            "/start o /help — istruzioni\n"
            "/list — dispositivi e pulsanti\n"
            "/wol [id] — richiedi WoL o seleziona un dispositivo\n"
            "/status [id] — stato segnalato dal router o selezione del dispositivo\n"
            "WoL non conferma l'accensione. Le informazioni del router potrebbero non essere aggiornate."
        ),
        "access_denied": "Accesso negato: utente non autorizzato o chat non privata.",
        "button_wol": "Accendi {name}",
        "button_status": "Stato {name}",
        "device_entry": "{id} — {name}",
        "device_list": "Dispositivi configurati:\n{devices}",
        "select_device": "Seleziona un dispositivo:",
        "command_usage": "Uso: /{action} [id]. Vedere /list.",
        "message_unavailable": "Messaggio non disponibile. Usare /list.",
        "invalid_selection": "Selezione non valida. Usare /list.",
        "unknown_command": "Comando non riconosciuto. Usare /help.",
        "operation_failed": "Operazione non completata. Esito non confermato; riprovare più tardi.",
        "not_configured": "Dispositivo o azione non configurati. Usare /list.",
        "cooldown": "Attendere 10 secondi tra i tentativi WoL per lo stesso dispositivo.",
        "wol_accepted": (
            "{name}: richiesta WoL accettata dal FRITZ!Box. L'accensione non è stata verificata. "
            "Controllare /status o un servizio del computer."
        ),
        "wol_error": "{error} Esito WoL non confermato; il comando potrebbe essere stato inviato.",
        "error_authentication": "Autenticazione FRITZ!Box fallita: controllare utente, password e permessi TR-064.",
        "error_timeout": "La richiesta al FRITZ!Box ha superato il tempo di attesa.",
        "error_connection": "FRITZ!Box non raggiungibile.",
        "error_unknown_host": "Il FRITZ!Box non riconosce questo dispositivo.",
        "error_router": "Richiesta TR-064 rifiutata o servizio non disponibile.",
        "status_active": "attivo, potenzialmente raggiungibile",
        "status_inactive": "inattivo, raggiungibilità non rilevata",
        "status_unknown": "sconosciuto, raggiungibilità non determinabile",
        "status_result": (
            "{name}: stato segnalato dal FRITZ!Box: {state}. "
            "Le informazioni del router potrebbero non essere aggiornate. "
            "L'accensione o lo spegnimento non sono stati verificati. "
            "Non è stato eseguito un test diretto di raggiungibilità."
        ),
        "config_language": "BOT_LANGUAGE non supportata. Usare en o it.",
        "config_required": "Configurare {variable} con un valore reale.",
        "config_duplicate_key": "Chiave JSON duplicata nel file dispositivi.",
        "config_file_size": "File dispositivi troppo grande (massimo 64 KiB).",
        "config_file_invalid": "File dispositivi non leggibile o JSON non valido.",
        "config_devices_key": "Il JSON deve contenere soltanto la lista devices.",
        "config_device_count": "Configurare da 1 a 32 dispositivi.",
        "config_device_fields": "Ogni dispositivo richiede soltanto id, name e mac.",
        "config_device_id": "ID dispositivo non valido: usare 1-24 caratteri a-z, 0-9, _ o -; iniziare con una lettera o cifra.",
        "config_device_name": "Nome dispositivo non valido: usare 1-32 caratteri stampabili senza spazi iniziali o finali.",
        "config_device_mac": "MAC non valido: sostituire i placeholder con MAC reali separati da due punti.",
        "config_mac_unicast": "Il MAC deve identificare un dispositivo unicast non nullo.",
        "config_duplicate_device": "ID o MAC dispositivo duplicato.",
        "config_token": "Formato TELEGRAM_BOT_TOKEN non valido.",
        "config_user_ids": "TELEGRAM_ALLOWED_USER_IDS richiede ID numerici separati da virgole.",
        "config_user_id_range": "TELEGRAM_ALLOWED_USER_IDS contiene un ID fuori intervallo.",
        "config_address": "FRITZ_ADDRESS richiede l'indirizzo IPv4 del router.",
        "config_address_private": "FRITZ_ADDRESS deve essere un indirizzo IPv4 privato della LAN.",
        "config_timeout_numeric": "FRITZ_TIMEOUT_SECONDS deve essere numerico.",
        "config_timeout_range": "FRITZ_TIMEOUT_SECONDS deve essere compreso tra 1 e 15.",
    },
}


def translate(language: str, key: str, **values: str) -> str:
    return MESSAGES[language][key].format(**values)
