def schedule_crawler():
    from .willhaben import schedule_crawler as schedule_crawler_willhaben
    schedule_crawler_willhaben()

    from .kleinanzeigen import schedule_crawler as schedule_crawler_kleinanzeigen
    schedule_crawler_kleinanzeigen()
