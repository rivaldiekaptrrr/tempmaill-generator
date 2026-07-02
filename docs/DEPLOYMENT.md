# 🚀 Deployment Guide

This guide will walk you through deploying the Interactive TempMail Telegram Bot to a production environment.

This project ships with a **`Dockerfile`** — a recipe that tells Docker how to build a **Docker Image** for this bot. That image is published to a container registry (e.g. Docker Hub or GitHub Container Registry), and Coolify pulls it from there.

---

## 1. Zero-Touch Deployment (GitHub Actions + Coolify) — ✨ Recommended

This is the ultimate automated workflow. You don't need Docker installed on your computer at all. We have included a GitHub Actions CI/CD pipeline that builds the image automatically on GitHub's servers every time you push code!

### Step 1 — Push to GitHub
1. Make sure your code is pushed to a GitHub repository.
2. Every time you push to the `main` branch, GitHub Actions will automatically:
   - Read the `Dockerfile`
   - Build the Docker Image
   - Publish it to the GitHub Container Registry (GHCR).

You can watch this happen in the **"Actions"** tab of your GitHub repository.

### Step 2 — Make the GitHub Package Public
By default, GitHub makes the uploaded package (Docker Image) private. 
1. Go to your GitHub Profile → **Packages**.
2. Find the `tempmail-bot` package.
3. Click **Package Settings** and change the visibility to **Public** so Coolify can download it without needing passwords.

### Step 3 — Deploy on Coolify
1. In your Coolify dashboard, click **New Resource → Docker Image**.
2. In the **Image Name** field, enter the GHCR link. For this repository, it is:
   ```
   ghcr.io/rivaldiekaptrrr/tempmaill-generator:latest
   ```
3. Go to the **Environment Variables** tab and add:
   - Key: `TELEGRAM_BOT_TOKEN`
   - Value: `your_telegram_bot_token_here`
4. Click **Save**, then **Deploy**.

> **Pro Tip:** Whenever you make changes to the code, simply `git push`. GitHub will automatically rebuild the image. Once finished, just go to Coolify and click "Deploy" again to pull the fresh update!

---

## 2. Manual Workflow (Build Locally & Push)

If you don't want to use GitHub Actions, you can build the image on your own computer and push it manually.

First, make sure you're logged in to Docker Hub on your machine:
```bash
docker login
```

Then build and push the image (replace `your_dockerhub_username` with your actual Docker Hub username):
```bash
# Build the Docker Image
docker build -t your_dockerhub_username/tempmail-bot:latest .

# Push the image to Docker Hub
docker push your_dockerhub_username/tempmail-bot:latest
```

Your image is now publicly available at:
`docker.io/your_dockerhub_username/tempmail-bot:latest`

### Step 2 — Deploy from Coolify

1. In your Coolify dashboard, click **New Resource → Docker Image**.
2. In the **Image Name** field, enter:
   ```
   your_dockerhub_username/tempmail-bot:latest
   ```
3. Go to the **Environment Variables** tab and add:
   - Key: `TELEGRAM_BOT_TOKEN`
   - Value: `your_telegram_bot_token_here`
4. Click **Save**, then **Deploy**.

> **Note:** Because this is a Telegram Polling bot, it does not need any open ports. You can leave the port settings empty.

---

## 2. Alternative: GitHub Container Registry (GHCR)

If you prefer to keep your image alongside your GitHub repository, you can push it to GHCR instead.

```bash
# Login with your GitHub Personal Access Token
echo YOUR_GITHUB_PAT | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin

# Build and push to GHCR
docker build -t ghcr.io/your_github_username/tempmail-bot:latest .
docker push ghcr.io/your_github_username/tempmail-bot:latest
```

Then in Coolify, use this as the **Image Name**:
```
ghcr.io/your_github_username/tempmail-bot:latest
```

---

## 3. Alternative: Deploying on a VPS (plain Docker)

If you have a raw VPS and want to build and run the image directly without a registry:

1. **Clone the repository** on your VPS:
   ```bash
   git clone https://github.com/yourname/tempmail-generator.git
   cd tempmail-generator
   ```

2. **Build the Docker Image** from the Dockerfile:
   ```bash
   docker build -t tempmail-bot .
   ```
   This command reads the `Dockerfile` and produces a **Docker Image** named `tempmail-bot`.

3. **Run a Container** from the image:
   ```bash
   docker run -d \
     --name tempmail-worker \
     --restart unless-stopped \
     -e TELEGRAM_BOT_TOKEN="your_telegram_bot_token_here" \
     tempmail-bot
   ```

4. **Check the logs**:
   ```bash
   docker logs -f tempmail-worker
   ```

---

## 💡 Production Tips

- **Resource Usage**: Use the bot's `/autocheck` command (via Telegram) to toggle real-time SSE monitoring on/off. Disabling it saves significant CPU and RAM on your server.
- **Updating the bot**: After pushing a new image version, re-deploy from the Coolify dashboard to pull the latest image.
- **Log Management**: The bot uses `INFO` level logging by default to prevent log bloat on your server.
