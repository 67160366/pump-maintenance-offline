# Public datasets and attribution

These are the original CSV bytes used by the committed training reports, included
to reproduce the work and run the offline demo without a separate download.
Do not interpret either dataset as validated measurements from the user's pump.

| File | Source | License |
| --- | --- | --- |
| `ai4i/ai4i2020.csv` | [AI4I 2020 Predictive Maintenance Dataset, UCI](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset), DOI [10.24432/C5HS5C](https://doi.org/10.24432/C5HS5C) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| `Large_Industrial_Pump_Maintenance_Dataset.csv` | [Large Industrial Pump Maintenance Dataset, Selona Maris / Kaggle](https://www.kaggle.com/datasets/selonamaris/large-industrial-pump-maintenance-dataset) | MIT, as declared by the Kaggle dataset API on 2026-10-27; notice in `licenses/pump-MIT.txt` |

The original CSV values/labels are unchanged. Demo selection/reordering is recorded
separately in `runtime/demo_provenance.json`; derived artifacts are explicitly labeled.
`sources.json` records hashes, source URLs, and the verified pump license metadata.
