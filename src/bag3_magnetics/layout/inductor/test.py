# -*- coding: utf-8 -*-
from typing import Mapping, Any

from bag.layout.template import TemplateDB, TemplateBase
from bag.layout.util import BBox
from bag.util.immutable import Param

from pybag.enum import PathStyle


class PolygonTest(TemplateBase):
    """A template for polygon test.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            lay_id='layer ID',
            width='Polygon width',
        )

    def draw_layout(self) -> None:
        lay_id: int = self.params['lay_id']
        width: int = self.params['width']
        lp = self.grid.tech_info.get_lay_purp_list(lay_id)[0]

        path1 = [[(235183, 1), (332598, 1)], [(332598, 1), (332598, 332598)], [(332598, 332598), (191699, 332598)],
                 [(156299, 332598), (1, 332598)], [(1, 332598), (1, 1)], [(1, 1), (153819, 1)],
                 [(178779, 1), (235183, 1)]]
        for path_coord in path1:
            self.add_path(lp, width, path_coord, PathStyle.round, join_style=PathStyle.round)

        path2 = [[(226898, 20001), (312598, 20001)], [(312598, 20001), (312598, 312598)],
                 [(312598, 312598), (176299, 312598)], [(140899, 312598), (20001, 312598)],
                 [(20001, 312598), (20001, 20001)], [(20001, 20001), (226898, 20001)]]
        for path_coord in path2:
            self.add_path(lp, width, path_coord, PathStyle.round, join_style=PathStyle.round)

        self.set_size_from_bound_box(lay_id, BBox(0, 0, width, width), round_up=True)
