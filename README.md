# Linx

![Linx](branding/banner.png)

Linx is a Discord bot that watches messages for links, strips tracking parameters (`utm_*`, `fbclid`, `si`, `?s=20&t=...`, etc.), and rewrites `x.com` / `twitter.com` links to `fixvx.com` so they embed properly.

When a message has a link that can be cleaned, the bot replies with the cleaned version and (optionally) hides the original message's embed. There's also a `/clean <link>` slash command.

## Setup

1. Create an application named **Linx** at https://discord.com/developers/applications.
2. On its **Bot** page, click **Reset Token** and copy the token, then enable **Message Content Intent** and save.
3. Double-click **`start.bat`**. On first run it installs everything and asks you to paste the token (saved to `.env`).
4. Open the invite link Linx prints in the window to add it to your server.

Keep the window open while you want the bot online. If the token is wrong, Linx clears it and asks again next run.

## Running with Docker

For an always-on server, build the image and pass settings through an env file (see `.env.example`):

```sh
docker build -t linx .
docker run -d --name linx --restart unless-stopped --env-file .env linx
```

`docker logs linx` shows the invite link. The token must be set in `.env`, since the container can't prompt for it.

## Tests

```powershell
.venv\Scripts\python -m unittest
```

## Customizing

Tracking parameter lists live at the top of `cleaner.py`: `GLOBAL_TRACKING_PARAMS` apply everywhere, `SITE_TRACKING_PARAMS` only on specific domains (e.g. `si` is tracking on YouTube/Spotify but may be meaningful elsewhere).

## Branding

`branding/` holds the avatar (`logo.png`, 1024×1024) and profile banner (`banner.png`, 1500×600), with SVG sources and `generate.py` to regenerate them.
