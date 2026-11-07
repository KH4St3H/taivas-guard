# 16 Protect TX as well as RX frequencies

Status: ready-for-agent
Type: task
Size: M
Blocked by: none
Priority: Do now. Ticket 14 must not export before this lands.
Owns: `ific_guard/screening/stations.py`, `ific_guard/screening/rule_stations.py`, `_stations_affected` in `ific_guard/terrestrial/rule_field_strength.py`, their tests

## Why

Both station checks protect the RX band only, and Traficom has said that is not enough.

Pekka (Traficom, Discord, 2026-11-07 8:53):

> Protected is the Finnish usage, i.e. RX frequencies in table, in some cases TX frequencies (if RX frequencies are not separately noted) is the ones to be protected. Note also, that TX frequencies are generally received in Finland (f. ex. BC and TV stations are received all around the transmitters, with even high gain antennas, fixed use have another end of the linki (i.e. receiving TX frequency of the link transmitter in the excel)) so possible high pfd's within Finland territory might raise concern.
>
> [Broadcasting:] Whole coverage area around them, see previous note. General rule: every TX is received in Finland.

## Effect on the sheet

Counted on the 873 loaded stations:

| Rows | Count | Change |
|---|---|---|
| TX and RX differ | 572 | TX band is newly screened |
| TX only, no RX | 58 | TX band is newly screened; these rows are skipped today |
| TX equals RX | 240 | None, already covered |
| No frequency at all | 3 | None, stay flagged and unscreened |

That is 630 newly screened bands.

## Do

1. Add a way to get a station's protected bands, each labelled `rx` or `tx`, with equal bands reduced to one. Use it in both rules. Keep `rx_band_mhz`.
2. `rule_stations.py`: screen every protected band (`:64`, `:94`). Each result must say which side matched.
3. `rule_field_strength.py`, `_stations_affected` (`:698`): the same change. A station's coordinates are not where a TX band is received: the receiver is the far end of a link, or anywhere in a broadcast coverage area. A field calculated at the site for a TX match must say so, and must not be presented as the field at the receiver.
4. Reword text that now misstates the rule: the assumptions at `rule_stations.py:71-76` (the "unanswered" and "may not be a receiver" notes), the "receive band" case title, and the module and `_stations_affected` docstrings. Attribute the new assumption to Traficom. Check `frontend/` for the same wording.
5. Regenerate `outputs/ific_3074/` and `outputs/ific_3076/`. This needs `IFIC_SHARED_DATA` pointing at the IFIC archives, which are not in a fresh checkout. If ticket 14 will regenerate them anyway, say so in the report rather than skipping silently.

## Acceptance

- The loader's counts above are covered by a test, including the 3 rows with no frequency.
- Tests cover: an RX-only match, a TX-only match, a station where TX equals RX producing one band, and a TX-only row (for example row 363, 107.5 MHz) now protected.
- The report gives before and after case counts for 3074 and 3076, split into cases found by RX and cases found only through TX. These are the over-flagging evidence for ticket 02 question 4.
- Spot-check 3 TX-only cases by hand against the spreadsheet and the `.mdb`.
- `uv run pytest` passes.

## Not in scope

- Modelling a coverage radius or far-end location. Screening uses frequency, and the pfd rule already evaluates points across Finland.
- Linking pfd results to stations. See ticket 18.
- Changing severity or scoring to compensate for more cases. Report the counts first.
