# telegram-marketplace-bot

## הגדרת משתני סביבה (DATABASE_URL)

ודאו שהכתובת היא בפורמט אסינכרוני עם asyncpg:

```bash
export DATABASE_URL="postgresql+asyncpg://USER:PASSWORD@HOST:5432/DBNAME"
```

הפורמטים הבאים יומרו אוטומטית בזמן טעינת הקונפיג ל‑asyncpg, אבל מומלץ לעדכן אותם במקור:
- `postgres://...`
- `postgresql://...`
- `postgresql+psycopg2://...`

בזמן אתחול המסד יופיע בלוגים איזו ספריית דרייבר נטענת בפועל, צפוי:
`Database driver loaded: postgresql+asyncpg`.