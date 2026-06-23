# Lokal demo og stille én-minutts videoguide

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
pnpm dev:down
```

## Opptaksrekkefølge — omtrent 60 sekunder

Opptaket skal være helt uten lyd. Vis bare handlingene under i angitt rekkefølge og tidsrom.

1. **0–7 s:** Åpne `http://127.0.0.1:3000/nb/login`, logg inn som
   `kari.eksempel+caseworker@demo.invalid`, og åpne den nyeste saken med tittelen
   _Syntetisk søknad om tilrettelegging_.
2. **7–17 s:** Vis _Venter på manuell vurdering_ og høy risiko. Åpne **Dokumenter**, velg
   _Syntetisk rutine for saksbehandling_, og klikk **Se metadata**. Vis tolking, indeksering og
   godkjent kildestatus.
3. **17–28 s:** Skroll til **Strukturerte opplysninger** og klikk **Åpne arbeidsflytspor**. Vis
   status, tidslinje og slutt-tilstand.
4. **28–38 s:** Åpne `http://127.0.0.1:8000/docs` i en ny fane. Åpne
   `POST /api/retrieval/answer`, velg **Try it out**, erstatt eksempelkroppen med det forberedte
   JSON-objektet, og velg **Execute**. Vis `answered`, `[S1]` og kildeobjektet i svaret.
5. **38–50 s:** Gå tilbake til applikasjonsfanen, logg ut, og logg inn som
   `ole.eksempel+reviewer@demo.invalid`. Åpne **Godkjenninger**, velg vurderingspakken for samme
   `DEMO-34-…`-sak, velg **Rediger og godkjenn**, skriv en kort syntetisk slutttekst, og bekreft.
6. **50–60 s:** Logg ut, logg inn som `per.eksempel+admin@demo.invalid`, åpne **Revisjon**, og vis
   de nye hendelsene. Åpne deretter **Evalueringer** og den nyeste kjøringen via **Åpne kjøring**.
