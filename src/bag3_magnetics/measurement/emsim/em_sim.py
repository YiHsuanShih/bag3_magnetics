# -*- coding: utf-8 -*-
import os
import time

from typing import Mapping, Any, List, Tuple
from pathlib import Path

from bag.concurrent.core import SubProcessManager, batch_async_task


class EmSim(object):
    def __init__(self, specs: Mapping[str, Any]):
        self._manager = SubProcessManager(max_workers=3)

        self._params: Mapping[str, Any] = specs['params']
        self._proc_file: Path = Path(specs['proc_file']).resolve()
        self._lib_name: str = specs['impl_lib']
        self._cell_name: str = specs['impl_cell']
        self._root_dir: Path = Path(specs['root_dir']).resolve()
        self._em_base_path = self._root_dir / 'em_sim'
        self._gds_file = self._root_dir / f'{self._cell_name}.gds'

        self._lib_path = self._em_base_path / self._lib_name
        self._model_path = self._lib_path / self._cell_name

    @property
    def manager(self) -> SubProcessManager:
        return self._manager

    @property
    def params(self) -> Mapping[str, Any]:
        """Returns the EM parameters."""
        return self._params

    @property
    def root_dir(self) -> Path:
        """Returns the base directory."""
        return self._root_dir

    @property
    def cell_name(self) -> str:
        """Returns cell name."""
        return self._cell_name

    @property
    def lib_name(self) -> str:
        """Returns lib name."""
        return self._lib_name

    @property
    def model_path(self) -> Path:
        """Returns the em path fo module directory"""
        return self._model_path

    @property
    def emx_path(self) -> Path:
        """Returns emx simulation directory"""
        return self._em_base_path

    def _set_dir(self) -> None:
        """
        set EMX gds and simulation directory
        """
        # create all necessary directories
        self._model_path.mkdir(parents=True, exist_ok=True)

        # check for proc file
        if not self._proc_file.exists():
            raise Exception(f'Cannot find process file: {self._proc_file}')

        # check for gds_path
        if not self._gds_file.exists():
            raise Exception(f'Cannot find gds file: {self._gds_file}')

    def _set_em_option(self) -> Tuple[List[str], List[Path]]:
        em_options: Mapping[str, Any] = self.params['em_options']
        fmin: float = em_options['fmin']
        fmax: float = em_options['fmax']
        fstep: float = em_options['fstep']
        edge_mesh: float = em_options['edge_mesh']
        thickness: float = em_options['thickness']
        via_separation: float = em_options['via_separation']
        show_log: bool = em_options['show_log']
        show_cmd: bool = em_options['show_cmd']

        # mesh option
        mesh_opts = f'-e {edge_mesh} -t {thickness} -v {via_separation} --3d=*'
        # freq option
        freq_opts = f'--sweep {fmin} {fmax} --sweep-stepsize {fstep}'
        # print options
        pr_num = 3 if show_log else 0
        pr_opts = f'--verbose={pr_num}'
        # print cmd options
        cmd_opts = '--print-command-line -l 0' if show_cmd else ''

        # get port list
        port_list: List[str] = self.params['port_list']
        gnd_list: List[str] = self.params['gnd_list']

        # port options: avoid changing the original list
        portlist_n = port_list.copy()
        gndlist_n = gnd_list.copy()
        # remove repeated ports
        for port in gndlist_n:
            portlist_n.remove(port)
        port_string = ''
        for idx, port in enumerate(portlist_n):
            port_string += f' -p P{idx:02d}={port} -i P{idx:02d}'
        n_ports = len(portlist_n)
        for idx, port in enumerate(gndlist_n):
            port_string += f' -p P{(idx + n_ports):02d}={port}'

        # get s/y parameters and model
        # s parameter file
        sp_file = self._model_path / f'{self._cell_name}.s{n_ports}p'
        sp_opts = f'--format=touchstone -s {sp_file}'
        # y parameter file
        yp_file = self._model_path / f'{self._cell_name}.y{n_ports}p'
        yp_opts = f'--format=touchstone -y {yp_file}'
        # y matlab file
        ym_file = self._model_path / f'{self._cell_name}.y'
        ym_opts = f'--format=matlab -y {ym_file}'
        # pz model
        state_file = self._model_path / f'{self._cell_name}.pz'
        st_opts = f'--format=spectre --model-file={state_file} --save-model-state'

        # log file
        log_file = self._model_path / f'{self._cell_name}.log'
        log_opts = f'--log-file={log_file}'

        # other options
        other_opts = '--parallel=4 --max-memory=80% --simultaneous-frequencies=0'

        # get extra options
        extra_opts = ''
        extra_options: Mapping[str, Any] = self.params['extra_options']
        if extra_options:
            for opt, value in extra_options.items():
                extra_opts += f'--{opt}={value} '

        emx_opts = [mesh_opts, freq_opts, port_string, pr_opts, cmd_opts, extra_opts, sp_opts, yp_opts, ym_opts,
                    st_opts, log_opts, other_opts]
        return emx_opts, [sp_file, yp_file, ym_file, state_file, log_file]

    async def gen_nport(self):
        """
        Run EM sim to get nport for the current module.
        """
        # get paths and options   proc_file, gds_file
        self._set_dir()
        emx_opts, outfiles = self._set_em_option()

        # delete log file if exist -- use it for error checking
        if outfiles[-1].exists():
            outfiles[-1].unlink()

        # get emx simulation working
        emx_cmd = [f'{os.environ["EMX_HOME"]}/emx', str(self._gds_file), self._cell_name, str(self._proc_file)]
        print("EMX simulation started.")
        start = time.time()
        await self.manager.async_new_subprocess(emx_cmd + emx_opts, cwd=str(self._em_base_path),
                                                log=f'{self._em_base_path}/bag_emx.log')
        # TODO: Why is it not waiting?

        # check whether ends correctly
        if not outfiles[-1].exists():
            raise Exception('EMX stops with error, please check your EMX command.')
        else:
            period = (time.time() - start) / 60
            print(f'EMX simulation finished successfully.\nLog file is in {outfiles[-1]}')
            print(f'EMX simulation takes {period} minutes')

    def _set_mdl_option(self, model_type: str) -> Tuple[List[str], Path, List[Path]]:
        # model type
        type_opts = f'--type={model_type}'

        ym_file = self._model_path / f'{self._cell_name}.y'

        # scs model
        scs_model = self._model_path / f'{self._cell_name}.scs'
        scs_opts = f'--spectre-file={scs_model}'

        # spice
        sp_model = self._model_path / f'{self._cell_name}.sp'
        sp_opts = f'--spice-file={sp_model}'
                
        mdl_opts = [type_opts, str(ym_file), scs_opts, sp_opts]

        return mdl_opts, ym_file, [scs_model, sp_model]
        
    async def gen_model(self):
        model_type: str = self._params['model_type']
        # get options
        mdl_opts, infile, outfiles = self._set_mdl_option(model_type)

        # delete model file if exist -- use it for error checking
        if outfiles[0].exists():
            outfiles[0].unlink()
        if outfiles[1].exists():
            outfiles[1].unlink()

        # emx command
        mdl_cmd = [f'{os.environ["EMX_HOME"]}/modelgen'] + mdl_opts
        print("Model generation started.\n")
        start = time.time()
        await self.manager.async_new_subprocess(mdl_cmd, cwd=str(self._em_base_path),
                                                log=f'{self._em_base_path}/bag_modelgen.log')

        # check whether ends correctly
        if not outfiles[0].exists() or not outfiles[1].exists():
            raise Exception('\nModel generation stops with error, please check your EMX command.')
        else:
            period = (time.time() - start) / 60
            print('Model generation finished successfully.')
            print(f'Model generation takes {period} minutes')

    def run_simulation(self) -> None:
        coro = self.gen_nport()
        batch_async_task([coro])
        coro = self.gen_model()
        batch_async_task([coro])
