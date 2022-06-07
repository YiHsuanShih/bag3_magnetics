# -*- coding: utf-8 -*-
import numpy as np
import abc
from typing import Sequence, Mapping, Any, Tuple

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


class IndTemplate(TemplateBase, abc.ABC):
    """Inductor template with helper methods"""
    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)
        self._actual_bbox = BBox(0, 0, 0, 0)

    @property
    def actual_bbox(self) -> BBox:
        return self._actual_bbox

    def _draw_turn(self, lay_id: int, width: int, n_sides: int, vertices: Sequence[PointType], start_x: int,
                   stop_x: int, bridge_xl: int, bridge_xr: int, suf: str) -> Mapping[str, Sequence[PointType]]:
        _mid = n_sides // 2
        _turn_r = [(start_x, vertices[0][1]), (bridge_xr, vertices[_mid - 1][1])]
        _turn_r[1:1] = vertices[:_mid]
        _turn_l = [(bridge_xl, vertices[_mid][1]), (stop_x, vertices[-1][1])]
        _turn_l[1:1] = vertices[_mid:]

        # cannot draw all paths in this layout because of mysterious C++ error.
        # Create separate sub layouts with each turn.
        path_list = [
            dict(lay_id=lay_id, width=width, points=_turn_l),
            dict(lay_id=lay_id, width=width, points=_turn_r),
        ]
        _master: IndLayoutHelper = self.new_template(IndLayoutHelper, params=dict(path_list=path_list))
        self.add_instance(_master, inst_name=f'IndTurn_{suf}')
        return dict(left=_turn_l, right=_turn_r)

    def _draw_bridge(self, coord_l: PointType, coord_r: PointType, layer_l: int, layer_r: int, layer_bridge: int,
                     width: int, style: PathStyle = PathStyle.round) -> None:
        points = []
        wext = int(width // 2 * np.sin(np.pi / 8))
        # left
        if layer_l == layer_bridge:
            points.append(coord_l)
        else:
            points.append((coord_l[0] - width, coord_l[1]))
            # draw via
            via_bbox = BBox(coord_l[0] - width - wext, coord_l[1] - width // 2,
                            coord_l[0] + wext, coord_l[1] + width // 2)
            if layer_l > layer_bridge:
                bot_lay, top_lay = layer_bridge, layer_l
            else:
                bot_lay, top_lay = layer_l, layer_bridge
            bot_lp = self.grid.tech_info.get_lay_purp_list(bot_lay)[0]
            top_lp = self.grid.tech_info.get_lay_purp_list(top_lay)[0]
            bot_dir = self.grid.get_direction(bot_lay)
            self.add_via(via_bbox, bot_lp, top_lp, bot_dir, extend=False)

        # mid
        if coord_l[1] != coord_r[1]:
            points.extend([(coord_l[0] + width, coord_l[1]), (coord_r[0] - width, coord_r[1])])

        # right
        if layer_r == layer_bridge:
            points.append(coord_r)
        else:
            points.append((coord_r[0] + width, coord_r[1]))
            # draw via
            via_bbox = BBox(coord_r[0] - wext, coord_r[1] - width // 2,
                            coord_r[0] + width + wext, coord_r[1] + width // 2)
            if layer_r > layer_bridge:
                bot_lay, top_lay = layer_bridge, layer_r
            else:
                bot_lay, top_lay = layer_r, layer_bridge
            bot_lp = self.grid.tech_info.get_lay_purp_list(bot_lay)[0]
            top_lp = self.grid.tech_info.get_lay_purp_list(top_lay)[0]
            bot_dir = self.grid.get_direction(bot_lay)
            self.add_via(via_bbox, bot_lp, top_lp, bot_dir, extend=False)

        # draw path
        bridge_lp = self.grid.tech_info.get_lay_purp_list(layer_bridge)[0]
        self.add_path(bridge_lp, width, points, style, join_style=style)

    def _draw_leads(self, lay_id: int, width: int, term_coords: Sequence[PointType], res1_l: int, res2_l: int,
                    y_end: int = 0, up: bool = False) -> Tuple[BBox, BBox]:
        term_ext = width + max(res1_l, res2_l) + 2 * width

        # BBox for lead metals
        if up:
            _lower = term_coords[0][1]
            _upper = max(y_end, term_coords[0][1] + term_ext)
            m_lower0 = m_lower1 = _lower + width
            m_upper0 = _lower + width + res1_l
            m_upper1 = _lower + width + res2_l
            p_lower = _upper - width
            p_upper = _upper
        else:
            _lower = min(y_end, term_coords[0][1] - term_ext)
            _upper = term_coords[0][1]
            m_lower0 = _upper - width - res1_l
            m_lower1 = _upper - width - res2_l
            m_upper0 = m_upper1 = _upper - width
            p_lower = _lower
            p_upper = _lower + width

        _bbox0 = BBox(term_coords[0][0] - width // 2, _lower, term_coords[0][0] + width // 2, _upper)
        _bbox1 = BBox(term_coords[1][0] - width // 2, _lower, term_coords[1][0] + width // 2, _upper)
        lp = self.grid.tech_info.get_lay_purp_list(lay_id)[0]
        self.add_rect(lp, _bbox0)
        self.add_rect(lp, _bbox1)

        # BBox for res_metal
        term0_res_bbox = BBox(_bbox0.xl, m_lower0, _bbox0.xh, m_upper0)
        term1_res_bbox = BBox(_bbox1.xl, m_lower1, _bbox1.xh, m_upper1)
        self.add_res_metal(lay_id, term0_res_bbox)
        self.add_res_metal(lay_id, term1_res_bbox)

        # BBox for pins
        term0 = BBox(_bbox0.xl, p_lower, _bbox0.xh, p_upper)
        term1 = BBox(_bbox1.xl, p_lower, _bbox1.xh, p_upper)
        return term0, term1

    def _draw_fill(self, n_sides: int, fill_specs: Mapping[str, Any],
                   core_turn_coords: Sequence[Mapping[str, Sequence[PointType]]], width: int, dx: int, dy: int,
                   ring_turn_coords: Sequence[PointType], ring_width: int) -> None:
        lay_id: int = fill_specs['lay_id']
        fill_w: int = fill_specs['fill_w']
        fill_sp: int = fill_specs['fill_sp']
        inside_ring: bool = fill_specs.get('inside_ring', True)
        outside_ring: bool = fill_specs.get('outside_ring', True)

        lp = self.grid.tech_info.get_lay_purp_list(lay_id)[0]
        w2 = width // 2
        rw2 = ring_width // 2

        if n_sides == 8:
            #          R0
            #       1-0  5-4
            #   2              3
            #   |              |
            #   |              |
            #   |              |
            #   3              2
            #       4-5  0-1

            # Step 1: draw inside ring
            if inside_ring:
                in_l = core_turn_coords[-1]['left']
                in_r = core_turn_coords[-1]['right']

                bbox_in = BBox(in_l[2][0] + w2 + fill_sp + dx, in_r[1][1] + w2 + fill_sp + dy,
                               in_r[2][0] - w2 - fill_sp + dx, in_l[1][1] - w2 - fill_sp + dy)
                bbox_in2 = BBox(in_l[1][0] + w2 + dx, in_r[2][1] + w2 + dy, in_r[1][0] - w2 + dx, in_l[2][1] - w2 + dy)

                tot_num_x = (bbox_in.w + fill_sp) // (fill_w + fill_sp)
                tot_len_x = tot_num_x * (fill_w + fill_sp) - fill_sp
                xl = bbox_in.xl + (bbox_in.w - tot_len_x) // 2

                tot_num_y = (bbox_in.h + fill_sp) // (fill_w + fill_sp)
                tot_len_y = tot_num_y * (fill_w + fill_sp) - fill_sp
                yl = bbox_in.yl + (bbox_in.h - tot_len_y) // 2

                for idx in range(tot_num_x):
                    for jdx in range(tot_num_y):
                        _xl = xl + idx * (fill_w + fill_sp)
                        _yl = yl + jdx * (fill_w + fill_sp)
                        if _xl + _yl < bbox_in.xl + bbox_in2.yl:
                            # lower left
                            continue
                        elif _yl + fill_w - _xl > bbox_in2.yh - bbox_in.xl:
                            # upper left
                            continue
                        elif _yl - _xl - fill_w < bbox_in2.yl - bbox_in.xh:
                            # lower right
                            continue
                        elif _xl + _yl + 2 * fill_w > bbox_in.xh + bbox_in2.yh:
                            # upper right
                            continue
                        self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))

            # Step 2: draw outside ring
            if outside_ring:
                out_l = core_turn_coords[0]['left']
                out_r = core_turn_coords[0]['right']

                bbox_out2 = BBox(out_l[1][0] - w2 - fill_sp + dx, out_r[2][1] - w2 - fill_sp + dy,
                                 out_r[1][0] + w2 + fill_sp + dx, out_l[2][1] + w2 + fill_sp + dy)
                bbox_out = BBox(out_l[2][0] - w2 + dx, out_r[1][1] - w2 + dy,
                                out_r[2][0] + w2 + dx, out_l[1][1] + w2 + dy)

                if ring_turn_coords:
                    #    R0
                    #  3-----2
                    #  |     |
                    #  |     |
                    #  4-5 0-1
                    rbbox = BBox(ring_turn_coords[3][0] + rw2 + fill_sp, ring_turn_coords[1][1] + rw2 + fill_sp,
                                 ring_turn_coords[1][0] - rw2 - fill_sp, ring_turn_coords[3][1] - rw2 - fill_sp)
                else:
                    rbbox = bbox_out

                tot_num_x = (rbbox.w + fill_sp) // (fill_w + fill_sp)
                tot_len_x = tot_num_x * (fill_w + fill_sp) - fill_sp
                xl = rbbox.xl + (rbbox.w - tot_len_x) // 2

                tot_num_y = (rbbox.h + fill_sp) // (fill_w + fill_sp)
                tot_len_y = tot_num_y * (fill_w + fill_sp) - fill_sp
                yl = rbbox.yl + (rbbox.h - tot_len_y) // 2

                for idx in range(tot_num_x):
                    for jdx in range(tot_num_y):
                        _xl = xl + idx * (fill_w + fill_sp)
                        _yl = yl + jdx * (fill_w + fill_sp)
                        if bbox_out2.xl < _xl < bbox_out2.xh - fill_w and _yl + fill_w < bbox_out.yl - fill_sp:
                            # keep-out
                            continue
                        elif _xl + fill_w < bbox_out.xl - fill_sp:
                            # left
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))
                        elif _xl > bbox_out.xh + fill_sp:
                            # right
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))
                        elif _yl > bbox_out.yh + fill_sp:
                            # top
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))
                        elif _yl + fill_w < bbox_out.yl - fill_sp:
                            # bottom
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))
                        elif _xl + _yl + 2 * fill_w < bbox_out.xl + bbox_out2.yl:
                            # lower left
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))
                        elif _yl - _xl - fill_w > bbox_out2.yh - bbox_out.xl:
                            # upper left
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))
                        elif _yl + fill_w - _xl < bbox_out2.yl - bbox_out.xh:
                            # lower right
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))
                        elif _xl + _yl > bbox_out.xh + bbox_out2.yh:
                            # upper right
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))

        elif n_sides == 4:
            #          R0
            #   1-----0  3-----2
            #   |              |
            #   |              |
            #   |              |
            #   2-----3  0-----1

            # Step 1: draw inside ring
            if inside_ring:
                in_l = core_turn_coords[-1]['left']
                in_r = core_turn_coords[-1]['right']

                bbox_in = BBox(in_l[1][0] + w2 + fill_sp + dx, in_r[1][1] + w2 + fill_sp + dy,
                               in_r[1][0] - w2 - fill_sp + dx, in_l[1][1] - w2 - fill_sp + dy)

                tot_num_x = (bbox_in.w + fill_sp) // (fill_w + fill_sp)
                tot_len_x = tot_num_x * (fill_w + fill_sp) - fill_sp
                xl = bbox_in.xl + (bbox_in.w - tot_len_x) // 2

                tot_num_y = (bbox_in.h + fill_sp) // (fill_w + fill_sp)
                tot_len_y = tot_num_y * (fill_w + fill_sp) - fill_sp
                yl = bbox_in.yl + (bbox_in.h - tot_len_y) // 2

                for idx in range(tot_num_x):
                    for jdx in range(tot_num_y):
                        _xl = xl + idx * (fill_w + fill_sp)
                        _yl = yl + jdx * (fill_w + fill_sp)
                        self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))

            # Step 2: draw outside ring
            if outside_ring:
                out_l = core_turn_coords[0]['left']
                out_r = core_turn_coords[0]['right']

                bbox_out = BBox(out_l[1][0] - w2 - fill_sp + dx, out_r[1][1] - w2 - fill_sp + dy,
                                out_r[1][0] + w2 + fill_sp + dx, out_l[1][1] + w2 + fill_sp + dy)

                if ring_turn_coords:
                    #    R0
                    #  3-----2
                    #  |     |
                    #  |     |
                    #  4-5 0-1
                    rbbox = BBox(ring_turn_coords[3][0] + rw2 + fill_sp, ring_turn_coords[1][1] + rw2 + fill_sp,
                                 ring_turn_coords[1][0] - rw2 - fill_sp, ring_turn_coords[3][1] - rw2 - fill_sp)
                else:
                    return

                tot_num_x = (rbbox.w + fill_sp) // (fill_w + fill_sp)
                tot_len_x = tot_num_x * (fill_w + fill_sp) - fill_sp
                xl = rbbox.xl + (rbbox.w - tot_len_x) // 2

                tot_num_y = (rbbox.h + fill_sp) // (fill_w + fill_sp)
                tot_len_y = tot_num_y * (fill_w + fill_sp) - fill_sp
                yl = rbbox.yl + (rbbox.h - tot_len_y) // 2

                for idx in range(tot_num_x):
                    for jdx in range(tot_num_y):
                        _xl = xl + idx * (fill_w + fill_sp)
                        _yl = yl + jdx * (fill_w + fill_sp)
                        if bbox_out.xl < _xl < bbox_out.xh - fill_w and _yl + fill_w < bbox_out.yl - fill_sp:
                            # keep-out
                            continue
                        elif _xl + fill_w < bbox_out.xl - fill_sp:
                            # left
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))
                        elif _xl > bbox_out.xh + fill_sp:
                            # right
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))
                        elif _yl > bbox_out.yh + fill_sp:
                            # top
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))
                        elif _yl + fill_w < bbox_out.yl - fill_sp:
                            # bottom
                            self.add_rect(lp, BBox(_xl, _yl, _xl + fill_w, _yl + fill_w))
        else:
            raise NotImplementedError(f'_draw_fill() is not implemented for n_sides={n_sides} yet.')


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
