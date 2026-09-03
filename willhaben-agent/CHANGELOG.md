# Changelog

## 1.0.0

- Első kiadás Home Assistant add-onként.
- A projekt egykonténeressé alakítva: a Selenium-alapú kleinanzeigen.de crawler
  eltávolítva, csak a willhaben.at figyelés maradt (tiszta HTTP kérések).
- Az adatok (`urls.db`, `config.json`) a Supervisor által kezelt `/data`
  könyvtárba kerülnek, így add-on újraindítás/frissítés után megmaradnak.
- A webes felület a `5000/tcp` porton érhető el (OPEN WEB UI).
