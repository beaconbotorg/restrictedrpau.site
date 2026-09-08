# RestrictedRP Website

A complete redesign of the supplied FiveM website using the provided RestrictedRP logo.

## Files
- `index.html` — main landing page
- `style.css` — responsive premium dark/red design
- `script.js` — animations, mobile menu, live FiveM player/status polling, copy server code
- `config.js` — edit your server/Discord/store links
- `assets/restrictedrp-logo.png` — supplied logo

## Setup
1. Upload all files to your web host.
2. Open `config.js`.
3. Change:
   - `serverCode` — your Cfx server code
   - `cfxJoinUrl` — your Cfx join link
   - `discordUrl` — your Discord invite
   - `storeUrl` — your store link
4. That's it. There is no `playersEndpoint` to configure and no FiveM resource/script is required.

## Live players
The website automatically checks the public Cfx.re server-list data using the configured server code and refreshes the live status/player count every 15 seconds.

If the server is publicly listed and reachable by Cfx.re, the site will show values such as `24 / 128` automatically.

If the Cfx.re listing cannot be reached, the site displays `OFFLINE` rather than pretending the server is online.

## Important
This setup uses Cfx.re's public server-list infrastructure rather than a custom API hosted by you. Cfx documents that its infrastructure polls servers for information such as player counts for the server browser.
