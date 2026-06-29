import numpy as np


# ──────────────────────────────────────────
# Frequency band helper
# ──────────────────────────────────────────

def frequency_band(f_mhz: float) -> str:
    """
    Classifies the frequency into a band that determines
    which propagation model and rain attenuation logic to use.

    < 1500 MHz  → mobile (Okumura-Hata)
    1500–2000   → mobile high-band (COST-231 Hata)
    > 2000 MHz  → microwave (Free Space + ITU-R P.530)
    """
    if f_mhz <= 1500:
        return "mobile"
    elif f_mhz <= 2000:
        return "mobile_high"
    else:
        return "microwave"


# ──────────────────────────────────────────
# Mobile propagation models (Okumura-Hata / COST-231)
# ──────────────────────────────────────────

def mobile_correction_factor(f_mhz: float, h_mobile: float, environment: str) -> float:
    """Height correction factor a(hm) for Okumura-Hata."""
    if environment == "urban":
        a = 3.2 * (np.log10(11.75 * h_mobile)) ** 2 - 4.97
    else:
        a = (1.1 * np.log10(f_mhz) - 0.7) * h_mobile - (1.56 * np.log10(f_mhz) - 0.8)
    return a


def okumura_hata(
    f_mhz: float, d_km: float, h_base: float,
    h_mobile: float, environment: str = "urban"
) -> float:
    """Path loss (dB) — Okumura-Hata. Valid for 150–1500 MHz."""
    d_km  = max(d_km, 0.01)
    f_mhz = np.clip(f_mhz, 150, 1500)
    a = mobile_correction_factor(f_mhz, h_mobile, environment)

    Lu = (
        69.55
        + 26.16 * np.log10(f_mhz)
        - 13.82 * np.log10(h_base)
        - a
        + (44.9 - 6.55 * np.log10(h_base)) * np.log10(d_km)
    )
    if environment == "suburban":
        Lu -= 2 * (np.log10(f_mhz / 28)) ** 2 + 5.4
    elif environment == "rural":
        Lu -= 4.78 * (np.log10(f_mhz)) ** 2 + 18.33 * np.log10(f_mhz) + 40.94
    return Lu


def cost231_hata(
    f_mhz: float, d_km: float, h_base: float,
    h_mobile: float, environment: str = "urban"
) -> float:
    """Path loss (dB) — COST-231 Hata. Valid for 1500–2000 MHz."""
    d_km  = max(d_km, 0.01)
    f_mhz = np.clip(f_mhz, 1500, 2000)
    a  = mobile_correction_factor(f_mhz, h_mobile, environment)
    Cm = 3.0 if environment == "urban" else 0.0

    return (
        46.3
        + 33.9 * np.log10(f_mhz)
        - 13.82 * np.log10(h_base)
        - a
        + (44.9 - 6.55 * np.log10(h_base)) * np.log10(d_km)
        + Cm
    )


# ──────────────────────────────────────────
# Microwave propagation model (ITU-R P.530)
# Free Space Path Loss — line-of-sight links
# Valid for > 2 GHz (typical: 7, 15, 23, 38 GHz backhaul bands)
# ──────────────────────────────────────────

def free_space_path_loss(f_mhz: float, d_km: float) -> float:
    """
    Free Space Path Loss (dB) — ITU-R P.530.

    Lu = 92.4 + 20·log10(f_GHz) + 20·log10(d_km)

    Used for microwave point-to-point links (backhaul).
    Assumes line-of-sight with no terrain obstruction.
    """
    d_km  = max(d_km, 0.01)
    f_ghz = f_mhz / 1000.0
    return 92.4 + 20 * np.log10(f_ghz) + 20 * np.log10(d_km)


def select_model(f_mhz: float):
    """Returns the appropriate propagation model based on frequency."""
    band = frequency_band(f_mhz)
    if band == "mobile":
        return okumura_hata
    elif band == "mobile_high":
        return cost231_hata
    else:
        # For microwave, wrap FSPL to accept the same signature as Hata
        def _fspl_wrapper(f_mhz, d_km, h_base, h_mobile, environment):
            return free_space_path_loss(f_mhz, d_km)
        return _fspl_wrapper


# ──────────────────────────────────────────
# Rain attenuation — ITU-R P.838
# Relevant above 5 GHz; critical above 10 GHz
# ──────────────────────────────────────────

_ITU_COEFFS = [
    (1,   0.0000387, 0.912),
    (2,   0.000154,  0.963),
    (4,   0.000650,  1.121),
    (6,   0.00175,   1.308),
    (8,   0.00454,   1.327),
    (10,  0.0101,    1.276),
    (12,  0.0188,    1.217),
    (15,  0.0367,    1.154),
    (20,  0.0751,    1.099),
    (25,  0.124,     1.061),
    (30,  0.187,     1.021),
    (40,  0.350,     0.939),
    (50,  0.536,     0.873),
    (60,  0.707,     0.826),
    (80,  0.975,     0.769),
    (100, 1.12,      0.743),
]

def _itu_coefficients(f_ghz: float) -> tuple:
    """
    Interpolates ITU-R P.838 k and alpha coefficients.
    Below 5 GHz rain attenuation is negligible for mobile networks.
    """
    if f_ghz < 5.0:
        return 0.0, 1.0
    freqs  = [r[0] for r in _ITU_COEFFS]
    ks     = [r[1] for r in _ITU_COEFFS]
    alphas = [r[2] for r in _ITU_COEFFS]
    k     = float(np.interp(f_ghz, freqs, ks))
    alpha = float(np.interp(f_ghz, freqs, alphas))
    return k, alpha


def rain_attenuation_db(f_mhz: float, d_km: float, rain_rate_mmh: float) -> float:
    """
    Additional path loss due to rainfall — ITU-R P.838.

    Parameters:
        f_mhz         : frequency in MHz
        d_km          : link distance in km
        rain_rate_mmh : rain intensity in mm/h
                        (0 = dry, 5 = drizzle, 25 = moderate,
                         50 = heavy, 100 = extreme)
    Returns:
        Rain attenuation in dB (0 if f < 5 GHz)
    """
    if rain_rate_mmh <= 0:
        return 0.0

    f_ghz = f_mhz / 1000.0
    k, alpha = _itu_coefficients(f_ghz)
    if k == 0.0:
        return 0.0

    # Specific attenuation γ in dB/km
    gamma = k * (rain_rate_mmh ** alpha)

    # Effective path length reduction factor (ITU-R P.530)
    r_eff = 1.0 / (1.0 + 0.045 * d_km)

    return gamma * d_km * r_eff


# ──────────────────────────────────────────
# Link budget
# ──────────────────────────────────────────

def calculate_rssi(
    p_tx_dbm: float,
    g_tx_dbi: float,
    path_loss_db: float,
    rain_loss_db: float    = 0.0,
    g_rx_dbi: float        = 0.0,
    extra_losses_db: float = 2.0
) -> float:
    """
    Received power in dBm.
    RSSI = Ptx + Gtx + Grx - PathLoss - RainLoss - ExtraLosses
    """
    return (
        p_tx_dbm + g_tx_dbi + g_rx_dbi
        - path_loss_db - rain_loss_db - extra_losses_db
    )


def classify_coverage(rssi_dbm: float) -> str:
    """Standard LTE coverage thresholds."""
    if rssi_dbm > -80:
        return "excellent"
    elif rssi_dbm > -90:
        return "good"
    elif rssi_dbm > -100:
        return "marginal"
    else:
        return "no_coverage"


# ──────────────────────────────────────────
# Geographic helpers
# ──────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in km between two coordinates (Haversine formula)."""
    R = 6371.0
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi    = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def _build_grid(center_lat, center_lon, radius_km, steps):
    """Returns (lats, lons) arrays for a bounding grid."""
    delta_lat = radius_km / 111.0
    delta_lon = radius_km / (111.0 * np.cos(np.radians(center_lat)))
    lats = np.linspace(center_lat - delta_lat, center_lat + delta_lat, steps)
    lons = np.linspace(center_lon - delta_lon, center_lon + delta_lon, steps)
    return lats, lons


COLOR_MAP = {
    "excellent":   "green",
    "good":        "blue",
    "marginal":    "orange",
    "no_coverage": "red",
}


# ──────────────────────────────────────────
# Single antenna coverage grid
# ──────────────────────────────────────────

def calculate_coverage_grid(
    antenna_lat: float,
    antenna_lon: float,
    f_mhz: float,
    p_tx_dbm: float,
    h_base: float,
    h_mobile: float        = 1.5,
    g_tx_dbi: float        = 15.0,
    g_rx_dbi: float        = 0.0,
    extra_losses_db: float = 2.0,
    environment: str       = "urban",
    radius_km: float       = 10.0,
    rain_rate_mmh: float   = 0.0,
    steps: int             = 50
) -> list:
    """
    Calculates RSSI at each point of a grid around a single antenna.
    Automatically selects Okumura-Hata, COST-231 or FSPL based on frequency.
    Includes optional ITU-R P.838 rain attenuatison (active above 5 GHz).
    """
    model = select_model(f_mhz)
    lats, lons = _build_grid(antenna_lat, antenna_lon, radius_km, steps)

    results = []
    for lat in lats:
        for lon in lons:
            d_km = haversine_km(antenna_lat, antenna_lon, lat, lon)
            if d_km < 0.05:
                continue

            path_loss = model(f_mhz, d_km, h_base, h_mobile, environment)
            rain_loss = rain_attenuation_db(f_mhz, d_km, rain_rate_mmh)
            rssi_dbm  = calculate_rssi(
                p_tx_dbm, g_tx_dbi, path_loss, rain_loss, g_rx_dbi, extra_losses_db
            )
            level = classify_coverage(rssi_dbm)

            results.append({
                "lat":            round(lat, 6),
                "lon":            round(lon, 6),
                "distance_km":    round(d_km, 3),
                "path_loss_db":   round(path_loss, 2),
                "rain_loss_db":   round(rain_loss, 2),
                "rssi_dbm":       round(rssi_dbm, 2),
                "coverage_level": level,
                "color":          COLOR_MAP[level],
            })

    return results


# ──────────────────────────────────────────
# Multiple antennas — best-server logic
# ──────────────────────────────────────────

def calculate_multi_antenna_grid(
    antennas: list,
    f_mhz: float,
    h_mobile: float        = 1.5,
    g_rx_dbi: float        = 0.0,
    extra_losses_db: float = 2.0,
    environment: str       = "urban",
    rain_rate_mmh: float   = 0.0,
    steps: int             = 50
) -> list:
    """
    Coverage for multiple antennas using best-server logic.
    At each grid point, only the antenna with the strongest RSSI is kept.

    Each antenna dict must have: lat, lon, p_tx_dbm, h_base, g_tx_dbi, name
    """
    if not antennas:
        return []

    model = select_model(f_mhz)

    center_lat = np.mean([a["lat"] for a in antennas])
    center_lon = np.mean([a["lon"] for a in antennas])
    max_spread = max(
        haversine_km(center_lat, center_lon, a["lat"], a["lon"])
        for a in antennas
    )
    radius_km = max_spread + 10.0
    lats, lons = _build_grid(center_lat, center_lon, radius_km, steps)

    results = []
    for lat in lats:
        for lon in lons:
            best_rssi    = -999.0
            best_antenna = None

            for antenna in antennas:
                d_km = haversine_km(antenna["lat"], antenna["lon"], lat, lon)
                if d_km < 0.05:
                    continue

                path_loss = model(f_mhz, d_km, antenna["h_base"], h_mobile, environment)
                rain_loss = rain_attenuation_db(f_mhz, d_km, rain_rate_mmh)
                rssi_dbm  = calculate_rssi(
                    antenna["p_tx_dbm"], antenna["g_tx_dbi"],
                    path_loss, rain_loss, g_rx_dbi, extra_losses_db
                )

                if rssi_dbm > best_rssi:
                    best_rssi    = rssi_dbm
                    best_antenna = antenna["name"]

            if best_antenna is None:
                continue

            level = classify_coverage(best_rssi)
            results.append({
                "lat":             round(lat, 6),
                "lon":             round(lon, 6),
                "rssi_dbm":        round(best_rssi, 2),
                "coverage_level":  level,
                "serving_antenna": best_antenna,
                "color":           COLOR_MAP[level],
            })

    return results