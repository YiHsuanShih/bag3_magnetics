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
        # add nport
        sp_file: Path = Path(self.specs['sp_file'])
        ext = sp_file.suffix[1:]
        ind_sp = f'ind.{ext}'
        sim_dir.mkdir(parents=True, exist_ok=True)
        copy(sp_file, sim_dir / ind_sp)
        nport_terms: Sequence[str] = self.specs['nport_terms']
        conns = {}
        for idx, term in enumerate(nport_terms):
            conns[f't{idx + 1}'] = term
            conns[f'b{idx + 1}'] = 'VSS'
        load_list = [dict(conns=conns, type=f'n{ext[1]}port', value=ind_sp)]

        # add ports
        port_conns: Sequence[Mapping[str, str]] = self.specs['port_conns']
        ports = []
        for idx, _conns in enumerate(port_conns):
            _name = f'PORT{idx}'
            ports.append(_name)
            load_list.append(dict(conns=_conns, type='port', value={'r': 50}, name=_name))

        sim_envs: Sequence[str] = self.specs['sim_envs']
        assert len(sim_envs) == 1, 'This measurement supports only one sim_env at a time.'
        tbm_specs = dict(
            **self.specs['tbm_specs'],
            load_list=load_list,
            sim_envs=self.specs['sim_envs'],
            param_type='Z',
            ports=ports,
        )
        tbm = cast(SPTB, self.make_tbm(SPTB, tbm_specs))
        sim_results = await sim_db.async_simulate_tbm_obj(name, sim_dir, dut, tbm, {})
        data = sim_results.data

        query_freq: float = self.specs['query_freq']
        return estimate_ind(data, query_freq, len(ports))


def estimate_ind(data: SimData, query_freq: float, num_port: int) -> Mapping[str, float]:
    freq = data['freq']
    w_arr = 2 * np.pi * freq

    z11 = np.squeeze(data['z11'])
    l0 = z11.imag / w_arr
    q0 = z11.imag / z11.real

    # query
    freq_idx = np.where(freq >= query_freq)[0][0]
    print(f'At frequency = {query_freq * 1e-9} GHz, the measured values are:')
    print(f'Inductance 0: {l0[freq_idx] * 1e12} pH with Q = {q0[freq_idx]}')
    print(f'Resistance 0: {z11.real[freq_idx]} ohm')

    results = dict(
        freq=query_freq,
        l0=l0[freq_idx],
        q0=q0[freq_idx],
        r0=z11.real[freq_idx],
    )

    # plot
    fig1, ax1_list = plt.subplots(num_port)

    if num_port == 2:
        fig0, ax0_list = plt.subplots(3, 2)
        ax00 = ax0_list[0, 0]
        ax01 = ax0_list[0, 1]
        ax1 = ax1_list[0]
    else:
        fig0, ax0_list = plt.subplots(1, 2)
        ax00 = ax0_list[0]
        ax01 = ax0_list[1]
        ax1 = ax1_list
    ax00.plot(freq * 1e-9, z11.real)
    ax00.set(xlabel='Frequency (GHz)', ylabel='Resistance 0 (Ohm)')
    ax00.grid()
    ax01.plot(freq * 1e-9, l0 * 1e12)
    ax01.set(xlabel='Frequency (GHz)', ylabel='Inductance 0 (pH)')
    ax01.grid()

    ax1.plot(freq * 1e-9, q0)
    ax1.set(xlabel='Frequency (GHz)', ylabel='Q 0')
    ax1.grid()

    if num_port == 2:
        z22 = np.squeeze(data['z22'])
        z12 = np.squeeze(data['z12'])
        z21 = np.squeeze(data['z21'])
        l1 = z22.imag / w_arr
        q1 = z22.imag / z22.real
        lm0 = z12.imag / w_arr
        lm1 = z21.imag / w_arr
        assert np.isclose(lm0, lm1).all()

        print(f'Inductance 1: {l1[freq_idx] * 1e12} pH with Q = {q1[freq_idx]}')
        print(f'Resistance 1: {z22.real[freq_idx]} ohm')
        print(f'Inductance mutual: {lm0[freq_idx] * 1e12} pH')

        results.update(dict(
            l1=l1[freq_idx],
            q1=q1[freq_idx],
            r1=z22.real[freq_idx],
            lm=lm0[freq_idx],
        ))

        ax0_list[1, 0].plot(freq * 1e-9, z22.real)
        ax0_list[1, 0].set(xlabel='Frequency (GHz)', ylabel='Resistance 1 (Ohm)')
        ax0_list[1, 0].grid()
        ax0_list[1, 1].plot(freq * 1e-9, l1 * 1e12)
        ax0_list[1, 1].set(xlabel='Frequency (GHz)', ylabel='Inductance 1 (pH)')
        ax0_list[1, 1].grid()

        ax0_list[2, 1].plot(freq * 1e-9, lm0 * 1e12)
        ax0_list[2, 1].set(xlabel='Frequency (GHz)', ylabel='Inductance mutual (pH)')
        ax0_list[2, 1].grid()

        ax1_list[1].plot(freq * 1e-9, q1)
        ax1_list[1].set(xlabel='Frequency (GHz)', ylabel='Q 1')
        ax1_list[1].grid()

    elif num_port > 2:
        raise NotImplementedError(f'This function currently supports num_port = 1 or 2, not num_port={num_port}')

    plt.tight_layout()
    plt.show()

    return results
