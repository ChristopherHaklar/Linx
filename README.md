# Linx

![Linx](branding/banner.png)

Linx is a Discord bot that watches messages for links, strips tracking parameters (`utm_*`, `fbclid`, `si`, `?s=20&t=...`, etc.), and rewrites `x.com` / `twitter.com` links to `fixvx.com` so they embed properly.

When a message has a link that can be cleaned, the bot replies with the cleaned version and (optionally) hides the original message's embed. There's also a `/clean <link>` slash command.

## What gets cleaned

Linx only replies when the cleaned link is different from the original.

**Removed from every link**

- Campaign tags: anything starting with `utm_`, `pk_` or `hsa_`
- Ad click IDs: `fbclid`, `gclid`, `gclsrc`, `dclid`, `gbraid`, `wbraid`, `srsltid`, `msclkid`, `yclid`, `ttclid`, `twclid`, `li_fat_id`
- Share and email trackers: `igshid`, `igsh`, `mc_cid`, `mc_eid`, `_hsenc`, `_hsmi`, `mkt_tok`, `_ga`, `_gl`, `oly_anon_id`, `oly_enc_id`, `vero_id`, `rb_clickid`, `wt_mc`, `ref_src`, `ref_url`

**Removed only on specific sites** (these names can mean something real elsewhere)

| Site | Removed |
|---|---|
| X / Twitter | `s`, `t` |
| YouTube (incl. `m.` and `music.`) | `si`, `feature`, `pp` |
| youtu.be | `si`, `feature` |
| Spotify | `si`, `context` |
| Instagram | `igsh`, `img_index` |
| TikTok | `_r`, `_d`, `_t`, `u_code`, `timestamp`, `share_app_id`, `share_item_id`, `share_link_id`, `sender_device`, `sender_web_id`, `is_from_webapp`, `social_share_type`, `sec_user_id`, `checksum`, `tt_from`, `source`, `refer` |
| Reddit | `share_id`, `rdt` |
| Facebook | `mibextid`, `__cft__`, `__tn__`, `rdid`, `sfnsn`, `extid`, `ref`, `fref`, `hc_ref`, `hc_location`, `paipv`, `eav`, `acontext`, `notif_id`, `notif_t`, `comment_tracking`, `xts` |
| Amazon (any country) | `tag`, `ref`, `ref_`, `psc`, `th`, `linkcode`, `creative`, `creativeasin`, `camp`, `ascsubtag`, `keywords`, `qid`, `sr`, `crid`, `sprefix`, `dib`, `dib_tag`, `content-id`, `_encoding`, `pd_rd_*`, `pf_rd_*`, `social_share`, `starsleft`, `linkid`, `ie` |
| Google search (any country) | `ei`, `ved`, `oq`, `gs_lp`, `gs_lcrp`, `sca_esv`, `sxsrf`, `sclient`, `client`, `source`, `rlz`, `bih`, `biw`, and other search-page noise. `q`, `tbm`, `udm`, `tbs`, `start` and `hl` are kept. |
| AliExpress | `spm`, `scm`, `pvid`, `algo_pvid`, `algo_exp_id` |
| LinkedIn | `trk`, `trackingid`, `lipi`, `rcm` |

**Other fixes**

- **X / Twitter embeds:** `x.com` and `twitter.com` links (including `www.` and `mobile.`) are rewritten to `fixvx.com`. Turn off with `FIX_X_LINKS=false`.
- **Amazon product links** are shortened to `/dp/<ASIN>`, dropping the product-name slug and `/ref=...` path tracking. Other Amazon pages lose their `/ref=...` path segment.
- **Redirect wrappers** are unwrapped to the real destination: `google.com/url?q=...`, `l.facebook.com/l.php?u=...`, `lm.facebook.com`, `l.messenger.com` and `l.instagram.com`.
- **Short links** are expanded and then cleaned: `amzn.to`, `a.co`, `amzn.eu`, `amzn.asia`, `vm.tiktok.com`, `vt.tiktok.com`, `tiktok.com/t/...`, Reddit `/r/<sub>/s/...` share links, `spotify.link` and `pin.it`. Linx reads only the redirect and never loads the destination page. If a short code is dead and redirects to a homepage, the link is left alone. Turn off with `EXPAND_SHORT_LINKS=false`.

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

Tracking parameter lists live at the top of `cleaner.py`: `GLOBAL_TRACKING_PARAMS` apply everywhere, `SITE_TRACKING_PARAMS` only on specific domains (e.g. `si` is tracking on YouTube/Spotify but may be meaningful elsewhere), and `COUNTRY_SITE_PARAMS` on sites with many country domains (Amazon, Google). Supported short-link services are listed in `shortlinks.py`. Only those hosts are ever contacted.

## Branding

`branding/` holds the avatar (`logo.png`, 1024×1024) and profile banner (`banner.png`, 1500×600), with SVG sources and `generate.py` to regenerate them.
