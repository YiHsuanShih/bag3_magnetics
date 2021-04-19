import argparse

from bag.io import read_yaml
from bag.util.misc import register_pdb_hook

from bag3_magnetics.measurement.emsim.em_sim import EmSim

register_pdb_hook()


def parse_options() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run EMX on cell from spec file.')
    parser.add_argument('specs', help='YAML specs file name.')
    args = parser.parse_args()
    return args


def run_main(args: argparse.Namespace) -> None:
    specs = read_yaml(args.specs)
    em = EmSim(specs)

    em.run_simulation()


if __name__ == '__main__':
    _args = parse_options()
    run_main(_args)
