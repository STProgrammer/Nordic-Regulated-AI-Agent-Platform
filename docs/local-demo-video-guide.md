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

Seed-kommandoen skriver én JSON-linje med sikre UUID-er, e-postadresser på `demo.invalid` og ferdige
relative ruter. Ta vare på `case_url`, `trace_url`, `approval_url` og `evaluation_url`; de er rutene
som brukes i opptaket. Hvert kall lager en ny, separat syntetisk demo-sak og sletter ikke tidligere
data.

Bruk en oppdiktet lokal passordfrase. Den skal ikke vises, skrives i et skript, lagres i historikk
eller legges i videoen. Etter opptaket:

```bash
unset NORDIC_LOCAL_SEED_PASSWORD
pnpm dev:down
```

## Opptaksrekkefølge — omtrent 60 sekunder

1. **0–7 s: Innlogging.** Åpne `http://127.0.0.1:3000/nb/login` og logg inn som
   `kari.eksempel+caseworker@demo.invalid`. Si: «Dette er en rollebasert, norsk saksflate. Kontoen
   og dataene er syntetiske.»
2. **7–16 s: Saksinnboks og dokument.** Åpne `case_url` fra seed-utskriften. Vis statusen _avventer
   menneskelig gjennomgang_ og dokumentet _Syntetisk rutine for saksbehandling_. Åpne
   dokumentdetaljer og pek på ferdig parsing, indeksering og godkjent kildestatus. Si: «Råfiler
   eksponeres ikke i nettleseren; flaten viser styrt metadata og kildegovernance.»
3. **16–25 s: Evidens og agentflyt.** Åpne `trace_url`. Vis nodene `source_policy`,
   `hybrid_retrieval` og `evidence_sufficiency`, samt `[S1]`. Si: «Flyten er sporbar med avgrensede
   metadata, kilder og timing — ikke hemmeligheter, promptinnhold eller rå dokumenttekst.»
4. **25–35 s: Direkte RAG med sitat.** Åpne `http://127.0.0.1:8000/docs`, bruk
   `POST /api/retrieval/answer`, og lim inn `rag_answer_request` fra seed-JSON. Vis `answered`,
   `[S1]` og kildeobjektet i svaret. Si: «I denne lokale demoen er svaret deterministisk og viser
   bare grounding- og siteringsmekanikken; det er ikke en kvalitetsmåling eller et eksternt
   modellkall.»
5. **35–47 s: Menneskelig beslutning.** Logg ut, logg inn som `ole.eksempel+reviewer@demo.invalid`,
   og åpne `approval_url`. Velg _rediger og godkjenn_, skriv en kort syntetisk slutttekst og
   bekreft. Si: «Høy risiko kan ikke omgå menneskelig godkjenning; KI-utkast og menneskelig
   slutttekst bevares separat.»
6. **47–57 s: Kontroll og kvalitet.** Logg inn som `per.eksempel+admin@demo.invalid`. Åpne
   `/nb/audit` og deretter `evaluation_url`. Si: «Beslutninger kan revideres, og deterministiske
   evalueringsresultater er tilgjengelige for regresjonskontroll.»
7. **57–60 s: Operasjonelt signal.** Etter at RAG-kallet og godkjenningen er gjort, vis eventuelt
   terminalen med:

   ```bash
   curl -fsS http://127.0.0.1:8000/metrics \
     | rg '^nordic_(api_http|workflow_runs|approval_decisions|evaluation_case)'
   ```

   Si: «Lokale målinger oppstår etter faktiske handlinger; de inneholder ikke person-, saks- eller
   kildeidentifikatorer.»

## Ærlighetsmerking og avgrensning

- Saks-, dokument-, evidens-, trace- og evalueringshistorikken er forhåndsseedet syntetisk for et
  kort og repeterbart opptak.
- RAG-kallet og reviewer-godkjenningen utføres live i den lokale stakken. Det lokale RAG-svaret er
  deterministisk fixture-plumbing og må omtales slik.
- Denne guiden er ikke en video-fil, en skydeployering eller en påstand om at Azure-ressurser er
  provisjonert. Produksjons- og deploy-klargjøring beskrives separat i senere faser.
