# Radio Coverage Simulator

Interactive tool to simulate and visualize radio coverage of base stations on a real map, using industry-standard propagation models.

Built as a portfolio project during a BSc in Telecommunications Systems Engineering (ETSETB – UPC), applying knowledge from an internship at Cellnex Telecom (Connectivity – Technology & Planning).

---

## Features

- **Three propagation models** selected automatically by frequency:
  - Okumura-Hata (150–1500 MHz) — mobile networks
  - COST-231 Hata (1500–2000 MHz) — high-band LTE
  - Free Space Path Loss / ITU-R P.530 (> 2 GHz) — microwave backhaul
- **ITU-R P.838 rain attenuation** — active above 5 GHz, with configurable rain intensity
- **Multi-antenna best-server mode** — simulates how coverage is distributed across multiple base stations
- **RSSI vs distance chart** — compares signal decay across environments (urban / suburban / rural) and rain conditions
- **CSV export** of all calculated points
- Frequency presets for real-world bands: 900 MHz, 1800 MHz, 7 / 15 / 23 / 38 GHz

---

## Coverage levels

| Color     | Level       | RSSI            |
| --------- | ----------- | --------------- |
| 🟢 Green  | Excellent   | > −80 dBm       |
| 🔵 Blue   | Good        | −80 to −90 dBm  |
| 🟠 Orange | Marginal    | −90 to −100 dBm |
| 🔴 Red    | No coverage | < −100 dBm      |

---

## Tech stack

- **Python 3.9+**
- **Streamlit** — interactive web interface
- **Folium + streamlit-folium** — interactive maps
- **NumPy / Pandas** — numerical calculations and data handling
- **Plotly** — RSSI vs distance chart

---

## Installation

```bash
git clone https://github.com/your-username/radio-simulator.git
cd radio-simulator

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

---

## Project structure

```
radio-simulator/
├── app.py            # Streamlit interface
├── models.py         # Propagation models, rain attenuation, link budget
├── requirements.txt
└── README.md
```

---

## Limitations

- Okumura-Hata and COST-231 are empirical models valid up to ~20 km. Results beyond that range are not reliable.
- FSPL assumes clear line-of-sight — no terrain obstruction is modelled.
- Rain attenuation is negligible below 5 GHz and is not applied in that range.
- Multi-antenna mode is designed for local areas (antennas within ~20 km of each other).
