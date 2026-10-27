# Linx

![Linx](branding/banner.png)

Linx is a Discord bot that reads messages for links. It removes tracking parameters, such as `utm_*`, `fbclid`, `si` and `?s=20&t=...`. It also changes `x.com` and `twitter.com` links to `fixvx.com`, so Discord shows a full embed for them.

When a message has a link that Linx can clean, Linx replies with the clean version. Linx can also hide the embed on the original message. To clean a link yourself, use the `/clean <link>` slash command. You can also right-click a message and select **Apps → Clean links**.

## What Linx removes

Linx replies only when the clean link is different from the original. Linx always keeps parameters that it does not know, so pagination, search terms and product variants continue to work. The full lists are in `cleaner.py`.

**Removed from every link** (about 150 names, plus all names that start with `utm_`, `pk_`, `mtm_`, `piwik_`, `matomo_`, `hsa_`, `vero_` or `oly_`)

| Kind | Examples |
|---|---|
| Ad click IDs | `fbclid`, `gclid`, `gbraid`, `wbraid`, `gad_source`, `gad_campaignid`, `msclkid`, `ttclid`, `twclid`, `li_fat_id`, `yclid`, `ysclid`, `ScCid`, `epik`, `srsltid` |
| Analytics | Google `_ga`, `_gl`<br>Adobe `s_cid`, `s_kwcid`, `ef_id`, `sc_*`<br>AT Internet `at_*`, `xtor`<br>comScore `ns_*`<br>Webtrends `WT.mc_id` |
| Social shares | `igshid`, `igsh`, `ig_rid`, `fb_action_ids`, `fb_ref`, `fb_source`, `ref_src`, `ref_url`, `rdt_cid` |
| Email and marketing | Mailchimp `mc_cid`, `mc_eid`<br>HubSpot `_hsenc`, `_hsmi`, `__hstc`, `__hssc`, `__hsfp`<br>Marketo `mkt_tok`<br>Klaviyo `_kx`<br>Eloqua `elq*` |
| Affiliate networks | Impact `irclickid`, CJ `cjevent`, ShareASale `sscid`, Awin `awc`, Rakuten `ranMID`, `ranEAID`, `ranSiteID`, PartnerStack `ps_xid` |
| Article widgets | Outbrain `obOrigUrl`, `ob_click_id`<br>Taboola `tblci`, `dicbo` |
| Other | Shopify `_pos`, `_sid`, `_ss`, `_psq`<br>Yahoo `guccounter`, `guce_referrer`<br>`cmpid`, `ito`, `referrer` |

Linx does **not** remove `ref` from every link, because some sites use it for real data. For example, GitHub uses `?ref=branch`.

**Removed only on specific sites.** On other sites, these names can have a real meaning. Each rule also applies to the site's subdomains and country domains.

| Site | Removed |
|---|---|
| X / Twitter | `s`, `t`, `cxt`, `rw_tt_thread` |
| YouTube and youtu.be | `si`, `is`, `feature`, `pp`, `ab_channel`, `kw`, `source_ve_path`, `embeds_referring_euri`, `embeds_referring_origin` |
| Spotify | `si`, `nd`, `context`, `_branch_match_id`, `_branch_referrer` |
| Instagram | `igsh`, `img_index`, `srtk` |
| TikTok | `_r`, `_d`, `_t`, `u_code`, `user_id`, `timestamp`, `share_app_id`, `share_item_id`, `share_link_id`, `sender_device`, `sender_web_id`, `web_id`, `is_from_webapp`, `social_share_type`, `sec_user_id`, `checksum`, `tt_from`, `tt_medium`, `source`, `refer` |
| Reddit | `share_id`, `share_source`, `share_recommendation`, `correlation_id`, `rdt`, `ref_source`, `ref_campaign`, `chainedPosts`, `post_fullname` |
| Facebook | `mibextid`, `__cft__`, `__tn__`, `__xts__`, `rdid`, `sfnsn`, `extid`, `ref`, `fref`, `hc_ref`, `hc_location`, `paipv`, `eav`, `acontext`, `notif_id`, `notif_t`, `comment_tracking`, `xts` |
| LinkedIn | `trk`, `trkInfo`, `trackingId`, `lipi`, `rcm`, `refId`, `eBP`, `otpToken`, `original_referer`, `licu`, `originalSubdomain`, `midToken`, `midSig` |
| Pinterest | `invite_code`, `sender`, `sfo` |
| Bing | `cvid`, `form` |
| Google search | `ei`, `ved`, `oq`, `gs_lp`, `gs_lcrp`, `sca_esv`, `sxsrf`, `sclient`, `client`, `source`, `rlz`, `cd`, `cad`, `rct`, `hs`, `num` and other parameters that only the search page uses. Linx keeps `q`, `tbm`, `udm`, `tbs`, `start` and `hl`. |
| Amazon | `tag`, `ref`, `ref_`, `psc`, `th`, `linkCode`, `linkId`, `creative`, `creativeASIN`, `camp`, `ascsubtag`, `keywords`, `qid`, `sr`, `crid`, `sprefix`, `dib`, `dib_tag`, `content-id`, `_encoding`, `pd_rd_*`, `pf_rd_*`, `social_share`, `starsleft`, `ie`, `rsd`, `edk`. Product links keep only `smid` (the seller). Linx removes all other parameters from them. |
| AliExpress / Temu | `spm`, `scm`, `pvid`, `algo_pvid`, `algo_exp_id`, `aff_*`, `terminal_id`, `sk`, `btsid`, `ws_ab_test`, `pdp_npi`, `curPageLogUid`, `_t`, `_x_ads_channel`, `_x_sessn_id`, `refer_page_name`, `refer_page_id`, `srcSp`, `top_gallery_url` |
| eBay | `_trkparms`, `_trksid`, `mkcid`, `mkrid`, `mkevt`, `campid`, `customid`, `toolid`, `siteid`, `amdata`, `norover`, `ssspo`, `sssrc`, `ssuid`, `widget_ver` |
| Etsy | `click_key`, `click_sum`, `frs`, `sc_g`, `organic_search_click`, `ga_order`, `ga_search_type`, `ga_view_type`, `ga_search_query`, `ref`, `ls`, `sr_prefetch`, `pf_from`, `cns`, `sts`, `content_source`, `logging_key`, `plkey`, `pro`, `sca`. Linx removes all parameters from listing links. |
| Walmart | `athbdg`, `athcpid`, `athena`, `athpgid`, `athznid`, `from`, `sid`, `veh`, `adsRedirect` |
| Best Buy | `intl`, `loc`, `acampID` |
| Shopify | `_v` |
| Google Play | everything except `id`, `hl` and `gl` |

**Other changes**

- **X / Twitter embeds:** Linx changes `x.com` and `twitter.com` links to `fixvx.com`. This includes `www.`, `m.` and `mobile.` links. To disable this, set `FIX_X_LINKS=false`.
- **Product links:** Linx reduces these links to the product ID: Amazon `/dp/<ASIN>` (plus `smid` if present), Best Buy `/site/<sku>.p`, Walmart `/ip/<id>`, Etsy `/listing/<id>/<name>`. On other Amazon pages, Linx removes the `/ref=...` path segment.
- **Discord formatting:**
  - A spoilered link (`||link||`) gets a spoilered reply.
  - A link without an embed (`<link>`) gets a reply without an embed.
  - Linx ignores links in `code` and in code blocks.
- **Tracking after the `#`:** Linx removes tracking such as `#utm_source=...`. Linx does not change page anchors, app routes (`#/inbox`) or text highlights (`#:~:text=`).
- **Redirect wrappers:** Linx replaces each wrapper with the real destination. This also works for nested and double-encoded wrappers:
  - Google `google.com/url?q=` and AMP pages (`google.com/amp/s/...`)
  - YouTube `/redirect` (links in video descriptions)
  - Facebook `l.facebook.com`, `lm.facebook.com`, `l.messenger.com`, `l.instagram.com`
  - Outlook Safe Links, Steam's link filter, `out.reddit.com`, Tumblr `t.umblr.com`, Medium `/r/`, LinkedIn `/redir/redirect`, XING, Slack, VK, Pocket, DeviantArt and `href.li`
- **Short links:** Linx expands short links, then cleans them. Linx reads only the redirect from the shortener. It never loads the destination page. If a short code is dead and goes to a homepage, Linx does not change the link. To disable this, set `EXPAND_SHORT_LINKS=false`.
  - Site shorteners: `amzn.to`, `a.co`, `amzn.eu`, `amzn.asia`, `vm.tiktok.com`, `vt.tiktok.com`, `tiktok.com/t/...`, Reddit `/r/<sub>/s/...`, `spotify.link`, `spoti.fi`, `pin.it`, `apple.co`, `fb.me`
  - General shorteners: `bit.ly`, `j.mp`, `t.co`, `tinyurl.com`, `ow.ly`, `buff.ly`, `rb.gy`, `cutt.ly`, `is.gd`, `v.gd`, `rebrand.ly`, `tiny.cc`, `shorturl.at`, `s.id`, `dlvr.it`, `trib.al`, `bl.ink`, `smarturl.it`. For these, Linx always replies to show the real destination.

## Setup

1. Create an application named **Linx** at https://discord.com/developers/applications.
2. On its **Bot** page, click **Reset Token** and copy the token. Then enable **Message Content Intent** and save.
3. Double-click **`start.bat`**. On the first run, it installs all dependencies and asks for the token. It saves the token to `.env`.
4. To add Linx to your server, open the invite link that Linx prints in the window.
5. Optional: let people use Linx in DMs and in servers that do not have Linx. On the app's **Installation** page, select **User Install** and add the `applications.commands` scope. Then open the second link that Linx prints. This link adds Linx to your own account.

Linx is online only while the window is open. If the token is wrong, Linx removes it from `.env` and asks for a new token on the next run.

## Server settings

People with the **Manage Server** permission control Linx in their server. Linx shows the settings in private replies, so other people do not see them.

- `/server settings` shows the current settings. To change a setting, give its option:
  - `auto_clean`: reply to links that people post. When this is off, Linx answers only `/clean` and **Clean links**.
  - `fix_x_links`: change X links to fixvx.
  - `expand_short_links`: expand short links such as `bit.ly`.
  - `hide_original_embeds`: hide the embed on the original message after Linx replies.
  - `delete_reaction`: the ❌ reaction. See [Deleting Linx's reply](#deleting-linxs-reply).
- `/server ignore-channel` stops automatic cleaning in a channel or in a full category. Threads use the setting of their channel. `/clean` still works in an ignored channel.
- `/server watch-channel` starts automatic cleaning again in an ignored channel.

`FIX_X_LINKS`, `EXPAND_SHORT_LINKS` and `SUPPRESS_ORIGINAL_EMBEDS` set the default for each server that did not change that setting. `EXPAND_SHORT_LINKS=false` disables expansion in all servers.

## Deleting Linx's reply

Linx adds a ❌ reaction to each link that it posts in a server. These people can click it:

- the person that Linx posted the link for
- people with the **Manage Messages** permission in that channel

When one of them clicks ❌, Linx deletes its post. Linx also restores the embed on the original message.

Linx needs the **Add Reactions** permission for this. Servers that added Linx before this release must give Linx this permission. Or they can invite Linx again with the new invite link.

## Using Linx where it is not installed

When Linx is on your account (Setup step 5), `/clean` and **Clean links** work in all servers and in DMs. Linx is not a member of those servers, so Linx cannot do these things there:

- clean links automatically
- hide embeds
- add the ❌ reaction
- send notifications

Some servers do not let outside apps post public messages. In those servers, Linx sends a private reply that only you can see.

## Reply and reaction notifications

When Linx posts a clean link for a person, replies and reactions to the post go to Linx, not to that person. So Linx sends them to that person by DM:

- For `/clean` and **Clean links**, notifications go to the person who used the command.
- For automatic replies, notifications go to the person who posted the original link.

Linx sends the two types of notification differently:

- **Replies:** Linx sends each reply immediately, with the reply text and a link to it.
- **Reactions:** Linx collects reactions into a bundle. After the first reaction, Linx waits 30 seconds. Then it sends all reactions from that period in one DM. A reaction after that starts a new bundle.

Each person controls their own notifications with `/notifications`. Without options, it shows the current settings.

- `/notifications replies:False` disables reply notifications. `/notifications reactions:False` disables reaction notifications. To disable all notifications, set both to `False`.
- `/notifications bundle_seconds:120` changes the bundle period. The range is 0 to 3600 seconds. With 0, Linx sends each reaction immediately.

Linx stores the settings in `data/linx.db` (or `$LINX_DATA_DIR/linx.db`). People who block DMs from server members do not get notifications.

## Running with Docker

To run Linx on a server all the time, build the image. Then give it the settings in an env file (see `.env.example`):

```sh
docker build -t linx .
docker run -d --name linx --restart unless-stopped --env-file .env -v linx-data:/data linx
```

`docker logs linx` shows the invite link. You must put the token in `.env`, because the container cannot ask for it.

## Tests

```powershell
.venv\Scripts\python -m unittest
```

To run the tests with Docker, use this command. It runs as your user, so the tests can read `.env`:

```sh
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD":/src -w /src linx python -m unittest
```

## Customizing

The lists of tracking parameters are at the top of `cleaner.py`:

- `GLOBAL_TRACKING_PARAMS` and `GLOBAL_TRACKING_PREFIXES` apply to all links.
- `SITE_RULES` apply only to specific sites. For example, `si` is tracking on YouTube and Spotify, but it may have a real meaning on other sites.
- `UNWRAPPERS` lists the redirect wrappers.

`shortlinks.py` lists the supported short-link services. Linx contacts only those hosts.

## Branding

`branding/` contains the avatar (`logo.png`, 1024×1024) and the profile banner (`banner.png`, 1500×600). It also contains the SVG sources and `generate.py`, which makes the images again from the SVG sources.
