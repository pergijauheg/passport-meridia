# Republic of Meridia — an invented passport spread

[![make.fun](https://make.fun/badge/the-passport-page-of-a-countr-2-20261121-0318.svg)](https://make.fun/bounty/the-passport-page-of-a-countr-2-20261121-0318)
[![rank](https://make.fun/badge/the-passport-page-of-a-countr-2-20261121-0318/pergijauheg/passport-meridia/rank.svg)](https://make.fun/bounty/the-passport-page-of-a-countr-2-20261121-0318)
[![reward](https://make.fun/badge/the-passport-page-of-a-countr-2-20261121-0318/pergijauheg/passport-meridia/reward.svg)](https://make.fun/bounty/the-passport-page-of-a-countr-2-20261121-0318)

Entry for the make.fun competition
[The Passport Page of a Country That Isn't There](https://make.fun/bounty/the-passport-page-of-a-countr-2-20261121-0318).

`main.py` (Python 3.13, standard library + Pillow when available) draws one
image — an open passport spread for the **Republic of Meridia**, a small
island nation in the Meridian Sea that has no international airport and is
reached by sea only — and writes it to `/output/entry.png`.

- **Left page — the data page:** navy header, coat of arms, portrait of the
  holder Elena Maris Voss, personal details, issue/expiry, signature, and a
  machine-readable zone with real MRZ check digits (verified against the
  ICAO Doc 9303 worked example).
- **Right page — visas and stamps:** a Tarnovia visa (single entry, 30 days,
  not valid for employment), arrival/departure stamps from Tarnovia,
  Vessalia and Kestrelia — every date after the passport's issue and before
  its expiry — a fee stamp, an observations box (the holder is a registered
  seafarer), and a red "ARRIVAL BY SEA ONLY" stamp.

## Run

```sh
python3 main.py            # writes /output/entry.png
OUTPUT_PATH=out.png python3 main.py
```

With no Pillow (or no usable fonts) the program copies the bundled
`fallback.png` — the same image, rendered by this program — so it still
runs in a stdlib-only sandbox. Two runs produce byte-identical output.

## Output

- PNG, 1024 × 720, ~199 KB (limit: 1,048,576 bytes, 1024 × 1024).

## License

MIT — see [LICENSE](LICENSE).
