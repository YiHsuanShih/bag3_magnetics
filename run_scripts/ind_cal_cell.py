import argparse

from bag.io import read_yaml
from bag.util.misc import register_pdb_hook

from bag3_magnetics.measurement.emsim.inductor_cal import IndCal

register_pdb_hook()


def parse_options() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Perform inductor calculations on cell from spec file.')
    parser.add_argument('specs', help='YAML specs file name.')
    args = parser.parse_args()
    return args


def run_main(args: argparse.Namespace) -> None:
    specs = read_yaml(args.specs)
    indcal = IndCal(specs)

    print(*indcal.sym_ind_cal(), sep='\n')


if __name__ == '__main__':
    _args = parse_options()
    run_main(_args)
