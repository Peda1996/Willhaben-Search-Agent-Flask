# Willhaben Search Agent

Home Assistant add-on (és önállóan is futtatható Docker alkalmazás), amely
rendszeres időközönként lekérdezi a megadott [willhaben.at](https://www.willhaben.at/)
keresési URL-eket, és **Telegramon** értesít az új hirdetésekről és az
árcsökkenésekről. Beépített webes felülettel: deal feed szűréssel/rendezéssel,
árelőzményekkel és gyors műveletgombokkal.

Ez a repó egyben egy **Home Assistant add-on repository** – közvetlenül
hozzáadható a Home Assistant add-on store-hoz, és onnan telepíthető/frissíthető.

## Funkciók

- **Periodikus crawl** – körönként egy mentett keresés, körkörösen.
- **Strukturált kinyerés** – a willhaben `__NEXT_DATA__` JSON-jából ár, eladó
  típusa (magán/kereskedő), hely + koordináták, feltöltés ideje, képek és
  autó-attribútumok (évjárat, km, üzemanyag, váltó, teljesítmény).
- **Árcsökkenés-figyelés** – minden crawl újraellenőrzi a már látott hirdetések
  árát, és jelez, ha csökkent (`price_history` tábla őrzi a teljes trailt).
- **Gazdag Telegram értesítések** – fotó + ár + főbb adatok + hely (Google Maps
  linkkel) + hirdetés kora, inline gombokkal (⭐ Merken / ✉️ Kontaktiert /
  ✅ Gekauft / 🔇 Stumm / ✍️ Nachricht / 🗺️ Karte).
- **Deal feed** (`/deals`) – szűrhető, rendezhető lista minden hirdetésről.

## Telepítés Home Assistantben (add-on)

1. **Settings → Add-ons → Add-on Store → ⋮ (jobb felül) → Repositories**
2. Illeszd be:
   `https://github.com/szepnorbee/Willhaben-Search-Agent-Flask`
3. A store-ban megjelenik a **Willhaben Search Agent** – telepítsd, majd
   **Start**. (Ajánlott: *Start on boot* és *Watchdog* bekapcsolása.)
4. **OPEN WEB UI** (vagy `http://<HOME-ASSISTANT-IP>:5000`) → a *Configuration*
   űrlapon add meg a Telegram botod tokenjét, egy `start_password`-öt, a
   `check_frequency`-t és opcionálisan az `offer_factor`-t.
5. A Telegram botodnak küldd el: `/start <start_password>`
6. Add hozzá a figyelendő willhaben kereséseket (webes **Add URL**, vagy a
   botban `/addurl <név> <url>`).

Részletes leírás: [`willhaben-agent/DOCS.md`](willhaben-agent/DOCS.md).

### Frissítés

Ha a repóban új verzió jelenik meg (a
[`willhaben-agent/config.yaml`](willhaben-agent/config.yaml) `version:` mezője
emelkedik), a Home Assistant add-on oldalán megjelenik az **Update** gomb.

## Önálló futtatás (Docker Compose, Home Assistant nélkül)

```bash
git clone https://github.com/szepnorbee/Willhaben-Search-Agent-Flask.git
cd Willhaben-Search-Agent-Flask
docker compose up --build -d
```

A felület: `http://localhost:5000`. Az adatok a `./data` mappába kerülnek.
Frissítés: `./update.sh`.

### Helyi futtatás Python-nal (fejlesztés)

```bash
cd willhaben-agent
pip install -r requirements.txt
cd src
python app.py
```

Az adatok ilyenkor a `willhaben-agent/src/data` mappába kerülnek (a `DATA_DIR`
környezeti változóval felülírható).

## Telegram parancsok

| Parancs | Leírás |
|---|---|
| `/start <jelszó>` | A bot aktiválása ehhez a chathez |
| `/help` | Súgó |
| `/addurl <név> <url>` | Új figyelt keresés |
| `/listurls` | Figyelt keresések listája |
| `/removeurl <id>` | Keresés törlése ID alapján |
| `/stop` | Leiratkozás |

## Projektstruktúra

```
repository.yaml            Home Assistant add-on repository manifest
docker-compose.yml         Önálló futtatás
willhaben-agent/           Maga az add-on
├── config.yaml            Add-on manifest (verzió, port, slug)
├── build.yaml             Build alap image
├── Dockerfile
├── run.sh                 Entrypoint
├── requirements.txt
└── src/
    ├── app.py             Flask alkalmazás
    ├── bot.py             Telegram bot
    ├── crawlers/willhaben.py
    ├── listings.py        Kinyerés + formázás
    ├── db_utils.py        SQLite
    └── config.py
```

## Licenc

MIT.
