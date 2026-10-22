"""Roache grid convergence index for three meshes (pre-registered in docs/prereg/track-b.md).
Source opened: https://www.grc.nasa.gov/www/wind/valid/tutorial/spatconv.html (p = ln[(f3-f2)/(f2-f1)]/ln r; GCI = Fs |(f2-f1)/f1| / (r^p - 1); Fs = 1.25 for >= 3 grids, 3.0 otherwise)."""
import math


def gci(f1, f2, f3, r, p_formal=2.0, unsteady=False):
    """f1 finest, f3 coarsest, constant refinement ratio r. Returns dict(p_obs, p_used, Fs, gci_fine (fraction), flags)."""
    e21, e32 = f2 - f1, f3 - f2
    flags, p_obs = [], None
    if e21 == 0 or e32 == 0:
        flags.append("zero difference between levels: p undefined")
    elif e21 * e32 < 0:
        flags.append("oscillatory (non-monotone) convergence")
    else:
        p_obs = math.log(e32 / e21) / math.log(r)
    if p_obs is not None and not (0.5 < p_obs < 2 * p_formal):
        flags.append(f"observed order {p_obs:.2f} outside (0.5, {2 * p_formal:g})")
    ok = p_obs is not None and not flags
    p, Fs = (p_obs, 1.25) if ok else (p_formal, 3.0)
    if not ok: flags.append(f"Fs = 3.0 with formal order {p_formal:g}")
    if unsteady: flags.append("unsteady: GCI not meaningful")
    g = Fs * abs(e21 / f1) / (r**p - 1)
    return dict(p_obs=p_obs, p_used=p, Fs=Fs, gci_fine=g, change_medium_to_fine=e21 / f1, flags=flags,
                f_richardson=f1 - e21 / (r**p - 1))
