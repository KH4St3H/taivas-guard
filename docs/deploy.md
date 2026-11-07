# Deploying to a server

`.github/workflows/deploy.yml` runs on every push to `main`, or by hand from the Actions tab. It runs the backend and frontend tests, unless they're turned off (below), copies the code to the server over SSH, and runs `docker compose -p ific-guard up -d --build`. The deploy fails if any of the three services doesn't answer within 2 minutes, and prints their logs.

What it deploys is the Compose stack: sync, screening, notifier, Postgres and the migration. The review UI isn't part of it; see "The review UI" below.

## Server, once

The server needs Docker with the Compose plugin, `rsync` and `curl`.

1. Create a user for deploys, in the `docker` group, and a folder it owns:

   ```sh
   sudo useradd --create-home --groups docker deploy
   sudo mkdir -p /opt/ific-guard && sudo chown deploy /opt/ific-guard
   ```

2. Make an SSH key pair used only for deploys, and allow its public key for that user:

   ```sh
   ssh-keygen -t ed25519 -N '' -C ific-guard-deploy -f deploy_key
   # append deploy_key.pub to /home/deploy/.ssh/authorized_keys on the server
   ```

3. Put the settings in `/opt/ific-guard/.env`. The deploy never overwrites or deletes this file. Start from `.env.example` and set at least:

   ```
   IFIC_API_KEY=<output of: openssl rand -hex 32>
   POSTGRES_PASSWORD=<a strong password>
   IFIC_EMAIL_BACKEND=smtp or file
   ```

   Set `POSTGRES_PASSWORD` before the first deploy: Postgres keeps the password it starts with.

## GitHub, once

In the repository settings, **Secrets and variables → Actions**. Set them at repository level, not on the environment: the check that skips the deploy runs before the environment is loaded.

| Name | Kind | Value |
|---|---|---|
| `DEPLOY_HOST` | variable | The server's address. Until it's set, the workflow runs the tests and skips the deploy. |
| `DEPLOY_USER` | secret | `deploy` |
| `DEPLOY_SSH_KEY` | secret | The contents of `deploy_key` (the private key) |
| `DEPLOY_KNOWN_HOSTS` | secret | The output of `ssh-keyscan <host>`, checked against the server's own fingerprint (`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` on the server) |
| `DEPLOY_PORT` | secret, optional | The SSH port, if not 22 |
| `DEPLOY_PATH` | variable, optional | The folder on the server, if not `/opt/ific-guard` |

To deploy without the tests: run the workflow by hand and untick **Run the tests before deploying**, or set the repository variable `SKIP_TESTS` to `true` to skip them on pushes too. Failed tests still stop a deploy.

The deploy job uses the `production` environment. To approve each deploy by hand, add required reviewers to it under **Environments**.

## What a deploy keeps

- `.env` on the server.
- The Postgres and data volumes, so the database, downloaded issues and review decisions survive.
- `data/shared/`, if you copied issue files there.

`.scratch/` and `outputs/` aren't copied. The commit that's running is in `/opt/ific-guard/DEPLOYED_COMMIT`.

The ports stay bound to `127.0.0.1` as in `compose.yaml`, so nothing is reachable from outside the server. The API key is a minimal guard, not internet-facing security: put a reverse proxy with its own sign-in in front before opening anything.

## Rolling back

Revert the commit on `main` and push, or run the workflow by hand from an earlier commit. The database isn't rolled back: `init-db` only adds tables.

## The review UI

The UI runs as a Vite dev server whose proxy adds the API key, which doesn't suit a server. To deploy it, it needs a container that serves `frontend/dist` and proxies `/api/sync` and `/api/screening`, behind a sign-in, because anyone who can open it could act with the key.
