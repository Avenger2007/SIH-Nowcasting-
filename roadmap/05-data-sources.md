# 05 · Data Sources

Every source, how it is reached, what it gives, and its current status.

---

## Summary

| Leg | Provider | Credential | Status |
|---|---|---|---|
| Satellite | ISRO / MOSDAC | none | **Live** |
| Multiple radars | India Meteorological Department | none | **Live** (3 sites publish) |
| Model data | Open-Meteo (GFS / ECMWF) | none | **Live** |
| Lightning | IITM / ENTLN / Blitzortung | institutional | Adapter ready, no feed |
| Surface | OpenWeatherMap | optional | Live via model fallback |
| Boundaries (India) | ISRO Bhuvan / NRSC | none | **Live** |
| World base map | Natural Earth 1:110m | none | **Committed** |

---

## 1 · Satellite — INSAT-3DS and INSAT-3DR

**Endpoint**
```
https://mosdac.gov.in/gallery/getImage.php?prod=<product-glob>
```

**Products verified working** — full disk, 2002 × 2242:

| Channel | Product glob | Wavelength | Use |
|---|---|---|---|
| IR1 | `3SIMG_*_L1B_STD_IR1_V*.jpg` | 10.8 µm | Primary — cloud-top temperature |
| IR2 | `3SIMG_*_L1B_STD_IR2_V*.jpg` | 12.0 µm | Split-window pair with IR1 |
| WV | `3SIMG_*_L1B_STD_WV_V*.jpg` | 6.8 µm | Mid-level moisture, dry intrusions |
| VIS | `3SIMG_*_L1B_STD_VIS_V*.jpg` | 0.65 µm | Daytime cloud texture |
| MIR | `3SIMG_*_L1B_STD_MIR_V*.jpg` | 3.9 µm | Low cloud and fog discrimination |
| 3DR IR1 | `3RIMG_*_L1B_STD_IR1_V*.jpg` | 10.8 µm | Second platform at 74° E |

The `3SIMG_` prefix is **INSAT-3DS** — confirmed by the header printed inside
the image itself. Sub-satellite longitude 82° E; INSAT-3DR sits at 74° E.

**The split-window difference (IR1 − IR2)** is a genuine convective
diagnostic. Optically thick anvils are near black-body in both channels so the
difference approaches zero, while thin cirrus shows a large positive
difference. It separates active storm tops from leftover high cloud, which
single-channel infrared cannot do.

**Limitations**
- Rendered 8-bit browse imagery, so Kelvin is inferred from an assumed display
  stretch and the scene saturates at the cold end.
- Only the newest scan is served, hence the rolling frame buffer.
- Not calibrated. A free MOSDAC account unlocks L1B NetCDF with true Kelvin.

**Upgrade path** — register at `mosdac.gov.in/signup` (1–2 day approval) and
set `MOSDAC_USERNAME` / `MOSDAC_PASSWORD`.

---

## 2 · Multiple radars — IMD Doppler Weather Radar

**Endpoint**
```
https://mausam.imd.gov.in/Radar/{product}_{station}.gif
```

| Product | Meaning |
|---|---|
| `caz` | Composite maximum reflectivity — the one used |
| `ppz` | PPI reflectivity, lowest tilt |
| `ppv` | PPI radial velocity — rotation signatures |
| `sri` | Surface rainfall intensity |
| `pac` | Precipitation accumulation |
| `vp2` | VAD wind profile |

**Decoding.** These are rendered products; reflectivity is encoded in the
colour palette. Two things make the decode trustworthy:

1. **The palette is read from the legend printed inside each image**, not
   hardcoded, so it adapts if a station uses a different scale.
2. **The PPI disc is located from the terrain basemap**, excluding the
   cross-section panels, station info box and legend — all of which are drawn
   in the same palette colours as the echoes.

Decoded values are sane: Delhi 1.65% echo coverage with a 40 dBZ peak, Goa
0.03% (clear), Jot 0.68% with a 58 dBZ convective core.

**Limitation — important and honest.** Of 36 mapped sites, only **Delhi, Goa
and Jot** currently publish public products. The multi-radar composite
therefore usually has one contributing radar. The system probes the network
and reports live status rather than implying full coverage.

**Upgrade path** — institutional access to IMD Level-II volume data would give
all sites plus true dBZ instead of a palette inversion.

---

## 3 · Model data — convective parameters

**Endpoint**
```
https://api.open-meteo.com/v1/forecast
```
Open data, no key, GFS / ECMWF blend. Licence CC-BY 4.0.

| Parameter | Symbol | Meaning |
|---|---|---|
| Convective Available Potential Energy | CAPE | The fuel |
| Convective Inhibition | CIN | The lid holding it down |
| Lifted Index | LI | Negative means unstable |
| Precipitable water | PWAT | Moisture available to rain out |
| Deep-layer shear | — | Derived: 10 m to 500 hPa vector difference |
| K-index, Total Totals | — | Derived classical thunderstorm indices |

Live example for Delhi: CAPE 1650 J/kg, LI −2.6 K.

**Production alternative.** NOAA NOMADS serves GFS GRIB2 directly and is also
open. It is documented in `utils/datasources/nwp.py` but not enabled, because
decoding GRIB2 needs `cfgrib`/`eccodes` — heavy native dependencies kept out
of the install so the demo works everywhere.

---

## 4 · Lightning — the missing leg

Lightning is both a predictor and the training target.

| Network | Operator | Access |
|---|---|---|
| IITM/ISRO LLN | Indian Institute of Tropical Meteorology | Institutional |
| ENTLN | Earth Networks | Commercial; IMD subscribes |
| GLD360 | Vaisala | Commercial |
| Blitzortung | Community | Contributor account |

There is **no space-based lightning mapper over India** — INSAT carries no
optical lightning imager, unlike GOES-16's GLM.

**What is implemented.** Feature extraction (strike density, CG/IC ratio,
lightning jump ratio, nearest-strike distance), a forward-looking label
builder, a Blitzortung adapter, and a **local archive adapter**. Drop a CSV
with `time,lat,lon[,type]` into `data/lightning/` and the pipeline gains real
labels immediately.

**Why the jump ratio matters.** A rapid rise in intracloud flash rate — the
"lightning jump" — often precedes severe weather at the surface by 10 to 20
minutes, which sits exactly in the nowcasting window.

---

## 5 · Boundaries — ISRO Bhuvan

**Endpoint**
```
https://bhuvan-vec1.nrsc.gov.in/bhuvan/wms
```

| Layer | Use |
|---|---|
| `basemap:STATE_BDY_UPD` | State boundaries, overlaid on imagery |
| `basemap:india_state_ql` | Filled states, globe texture |
| `basemap:INDIA_DIST` | District boundaries |

**Why this source specifically.** India's official external boundary differs
from the de-facto lines shown by international datasets. Natural Earth,
OpenStreetMap and GADM depict the Line of Control, not the boundary the
Government of India recognises. Bhuvan is operated by the National Remote
Sensing Centre, Department of Space, and carries the Survey of India
depiction.

Verified current: Ladakh appears as a Union Territory distinct from Jammu &
Kashmir, reflecting the 2019 reorganisation.

**There is no fallback.** If Bhuvan is unreachable, no boundary is drawn and
the UI explains why. A test enforces this so it cannot be quietly changed.

---

## 6 · World base map — Natural Earth, with India carved out

The globes need the rest of the world, or a viewer cannot see where the Indian
domain sits. `data/world/earth_texture.png` is a 4096x2048 equirectangular
raster — every coastline, a distinct colour per country, and one blue for
ocean, sea and inland water alike.

| | |
|---|---|
| Geometry | Natural Earth 1:110m, public domain |
| Built by | `tools/build_world_atlas.py`, offline |
| Fetched at runtime | Never. The raster is committed. |
| Served by | `utils/datasources/worldmap.py` |

**Three countries are drawn without any border: India, Pakistan and China.**
Those are the polygons whose Natural Earth outlines run along frontiers India
contests — Pakistan's takes in Gilgit-Baltistan and what India calls PoK,
China's takes in Aksai Chin and stops short of Arunachal Pradesh. They keep a
neutral land fill instead, which depicts terrain and claims nothing. Every
other country, including Nepal, Bhutan, Bangladesh, Myanmar and Afghanistan,
is drawn normally, because none of those boundaries is contested.

India is then drawn on the layer above the sphere, from the Bhuvan raster
described in section 5. That raster covers India's full official extent, Aksai
Chin and PoK included, so the frontiers a viewer actually sees along those
margins are the Survey of India ones — never Natural Earth's.

The effect is that **no foreign dataset ever draws an Indian boundary**, at
runtime or in the committed artefact. `tests/test_pipeline.py` asserts the
exclusion set, and asserts that the build script and the runtime module agree
on it, so the app can never describe a map it is not drawing.

Colours are assigned by greedy graph colouring over an adjacency graph derived
from the geometry itself, so no two countries that share a border share a
colour. Neither the Natural Earth downloads nor any other third-party
boundary file is committed to this repository.

---

## Attribution

- Satellite imagery: ISRO / MOSDAC, INSAT-3DS and INSAT-3DR IMAGER
- Radar products: India Meteorological Department, `mausam.imd.gov.in`
- Administrative boundaries: ISRO Bhuvan / NRSC, Department of Space,
  Survey of India depiction
- World coastlines and non-Indian boundaries: Natural Earth 1:110m,
  public domain
- Numerical model data: Open-Meteo (GFS / ECMWF IFS), CC-BY 4.0
- Surface observations: OpenWeatherMap
