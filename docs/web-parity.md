# YouTube Music web parity

This checklist tracks how closely the fork matches music.youtube.com on a desktop browser.
Each row names one region or behaviour of the web app, then the status here.
A row is done only when a Pilot test covers it and a live click test in kitty passes.

Status values: `done`, `partial`, `todo`.

## Layout

| # | Web region | Here | Status |
| --- | --- | --- | --- |
| L1 | Left guide: Home, Explore, Library | Footer buttons and `g h` / `g b` / `g l` | partial |
| L2 | Left guide: your playlists | Playlist sidebar | done |
| L3 | Top bar: search box | Search page | partial |
| L4 | Main area: Home shelves of cover cards | Home page | done |
| L5 | Bottom player bar: cover, title, artist, controls, progress, volume | Playback bar | partial |
| L6 | Real cover art everywhere | Covers on Home only | partial |

## Behaviour

| # | Web action | Here | Status |
| --- | --- | --- | --- |
| B1 | Click a song card: play it | Home card click, Enter | done |
| B2 | Click an album or playlist card: open its page | Home card click, Enter | done |
| B3 | Shelf ◀ ▶ arrows scroll the row | Shelf arrow buttons, Shift+wheel, tilt wheel | done |
| B4 | Search from the top bar, results by type | Search page | partial |
| B5 | Album and playlist page: big cover, Play, track list | Context page | partial |
| B6 | Player bar: play/pause, next, previous, seek by click | Playback bar | partial |
| B7 | Up next queue | Queue page | partial |
| B8 | Like a song | `+` key and track actions | partial |
| B9 | Explore: new releases, charts, moods | Browse page | partial |
