# YouTube Music web parity

This checklist tracks how closely the fork matches music.youtube.com on a desktop browser.
Each row names one region or behaviour of the web app, then the status here.
A row is done only when a Pilot test covers it and a live click test in kitty passes.

Status values: `done`, `partial`, `todo`.

## Layout

| # | Web region | Here | Status |
| --- | --- | --- | --- |
| L1 | Left guide: Home, Explore, Library | Sidebar menu with active highlight, footer, `g h` / `g b` / `g l` | done |
| L2 | Left guide: your playlists | Playlist sidebar | done |
| L3 | Top bar: search box | Header search box opens Search with the cursor in it | done |
| L4 | Main area: Home shelves of cover cards | Home page | done |
| L5 | Bottom player bar: cover, title, artist, controls, progress, volume | Playback bar with real cover | partial |
| L6 | Real cover art everywhere | Home, album and playlist pages, player bar. Not yet Search, Library, Explore | partial |

## Behaviour

| # | Web action | Here | Status |
| --- | --- | --- | --- |
| B1 | Click a song card: play it | Home card click, Enter | done |
| B2 | Click an album or playlist card: open its page | Home card click, Enter | done |
| B3 | Shelf ◀ ▶ arrows scroll the row | Shelf arrow buttons, Shift+wheel, tilt wheel | done |
| B4 | Search from the top bar, results by type | Search page | partial |
| B5 | Album and playlist page: big cover, Play, track list | Hero header: cover, details, Play, Shuffle, Save, Radio | done |
| B6 | Player bar: play/pause, next, previous, seek by click | Playback bar | partial |
| B7 | Up next queue | Queue page | partial |
| B8 | Like a song | `+` key and track actions | partial |
| B9 | Explore: new releases, charts, moods | Browse page | partial |
| B10 | Library page: grid of your playlists | "Select a playlist" placeholder | todo |
| B11 | Back to Home is instant | Home feed cached for 10 minutes | done |

## Speed

| # | Web | Here | Status |
| --- | --- | --- | --- |
| S1 | A song starts in about 1 s | 10 to 15 s (stream resolution through yt-dlp) | todo |
| S2 | A 400-track playlist opens in about 2 s | about 10 s | todo |
