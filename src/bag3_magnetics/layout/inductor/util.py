# -*- coding: utf-8 -*-
import numpy as np
from typing import Sequence, Mapping, Any

from bag.typing import PointType
from bag.layout.template import TemplateDB, TemplateBase
from bag.layout.util import BBox
from bag.util.immutable import Param

from pybag.enum import PathStyle


def round_up(val_f: float) -> int:
    return int(np.ceil(val_f)) if val_f > 0 else int(np.floor(val_f))


def compute_vertices(n_sides: int, n_turns: int, radius_x: int, radius_y: int, width: int, spacing: int
                     ) -> Sequence[Sequence[PointType]]:
    # Compute vertices in anti-clockwise order starting from bottom right.
    # In order to get 45 degree turns for octagonal case even when radius_x != radius_y,
    # compute all vertices using radius_x and then shift top half based on radius_y
    phase_step = 2 * np.pi / n_sides
    phase_ini = - np.pi / 2 + phase_step / 2
    off_x = radius_x + width // 2

    vertices = [[] for _ in range(n_turns)]
    for tidx in range(n_turns):
        _rad_x = round_up((radius_x - tidx * (width + spacing)) / np.cos(phase_step / 2))
        for sidx in range(n_sides):
            if n_sides // 4 <= sidx < 3 * n_sides // 4:
                off_y = 2 * (radius_y - radius_x)
            else:
                off_y = 0
            _phase = phase_ini + phase_step * sidx
            vertices[tidx].append((off_x + round_up(_rad_x * np.cos(_phase)),
                                   off_x + round_up(_rad_x * np.sin(_phase)) + off_y))
    return vertices


class IndLayoutHelper(TemplateBase):
    """Class for drawing various geometries. This is used as a hack because of the mysterious C++ error that happens
    while drawing multi turn inductor in the normal way"""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            path_list='List of path specification dictionaries',
        )

    def draw_layout(self) -> None:
        top_lay_id = -1

        # draw paths
        path_list: Sequence[Mapping[str, Any]] = self.params['path_list']
        for _specs in path_list:
            lay_id: int = _specs['lay_id']
            lp = self.grid.tech_info.get_lay_purp_list(lay_id)[0]

            style: PathStyle = _specs.get('style', PathStyle.round)

            self.add_path(lp, _specs['width'], list(_specs['points']), style, join_style=style)
            top_lay_id = max(top_lay_id, lay_id)

        # set size
        self.set_size_from_bound_box(top_lay_id, BBox(0, 0, 10, 10), round_up=True)
