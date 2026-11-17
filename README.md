[English](README.md) | [Italiano](README_ITA.md)

# telegram-fritz-wol

A lightweight Telegram bot that wakes configured computers through a FRITZ!Box
using TR-064. It uses long polling, requires no public ports or webhooks, and
stores no database. Repository: [raclo/telegram-fritz-wol](https://github.com/raclo/telegram-fritz-wol).

Deploy with **Docker Compose** or **Portainer on Docker Standalone**. Both run the
same application; choose one manager for a deployment, and run only one bot
instance per Telegram token. Set `BOT_LANGUAGE=en` or `BOT_LANGUAGE=it` for all
bot replies and inline buttons. The default is **English** (`en`); the setting
applies to the whole instance, not to each user's Telegram language.

## Features and commands

- Explicit Telegram user ID allowlist, checked for commands and inline callbacks.
- Private chats only; group membership and Telegram usernames do not grant access.
- External JSON device configuration, with inline buttons for wake and status.
- Authenticated TR-064 requests, bounded HTTP timeouts and safe error messages.
- Non-root container, read-only filesystem, no published ports, no Linux
  capabilities and no Docker socket access.

| Command | Action |
| --- | --- |
| `/start`, `/help` | Instructions and device buttons |
| `/list` | Configured devices, with wake and status buttons |
| `/wol [id]` | Request WoL for a device, or display a selection |
| `/status [id]` | Read the router's observation for a device, or display a selection |

After configuring the example device IDs, use `/wol desktop-pc` or `/status desktop-pc`.
The bot accepts only configured IDs, never arbitrary MAC addresses from Telegram.

### Telegram activity indicator

For an authorized `/wol` or `/status` request for a configured device, the bot
sends one native Telegram `typing` chat action before starting the operation.
The inline buttons do the same, after acknowledging the callback as before.
Invalid selections and unauthorized requests do not trigger it. No temporary
messages are posted, edited or deleted; if the chat action fails, the operation
still proceeds.

Telegram displays the action for **up to about five seconds**, or until a bot
message clears it. The bot does not refresh it. If the router takes longer,
the indicator can disappear while the request is still running; wait for the
final response. It is feedback, not progress tracking or proof of WoL success.
TR-064 timeouts, serialization and the WoL cooldown are unchanged.

### What wake and status mean

WoL calls `Hosts1 / X_AVM-DE_WakeOnLANByMACAddress` with `NewMACAddress`.
Success means the FRITZ!Box accepted the request, **not that the computer is on**.
A lost response may occur after the command was sent, so the application does not
retry WoL automatically. Each device has a 10-second cooldown between attempts,
including failed attempts; this in-memory limit resets when the bot restarts.

`/status` calls `Hosts1 / GetSpecificHostEntry` for the selected MAC only:

| Result | Meaning |
| --- | --- |
| `NewActive=true` | Active according to the router; potentially reachable |
| `NewActive=false` | Inactive according to the router; reachability not detected |
| SOAP fault 714 or uninterpretable state | Unknown, not proof of being offline |
| Connection, timeout or authentication failure | Router error, not a computer power state |

The observation can be stale. No direct ping, TCP check or LAN scan is performed;
status does not confirm power-on, power-off or operating-system readiness. Check
a service on the target computer if you need that confirmation.

## Requirements

- A FRITZ!Box with TR-064 enabled and WoL already working for the target devices.
- FRITZ!Box credentials authorized to use the required actions. Prefer a dedicated
  user with the permissions required by your FRITZ!OS installation; the bot does
  not create users or change router settings.
- A Telegram bot token from BotFather and verified numeric user IDs to authorize.
- Docker and, for the CLI workflow, Docker Compose **2.30 or newer** for raw
  `env_file` support. For the GUI workflow, use Portainer with Docker Standalone.
  These instructions do not claim Docker Swarm support.
- Outbound access to the router on TCP `49000`, and DNS/HTTPS access to
  `api.telegram.org:443`. Do not expose TR-064 to the Internet.
- An always-on host. A bot hosted on the computer you turn off cannot wake that
  same host while it is off.

The Dockerfile uses Python 3.13 on `python:3.13-slim-bookworm`. Direct dependencies
are `python-telegram-bot==22.8` and `fritzconnection==1.15.1`;
[requirements.txt](requirements.txt) also pins transitive dependencies. The base
image tag can change; the build is not locked to a base-image digest.

## Shared configuration

Get the source and work from the repository root. The following setup commands
are for **new installations**; preserve existing configuration on upgrades.

```sh
git clone https://github.com/raclo/telegram-fritz-wol.git
cd telegram-fritz-wol
mkdir -p secrets
cp config/devices.example.json secrets/devices.json
```

Replace every MAC placeholder in `secrets/devices.json` with the real MAC of the
interface that supports WoL. The example intentionally cannot pass validation
until completed. Do not commit the completed file.

`desktop-pc` / `Desktop PC` and `home-server` / `Home Server` are generic examples.
Choose your own IDs and names before first deployment. On an existing deployment,
keep your private JSON unchanged: these example renames do not require migration
or change callback payloads for configured devices. The bot reads IDs from your
JSON rather than hardcoding them. `.env.example` uses placeholders for the router
address, Telegram user IDs and credentials: replace them privately for your own
network. The router address in the table below is the application's default,
not a required address or a description of the maintainer's network.

Each device must contain exactly `id`, `name` and `mac`. There must be 1–32
devices. IDs are unique, 1–24 characters, beginning with a lowercase letter or
digit and containing only `a-z`, digits, `_` or `-`. Names are 1–32 printable
characters with no surrounding spaces. MAC addresses must be nonzero unicast
addresses with six colon-separated octets; duplicate MACs, IDs and JSON keys
are rejected. See [config/devices.example.json](config/devices.example.json).

| Variable | Meaning | Default / requirement |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | BotFather token | Required |
| `TELEGRAM_ALLOWED_USER_IDS` | Numeric user IDs separated by commas | Required |
| `FRITZ_ADDRESS` | Private IPv4 address of the router | App default: `192.168.178.1`; required in Portainer YAML |
| `FRITZ_USERNAME` | FRITZ!Box user | Required |
| `FRITZ_PASSWORD` | FRITZ!Box password | Required |
| `FRITZ_TIMEOUT_SECONDS` | Timeout per HTTP request, 1–15 seconds | Optional; `5` in both workflows |
| `BOT_LANGUAGE` | Instance-wide language: `en` or `it` | Optional; `en` |
| `DEVICES_FILE` | JSON path inside the process | Both YAML files set `/app/config/devices.json` |

Use **user IDs**, not usernames or group IDs. Never paste credentials into issues,
README files, screenshots or committed YAML. Configuration is loaded at startup.
Only the exact language codes `en` and `it` are supported; other values are
rejected at startup with a safe error that does not echo the supplied value.
Commands, device IDs and callback payloads do not change with the language.

### JSON bind mount permissions

The image runs as **UID/GID `10001:10001`**. The JSON must exist on the Docker
host and be readable by that identity. It is mounted read-only; Docker will not
create a missing source path. In a typical rootful Docker installation:

```sh
sudo chgrp 10001 secrets secrets/devices.json
sudo chmod 0750 secrets
sudo chmod 0640 secrets/devices.json
```

These commands retain the current owner while granting group `10001` access.
Ensure the Docker daemon can traverse the host path. With rootless Docker or
user-namespace remapping, check the mapped host IDs before changing ownership;
the commands above do not establish compatibility with those modes. Avoid
world-readable configuration and broad recursive permission changes.

## Deploy with Docker Compose

### 1. Configure environment variables

For a new CLI deployment:

```sh
cp .env.example .env
chmod 0600 .env
```

Edit `.env` with the real token, user IDs and router credentials. The service
reads it using `format: raw`: do not wrap values in quotes, append inline
comments, or run `source .env`. Characters such as `$` and `#` are literal.
`.env` and `secrets/` are already excluded from Git.
Set `BOT_LANGUAGE=it` if you want Italian; leave `BOT_LANGUAGE=en` from the
example for English. `FRITZ_TIMEOUT_SECONDS=5` remains the example timeout.

The commands below use `--env-file .env.example` for Compose interpolation,
while the service still loads its real environment from `.env`. This avoids
Compose implicitly parsing the credentials file for interpolation.
`BOT_ENV_FILE` is a host-side selector used only for the example validation below;
leave it unset for the normal CLI deployment.

### 2. Validate the YAML without starting a service

```sh
BOT_ENV_FILE=.env.example docker compose --env-file .env.example -f compose.yaml config --quiet
```

This validates structure using placeholders; it does not validate credentials,
MACs, mount permissions or connectivity.

### 3. Build and start

```sh
docker compose --env-file .env.example -f compose.yaml up -d --build
```

`compose.yaml` builds from the local source and mounts `./secrets/devices.json`.
No prebuilt application image or registry account is required.

### 4. Inspect and stop

```sh
docker compose --env-file .env.example -f compose.yaml ps
docker compose --env-file .env.example -f compose.yaml logs --tail=100 -f bot
docker compose --env-file .env.example -f compose.yaml stop
```

Stopping interrupts the bot; run it only when intended. After startup, test from
an authorized private Telegram chat. A running container alone does not prove
Telegram or TR-064 connectivity.

## Deploy with Portainer

### 1. Build the local image on the target Docker host

From the source directory on the **Docker host managed by the selected Portainer
environment**, build the exact tag referenced by
[compose.portainer.yaml](compose.portainer.yaml):

```sh
docker build -t telegram-fritz-wol:local .
```

This builds an image; it does not start the bot. The tag is local, not a published
Docker Hub image. Building on your laptop or the Portainer server is insufficient
if the selected Docker endpoint runs elsewhere. This stack file has no `build:`
section, so Portainer does not build the application for you.

### 2. Prepare the JSON host path

The supplied YAML uses this absolute bind source:

```text
/srv/docker/telegram-fritz-wol/secrets/devices.json
```

Place the completed JSON there on the **target Docker host**, applying the shared
UID/GID permissions above. If your checkout is elsewhere, adapt `volumes.source`
in the stack definition you deploy. The path is a deployment example, not a
required installation directory. It is not a path inside the Portainer container
or your browser's computer.

### 3. Enter variables in the Portainer GUI

Select the Docker Standalone environment, open **Stacks → Add stack**, name the
stack `telegram-fritz-wol`, select **Web editor**, and paste the contents of
`compose.portainer.yaml`. Under **Environment variables**, configure the following
seven variables; five are required and two have defaults:

| Variable | Required in the GUI | Value / default |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | Yes | Your bot token |
| `TELEGRAM_ALLOWED_USER_IDS` | Yes | Authorized numeric user IDs, comma-separated |
| `FRITZ_ADDRESS` | Yes | Your router's private IPv4 address |
| `FRITZ_USERNAME` | Yes | Your FRITZ!Box username |
| `FRITZ_PASSWORD` | Yes | Your FRITZ!Box password |
| `FRITZ_TIMEOUT_SECONDS` | No | `5`; allowed range 1–15 seconds |
| `BOT_LANGUAGE` | No | `en`; set `it` for Italian |

`DEVICES_FILE` is already fixed in the YAML. Do not add it in the GUI.
The five `${...:?required}` substitutions must all be supplied. Enter bare values
without shell assignments or surrounding quotes.

Alternatively, select **Load variables from .env file** in the same GUI section
and upload a privately completed environment file from your browser's computer.
Use `.env.example` as a template, replace placeholders privately, and retain only
the seven keys above. This imports values into Portainer; it does not make
Portainer read an arbitrary `.env` path on the Docker host. Check the imported
values privately, especially passwords containing special characters: GUI file
import is not the CLI service's `format: raw` reader. Never commit or share the
completed file, and never overwrite existing credentials with example values.

The actual Portainer deployment could not use a host-path `env_file` directly;
this variant instead substitutes GUI variables into explicit `environment`
entries. Follow this workflow rather than adding `.env` as a host-path
`env_file`. A CLI `.env` file is not required by this Portainer deployment.
Both individual GUI entry and GUI file import use the same explicit YAML
environment mappings. See the
[Portainer stack documentation](https://docs.portainer.io/user/docker/stacks/add).

The supplied Portainer YAML now forwards both optional settings, defaulting to
`FRITZ_TIMEOUT_SECONDS=5` and `BOT_LANGUAGE=en` when omitted or empty. Explicit
unsupported language values are rejected by the application. The CLI raw
environment file forwards values literally, so an explicitly empty
`BOT_LANGUAGE=` there is invalid; omit the key to use the application default.

### 4. Deploy and inspect

Select **Deploy the stack**. Keep registry image re-pull disabled for the local
image tag. Inspect the stack's bot container and its **Logs** view; then test
from an authorized private Telegram chat. To stop it, use the stack's stop
action. Do not start a second CLI-managed instance for the same token.

## Updates and configuration changes

Back up configuration first. Review upstream changes and obtain the intended
revision; with an unmodified checkout, `git pull --ff-only` updates without
rewriting history. Resolve local changes before upgrading. Source updates do not
by themselves replace a running container.

Before rebuilding, retain the image currently used by the bot. For CLI-managed
deployments, on the same Docker host:

```sh
wol_previous_image=$(docker compose --env-file .env.example -f compose.yaml images --quiet bot)
docker image tag "$wol_previous_image" telegram-fritz-wol:rollback
```

For Portainer, find the running bot's image ID in its container details, then
run this on the selected Docker endpoint, replacing the placeholder:

```sh
docker image tag REPLACE_WITH_RUNNING_IMAGE_ID telegram-fritz-wol:rollback
```

Save the matching source revision and configuration privately as well. Retain
the rollback image until the upgrade is verified; do not prune it or overwrite
the rollback tag if you still need that version.

**Docker Compose:** rebuild and recreate the bot from the repository root:

```sh
docker compose --env-file .env.example -f compose.yaml up -d --build --force-recreate bot
```

**Portainer:** rebuild `telegram-fritz-wol:local` on the same Docker endpoint:

```sh
docker build -t telegram-fritz-wol:local .
```

Then open the existing stack's **Editor**, preserve its environment variables and
host path, and select **Update the stack** with registry re-pull disabled.
Ensure the bot container is recreated using the new image. For a JSON-only
change, use Portainer's container recreation action if a stack update leaves it
unchanged. Manage subsequent updates through the same stack.

### Upgrade an existing deployment and keep Italian

The previous bot replied in Italian; a new image without `BOT_LANGUAGE` defaults
to English. To retain Italian, set **`BOT_LANGUAGE=it`** before recreating it:

1. Preserve the current JSON and credentials. Do not copy `.env.example` over
   an existing `.env` or import placeholder values over a live Portainer stack.
2. For CLI deployments, add or update only `BOT_LANGUAGE=it` in the existing
   `.env`, keeping the current credentials and timeout.
3. For Portainer, update the existing stack definition from
   `compose.portainer.yaml` while retaining any deployment-specific host path.
   Keep all five required GUI values, add `BOT_LANGUAGE=it`, and set
   `FRITZ_TIMEOUT_SECONDS` only if a value other than the default is wanted.
   Prefer editing the optional GUI fields manually for this upgrade. If using
   file import, include the correct existing required values and verify every
   field before applying it.
4. **Code changes require a new image build and container recreation.** Use the
   appropriate rebuild/redeploy steps above; a restart keeps the old image and
   environment. Check logs and the bot's language after the planned deployment.

Both workflows reload configuration only in a new process. Environment changes
require recreation, not just a restart of the existing container. Recreate after
JSON edits too: an editor that replaces the file can leave a bind mount pointing
to the previous inode. On every bot startup, pending Telegram updates are dropped
to avoid processing commands queued while it was stopped.

### Roll back the Docker image

If an update fails, use the retained image rather than rebuilding the old source
with potentially changed base images. For Docker Compose, this temporary override
selects the saved local image and explicitly disables building and pulling:

```sh
docker compose --env-file .env.example -f compose.yaml -f - up -d --no-build --pull never --force-recreate bot <<'YAML'
services:
  bot:
    image: telegram-fritz-wol:rollback
YAML
```

For Portainer, change only the stack's `image` to `telegram-fritz-wol:rollback`,
keep registry re-pull disabled, preserve the environment and bind mount, and
update the existing stack so the bot is recreated. Restore the matching private
configuration if its format changed, without resetting credentials. Check logs
and Telegram after rollback. Before a later upgrade, restore the usual image
selection (`telegram-fritz-wol:local` for Portainer) and use the intended source
revision. These operations replace the bot container and briefly interrupt it;
they are not performed automatically.

## Logs and shutdown

For CLI logs, use the Compose command above. In Portainer, open **Containers**,
select the bot belonging to the stack, then **Logs**. Logs contain controlled
messages and error categories, without token-bearing URLs, SOAP bodies,
credentials or raw exception tracebacks. Inspect exports before sharing them;
Docker/Portainer metadata may expose environment variables.

Both YAML files rotate JSON logs at 5 MB with three files, restart the bot with
`unless-stopped`, and allow 120 seconds for shutdown. `SIGINT`/`SIGTERM` stop
polling and close the router session. TR-064 timeouts apply per HTTP request;
initial API discovery can involve several requests and make the first command
slower. No healthcheck is configured: process existence is not a meaningful
end-to-end connectivity check.

## Configuration backups and restore

There is no database or application state volume. Back up the completed device
JSON, your chosen YAML and source revision, and either the CLI `.env` or the
Portainer environment values. Store copies privately, preferably encrypted, and
retain restrictive permissions. Do not commit backups or Portainer data exports.

For the CLI workflow, this example writes a protected archive under the already
ignored `secrets/` directory:

```sh
mkdir -p secrets/backups
chmod 0700 secrets/backups
(umask 077; tar -czf "secrets/backups/config-$(date +%Y%m%d-%H%M%S).tar.gz" .env secrets/devices.json)
```

The archive is **not encrypted**; transfer it to protected backup storage. This
command assumes CLI `.env` exists. For a GUI-only deployment, back up the JSON
and save the configured Portainer values, including language and timeout, in a
protected secret store instead;
keep a protected copy of the deployed stack definition as well.

To restore or migrate, restore the files on the target Docker host, reapply
UID/GID access, restore environment values through the selected deployment
method, build the image there, and deploy a single instance. Rebuild for a new
CPU architecture. ARM/Raspberry Pi operation has not been validated by this
project; a multiarch base image alone does not prove runtime compatibility.

## Troubleshooting

| Symptom | Checks |
| --- | --- |
| Configuration failure or restart loop | Replace placeholders, validate JSON and required variables. Config errors exit with code `2`; fatal runtime errors with `1`. |
| Access denied in Telegram | Verify the sender's numeric user ID, the allowlist and a private chat; callbacks have the same checks. |
| Telegram conflict / another polling instance | Stop the duplicate instance using that token. Use one deployment manager. |
| Portainer required-variable error | Fill all five required GUI fields; do not rely on a host-path `env_file`. |
| Wrong language or unsupported `BOT_LANGUAGE` | Use exactly `en` or `it`; the default is `en`. Set `it` to preserve the old Italian replies, then recreate the container with the rebuilt image. |
| Portainer image pull failure | Build `telegram-fritz-wol:local` on the selected endpoint and disable registry re-pull. |
| JSON mount missing or unreadable | Check the Docker-host path, file existence, GID `10001`, mode `0640` and any user-namespace mapping. Recreate after file replacement. |
| Router authentication/authorization error | Check username, password and TR-064 permissions locally; do not paste them into logs or issues. |
| Router timeout / unavailable | Check the configured router address, LAN path and TCP `49000`. Initial discovery may take multiple request timeouts. |
| WoL accepted but computer stays off | Check power, network interface, firmware/OS WoL settings and the MAC. Acceptance is not proof of startup. |
| Status inactive or unknown | Router observations may lag; fault 714 means no known entry. Verify a target service separately. |
| No response after host shutdown | Move the bot to an always-on host. It cannot wake its own powered-off host. |

Do not enable HTTP debug dumps to troubleshoot credentials: Telegram URLs contain
the token. Rotate any credential accidentally disclosed before opening an issue.

## Validation and development

The following results describe different kinds of evidence:

| Validation | Scope and result |
| --- | --- |
| **71 unit tests** | Passed on 2026-11-17: the 63-test i18n suite plus eight activity-indicator tests. Offline mocks and blocked network connections; no real router or Telegram calls. |
| **Manual end-to-end test before this revision** | The maintainer confirms successful production operation in Italian and English through Telegram and TR-064 under Docker managed by Portainer. See tested hardware below. The new activity indicator has not been deployed or tested live during this change. |

### Tested hardware

The maintainer reports end-to-end WoL testing with a **FRITZ!Box 5530 Fiber**, a
configured desktop target and a Docker host managed through Portainer. Hostnames,
MACs, personal Telegram IDs and the deployment's actual network details are not
needed to reproduce the configuration and are intentionally omitted.

The live test does not establish that every error path was tested on hardware.
Other FRITZ!Box models, ARM/Raspberry Pi and Docker Swarm have not been validated.
The CLI deployment is documented from the supplied Compose file; the stated live
end-to-end evidence is for Portainer.

Reproduce the automated checks from the repository root without global packages:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --no-cache-dir -r requirements.txt
.venv/bin/python -m unittest discover -v
.venv/bin/python -m compileall -q telegram_fritz_wol tests
.venv/bin/python -m pip check
BOT_ENV_FILE=.env.example docker compose --env-file .env.example -f compose.yaml config --quiet
docker compose --env-file .env.example -f compose.portainer.yaml config --quiet
```

The two YAML checks use non-secret example values and do not start services.
Tests cover authorization, callback manipulation, configuration, WoL selection,
cooldown, status wording, resource closure and errors. SOAP fault tests exercise
the parser in `fritzconnection==1.15.1`: 714 maps to `FritzLookUpError`, becomes
unknown for status, and remains a safe error for WoL. Other faults, including
authorization fault 606, remain errors. Test tokens, IDs and MACs are synthetic.
Language tests cover key and named-placeholder completeness, rendering, both
languages, safe rejection of unsupported codes, translated commands/buttons and
errors, fixed callback payloads, authorization, WoL and cooldown invariants.
Activity tests cover typing before TR-064, callback acknowledgement order,
unauthorized/invalid requests, chat-action failure tolerance and both languages.

For offline validation of actual settings, run
`python -m telegram_fritz_wol --check-config` with the variables already in the
process environment and `DEVICES_FILE` pointing to the local JSON. The Python
entrypoint does not automatically read `.env`. This verifies configuration only,
not whether remote services accept the credentials.

## Architecture and security

| Module | Responsibility |
| --- | --- |
| `config.py` | Offline environment and device validation |
| `i18n.py` | English/Italian dictionaries and named-placeholder rendering |
| `bot.py` | Async Telegram handlers, authorization and inline buttons |
| `service.py` | Device allowlist, cooldown and safe outcome messages |
| `router.py` | Authenticated TR-064 adapter and error classification |
| `__main__.py` | Logging, configuration check and polling lifecycle |

Blocking TR-064 work runs through `asyncio.to_thread`. Updates and router
operations are serialized; the router client is created lazily and reused.
Only `message` and `callback_query` updates are requested.

Telegram uses verified HTTPS. TR-064 uses **HTTP Digest on the LAN**: requests
are authenticated, but HTTP traffic is not encrypted and the router is not
verified by a certificate. Use a trusted LAN or protected network path. The
project does not enable the library's TLS mode, which disables router certificate
verification in this version.

Secrets are excluded from Git and from the Docker build context. Docker and
Portainer administrators can still read container environment values; these are
not a secret vault. Both deployments use `no-new-privileges`, drop all
capabilities and need no host networking or privileged mode.

## License and references

[MIT License](LICENSE). Copyright (c) 2026 Carlo Catapano.

- [FRITZ! TR-064 Hosts actions](https://fritz.support/resources/TR-064_Hosts.pdf)
- [FRITZ! TR-064 authentication](https://fritz.support/resources/TR-064_Authentication.pdf)
- [python-telegram-bot 22.8 lifecycle](https://docs.python-telegram-bot.org/en/v22.8/telegram.ext.application.html)
- [fritzconnection API documentation](https://fritzconnection.readthedocs.io/en/1.15.0/sources/fritzconnection_api.html)
- [Docker Compose environment files](https://docs.docker.com/reference/compose-file/services/#env_file)
- [Portainer: create a stack and enter variables](https://docs.portainer.io/user/docker/stacks/add)
- [Portainer: edit and update a stack](https://docs.portainer.io/user/docker/stacks/edit)
- [Portainer: view container logs](https://docs.portainer.io/user/docker/containers/logs)
