# -*- coding: utf-8 -*-
import numpy as np
import abc
from typing import Sequence, Any

from bag.typing import PointType
from bag.layout.template import TemplateDB, TemplateBase
from bag.layout.util import BBox
from bag.util.immutable import Param


def round_up(val_f: float) -> int:
    return int(np.ceil(val_f)) if val_f > 0 else int(np.floor(val_f))


def compute_vertices(n_turns: int, radius: int, width: int, spacing: int, dx: int, interleave: bool, draw_lead: bool,
                     ) -> Sequence[PointType]:
    xm = ym = width // 2 + radius
    vertices = [(xm - dx if draw_lead else xm + dx, ym - radius)]  # start spiralling in
    for turn_idx in range(n_turns):
        vertices.append((xm - radius, ym - radius))  # go left

        # update radius
        new_radius = radius - (width + spacing) if interleave else radius

        vertices.append((xm - radius, ym + new_radius))  # go up
        vertices.append((xm + new_radius, ym + new_radius))  # go right

        # update radius
        new_radius2 = new_radius - (width + spacing)

        vertices.append((xm + new_radius, ym - new_radius2))  # go down
        if turn_idx == n_turns - 1:
            vertices.append((xm - dx, ym - new_radius2))  # go left and terminate

        radius = new_radius2

    return vertices


class IndSpiralTemplate(TemplateBase, abc.ABC):
    """Spiral inductor template with helper methods"""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)
        self._actual_bbox = BBox(0, 0, 0, 0)

    @property
    def actual_bbox(self) -> BBox:
        return self._actual_bbox
