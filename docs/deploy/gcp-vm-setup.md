# GCP VM provisioning and deploy runbook

Companion to `docs/superpowers/plans/2026-09-23-gcp-deployment.md`. Run from
Google Cloud Console (or `gcloud` CLI if preferred) against the project with
the $300/90-day free trial credit active.

## 1. Reserve a static external IP
Console: VPC network → IP addresses → Reserve external static address.
Or CLI: `gcloud compute addresses create altayai-ip --region=us-central1`

## 2. Create the VM
Console: Compute Engine → VM instances → Create instance.
- Machine type: `e2-standard-2` (2 vCPU / 8GB RAM)
- Boot disk: Ubuntu 22.04 LTS, 40GB
- Network: attach the reserved static IP from step 1
- Firewall: allow HTTP and HTTPS traffic (checkboxes in the console)

Or CLI:
```
gcloud compute instances create altayai-vm \
  --zone=us-central1-a \
  --machine-type=e2-standard-2 \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=40GB \
  --address=altayai-ip \
  --tags=http-server,https-server

gcloud compute firewall-rules create allow-http --allow=tcp:80 --target-tags=http-server
gcloud compute firewall-rules create allow-https --allow=tcp:443 --target-tags=https-server
```

## 3. SSH in and install Docker + Compose plugin
Console: click "SSH" next to the VM in the instances list (opens a browser terminal).

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER
```
Log out of the SSH session and reconnect for the docker group change to apply.

## 4. DNS
At your domain registrar, create an `A` record: `<your-domain>` → the reserved IP from step 1.
Wait for propagation (`dig <your-domain>` or https://dnschecker.org) before continuing.

## 5. Deploy
```bash
git clone <your-repo-url> ~/altayai
cd ~/altayai/deploy
cp .env.example .env
# edit .env with real values — see below
nano .env
docker compose build
docker compose up -d postgres milvus etcd minio
sleep 30
docker compose run --rm backend alembic upgrade head
docker compose up -d
```

`.env` values to fill:
- `POSTGRES_PASSWORD`: generate with `openssl rand -base64 24`
- `JWT_SECRET`: generate with `python3 -c "import secrets; print(secrets.token_hex(32))"`
- `OPENROUTER_API_KEY`: from openrouter.ai/keys
- `OPENROUTER_MODEL`: confirm with the project owner before filling — do not leave the default unexamined
- `PUBLIC_ORIGIN` / `PUBLIC_DOMAIN`: the real domain from step 4, e.g. `https://altayai.example.com` / `altayai.example.com`
- `ADMIN_EMAILS`: real admin account email(s)

Verify: `docker compose ps` shows every service `Up`; `curl http://<your-domain>/` returns the frontend HTML.

## 6. TLS (Let's Encrypt via certbot)
```bash
cd ~/altayai/deploy
mkdir -p certbot/www certbot/conf
docker run --rm \
  -v "$(pwd)/certbot/www:/var/www/certbot" \
  -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
  certbot/certbot certonly --webroot -w /var/www/certbot \
  -d <your-domain> --email <your-email> --agree-tos --no-eff-email
```
Once it succeeds, switch nginx to the HTTPS config and reload:
```bash
cp nginx/nginx-https.conf.template nginx/default.conf.template
docker compose restart nginx
```
Verify: `curl -I https://<your-domain>/` returns `HTTP/2 200`.

Auto-renewal (run on the VM):
```bash
(crontab -l 2>/dev/null; echo "0 3 * * * cd ~/altayai/deploy && docker run --rm -v \$(pwd)/certbot/www:/var/www/certbot -v \$(pwd)/certbot/conf:/etc/letsencrypt certbot/certbot renew --webroot -w /var/www/certbot -q && docker compose restart nginx") | crontab -
```

## 7. Smoke test
- `curl -I https://<your-domain>/` → 200
- Browser: register a test account, reload the page, confirm you're still logged in (validates the same-origin cookie setup)
- Upload a small PDF, confirm it processes without errors (validates Postgres + Milvus + embedding model wiring)
- Check browser console/network tab for CORS or 401 errors — there should be none

## Post-launch
- Set a GCP budget alert on the trial credit so nothing bills a card silently after 90 days.
- Recheck the certbot cron renewal once, ~60-90 days out.
