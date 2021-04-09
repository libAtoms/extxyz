import numpy as np

from ase.constraints import full_3x3_to_voigt_6_stress
from ase.calculators.singlepoint import SinglePointCalculator

# partition ase.calculators.calculator.all_properties into two lists:
#  'per-atom' and 'per-config'
per_atom_properties = ['forces',  'stresses', 'charges',  'magmoms', 'energies']
per_config_properties = ['energy', 'stress', 'dipole', 'magmom', 'free_energy']

def create_single_point_calculator(atoms, info=None, arrays=None, calc_prefix=''):
    """
    Move results from info/arrays dicts to an attached SinglePointCalculator

    Args:
        atoms (ase.Atoms): input structure
        info (dict, optional): Dictionary of per-config values. Defaults to atoms.info
        arrays (dict, optional): Dictionary of per-atom values. Defaults to atoms.arrays
        calc_prefix (str, optional): String prefix to prepend to canonical name
    """
    if info is None:
        info = atoms.info
    if arrays is None:
        arrays = atoms.arrays
    calc_results = {}

    # first check for per-config properties, energy, free_energy etc.
    for prop in per_config_properties:
        if calc_prefix + prop in info:
            calc_results[prop] = info.pop(calc_prefix + prop)

    # special case for virial -> stress conversion
    if calc_prefix + 'virial' in info:
        virial = info.pop(calc_prefix + 'virial')
        stress = - full_3x3_to_voigt_6_stress(virial / atoms.get_volume())
        if 'stress' in calc_results:
            raise RuntimeError(f'stress {stress} and virial {virial} both present')
        calc_results['stress'] = stress

    # now the per-atom properties - forces, energies, etc.
    for prop in per_atom_properties:
        if calc_prefix + prop in arrays:
            calc_results[prop] = arrays.pop(calc_prefix + prop)

    # special case for local_virial -> stresses conversion
    if calc_prefix + 'local_virial' in arrays:
        virials = arrays.pop(calc_prefix + 'local_virial')
        stresses = - full_3x3_to_voigt_6_stress(virials / atoms.get_volume())
        if 'stresses' in calc_results:
            raise RuntimeError(f'stresses {stresses} and virial {virials} both present')
        calc_results['stress'] = stress

    calc = None
    if calc_results:
        calc = SinglePointCalculator(atoms, **calc_results)
    return calc


def update_atoms_from_calc(atoms, calc=None, calc_prefix=''):
    """Update information in atoms from results in a calculator

    Args:
        atoms (ase.atoms.Atoms): Atoms object, modified in place
        calc (ase.calculators.Calculator, optional): calculator to take results from.
            Defaults to :attr:`atoms.calc`
        calc_prefix (str, optional): String to prefix to results names
            in `atoms.arrays` and `atoms.info.`
    """
    if calc is None:
        calc = atoms.calc
    for prop, value in calc.results.items():
        if prop in per_config_properties:
            atoms.info[calc_prefix + prop] = value
        elif prop in per_atom_properties:
            atoms.arrays[calc_prefix + prop] = value
        else:
            raise KeyError(f'unknown property {prop}')

