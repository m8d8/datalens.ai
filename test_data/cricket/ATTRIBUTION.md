# Cricket demo data: attribution

The files in this directory are derived from **Cricsheet** (https://cricsheet.org):

- Match data: https://cricsheet.org/downloads/ipl_json.zip (Indian Premier League, JSON format v1.2.0)
- Player register: https://cricsheet.org/register/people.csv

Cricsheet data is made available under the **Open Data Commons Attribution License (ODC-BY 1.0)**:
http://opendatacommons.org/licenses/by/1.0/

## Changes made

These files are *not* the original Cricsheet data. They were produced by
`examples/demo/build_demo_data.py`, which:

- keeps IPL seasons from 2017 onward;
- normalises each match into five related entities: `matches`, `deliveries`,
  `players`, `teams`, `venues`;
- writes `day1/` (all matches up to the second-to-last match day) and `day2/` (one
  match day later, with **deliberately injected schema and data drift, synthetic
  e-mail addresses, and corrupted values**). See `manifest.json` for the full list.

Do not use `day2/` as a source of real cricket statistics.

To regenerate:

```bash
python examples/demo/build_demo_data.py --out test_data/cricket
```
