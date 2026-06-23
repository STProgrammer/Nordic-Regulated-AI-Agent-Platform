# Lokal demo og én-minutts videogjennomgang

Denne guiden viser én sikker, syntetisk porteføljedemo av en norsk regulert saksflyt. Den bruker
bare `demo.invalid`-kontoer og oppdiktet innhold. Ikke bruk ekte personopplysninger, passord eller
skjermbilder med hemmeligheter.

## Klargjøring før opptak

Kjør dette fra repository-roten. Kommandoen under slår på lokale, deterministiske leverandører for
indeksering og direkte RAG-svar; den gjør ingen eksterne modellkall og er ikke en påstand om modell-
eller søkekvalitet.

```bash
NORDIC_API_EMBEDDING_PROVIDER=deterministic \
NORDIC_API_RAG_COMPLETION_PROVIDER=deterministic \
pnpm dev:up

docker compose --env-file .env.example exec api \
  alembic -c apps/api/alembic.ini upgrade head

read -r -s NORDIC_LOCAL_SEED_PASSWORD
export NORDIC_LOCAL_SEED_PASSWORD
docker compose --env-file .env.example exec -T \
  -e NORDIC_LOCAL_SEED_PASSWORD api \
  python scripts/seed_phase34_demo.py \
  --password-env NORDIC_LOCAL_SEED_PASSWORD
```

Seed-kommandoen skriver én JSON-linje med sikre UUID-er, `demo.invalid`-e-postadresser og tekniske
ruter. De tekniske rutene er bare støtteinformasjon: **ikke** lim dem inn eller vis dem i opptaket.
Hvert kall lager en ny, separat syntetisk demo-sak og sletter ikke tidligere data.

### Klargjør én API-innliming før skjermopptak

Før du starter opptaket, kopier **bare verdien** under `rag_answer_request` fra den ferske
seed-utskriften til utklippstavlen. Det er den eneste teksten som skal limes inn mens du tar opp.
Kopier hele det indre JSON-objektet, inkludert de ytterste klammene, men ikke hele seed-linjen eller
navnet `rag_answer_request`.

Objektet har alltid denne formen; bruk den faktiske `case_id`-verdien som seed-kommandoen nettopp
skrev ut, ikke plassholderen under:

```json
{
  "answer_language": "nb",
  "case_id": "<case_id-fra-den-ferske-seed-utskriften>",
  "question": "Hva må dokumenteres før et svar kan brukes?"
}
```

Dette forberedes før skjermopptaket. Når opptaket begynner, bruker du bare nettleseren og
applikasjonens navigasjon. Terminalen, seed-utskriften og UUID-rutene skal ikke være med i bildet.

Bruk en oppdiktet lokal passordfrase. Den skal ikke vises, skrives i et skript, lagres i historikk
eller legges i videoen. Etter opptaket:

```bash
unset NORDIC_LOCAL_SEED_PASSWORD
pnpm dev:reset
```

`pnpm dev:reset` is deliberately destructive for this local Compose project: it removes the seeded
database, Redis, and Azurite volumes so the next startup returns to the clean migration-only mode.
Do not use it when local data should be retained.

## Opptaksrekkefølge — omtrent 60 sekunder

1. **0–7 s: Innlogging og innboks.** Åpne `http://127.0.0.1:3000/nb/login` og logg inn som
   `kari.eksempel+caseworker@demo.invalid`. Du kommer til **Saker**. Åpne den nyeste saken med
   tittelen _Syntetisk søknad om tilrettelegging_. Noter det korte `DEMO-34-…`-saksnummeret som
   vises øverst på sakssiden; det brukes bare for å finne samme sak i godkjenningskøen. Si: «Dette
   er en rollebasert, norsk saksflate. Kontoen og dataene er syntetiske.»
2. **7–17 s: Sak og dokument.** Vis _Venter på manuell vurdering_ og høy risiko. I seksjonen
   **Dokumenter**, velg _Syntetisk rutine for saksbehandling_ og klikk **Se metadata**. Pek på
   ferdig tolking, indeksering og godkjent kildestatus. Si: «Råfiler eksponeres ikke i nettleseren;
   flaten viser styrt metadata og kildegovernance.»
3. **17–28 s: Evidens og spor.** Skroll til **Strukturerte opplysninger**, som allerede er fylt fra
   den seedede saken, og klikk **Åpne arbeidsflytspor**. Vis status, tidslinje og avgrenset
   slutt-tilstand. Si: «Flyten er sporbar med avgrensede metadata og timing — ikke hemmeligheter,
   promptinnhold eller rå dokumenttekst.»
4. **28–38 s: Direkte RAG med sitat.** Åpne API-dokumentasjonen i en ny nettleserfane på
   `http://127.0.0.1:8000/docs`. Åpne `POST /api/retrieval/answer`, velg **Try it out**, marker hele
   eksempelkroppen og erstatt den med det ene forberedte JSON-objektet fra utklippstavlen. Velg
   **Execute**. Vis `answered`, `[S1]` og kildeobjektet i svaret. Si: «I denne lokale demoen er
   svaret deterministisk og viser bare grounding- og siteringsmekanikken; det er ikke en
   kvalitetsmåling eller et eksternt modellkall.»
5. **38–50 s: Menneskelig beslutning.** Gå tilbake til applikasjonsfanen, logg ut og logg inn som
   `ole.eksempel+reviewer@demo.invalid`. Velg **Godkjenninger** i menyen, åpne vurderingspakken med
   det samme korte `DEMO-34-…`-saksnummeret, velg **Rediger og godkjenn**, skriv en kort syntetisk
   slutttekst og bekreft. Si: «Høy risiko kan ikke omgå menneskelig godkjenning; KI-utkast og
   menneskelig slutttekst bevares separat.»
6. **50–60 s: Kontroll og kvalitet.** Logg ut og inn som `per.eksempel+admin@demo.invalid`. Velg
   **Revisjon** i menyen og vis de nye hendelsene. Velg deretter **Evalueringer** og åpne den nyeste
   kjøringen via **Åpne kjøring**. Si: «Beslutninger kan revideres, og deterministiske
   evalueringsresultater er tilgjengelige for regresjonskontroll.»

## Ærlighetsmerking og avgrensning

- Saks-, dokument-, evidens-, trace- og evalueringshistorikken er forhåndsseedet syntetisk for et
  kort og repeterbart opptak.
- RAG-kallet og reviewer-godkjenningen utføres live i den lokale stakken. Det lokale RAG-svaret er
  deterministisk fixture-plumbing og må omtales slik.
- Denne guiden er ikke en video-fil, en skydeployering eller en påstand om at Azure-ressurser er
  provisjonert. Produksjons- og deploy-klargjøring beskrives separat i senere faser.
