# BLS archived release example

This example traces one real observation through three published versions. It is
separate from RewindLab's synthetic fault corpus, whose expected answers can be
controlled exactly.

From the RewindLab repository root:

```bash
PYTHONPATH=src python3 examples/bls/demo.py
```

The event is the **seasonally adjusted month-over-month change in total nonfarm
payroll employment for May 2025** from the U.S. Bureau of Labor Statistics
(BLS) Current Employment Statistics program. Values are changes in **payroll
jobs**; they are neither total employment levels nor investment signals. The
[BLS methods guide](https://www.bls.gov/bls/empsitquickguide.htm) explains that
CES estimates jobs, so a person with two jobs can be counted twice.

| Release | Published value | Source |
| --- | ---: | --- |
| June 6, 2025 | +139,000 | [Archived May Employment Situation](https://www.bls.gov/news.release/archives/empsit_06062025.htm) |
| July 3, 2025 | +144,000 | [Archived June Employment Situation](https://www.bls.gov/news.release/archives/empsit_07032025.htm) |
| August 1, 2025 | +19,000 | [Archived July Employment Situation](https://www.bls.gov/news.release/archives/empsit_08012025.htm) |

The July release states that May was revised from +139,000 to +144,000. The
August release states that May was revised from +144,000 to +19,000. BLS's
[archive index](https://www.bls.gov/bls/news-release/empsit.htm) warns that
values in archived releases can be revised in later releases.

## Timestamp meanings and limits

- `event_id` identifies the measure and May 2025 reference month.
- `valid_at = 2025-05-01T00:00:00Z` is a month-key anchor used by this demo's
  query model. It is not a survey time or the time the employment change
  occurred.
- `known_at` is a **release-time proxy**: each archived report says it was
  embargoed until 8:30 a.m. Eastern time on its release date. Those June,
  July, and August dates were in Eastern Daylight Time, so the fixture uses
  12:30 UTC. This is not a logged website availability time, ingestion time,
  or proof of when any particular researcher received the data.
- Each `source` field is the exact archived BLS release URL supporting that
  version. This tiny curated fixture was transcribed from the release text;
  it is not a live download or a full BLS vintage archive. The fixture was
  checked on October 9, 2026.

BLS says its published material is [public domain and asks for source
attribution](https://www.bls.gov/bls/linksite.htm). The archived HTML pages
are publicly accessible without an API key. For expansion, BLS also publishes
[CES vintage spreadsheets and CSV files](https://www.bls.gov/web/empsit/cesvindata.htm)
and [explains their release-by-reference-month layout](https://www.bls.gov/web/empsit/cesvininfo.htm).
