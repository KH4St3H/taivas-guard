# Demo script

Steps 1-5 were rehearsed once from an empty database on 2026-11-07, with Space and Terrestrial 3083, at commit d9fee4e. Steps 2b, 2c, 6 and 7 were added later the same day for the reach map, the CEPT check, Trends and screening rules, and **have not been rehearsed yet** (ticket 32). Their numbers come from the development database and can differ on a fresh run.

It takes about 8 minutes, plus about 4 minutes for the first screening.

It needs Docker, Node and internet access to the ITU. Email goes to a file, so nothing is sent.

## Before you start

Use a fresh Compose project so the database is empty.

```sh
cp .env.example .env
```

In `.env`, set these:

```
IFIC_API_KEY=<output of: openssl rand -hex 32>
IFIC_EMAIL_BACKEND=file
IFIC_MIN_ISSUE=3082
```

`IFIC_MIN_ISSUE=3082` limits the first sync to the two newest issues, so the demo doesn't wait for 20 issues. Trends (step 6) need at least two issues to compare; with 3083 alone it says so instead of flagging anything.

Start the review UI in its own terminal. If port 5173 is in use, add `-- --port 5174 --strictPort`.

```sh
cd frontend && npm install && npm run dev
```

## 1. A new issue is picked up

```sh
docker compose -p ificdemo up --build -d
docker compose -p ificdemo logs -f sync | grep fetched
```

**Show:** the sync service finds and downloads Space and Terrestrial 3082 and 3083 by itself. Stop following the log, then wait for screening:

```sh
curl -s 'localhost:8001/issues' | python3 -c "import json,sys; [print(i['domain'],i['issue_no'],i['screen_status']) for i in json.load(sys.stdin)]"
```

All four show `done` after a few minutes.

**Open** <http://localhost:5173>. "Latest issue" shows BR IFIC 3083, the comment window and the cases by rule.

**Say:** cron does this on its own schedule. An operator can also press "Check ITU now" or upload a file.

## 2. A case with evidence

Open **Findings**, then a high pfd case. In the rehearsal this was J-BLUEBIRD-NGSO (Japan), `pfd-ngso-app5`, at `/findings/142`. IDs can change between runs.

**Show:**

- The title: it exceeds the trigger in a one-day flight, under worst-case assumptions.
- The calculation: power, gain, and the value of -86.3 dB against -123.0 dB, a margin of +36.7 dB.
- The worst point, with its latitude, longitude, angle and minute of the flight.
- The evidence panel: source file hash, notice ID and regulation citation.
- The assumptions.

**Say:** the numbers come from deterministic rules. No AI decided this case. Maximum gain is applied towards Finland because the beam contours aren't available, so this is a possible concern for an expert.

For contrast, show a case titled "upper bound above the limit". It isn't presented as an exceedance.

## 2b. Where the satellite can reach

Open a "No space-to-Earth allocation in Finland" finding for a GSO satellite. In development this was ARABSAT-12G-1E (Saudi Arabia), at 1° E.

**Show:**

- **Reach over Finland**: the angle above the horizon across the country (9-20° for ARABSAT-12G-1E), then **Worst-case pfd**.
- **Stations on this satellite's frequencies**: listed stations whose RX or TX band overlaps what it transmits, not every station in the wider M4 band (26 for ARABSAT-12G-1E).
- "How this map is made": the transmission the pfd layer assumes, and the frequencies the stations were matched on.

**Say:** the filing has no beam footprint, so this is where it can reach, not where its beam points. Traficom said to assume the worst case.

For a non-GSO contrast, TOUTATIS (France) adds **Minutes in view per day** and **Margin to the RR limit**, and says no listed station shares its frequencies.

## 2c. A CEPT condition

Search Findings for **SPACERAN** (Canada, non-GSO) and open its "pfd against a CEPT condition" case.

**Show:** ECC Decision (25)02 says satellite transmissions in 862-870 MHz must not exceed -142 dB(W/(m²·4 kHz)) on the Earth's surface. SPACERAN's one-day flight reaches about -110.5 dB at 68° N, about 31.5 dB over, and the case says it isn't on the Decision's Annex 2 list of compliant systems.

**Say:** a CEPT condition isn't an RR limit, and the case says so. The value is read from the Decision itself, with its page cited; Finland's implementation is planned for 31 January 2027. Only the top 1 MHz of SPACERAN's 869-890 MHz assignment falls in the Decision's band, which the expert should weigh.

## 3. Expert review

In "Your review", enter a note and press **Accept**. The badge changes to Accepted.

**Say:** accepting sends nothing. If the filing changes in a later issue, the case returns to review. The browser never holds the API key, because the dev server's proxy adds it.

## 4. Draft letter

Until ticket 25 is merged, the finding page shows a browser template. The API draft is the one with the citations and guardrails. Use the case ID from step 2:

```sh
curl -s localhost:8002/cases/142/draft | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['status'], 'sent:', d['sent']); print(d['letter'])"
```

**Show:** the banner "DRAFT FOR EXPERT REVIEW. NOT SENT.", the source data block, and the placeholders the expert completes.

**Say:** this template needs no language model. With `ANTHROPIC_API_KEY` set, `?use_llm=true` asks a model to rewrite it. A guardrail checks each number, date and citation against the case and rejects claims the evidence doesn't support, then falls back to this template.

The language-model path was tested with a fake model only. The rehearsal didn't call a real one.

## 5. Digest email

```sh
docker compose -p ificdemo exec notifier sh -c 'ls /app/data/outbox; grep -h ^Subject /app/data/outbox/*.eml'
```

**Show:** in the rehearsal, the subjects were:

```
BR IFIC 3083 (space): 121 possible concerns for review, 36 high
BR IFIC 3083 (terrestrial): 80 possible concerns for review, 0 high
```

**Say:** there's one digest per issue, not one email per case. It lists severity, rule, notice IDs, the estimated deadline and a review link. Screening the same issue again adds no cases and sends no email.

## 6. Trends

Open **Trends**.

**Show:** in development, with Space 3074, 3082 and 3083 stored, IFIC 3083 flagged Japan (12 notices, from an average of 2) and Saudi Arabia (12, from 0), and V and W band downlinks. The largest new non-GSO system was INDSAT-NGSO-LEO-1 (India), with 1,600 planned satellites. Switch to **Terrestrial** for the neighbours' land-mobile counts.

**Say:** these are descriptive counts with one plain flag rule, stated on the page. They point an expert at what changed; they don't predict anything.

## 7. A rule the expert writes

Open **Screening rules**, then **New rule**. Name it "Uplinks in Finnish terrestrial bands". Under "Which frequencies", choose **Receives (Earth-to-space)**. Under "What M4 says there", set **Earth-to-space allocation** to "Not allocated" and **Primary terrestrial use** to "Yes". Press **Preview** on IFIC 3083.

**Show:** in development this would raise 32 cases, led by China (7) and Saudi Arabia (6), without saving anything.

**Say:** experts change the screening without code. A rule is validated data, every save is a version, and each case names the version that raised it. Saving doesn't change cases until issues are screened again.

## If you have more time

- Show `outputs/ific_3074/` and `outputs/ific_3076/`, the evaluation files.
- Show `outputs/hand-check.md`: what was independently rechecked, and what can't be measured.
- Show the "Known limitations" section of the README.

## Clean up

This deletes the demo project's containers and its volumes only.

```sh
docker compose -p ificdemo down -v
```

## What the rehearsal did not cover

Steps 2b, 2c, 6 and 7 haven't been rehearsed (ticket 32 is open for that), and step 4 changes when ticket 25 lands. Timings and counts above for those steps come from the development database, not a fresh run.

In the first rehearsal, the browser was driven with headless screenshots, and the review was saved through the UI's proxy API rather than by a mouse click on Accept. The draft letter step, the digest and the screening-again check were run on the same stack. Press Accept once yourself before presenting.
