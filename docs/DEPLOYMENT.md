# 🚀 Deployment Guide

This guide will walk you through deploying the Interactive TempMail Telegram Bot to a production environment. 

The bot is designed to be fully containerized using **Docker**, meaning it runs perfectly on modern PaaS platforms like Coolify, or directly on a VPS.

---

## 1. Deploying on Coolify (Recommended)

Coolify is an open-source, self-hostable Heroku/Netlify alternative. Deploying this bot to Coolify is incredibly straightforward because we have provided a multi-stage `Dockerfile`.

### Steps:
1. **Push your code** to a GitHub, GitLab, or Gitea repository.
2. In your Coolify dashboard, create a **New Resource** and select **Git Repository**.
3. Choose your TempMail repository.
4. In the configuration settings, set the **Build Pack** to **`Dockerfile`**.
   *(Coolify will automatically detect the `Dockerfile` at the root of the project).*
5. Go to the **Environment Variables** tab and add your bot token:
   - Key: `TELEGRAM_BOT_TOKEN`
   - Value: `your_telegram_bot_token_here`
6. Click **Deploy**.

> **Note:** Because this is a Telegram Polling bot, it does not expose any web servers or HTTP ports. Coolify will run it as a background worker.

---

## 2. Deploying on a VPS (using Docker)

If you have a raw VPS (Ubuntu, Debian, etc.) and want to run the bot using plain Docker, you can do so in just a few commands.

### Prerequisites:
- Docker installed on your VPS.
- Git installed.

### Steps:

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourname/tempmail-generator.git
   cd tempmail-generator
   ```

2. **Build the Docker Image**:
   ```bash
   docker build -t tempmail-bot .
   ```

3. **Run the Container**:
   Run the container in the background (`-d`) and pass the bot token via environment variables (`-e`).
   ```bash
   docker run -d \
     --name tempmail-worker \
     --restart unless-stopped \
     -e TELEGRAM_BOT_TOKEN="your_telegram_bot_token_here" \
     tempmail-bot
   ```

4. **Check the logs**:
   To ensure the bot is running smoothly without errors:
   ```bash
   docker logs -f tempmail-worker
   ```

---

## 💡 Production Tips

- **Resource Usage**: If your server is running low on RAM/CPU, you can use the bot's `/autocheck` command (via Telegram) to disable real-time SSE background connections. The bot will then operate purely on a manual basis using `/check`, which uses almost zero idle resources.
- **Data Persistence**: Currently, active emails are stored in memory. If your Coolify container or VPS restarts, the active email list will be cleared.
- **Log Management**: The bot is configured to use `INFO` level logging by default in production to prevent log bloat.
