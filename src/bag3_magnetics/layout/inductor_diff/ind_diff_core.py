from typing import Mapping, Any, Sequence

from bag.layout.template import TemplateBase, TemplateDB
from bag.layout.util import BBox
from bag.layout.routing.base import TrackManager, TrackID
from bag.util.immutable import Param
from bag.typing import PointType

from pybag.enum import PathStyle, Orient2D, Direction, MinLenMode


class IndDiffCore(TemplateBase):
    """Assymmetric inductor which can be interleaved"""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)
        self._actual_bbox: BBox = BBox(0, 0, 0, 0)

    @property
    def actual_bbox(self) -> BBox:
        # actual BBox may extend outside first quadrant
        return self._actual_bbox

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            n_turn='Number of turns',
            lay_id='Inductor layer ID',
            radius='Outermost radius',
            width='Width of inductor sides',
            spacing='Spacing between inductor turns',
            port_xl='x co-ordinate of left port',
            port_xr='x co-ordinate of right port',
            tr_manager='Track Manager',
        )

    def draw_layout(self) -> None:
        n_turn: int = self.params['n_turn']
        lay_id: int = self.params['lay_id']
        radius: int = self.params['radius']
        width: int = self.params['width']
        spacing: int = self.params['spacing']
        tr_manager: TrackManager = self.params['tr_manager']

        # check feasibility
        assert radius + width // 2 >= (2 * n_turn + 1) * (width + spacing), 'Inductor is infeasible.'

        port_xl: int = self.params['port_xl']
        port_xr: int = self.params['port_xr']
        xm = (port_xl + port_xr) // 2

        coords = get_coords(n_turn, radius, width, spacing, xm, port_xl)
        num_coords = len(coords)

        # draw paths
        lp = self.grid.tech_info.get_lay_purp_list(lay_id)[0]
        for idx in range(num_coords - 1):
            self.add_path(lp, width, [coords[idx], coords[idx + 1]], PathStyle.extend)

        # draw leads
        port_lay_id = lay_id - 1
        if self.grid.get_direction(port_lay_id) != Orient2D.y:
            raise ValueError(f'This generator expects port_layer={port_lay_id} to be vertical.')
        w_port = tr_manager.get_width(port_lay_id, 'sig_hs')
        w_min = self.grid.get_min_track_width(port_lay_id, top_ntr=1)
        assert w_port >= w_min, f'w_port={w_port} must be at least {w_min} on layer={port_lay_id} in track manager.'
        port_idx = self.grid.coord_to_track(port_lay_id, port_xl)
        port_tid = TrackID(port_lay_id, port_idx, w_port)

        term0_coord = coords[0]
        term0_bbox = BBox(term0_coord[0] - width // 2, term0_coord[1] - width // 2,
                          term0_coord[0] + width // 2, term0_coord[1] + width // 2)
        term0 = self.connect_bbox_to_tracks(Direction.UPPER, lp, term0_bbox, port_tid, min_len_mode=MinLenMode.LOWER)
        self.add_pin('term0', term0)

        term1_coord = coords[-1]
        term1_bbox = BBox(term1_coord[0] - width // 2, term1_coord[1] - width // 2,
                          term1_coord[0] + width // 2, term1_coord[1] + width // 2)
        term1 = self.connect_bbox_to_tracks(Direction.UPPER, lp, term1_bbox, port_tid, min_len_mode=MinLenMode.UPPER,
                                            track_upper=2 * radius + width)
        self.add_pin('term1', term1)

        # set size
        self._actual_bbox = BBox(xm - radius - width // 2, 0, xm + radius + width // 2, 2 * radius + width)
        self.set_size_from_bound_box(lay_id, BBox(0, 0, self._actual_bbox.xh, self._actual_bbox.yh), round_up=True)


def get_coords(n_turn: int, radius: int, width: int, spacing: int, xm: int, xl: int) -> Sequence[PointType]:
    ym = width // 2 + radius
    coords = [(xl, ym - radius)]  # start
    for turn_idx in range(n_turn):
        coords.append((xm - radius, ym - radius))  # go left

        # update radius
        new_radius = radius - (width + spacing)

        coords.append((xm - radius, ym + new_radius))  # go up
        coords.append((xm + new_radius, ym + new_radius))  # go right

        # update radius
        new_radius2 = new_radius - (width + spacing)

        coords.append((xm + new_radius, ym - new_radius2))  # go down
        if turn_idx == n_turn - 1:
            coords.append((xl, ym - new_radius2))  # go left and terminate

        radius = new_radius2

    return coords
