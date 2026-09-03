# Willhaben Search Agent

Ez az add-on egy Flask webalkalmazást és egy Telegram botot futtat, amely
rendszeres időközönként lekérdezi a megadott willhaben.at keresési URL-eket,
és Telegramon értesít az új hirdetésekről, valamint az árcsökkenésekről.

## Telepítés

1. **Settings → Add-ons → Add-on Store → ⋮ (jobb felül) → Repositories**
2. Add hozzá a repót:
   `https://github.com/szepnorbee/Willhaben-Search-Agent-Flask`
3. A store-ban jelenik meg a **Willhaben Search Agent** – telepítsd.
4. Indítsd el (**Start**). Érdemes bekapcsolni a *Start on boot* és a
   *Watchdog* opciót.

## Beállítás

Az add-onnak nincs külön beállítási panelje – a konfiguráció a webes felületen
történik.

1. Nyisd meg a webes felületet: **OPEN WEB UI** gomb, vagy
   `http://<HOME-ASSISTANT-IP>:5000`
2. A **Searches** oldalon a *Configuration* űrlapon add meg:
   - **check_frequency** – másodperc két keresési kör között (körönként egy
     mentett keresés fut le, körkörösen).
   - **telegram_token** – a [@BotFather](https://t.me/BotFather)-től kapott
     bot token.
   - **start_password** – tetszőleges jelszó, ezzel aktiválod a botot.
   - **offer_factor** – az ajánlott vételár = kért ár × ez a szorzó
     (alapértelmezett: `0.87`).
3. Mentés után a Telegram botodnak küldd el: `/start <start_password>`
4. Add hozzá a figyelendő willhaben kereséseket:
   - a webes felület **Add URL** mezőjében, vagy
   - a botban: `/addurl <név> <willhaben-URL>`

A willhaben oldalon állítsd össze a keresést a szűrőkkel, majd a böngésző
címsorából másold ki a teljes URL-t.

## Használat

- **🔥 Deal Feed** – az összes látott hirdetés szűrhető/rendezhető listája,
  árváltozással, árelőzményekkel és gombokkal (Merken / Kontaktiert / Gekauft /
  Stumm / Nachricht / Karte).
- **⚙️ Searches** – mentett keresések és a konfiguráció.
- **🕓 History** – a talált hirdetések naplója.

### Telegram parancsok

| Parancs | Leírás |
|---|---|
| `/start <jelszó>` | A bot aktiválása ehhez a chathez |
| `/help` | Súgó |
| `/addurl <név> <url>` | Új figyelt keresés |
| `/listurls` | Figyelt keresések listája |
| `/removeurl <id>` | Keresés törlése ID alapján |
| `/stop` | Leiratkozás az értesítésekről |

## Adatok

Minden állapot a Supervisor által kezelt `/data` könyvtárba kerül
(`urls.db`, `config.json`), így az add-on újraindítása vagy frissítése után
megmarad.

## Frissítés

Amikor a repóban új verzió jelenik meg (a `config.yaml` `version:` mezője
emelkedik), a Home Assistant add-on oldalán megjelenik az **Update** gomb.
