# -*- coding: utf-8 -*-
from typing import Mapping, Any
from pathlib import Path
import numpy as np


class IndCal(object):
    def __init__(self, specs: Mapping[str, Any]):
        self._root_dir: Path = Path(specs['root_dir']).resolve()
        self._lib_name: str = specs['impl_lib']
        self._cell_name: str = specs['impl_cell']
        self._em_base_path = self._root_dir / 'em_sim'

        self._lib_path = self._em_base_path / self._lib_name
        self._model_path = self._lib_path / self._cell_name
        self._center_tap: bool = specs['center_tap']

    def sym_ind_cal(self):
        """
        Calculate inductance and Q for given y parameter file.
        """
        ym_file = self._model_path / f'{self._cell_name}.y'
        try:
            with open(ym_file, 'r') as f:
                lines = f.readlines()
        except FileNotFoundError:
            print(f'Y parameter file {ym_file} is not found')
        else:
            results = []
            for i, line in enumerate(lines):
                yparam = np.fromstring(line, sep=' ')
                # get frequency and real yparam
                f = yparam[0]
                yparam = yparam[1:]

                if self._center_tap:
                    # get real part and imag part
                    real_part = yparam[::2].reshape(3, 3)
                    imag_part = yparam[1::2].reshape(3, 3)
                    # get complex value
                    y = real_part + imag_part * 1j
                    # get z parameters
                    zdiff = 2 * np.divide(y[1, 2] + y[0, 2],
                                          np.multiply(y[1, 2], (y[0, 0] - y[0, 1])) -
                                          np.multiply(y[0, 2], (y[1, 0] - y[1, 1])))
                else:
                    # get real part and imag part
                    real_part = yparam[::2].reshape(2, 2)
                    imag_part = yparam[1::2].reshape(2, 2)
                    # get complex value
                    y = real_part + imag_part * 1j
                    # get z parameters
                    zdiff = np.divide(4, y[0, 0] + y[1, 1] - y[0, 1] - y[1, 0])

                z11 = np.divide(1, y[0, 0])
                z22 = np.divide(1, y[1, 1])

                # get l and qs
                ldiff0 = np.imag(zdiff)/2/np.pi/f
                qdiff0 = np.imag(zdiff) / np.real(zdiff)

                # add to list
                results.append(dict(freq=f, ldiff=ldiff0, qdiff=qdiff0))

            return results
