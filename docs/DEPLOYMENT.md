# 🚀 Deployment Guide

This guide will walk you through deploying the Interactive TempMail Telegram Bot to a production environment.

The most foolproof and highly recommended method is deploying directly from your GitHub Repository using **Coolify**, which automatically builds the `Dockerfile` included in this project.

---

## 1. Zero-Hassle Deployment (Coolify Git Repository) — ✨ Recommended

This method avoids any complicated Docker Registry (GHCR/Docker Hub) permissions. Coolify will simply pull your code and build the Docker Image itself directly on your server.

### Step 1 — Link GitHub to Coolify
1. In your Coolify dashboard, navigate to **Sources** or click **New Resource → Git Repository**.
2. If you haven't linked GitHub yet, choose **GitHub App** and click **Automated Installation** -> **Register Now**.
3. Follow the on-screen instructions on GitHub to authorize Coolify for this repository (`tempmaill-generator`).
4. Once authorized, select your `tempmaill-generator` repository and the `main` branch.

### Step 2 — Configure the Deployment
1. **Build Pack**: Change the build pack to **`Dockerfile`**.
2. **Environment Variables**: Open the Environment Variables tab and add:
   - Key: `TELEGRAM_BOT_TOKEN`
   - Value: `your_telegram_bot_token_here`
3. **Domains**: ⚠️ **CRITICAL:** If Coolify auto-generates a Domain (e.g., `http://xyz.sslip.io`), **delete it entirely** so the field is empty. This is a background bot, not a website.
4. **Ports Exposes**: You can leave the default (e.g., `3000`), the bot will safely ignore it.

### Step 3 — Deploy
Click **Save** and then **Deploy**! 
Coolify will automatically build the image and start the container in the background. Whenever you update your code on GitHub, you can simply click Deploy again to update the bot.

---

## 2. Deploying on a VPS (Plain Docker)

If you don't use Coolify and have a raw VPS (Ubuntu, Debian, etc.), you can build and run the image directly.

1. **Clone the repository** on your VPS:
   ```bash
   git clone https://github.com/yourname/tempmaill-generator.git
   cd tempmaill-generator
   ```

2. **Build the Docker Image**:
   ```bash
   docker build -t tempmail-bot .
   ```

3. **Run a Container**:
   Run the container in the background (`-d`) and pass the bot token via environment variables (`-e`).
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

- **Resource Usage**: Use the bot's `/autocheck` command (via Telegram) to toggle real-time SSE monitoring on/off. Disabling it saves significant CPU and RAM on your server if you have many users.
- **Data Persistence**: Because temporary emails only last a few hours anyway, this bot safely stores active sessions in RAM. A server restart will simply clear the active monitoring list.
- **Log Management**: The bot is configured to use `INFO` level logging by default in production to prevent server storage bloat.
