from typing import Mapping, Any, Sequence

from bag.layout.template import TemplateBase, TemplateDB
from bag.layout.util import BBox
from bag.util.immutable import Param
from bag.typing import PointType

from pybag.enum import PathStyle


class IndDiffCore(TemplateBase):
    """Assymmetric inductor which can be interleaved"""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)
        self._actual_bbox: BBox = BBox(0, 0, 0, 0)

    @property
    def actual_bbox(self) -> BBox:
        # actual BBox may extend because of grid quantization
        return self._actual_bbox

    @classmethod
    def get_params_info(cls) -> Mapping[str, str]:
        return dict(
            n_turn='Number of turns',
            lay_id='Inductor layer ID',
            radius='Outermost radius',
            width='Width of inductor sides',
            spacing='Spacing between inductor turns',
            lead_width='Width of inductor leads',
            lead_spacing='Spacing between inductor leads',
        )

    def draw_layout(self) -> None:
        n_turn: int = self.params['n_turn']
        lay_id: int = self.params['lay_id']
        radius: int = self.params['radius']
        width: int = self.params['width']
        spacing: int = self.params['spacing']
        lead_width: int = self.params['lead_width']
        lead_spacing: int = self.params['lead_spacing']

        # check feasibility
        outer_radius = radius + width // 2
        assert outer_radius >= (2 * n_turn + 1) * (width + spacing), 'Inductor is infeasible.'

        port_xl = outer_radius - (lead_width + lead_spacing) // 2

        coords = get_coords(n_turn, radius, width, spacing, port_xl)
        num_coords = len(coords)

        # draw paths
        lp = self.grid.tech_info.get_lay_purp_list(lay_id)[0]
        for idx in range(num_coords - 1):
            self.add_path(lp, width, [coords[idx], coords[idx + 1]], PathStyle.extend)

        # draw leads
        port_lay_id = lay_id - 1
        port_dir = self.grid.get_direction(port_lay_id)
        lp_lead = self.grid.tech_info.get_lay_purp_list(port_lay_id)[0]

        term0_coord = coords[0]
        term0_bbox = BBox(term0_coord[0] - lead_width // 2, term0_coord[1] - lead_width // 2,
                          term0_coord[0] + lead_width // 2, term0_coord[1] + lead_width // 2)
        lead0_bbox = BBox(term0_bbox.xl, 0, term0_bbox.xh, term0_bbox.yh)
        self.add_rect(lp_lead, lead0_bbox)
        self.add_via(term0_bbox, lp_lead, lp, port_dir, extend=False)
        self.add_pin_primitive('term0', lp_lead[0], lead0_bbox, hide=True)

        term1_coord = coords[-1]
        term1_bbox = BBox(term1_coord[0] - lead_width // 2, term1_coord[1] - lead_width // 2,
                          term1_coord[0] + lead_width // 2, term1_coord[1] + lead_width // 2)
        lead1_bbox = BBox(term1_bbox.xl, term1_bbox.yl, term1_bbox.xh, 2 * outer_radius)
        self.add_rect(lp_lead, lead1_bbox)
        self.add_via(term1_bbox, lp_lead, lp, port_dir, extend=False)
        self.add_pin_primitive('term1', lp_lead[0], lead1_bbox, hide=True)

        # set size
        self._actual_bbox = BBox(0, 0, 2 * outer_radius, 2 * outer_radius)
        self.set_size_from_bound_box(lay_id, self._actual_bbox, round_up=True)


def get_coords(n_turn: int, radius: int, width: int, spacing: int, xl: int) -> Sequence[PointType]:
    xm = ym = width // 2 + radius
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
