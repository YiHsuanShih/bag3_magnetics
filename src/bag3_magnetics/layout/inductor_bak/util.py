# -*- coding: utf-8 -*-
import numpy as np
import abc
from typing import List, Tuple, Mapping, Any, Union, Optional

from bag.layout.template import TemplateDB, TemplateBase
from bag.layout.util import BBox
from bag.util.immutable import Param
from bag.typing import PointType

from pybag.enum import PathStyle, Orientation


class IndTemplate(TemplateBase):
    """An inductor template.
    """

    def __init__(self, temp_db: TemplateDB, params: Param, **kwargs: Any) -> None:
        TemplateBase.__init__(self, temp_db, params, **kwargs)
        self._feasibility = True

    @property
    def feasibility(self) -> bool:
        return self._feasibility

    @classmethod
    @abc.abstractmethod
    def get_params_info(cls) -> Mapping[str, str]:
        """Returns a dictionary containing parameter descriptions.

        Override this method to return a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : Mapping[str, str]
            dictionary from parameter name to description.
        """
        return {}

    @abc.abstractmethod
    def draw_layout(self) -> None:
        pass

    def _draw_ind_turn(self, n_turn: int, radius: int, n_side: int, width: int, spacing: int, opening: int,
                       orient: Orientation, ind_layid: int, bdg_layid: int, via_width: int, turn: int
                       ) -> Tuple[List[List[PointType]], Optional[List[PointType]], Optional[List[PointType]],
                                  Optional[List[PointType]], List[PointType], Optional[PointType]]:
        """ draw each turn of inductor

        Parameters
        ----------
        n_turn : int
            total inductor turn number.
        radius : int
            inductor outer radius, in resolution unit.
        n_side : int
            total inductor side number.
        width : int
            inductor path width, in resolution unit.
        spacing: int
            inductor spacing (gap), in resolution unit.
        opening: float or int
            inductor opening pitch, in resolution unit
        orient: Orientation
            orientation of the inductor
        ind_layid : int
            the layer id.
        bdg_layid : int
            the layer id
        via_width : int
            Width of via.
        turn: int
            inductor turn number
        """

        if turn == 0 and n_turn == 1:  # outer path with only 1 turn inductor (mode 1)
            if orient is Orientation.R0:
                mode = 1
            elif orient is Orientation.R270:
                mode = 14
            else:
                raise NotImplementedError(f'orient={orient} is not supported yet.')
        elif turn == 0 and n_turn > 1:  # outer path with more than 1 turn inductor (mode 2)
            mode = 2
        elif turn == n_turn - 1 and n_turn % 2 == 0:  # inner path with odd turn index (mode 3)
            mode = 3
        elif turn == n_turn - 1 and n_turn % 2 != 0:  # inner path with even turn index (mode 3)
            mode = 4
        elif turn % 2 == 0:    # Mode 5: other turns on even index
            mode = 5
        else:   # Mode 6: other turns on odd index
            mode = 6

        path_coord, lead_coord, tail_coord, top_coord, bot_coord, via_coord, center_tap_coord = \
            get_octpath_coord(radius, turn, n_side, width, spacing, opening, 0, via_width, mode=mode)

        # draw paths in this turn
        # draw inductor layer
        self.draw_path(ind_layid, width, path_coord, end_style=PathStyle.round, join_style=PathStyle.round)
        # draw bridge layer
        if tail_coord:
            self.draw_path(bdg_layid, width, tail_coord, end_style=PathStyle.round, join_style=PathStyle.round)

        # return path, lead, top bridge, bottom bridge, via, center_tap
        return path_coord, lead_coord, top_coord, bot_coord, via_coord, center_tap_coord

    def _draw_ind_ring(self, halflen: int, width: int, spacing: int, turn: int, opening: int, ind_layid: int,
                       layer_list: List[int], orient: Orientation = Orientation.R0
                       ) -> Tuple[List[List[List[List[PointType]]]], List[int], BBox]:
        pitch = width + spacing
        ring_arr = []
        ring_lenarr = []
        for idx in range(turn):
            path_arr, length = self.draw_sqr_guardring(halflen + idx * pitch, width, opening, ind_layid,
                                                       layer_list, orient=orient)
            ring_arr.append(path_arr)
            ring_lenarr.append(length)

        # --- complete guard ring on (ind_layid - 1) --- #
        #     R0          R270
        #  2-----1      2-----1
        #  |     |      3     |
        #  |     |            |
        #  |     |      4     |
        #  3-4 5-0      5-----0
        outer_path_coord = ring_arr[-1][-1]
        if orient is Orientation.R0:
            left_path = outer_path_coord[3]
            right_path = outer_path_coord[4]
            path_coord = [left_path[-1], right_path[0]]
            self.draw_path(ind_layid - 1, width, path_coord, end_style=PathStyle.extend, join_style=PathStyle.extend)
            _bbox = BBox((path_coord[0][0] + path_coord[-1][0]) // 2 - width, path_coord[0][1] - width // 2,
                         (path_coord[0][0] + path_coord[-1][0]) // 2 + width, path_coord[0][1] + width // 2)
        else:
            top_path = outer_path_coord[2]
            bot_path = outer_path_coord[3]
            path_coord = [bot_path[0], top_path[-1]]
            self.draw_path(ind_layid - 1, width, path_coord, end_style=PathStyle.extend, join_style=PathStyle.extend)
            _bbox = BBox(path_coord[0][0] - width // 2, (path_coord[0][1] + path_coord[-1][1]) // 2 - width,
                         path_coord[0][0] + width // 2, (path_coord[0][1] + path_coord[-1][1]) // 2 + width)
        for coord in path_coord:
            self.draw_via(coord, width, width, ind_layid - 1, ind_layid)

        return ring_arr, ring_lenarr, _bbox

    def draw_sqr_guardring(self, halflen: int, width: int, opening: int, ind_layid: int, layer_list: List[int],
                           orient: Orientation = Orientation.R0) -> Tuple[List[List[List[PointType]]], int]:
        """

        Draw inductor guard ring for designated layers

        Parameters
        ----------
        halflen: float
            guard ring half length
        width: float
            guard ring metal width
        opening : int
            lead opening
        ind_layid: int
            inductor top layer
        layer_list: List[int]
            layer list for guard ring
        orient: Orientation
             Orientation of inductor

        Returns
        ----------
        path_arr: List[List[List[PointType]]]
            Array of path co-ordinates
        length: int
            length of guard ring
        """

        # check if all layers are adjacent
        if len(layer_list) == 0:
            raise ValueError("Layer list should not be empty")
        elif len(layer_list) != layer_list[-1] - layer_list[0] + 1:
            raise ValueError("All layer should be adjacent, from low to high")

        # some constant
        radius = round_up(halflen * np.sqrt(2))
        n_side = 4

        # Step 1: draw each turn of guard ring
        # draw each turn of the guard ring
        path_arr = []
        for lay_id in layer_list:
            if lay_id == ind_layid:     # on inductor layer
                if orient in (Orientation.R0, Orientation.MY):
                    mode = 11
                elif orient in (Orientation.R180, Orientation.MX):
                    mode = 10
                elif orient is Orientation.R90:
                    mode = 13
                elif orient is Orientation.R270:
                    mode = 14
                else:
                    raise ValueError('Not supported')
            else:   # other layers
                mode = 0

            # put them in an array
            path_coord, _, _, _, _, _, _ = get_octpath_coord(radius, 0, n_side, width, 0, opening, 0, 0, mode=mode)
            path_arr.append(path_coord)

        # draw path
        for path_coord, lay_id in zip(path_arr, layer_list):
            self.draw_path(lay_id, width, path_coord, end_style=PathStyle.extend, join_style=PathStyle.extend)

        # get length of this guard ring
        length = path_arr[-1][0][0][0]

        # draw via on different layers
        for path_coord, lay_id in zip(path_arr, layer_list):
            via_coord = []
            via_dir = []
            via_width = []
            if lay_id != ind_layid:     # skip for the last layer
                for i, path in enumerate(path_coord):
                    via_coord.append(((path[0][0] + path[1][0]) // 2, (path[0][1] + path[1][1]) // 2))
                    if path[0][0] == path[1][0]:
                        via_dir.append(1)
                        via_width.append(abs(path[0][1] - path[1][1]) - width * 2)
                    else:
                        via_dir.append(0)
                        via_width.append(abs(path[0][0] - path[1][0]) - width * 2)

                # draw via on one layer
                for coord, _dir, wid in zip(via_coord, via_dir, via_width):
                    if _dir == 0:
                        self.draw_via(coord, wid, width, lay_id, lay_id + 1)
                    else:
                        self.draw_via(coord, width, wid, lay_id, lay_id + 1)
        return path_arr, length

    # def draw_ground_shield(self, layid: int, radius: int, n_side: int, space: int, width: int) -> None:
    #     """
    #     draw ground shielding for inductors, only rectangular for now
    #     Parameters
    #     ----------
    #     layid: int
    #         layer id
    #     radius: int
    #         radius of ground shielding
    #     n_side: int
    #         inductor # of side
    #     space: int
    #         space between shield metals
    #     width:  int
    #         shield metal width
    #     """
    #     # get length
    #     length = int(np.ceil(radius * np.cos(np.pi/2/n_side)))
    #     pitch = width+space
    #     # draw center two crossing metals
    #     self.draw_path(layid, width, [(-length, 0), (length, 0)], end_style=PathStyle.extend)
    #     self.draw_path(layid, width, [(0, -length), (0, length)], end_style=PathStyle.extend)
    #     # draw
    #     x0 = 0
    #     y0 = 0
    #     while x0 + 2 * pitch <= length:
    #         x0 = x0 + pitch
    #         y0 = y0 + pitch
    #         # on first quadrant
    #         self.draw_rect(layid, x0 - pitch, y0 - pitch, x0, y0)
    #         self.draw_path(layid, width, [(x0, y0), (length, y0)], end_style=PathStyle.extend)
    #         self.draw_path(layid, width, [(x0, y0), (x0, length)], end_style=PathStyle.extend)
    #         # on second quadrant
    #         self.draw_rect(layid, -x0, y0 - pitch, -x0 + pitch, y0)
    #         self.draw_path(layid, width, [(-x0, y0), (-length, y0)], end_style=PathStyle.extend)
    #         self.draw_path(layid, width, [(-x0, y0), (-x0, length)], end_style=PathStyle.extend)
    #         # on third quadrant
    #         self.draw_rect(layid, -x0, -y0, -x0 + pitch, -y0 + pitch)
    #         self.draw_path(layid, width, [(-x0, -y0), (-length, -y0)], end_style=PathStyle.extend)
    #         self.draw_path(layid, width, [(-x0, -y0), (-x0, -length)], end_style=PathStyle.extend)
    #         # on fouth quadrant
    #         self.draw_rect(layid, x0 - pitch, -y0, x0, -y0 + pitch)
    #         self.draw_path(layid, width, [(x0, -y0), (length, -y0)], end_style=PathStyle.extend)
    #         self.draw_path(layid, width, [(x0, -y0), (x0, -length)], end_style=PathStyle.extend)

    def _draw_center_tap(self, width: int, n_turn: int, tap_len: int, ind_layid: int, pin_len: int, res3_l: int,
                         res_space: int, center_tap_coord: PointType, orient: Orientation) -> BBox:
        tap_ext = width // 2 + res_space + res3_l

        if n_turn == 1:
            if orient is Orientation.R0:
                _lower = center_tap_coord[1]
                _upper = center_tap_coord[1] + tap_len + tap_ext

                _bbox = BBox(center_tap_coord[0] - width // 2, _lower,
                             center_tap_coord[0] + width // 2, _upper)
                tap = BBox(center_tap_coord[0] - width // 2, _upper - pin_len,
                           center_tap_coord[0] + width // 2, _upper)

                res_bbox = BBox(tap.xl, tap.yl - res3_l - res_space, tap.xh, tap.yl - res_space)

            else:
                _lower = center_tap_coord[0]
                _upper = center_tap_coord[0] + tap_len + tap_ext

                _bbox = BBox(_lower, center_tap_coord[1] - width // 2,
                             _upper, center_tap_coord[1] + width // 2)
                tap = BBox(_upper - pin_len, center_tap_coord[1] - width // 2,
                           _upper, center_tap_coord[1] + width // 2)

                res_bbox = BBox(tap.xl - res3_l - res_space, tap.yl, tap.xl - res_space, tap.yh)

            # draw metal for pins
            lp = self.grid.tech_info.get_lay_purp_list(ind_layid)[0]
            self.add_rect(lp, _bbox)

            # add metal res
            self.add_res_metal(ind_layid, res_bbox)

            return tap
        else:
            raise NotImplementedError('Multiple turns not supported yet.')

    def _draw_lead(self, ind_layid: int, width: int, lead_len: int, lead_coord: List[PointType], pin_len: int,
                   res1_l: int, res2_l: int, res_space: int, orient: Orientation) -> Tuple[BBox, BBox]:
        lead_ext = width // 2 + res_space + max(res1_l, res2_l)

        if orient is Orientation.R0:
            # BBox for lead metals
            _lower = min(0, lead_coord[0][1] - lead_len - lead_ext)
            _upper = lead_coord[0][1]

            _bbox0 = BBox(lead_coord[0][0] - width // 2, _lower,
                          lead_coord[0][0] + width // 2, _upper)
            _bbox1 = BBox(lead_coord[1][0] - width // 2, _lower,
                          lead_coord[1][0] + width // 2, _upper)
            term0 = BBox(lead_coord[0][0] - width // 2, _lower,
                         lead_coord[0][0] + width // 2, _lower + pin_len)
            term1 = BBox(lead_coord[1][0] - width // 2, _lower,
                         lead_coord[1][0] + width // 2, _lower + pin_len)

            # BBox for res_metal
            term0_res_bbox = BBox(term0.xl, term0.yh + res_space, term0.xh, term0.yh + res1_l + res_space)
            term1_res_bbox = BBox(term1.xl, term1.yh + res_space, term1.xh, term1.yh + res2_l + res_space)
        else:
            # BBox for lead metals
            _lower = min(0, lead_coord[0][0] - lead_len - lead_ext)
            _upper = lead_coord[0][0]

            _bbox0 = BBox(_lower, lead_coord[0][1] - width // 2,
                          _upper, lead_coord[0][1] + width // 2)
            _bbox1 = BBox(_lower, lead_coord[1][1] - width // 2,
                          _upper, lead_coord[1][1] + width // 2)
            term0 = BBox(_lower, lead_coord[0][1] - width // 2,
                         _lower + pin_len, lead_coord[0][1] + width // 2)
            term1 = BBox(_lower, lead_coord[1][1] - width // 2,
                         _lower + pin_len, lead_coord[1][1] + width // 2)

            # BBox for res_metal
            term0_res_bbox = BBox(term0.xh + res_space, term0.yl, term0.xh + res1_l + res_space, term0.yh)
            term1_res_bbox = BBox(term1.xh + res_space, term1.yl, term1.xh + res2_l + res_space, term1.yh)

        # draw metal for pins
        lp = self.grid.tech_info.get_lay_purp_list(ind_layid)[0]
        self.add_rect(lp, _bbox0)
        self.add_rect(lp, _bbox1)

        # add metal res
        self.add_res_metal(ind_layid, term0_res_bbox)
        self.add_res_metal(ind_layid, term1_res_bbox)

        return term0, term1

    def draw_path(self, layid: int, width: int, path_coord: Union[List[List[PointType]], List[PointType]],
                  end_style: PathStyle = PathStyle.round, join_style: PathStyle = PathStyle.round):
        """draw layout path/paths.  Only 45/90 degree turns are allowed.

        Parameters
        ----------
        layid : int
            the layer id
        width : int
            width of this path, in layout units.
        path_coord : Union[List[List[PointType]], List[PointType]]
            list of path coordinate
        end_style : PathStyle
            the path ends style.
        join_style : PathStyle
            the ends style at intermediate points of the path.
        """
        # get layer name
        lp = self.grid.tech_info.get_lay_purp_list(layid)[0]
        path_arr = []

        # draw path layout
        # if path_coord is empty list
        if len(path_coord) == 0:
            print("Nothing to draw for path. Return")
            return path_arr
        # if path_coord is only one coordinate
        if isinstance(path_coord[0], Tuple):
            path_arr.append(self.add_path(lp, width, path_coord, end_style, join_style=join_style))
        # if path_coord is a coordinate list
        else:
            for coord in path_coord:
                path_arr.append(self.add_path(lp, width, coord, end_style, join_style=join_style))
        return path_arr

    def draw_via(self, via_coord: Union[List[PointType], PointType], width: int, height: int, layid1: int, layid2: int):
        """
        draw via between two adjacent layers at given coordinate, width and height

        """

        # check layer
        if abs(layid1 - layid2) != 1:
            raise ValueError("'draw_via' function is only for adjacent layers.")

        # get bot/top layer id
        bot_layid = np.min([layid1, layid2])
        top_layid = np.max([layid1, layid2])

        # get layer name
        bot_lp = self.grid.tech_info.get_lay_purp_list(bot_layid)[0]
        top_lp = self.grid.tech_info.get_lay_purp_list(top_layid)[0]

        via_arr = []
        # if via_coord is empty list
        if len(via_coord) == 0:
            print("Nothing to draw for via. Return")
            return via_arr

        # if via_coord is only one coordinate
        if isinstance(via_coord, Tuple):
            bbox = BBox(via_coord[0] - width // 2, via_coord[1] - height // 2,
                        via_coord[0] + width // 2, via_coord[1] + height // 2)
            bot_dir = self.grid.get_direction(bot_layid)
            via_arr.append(self.add_via(bbox, bot_lp, top_lp, bot_dir, extend=False))
        # if via_coord is a coordinate list
        else:
            for coord in via_coord:
                bbox = BBox(coord[0] - width // 2, coord[1] - height // 2,
                            coord[0] + width // 2, coord[1] + height // 2)
                bot_dir = self.grid.get_direction(bot_layid)
                via_arr.append((self.add_via(bbox, bot_lp, top_lp, bot_dir, extend=False)))
        return via_arr

    def draw_mulvia(self, via_coord: PointType, width: int, height: int, bot_layid: int, top_layid: int):
        """
        draw via stack between any layers at given coordinate, width and height

        """
        mulvia_arr = []
        if top_layid - bot_layid == 1:
            mulvia_arr.append(self.draw_via(via_coord, width, height, bot_layid, top_layid))
        elif top_layid - bot_layid > 1:
            for i in range(bot_layid, top_layid):
                mulvia_arr.append(self.draw_via(via_coord, width, height, i, i+1))
        else:
            raise ValueError(f'Need to make sure top_layid={top_layid} >= bot_layid={bot_layid}.')
        return mulvia_arr

    def draw_rect(self, layid: int, x0: int, y0: int, x1: int, y1: int) -> None:
        """
        draw rectangles with given coordinates.

        Parameters
        -------------
        layid: int
            layer id
        x0: int
            left bottom x coordinate
        y0: int
            left bottom y coordinate
        x1: int
            right top x coordinate
        y1: int
            right top y coordinate
        """
        bbox = BBox(x0, y0, x1, y1)
        lp = self.grid.tech_info.get_lay_purp_list(layid)[0]
        self.add_rect(lp, bbox)

    def _draw_fill(self, n_side: int, path_coord: List[List[List[PointType]]], width: int, ind_layid: int,
                   fill_specs: Mapping[str, Any], ring_coord: Optional[List[List[List[PointType]]]],
                   ring_width: int, orient: Orientation) -> None:
        fill_w: int = fill_specs['fill_w']
        fill_sp: int = fill_specs['fill_sp']
        lp = self.grid.tech_info.get_lay_purp_list(ind_layid)[0]
        inside_ring: bool = fill_specs['inside_ring']
        outside_ring: bool = fill_specs['outside_ring']
        if n_side == 8:
            #          R0                     R270
            #       4------3                4------3
            #   5              2        5              2
            #   |              |        6              |
            #   |              |                       |
            #   |              |        7              |
            #   6              1        8              1
            #       7-8  9-0                9------0

            # Step 1: draw inside ring
            if inside_ring:
                path_in = path_coord[-1]
                coord = [path[0] for path in path_in]

                bbox_in = BBox(coord[5][0] + width // 2 + fill_sp, coord[0][1] + width // 2 + fill_sp,
                               coord[1][0] - width // 2 - fill_sp, coord[3][1] - width // 2 - fill_sp)
                bbox_in2 = BBox(coord[4][0] + width // 2, coord[1][1] + width // 2,
                                coord[3][0] - width // 2, coord[5][1] - width // 2)

                tot_num = (bbox_in.w + fill_sp) // (fill_w + fill_sp)
                tot_len = tot_num * (fill_w + fill_sp) - fill_sp
                xl = bbox_in.xl + (bbox_in.w - tot_len) // 2
                yl = bbox_in.yl + (bbox_in.w - tot_len) // 2
                for idx in range(tot_num):
                    for jdx in range(tot_num):
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
                path_out = path_coord[0]
                coord = [path[0] for path in path_out]

                bbox_out2 = BBox(coord[4][0] - width // 2 - fill_sp, coord[1][1] - width // 2 - fill_sp,
                                 coord[3][0] + width // 2 + fill_sp, coord[5][1] + width // 2 + fill_sp)
                bbox_out = BBox(coord[5][0] - width // 2, coord[0][1] - width // 2,
                                coord[1][0] + width // 2, coord[3][1] + width // 2)
                if ring_coord:
                    ring_in = ring_coord[-1]
                    rcoord = [path[0] for path in ring_in]
                    #    R0           R270
                    #  2-----1      2-----1
                    #  |     |      3     |
                    #  |     |            |
                    #  |     |      4     |
                    #  3-4 5-0      5-----0
                    rbbox = BBox(rcoord[2][0] + ring_width // 2 + fill_sp, rcoord[0][1] + ring_width // 2 + fill_sp,
                                 rcoord[0][0] - ring_width // 2 - fill_sp, rcoord[1][1] - ring_width // 2 - fill_sp)
                else:
                    rbbox = bbox_out

                tot_num = (rbbox.w + fill_sp) // (fill_w + fill_sp)
                tot_len = tot_num * (fill_w + fill_sp) - fill_sp
                xl = rbbox.xl + (rbbox.w - tot_len) // 2
                yl = rbbox.yl + (rbbox.w - tot_len) // 2
                for idx in range(tot_num):
                    for jdx in range(tot_num):
                        _xl = xl + idx * (fill_w + fill_sp)
                        _yl = yl + jdx * (fill_w + fill_sp)
                        if (orient is Orientation.R0 and bbox_out2.xl < _xl < bbox_out2.xh - fill_w and
                            _yl + fill_w < bbox_out.yl - fill_sp) or \
                                (orient is Orientation.R270 and _xl + fill_w < bbox_out.xl - fill_sp
                                 and bbox_out2.yl < _yl < bbox_out2.yh - fill_w):
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
        else:
            raise NotImplementedError(f'n_side={n_side} not supported yet.')


def get_octpath_coord(radius: int, turn: int, n_side: int, width: int, spacing: int, bot_open: int, top_open: int,
                      via_width: int, mode: int) -> Tuple[List[List[PointType]], Optional[List[PointType]], 
                                                          List[List[PointType]], Optional[List[PointType]], 
                                                          Optional[List[PointType]], List[PointType], 
                                                          Optional[PointType]]:
    """
    Get coordinates for all the paths, including lead, tail, via, top, bottom and center tap

    """
    # Mode 0: a turn w/o any break
    # Mode 1: outer turn with only lead break
    # Mode 2: outer turn with lead and bridge break
    # Mode 3: inner turn on odd index (index starts from 0), bridge break at top
    # Mode 4: inner turn on even index, bridge break at bottom
    # Mode 5: other turns on even index
    # Mode 6: other turns on odd index
    # Mode 7: a turn without the last side
    # Mode 8: a turn without the mid side
    # Mode 9: a turn without the mid and last side

    # get step phase and initial phase
    step_phase = 2 * np.pi / n_side
    init_phase = -np.pi / 2 + step_phase / 2
    turn_rad = round_up(radius - turn * (width + spacing) / np.sin(-init_phase))
    offset = round_up(radius * np.cos(np.pi / n_side)) + width // 2

    # get coordinate
    coord = []
    for i in range(n_side):
        x0 = round_up(turn_rad * np.cos(init_phase + step_phase * i)) + offset
        y0 = round_up(turn_rad * np.sin(init_phase + step_phase * i)) + offset
        coord.append((x0, y0))

    # Step 1: get bridge open distance, top/bot bridge coordinate, tail coordinate
    # for top bridge
    # if turn index is even, we need bridge distance equal to pitch of this and previous turn
    top_bdg0 = round_up(turn_rad * np.sin(init_phase + step_phase * (n_side//2)) - \
                       (turn_rad - (spacing + width) / np.sin(-init_phase) *
                       np.sin(init_phase + step_phase * (n_side//2))))
    top_coord0 = [((-top_bdg0) // 2 + offset, coord[n_side//2][1]), (top_bdg0 // 2 + offset, coord[n_side//2][1])]
    top_r_coord0 = (top_bdg0 // 2 + width + (via_width - width) // 2 + offset, coord[n_side//2][1])
    top_l_coord0 = ((-top_bdg0 // 2) - width - (via_width - width) // 2 + offset, coord[n_side//2][1])
    # if turn index is odd, we need bridge distance equal to pitch of this and next turn
    top_bdg1 = round_up((turn_rad + (spacing + width) / np.sin(-init_phase))
                        * np.sin(init_phase + step_phase * (n_side//2)) - \
                        turn_rad * np.sin(init_phase + step_phase * (n_side//2)))
    top_coord1 = [((-top_bdg1) // 2 + offset, coord[n_side//2][1]), (top_bdg1 // 2 + offset, coord[n_side//2][1])]
    top_r_coord1 = (top_bdg1 // 2 + width + (via_width - width) // 2 + offset, coord[n_side//2][1])
    top_l_coord1 = ((-top_bdg1 // 2) - width - (via_width - width) // 2 + offset, coord[n_side//2][1])

    # for bottom bridge
    # if turn number is even, we need bridge distance equal to pitch of this and next turn
    bot_bdg0 = round_up((turn_rad + (spacing + width) / np.sin(-init_phase))
                        * np.sin(init_phase + step_phase * (n_side//2)) - \
                        turn_rad * np.sin(init_phase + step_phase * (n_side//2)))
    bot_coord0 = [((-bot_bdg0) // 2 + offset, coord[0][1]), (bot_bdg0 // 2 + offset, coord[0][1])]
    bot_r_coord0 = (bot_bdg0 // 2 + width + (via_width - width) // 2 + offset, coord[0][1])
    bot_l_coord0 = ((-bot_bdg0 // 2) - width - (via_width - width) // 2 + offset, coord[0][1])
    # if turn number is odd, we need bridge distance equal to pitch of this and previous turn
    bot_bdg1 = round_up(turn_rad * np.sin(init_phase + step_phase * (n_side//2)) - \
                        (turn_rad - (spacing + width) / np.sin(-init_phase))
                        * np.sin(init_phase + step_phase * (n_side//2)))
    bot_coord1 = [((-bot_bdg1) // 2 + offset, coord[0][1]), (bot_bdg1 // 2 + offset, coord[0][1])]
    bot_r_coord1 = (bot_bdg1 // 2 + width + (via_width - width) // 2 + offset, coord[0][1])
    bot_l_coord1 = ((-bot_bdg1 // 2) - width - (via_width - width) // 2 + offset, coord[0][1])

    # Step 2: lead coordinate
    # lead coordinate for R0
    lead_coord0 = [(-bot_open // 2 + offset, coord[0][1]), (bot_open // 2 + offset, coord[0][1])]

    # bot/top open for R0
    bot_open_coord = lead_coord0
    top_open_coord = [(-top_open // 2 + offset, coord[n_side//2][1]),
                      (top_open // 2 + offset, coord[n_side//2][1])]

    # lead coordinate for R270
    lead_coord270 = [(coord[n_side * 3 // 4][0], -bot_open // 2 + offset),
                     (coord[n_side * 3 // 4][0], bot_open // 2 + offset)]

    # right/left open for R270
    left_open_coord = lead_coord270
    right_open_coord = [(coord[n_side // 4][0], -top_open // 2 + offset),
                        (coord[n_side // 4][0], top_open // 2 + offset)]

    # Step 3: get all coordinates under different mode
    path_coord = []
    tail_coord = []
    via_coord = []
    lead_coord = None
    top_coord = None
    bot_coord = None
    center_tap_coord = None
    if mode == 0:   # Mode 0: a turn w/o any break
        for i in range(n_side):
            if i == n_side - 1:
                path_coord.append([coord[n_side-1], coord[0]])
            else:
                path_coord.append([coord[i], coord[i+1]])

    elif mode == 1:  # Mode 1: outer turn with only lead break
        # top/bot bridge coordinate
        lead_coord = lead_coord0
        center_tap_coord = (offset, coord[n_side // 2][1])
        for i in range(n_side):
            if i == n_side - 1:
                path_coord.append([coord[n_side-1], lead_coord0[0]])
                path_coord.append([lead_coord0[1], coord[0]])
            else:
                path_coord.append([coord[i], coord[i+1]])

    elif mode == 2:   # Mode 2: outer turn with lead and bridge break
        lead_coord = lead_coord0
        top_coord = top_coord0
        for i in range(n_side):
            if i == n_side // 2 - 1:
                # path coordinate
                path_coord.append([coord[n_side//2-1], top_r_coord0])
                path_coord.append([top_coord0[0], coord[n_side//2]])
                # tail coordinate
                tail_coord.append([top_r_coord0, top_coord0[1]])
                via_coord.append(top_r_coord0)
            elif i == n_side - 1:
                path_coord.append([coord[n_side-1], lead_coord0[0]])
                path_coord.append([lead_coord0[1], coord[0]])
            else:
                path_coord.append([coord[i], coord[i+1]])

    elif mode == 3:     # Mode 3: inner turn on odd index, bridge break at top
        top_coord = top_coord1
        for i in range(n_side):
            if i == n_side // 2 - 1:
                path_coord.append([coord[n_side//2-1], top_coord1[1]])
                path_coord.append([top_l_coord1, coord[n_side//2]])
                # tail coordinate
                tail_coord.append([top_coord1[0], top_l_coord1])
                via_coord.append(top_l_coord1)
            elif i == n_side - 1:
                path_coord.append([coord[i], coord[0]])
            else:
                path_coord.append([coord[i], coord[i+1]])

    elif mode == 4:  # Mode 4: inner turn on even index, bridge break at bottom
        bot_coord = bot_coord0
        for i in range(n_side):
            if i == n_side - 1:
                path_coord.append([coord[n_side-1], bot_l_coord0])
                path_coord.append([bot_coord0[1], coord[0]])
                # tail coordinate
                tail_coord.append([bot_l_coord0, bot_coord0[0]])
                via_coord.append(bot_l_coord0)
            else:
                path_coord.append([coord[i], coord[i+1]])

    elif mode == 5:     # Mode 5: other turns on even index
        top_coord = top_coord0
        bot_coord = bot_coord0
        for i in range(n_side):
            if i == n_side // 2 - 1:
                # path coordinate
                path_coord.append([coord[n_side//2-1], top_r_coord0])
                path_coord.append([top_coord0[0], coord[n_side//2]])
                # tail coordinate
                tail_coord.append([top_r_coord0, top_coord0[1]])
                via_coord.append(top_r_coord0)
            elif i == n_side - 1:
                path_coord.append([coord[n_side-1], bot_l_coord0])
                path_coord.append([bot_coord0[1], coord[0]])
                # tail coordinate
                tail_coord.append([bot_l_coord0, bot_coord0[0]])
                via_coord.append(bot_l_coord0)
            else:
                path_coord.append([coord[i], coord[i+1]])

    elif mode == 6:     # Mode 6: other turns on odd index
        # lead coordinate
        top_coord = top_coord1
        bot_coord = bot_coord1
        for i in range(n_side):
            if i == n_side / 2 - 1:
                # path coordinate
                path_coord.append([coord[n_side//2-1], top_coord1[1]])
                path_coord.append([top_l_coord1, coord[n_side//2]])
                # tail coordinate
                tail_coord.append([top_coord1[0], top_l_coord1])
                via_coord.append(top_l_coord1)
            elif i == n_side - 1:
                path_coord.append([coord[n_side-1], bot_coord1[0]])
                path_coord.append([bot_r_coord1, coord[0]])
                # tail coordinate
                tail_coord.append([bot_coord1[1], bot_r_coord1])
                via_coord.append(bot_r_coord1)
            else:
                path_coord.append([coord[i], coord[i+1]])

    elif mode == 7:     # Mode 7: a turn without the last side
        for i in range(n_side):
            if i == n_side - 1:
                pass
            else:
                path_coord.append([coord[i], coord[i+1]])

    elif mode == 8:     # Mode 8: a turn without the mid side
        for i in range(n_side):
            if i == n_side - 1:
                path_coord.append([coord[n_side-1], coord[0]])
            elif i == n_side//2 - 1:
                pass
            else:
                path_coord.append([coord[i], coord[i+1]])
    elif mode == 9:     # Mode 9: a turn without the mid and last side
        for i in range(n_side):
            if i == n_side - 1 or i == n_side/2 - 1:
                pass
            else:
                path_coord.append([coord[i], coord[i+1]])

    elif mode == 10:     # Mode 10: a turn with top open
        for i in range(n_side):
            if i == n_side - 1:
                path_coord.append([coord[-1], coord[0]])
            elif i == n_side//2 - 1:
                path_coord.append([coord[n_side//2-1], top_open_coord[1]])
                path_coord.append([top_open_coord[0], coord[n_side//2]])
            else:
                path_coord.append([coord[i], coord[i+1]])

    elif mode == 11:     # Mode 11: a turn with bot open
        for i in range(n_side):
            if i == n_side - 1:
                path_coord.append([coord[-1], bot_open_coord[0]])
                path_coord.append([bot_open_coord[1], coord[0]])
            else:
                path_coord.append([coord[i], coord[i+1]])

    elif mode == 12:    # Mode 12: a turn with top/bot open
        for i in range(n_side):
            if i == n_side - 1:
                path_coord.append([coord[-1], bot_open_coord[0]])
                path_coord.append([bot_open_coord[1], coord[0]])
            elif i == n_side//2 - 1:
                path_coord.append([coord[n_side//2-1], top_open_coord[1]])
                path_coord.append([top_open_coord[0], coord[n_side//2]])
            else:
                path_coord.append([coord[i], coord[i+1]])

    elif mode == 14:    # Mode 14: a turn with left open
        lead_coord = lead_coord270
        center_tap_coord = (coord[n_side // 4][0], offset)
        for i in range(n_side):
            if i == n_side * 3 // 4 - 1:
                path_coord.append([coord[i], left_open_coord[1]])
                path_coord.append([left_open_coord[0], coord[i + 1]])
            else:
                path_coord.append([coord[i], coord[(i + 1) % n_side]])

    else:
        raise ValueError("Other modes are not done yet.")

    return path_coord, lead_coord, tail_coord, top_coord, bot_coord, via_coord, center_tap_coord


def round_up(val_f: float) -> int:
    return int(np.ceil(val_f)) if val_f > 0 else int(np.floor(val_f))
