from __future__ import annotations

from typing import Any, Mapping, Optional, Union, Sequence, Tuple, cast
from pathlib import Path
from shutil import copy
import numpy as np
import matplotlib.pyplot as plt

from bag.simulation.cache import SimulationDB, DesignInstance, SimResults, MeasureResult
from bag.simulation.measure import MeasurementManager, MeasInfo
from bag.simulation.core import TestbenchManager
from bag.simulation.data import SimData

from bag3_testbenches.measurement.sp.base import SPTB


class IndSPMeas(MeasurementManager):
    def get_sim_info(self, sim_db: SimulationDB, dut: DesignInstance, cur_info: MeasInfo,
                     harnesses: Optional[Sequence[DesignInstance]] = None
                     ) -> Tuple[Union[Tuple[TestbenchManager, Mapping[str, Any]],
                                      MeasurementManager], bool]:
        raise NotImplementedError

    def initialize(self, sim_db: SimulationDB, dut: DesignInstance,
                   harnesses: Optional[Sequence[DesignInstance]] = None) -> Tuple[bool, MeasInfo]:
        raise NotImplementedError

    def process_output(self, cur_info: MeasInfo, sim_results: Union[SimResults, MeasureResult]
                       ) -> Tuple[bool, MeasInfo]:
        raise NotImplementedError

    async def async_measure_performance(self, name: str, sim_dir: Path, sim_db: SimulationDB,
                                        dut: Optional[DesignInstance],
                                        harnesses: Optional[Sequence[DesignInstance]] = None) -> Mapping[str, Any]:
        # add n4port
        s4p_file: str = self.specs['s4p_file']
        ind_s4p = 'ind.s4p'
        sim_dir.mkdir(parents=True, exist_ok=True)
        copy(Path(s4p_file), sim_dir / ind_s4p)
        load_list = [dict(conns={'t1': 'plus0', 'b1': 'VSS', 't2': 'minus0', 'b2': 'VSS', 't3': 'plus1', 'b3': 'VSS',
                                 't4': 'minus1', 'b4': 'VSS'}, type='n4port', value=ind_s4p)]

        # add ports
        load_list.extend([dict(conns={'PLUS': 'plus0', 'MINUS': 'minus0'}, type='port', value={'r': 50}, name='PORT0'),
                          dict(conns={'PLUS': 'plus1', 'MINUS': 'minus1'}, type='port', value={'r': 50}, name='PORT1')])

        sim_envs: Sequence[str] = self.specs['sim_envs']
        assert len(sim_envs) == 1, 'This measurement supports only one sim_env at a time.'
        tbm_specs = dict(
            **self.specs['tbm_specs'],
            load_list=load_list,
            sim_envs=self.specs['sim_envs'],
            param_type='Z',
            ports=['PORT0', 'PORT1'],
        )
        tbm = cast(SPTB, self.make_tbm(SPTB, tbm_specs))
        sim_results = await sim_db.async_simulate_tbm_obj(name, sim_dir, dut, tbm, {})
        data = sim_results.data

        query_freq: float = self.specs['query_freq']
        return estimate_ind(data, query_freq)


def estimate_ind(data: SimData, query_freq: float) -> Mapping[str, float]:
    freq = data['freq']
    w_arr = 2 * np.pi * freq

    z11 = np.squeeze(data['z11'])
    z22 = np.squeeze(data['z22'])
    z12 = np.squeeze(data['z12'])
    z21 = np.squeeze(data['z21'])

    l0 = z11.imag / w_arr
    l1 = z22.imag / w_arr
    q0 = z11.imag / z11.real
    q1 = z22.imag / z22.real
    lm0 = z12.imag / w_arr
    lm1 = z21.imag / w_arr
    assert np.isclose(lm0, lm1).all()

    # query
    freq_idx = np.where(freq >= query_freq)[0][0]
    print(f'At frequency = {query_freq * 1e-9} GHz, the measured values are:')
    print(f'Inductance 0: {l0[freq_idx] * 1e12} pH with Q = {q0[freq_idx]}')
    print(f'Inductance 1: {l1[freq_idx] * 1e12} pH with Q = {q1[freq_idx]}')
    print(f'Inductance mutual: {lm0[freq_idx] * 1e12} pH')
    results = dict(
        freq=query_freq,
        l0=l0[freq_idx],
        q0=q0[freq_idx],
        l1=l1[freq_idx],
        q1=q1[freq_idx],
        lm=lm0[freq_idx],
    )

    # plot
    fig0, (ax0, ax1, ax2) = plt.subplots(3)
    ax0.plot(freq * 1e-9, l0 * 1e12)
    ax0.set(xlabel='Frequency (GHz)', ylabel='Inductance 0 (pH)')
    ax0.grid()

    ax1.plot(freq * 1e-9, l1 * 1e12)
    ax1.set(xlabel='Frequency (GHz)', ylabel='Inductance 1 (pH)')
    ax1.grid()

    ax2.plot(freq * 1e-9, lm0 * 1e12)
    ax2.set(xlabel='Frequency (GHz)', ylabel='Inductance mutual (pH)')
    ax2.grid()

    fig1, (ax3, ax4) = plt.subplots(2)
    ax3.plot(freq * 1e-9, q0)
    ax3.set(xlabel='Frequency (GHz)', ylabel='Q 0')
    ax3.grid()

    ax4.plot(freq * 1e-9, q1)
    ax4.set(xlabel='Frequency (GHz)', ylabel='Q 1')
    ax4.grid()

    plt.tight_layout()
    plt.show()

    return results
