#!/usr/bin/env python3
import json, argparse
from pathlib import Path
from typing import Any, Dict

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logfile")
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args()

    from cclib.io import ccread

    data = ccread(args.logfile)
    if data is None:
        raise RuntimeError("cclib failed to parse the file.")

    def get(obj, name, default=None):
        return getattr(obj, name, default) if hasattr(obj, name) else default

    EV_PER_HARTREE = 27.211386245988

    scfenergies = get(data, "scfenergies")
    scfenergies_au = [float(e)/EV_PER_HARTREE for e in scfenergies] if scfenergies is not None else None

    out: Dict[str, Any] = {
        "file": Path(args.logfile).name,
        "metadata": get(data, "metadata") or {},
        "charge": float(get(data, "charge")) if get(data, "charge") is not None else None,
        "multiplicity": int(get(data, "mult")) if get(data, "mult") is not None else None,
        "nbasis": int(get(data, "nbasis")) if get(data, "nbasis") is not None else None,
        "natoms": int(get(data, "atomcoords")[-1].shape[0]) if get(data, "atomcoords") is not None else None,
        "scf_energies_au": scfenergies_au,
        "final_scf_energy_au": scfenergies_au[-1] if scfenergies_au else None,
        "vibrations": {
            "frequencies_cm-1": get(data, "vibfreqs"),
            "ir_intensities_km/mol": get(data, "vibirs"),
            "force_constants_mDyneA": get(data, "vibfconsts"),
            "reduced_masses_amu": get(data, "vibredmass"),
        },
        "dipole_moment_debye": (lambda dip:
            {"x": float(dip[0]), "y": float(dip[1]), "z": float(dip[2]),
             "total": float((dip[0]**2+dip[1]**2+dip[2]**2)**0.5)} if dip is not None else None
        )( (get(data,"moments")[1] if get(data,"moments") and len(get(data,"moments"))>1 else None) ),
        "mulliken_charges": [float(x) for x in get(data,"mulliken_charges")[-1]] if get(data,"mulliken_charges") is not None else None,
        "zpe_au": float(get(data, "zpve")) if get(data,"zpve") is not None else None,
        "atom_numbers": get(data, "atomnos").tolist() if get(data, "atomnos") is not None else None,
        "final_geometry_angstrom": get(data, "atomcoords")[-1].tolist() if get(data, "atomcoords") is not None else None,
    }

    out_path = Path(args.out) if args.out else Path(args.logfile).with_suffix(".cclib.json")
    out_path.write_text(json.dumps(out, indent=2))
    print(f"Saved: {out_path}")

if __name__ == "__main__":
    main()
