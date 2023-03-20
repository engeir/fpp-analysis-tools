import fppanalysis.time_delay_estimation as tde
from fppanalysis.conditional_averaging import cond_av
from fppanalysis.running_moments import run_norm
import numpy as np
import xarray as xr

def get_2d_velocities_from_time_delays(delta_tx, delta_ty, delta_x, delta_y):
    """
    Estimates radial and poloidal velocities given the input parameters:
    Input:
         delta_tx Estimation of the time delay between radially separated points.
         delta_ty Estimation of the time delay between poloidally separated points.
         delta_x Spatial separation between radially separated points.
         delta_y Spatial separation between poloidally separated points.

    These quantities should be obtained from three pixel points: a reference pixel point,
    a pixel point separated radially, and a pixel point separated poloidally.
    Returns:
         vx Radial velocity
         vy Poloidal velocity
    """
    if delta_tx == 0:
        return 0, delta_y / delta_ty
    if delta_ty == 0:
        return delta_x / delta_tx, 0
    fx = delta_x / delta_tx
    fy = delta_y / delta_ty
    return fx / (1 + (fx / fy) ** 2), fy / (1 + (fy / fx) ** 2)


def _get_rz(x, y, ds):
    # Sajidah's format
    if hasattr(ds, "time"):
        return ds.R.isel(x=x, y=y).values, ds.Z.isel(x=x, y=y).values
    # 2d code
    if hasattr(ds, "t"):
        return ds.x.isel(x=x).values, ds.y.isel(y=y).values
    raise "Unknown format"


def _get_rz_full(ds):
    # Sajidah's format
    if hasattr(ds, "time"):
        shape = (len(ds.x.values), len(ds.y.values))
        R = np.zeros(shape=shape)
        Z = np.zeros(shape=shape)
        for x in ds.x.values:
            for y in ds.y.values:
                R[x, y] = ds.R.isel(x=x, y=y).values
                Z[x, y] = ds.Z.isel(x=x, y=y).values
        return R, Z
    # 2d code
    if hasattr(ds, "t"):
        return np.meshgrid(ds.x.values, ds.y.values)
    raise "Unknown format"


def _get_signal(x, y, ds):
    # Sajidah's format
    if hasattr(ds, "time"):
        return ds.isel(x=x, y=y).dropna(dim="time", how="any")["frames"].values
    # 2d code
    if hasattr(ds, "t"):
        return ds.isel(x=x, y=y).dropna(dim="t", how="any")["n"].values
    raise "Unknown format"


def _get_dt(ds):
    # Sajidah's format
    if hasattr(ds, "time"):
        times = ds["time"]
        return times[1].values - times[0].values
    # 2d code
    if hasattr(ds, "t"):
        times = ds["t"]
        return times[1].values - times[0].values
    raise "Unknown format"

def run_norm_window(cut_off_freq, good_time):
    '''Returns window size for running normalization'''
    dt = np.diff(good_time)[0]
    t_RM = 1/cut_off_freq
    samples = ((t_RM/dt)-1)/2
    window = int(2*samples)
    return window 

def _estimate_velocities_given_points(p0, p1, p2, ds):
    dt = _get_dt(ds)
    r0, z0 = _get_rz(p0[0], p0[1], ds)
    r1, z1 = _get_rz(p1[0], p1[1], ds)
    r2, z2 = _get_rz(p2[0], p2[1], ds)
    signal0 = _get_signal(p0[0], p0[1], ds)
    signal1 = _get_signal(p1[0], p1[1], ds)
    signal2 = _get_signal(p2[0], p2[1], ds)

    if len(signal0) == 0 or len(signal1) == 0 or len(signal2) == 0:
        return None
    
    # Normalize signal
    freq = 1e3
    window0 = run_norm_window(freq, signal0)  # Find length of time window for running normalization
    window1 = run_norm_window(freq, signal1)
    window2 = run_norm_window(freq, signal2)

    signal0_norm, signal0_time_norm = run_norm(signal0, window0, signal0.time.values)
    signal1_norm, signal1_time_norm = run_norm(signal1, window1, signal1.time.values)
    signal2_norm, signal2_time_norm = run_norm(signal2, window2, signal2.time.values)

    # Cross conditional average
    threshold = 2.5
    Svals1, s_av1, s_var1, t_av1, peaks1, wait1 = cond_av(
        signal1_norm, signal1_time_norm, threshold, Sref=signal0_norm
    )
    norm_s_av1 = s_av1 - min(s_av1)
    norm_s_av1 = norm_s_av1 / max(norm_s_av1)
    # Maximum correlation value: Confidence value
    cx = max(norm_s_av1)    

    Svals2, s_av2, s_var2, t_av2, peaks2, wait2 = cond_av(
        signal2_norm, signal2_time_norm, threshold, Sref=signal0_norm
    )
    norm_s_av2 = s_av2 - min(s_av2)
    norm_s_av2 = norm_s_av2 / max(norm_s_av2)
    # Maximum correlation value: Confidence value
    cy = max(norm_s_av2)    

    # Time lag value at maximum correlation
    delta_tx = t_av1[np.where(norm_s_av1 == cx)]
    delta_ty = t_av2[np.where(norm_s_av2 == cy)]   
    confidence = min(cx, cy)

    return (
        *get_2d_velocities_from_time_delays(delta_tx, delta_ty, r1 - r0, z2 - z0),
        confidence,
    )


def _is_within_boundaries(p, ds):
    return 0 <= p[0] < ds.sizes["x"] and 0 <= p[1] < ds.sizes["y"]


def estimate_velocities_for_pixel(x, y, ds: xr.Dataset):
    """Estimates radial and poloidal velocity for a pixel with indexes x,y
    using all four possible combinations of nearest neighbour pixels (x-1, y),
    (x, y+1), (x+1, y) and (x, y-1). Dead-pixels (stored as np.nan arrays) are
    ignored. Pixels outside the coordinate domain are ignored. Time delay
    estimation is performed by maximizing the cross- correlation function. The
    confidence of the estimation is a value in the interval (0, 1) given by the
    mean of the confidences for each combination, which is given by the minimum
    of the maximums of the two cross-correlations involved (good luck
    understanding this last sentence :))

    Returns:
        vx Radial velocity
        vy Poloidal velocity
        c Confidence on the estimation
    """

    h_neighbors = [(x - 1, y), (x + 1, y)]
    v_neighbors = [(x, y - 1), (x, y + 1)]
    results = [
        _estimate_velocities_given_points((x, y), px, py, ds)
        for px in h_neighbors
        if _is_within_boundaries(px, ds)
        for py in v_neighbors
        if _is_within_boundaries(py, ds)
    ]
    results = [r for r in results if r is not None]
    if len(results) == 0:  # If (x,y) is dead we cannot estimate
        return None, None, None
    mean_vx = sum(map(lambda r: r[0], results)) / len(results)
    mean_vy = sum(map(lambda r: r[1], results)) / len(results)
    confidence = sum(map(lambda r: r[2], results)) / len(results)
    return mean_vx, mean_vy, confidence


def estimate_velocity_field(ds: xr.Dataset):
    """
    Given a dataset ds with GPI data in a format produced by https://github.com/sajidah-ahmed/cmod_functions,
    computed the velocity field. The estimation takes into account poloidal flows as described in
    the 2D filament model. For each pixel, the velocities are estimated using the given pixel, and two neighbour
    pixels: the right neighbour and the down neighbour. The return objects are matrices of the size of the
    GPI grid, from which the velocity field can be easily plotted via f.e matplotlib.quiver.

    Returns:
        vx Radial velocities
        vy Poloidal velocities
        confidences Maximum value of the cross-correlations at each pixel.
        R Radial positions
        Z Radial positions
    """
    shape = (len(ds.x.values), len(ds.y.values))
    vx = np.zeros(shape=shape)
    vy = np.zeros(shape=shape)
    confidences = np.zeros(shape=shape)
    R, Z = _get_rz_full(ds)

    for i in range(0, shape[0]):
        for j in range(0, shape[1]):
            try:
                vx[i, j], vy[i, j], confidences[i, j] = estimate_velocities_for_pixel(
                    i, j, ds
                )
            except:
                print(
                    "Issues estimating velocity for pixel",
                    i,
                    j,
                    "Run estimate_velocities_for_pixel(i, j, ds) to get a detailed error stacktrace",
                )

    vx[np.isnan(vx) | np.isinf(vx)] = 0
    vy[np.isnan(vy) | np.isinf(vy)] = 0
    return vx, vy, confidences, R, Z
