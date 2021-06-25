# -*- coding: utf-8 -*-
import numpy as np
import abc
from typing import List, Tuple, Mapping, Any, Union, Optional

from bag.layout.template import TemplateDB, TemplateBase
from bag.layout.util import BBox
from bag.util.immutable import Param
from bag.typing import PointType
from bag.layout.routing.base import WireArray

from pybag.enum import PathStyle, Orientation, RoundMode, Direction


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

    def _draw_ind_ring(self, halflen: int, width: int, spacing: int, turn: int, n_conn: int, conn_width: int,
                       opening: int, ind_layid: int, layer_list: List[int], pin_len: int,
                       orient: Orientation = Orientation.R0) -> Tuple[List[List[List[List[PointType]]]], List[int]]:
        if n_conn == 1:
            raise ValueError("number of connection points should be larger than 1.")

        pitch = width + spacing
        ring_arr = []
        ring_lenarr = []
        for idx in range(turn):
            path_arr, length = self.draw_sqr_guardring(halflen + idx * pitch, width, opening, ind_layid,
                                                       layer_list, orient=orient)
            ring_arr.append(path_arr)
            ring_lenarr.append(length)

        # # get connect step on inductor layer
        # conn_tr = self.grid.dim_to_num_tracks(ind_layid, conn_width, round_mode=RoundMode.GREATER_EQ)
        # conn_width = self.grid.track_to_coord(ind_layid, conn_tr)
        # step = -(-(ring_lenarr[0] - conn_width) // (n_conn - 1))
        #
        # if orient in (Orientation.R0, Orientation.MY) and ind_layid % 2 == 1 or \
        #         orient is Orientation.R270 and ind_layid % 2 == 0:
        #     for idx in range(n_conn):
        #         conn_idx = self.grid.coord_to_track(ind_layid, (- ring_lenarr[0] + conn_width) // 2 + idx * step,
        #                                             RoundMode.NEAREST)
        #         self.add_wires(ind_layid, conn_idx, (ring_lenarr[0] - width) // 2, (ring_lenarr[-1] + width) // 2,
        #                        width=conn_tr.dbl_value)
        #         ring_conn.append(self.add_wires(ind_layid, conn_idx, (ring_lenarr[-1] + width) // 2 - pin_len,
        #                                         (ring_lenarr[-1] + width) // 2, width=conn_tr.dbl_value))
        # elif orient in (Orientation.R180, Orientation.MX) and ind_layid % 2 == 1 or \
        #         orient is Orientation.R90 and ind_layid % 2 == 0:
        #     for idx in range(n_conn):
        #         conn_idx = self.grid.coord_to_track(ind_layid, (- ring_lenarr[0] + conn_width) // 2 + idx * step,
        #                                             RoundMode.NEAREST)
        #         self.add_wires(ind_layid, conn_idx, (- ring_lenarr[-1] - width) // 2, (-ring_lenarr[0] + width) // 2,
        #                        width=conn_tr.dbl_value)
        #         ring_conn.append(self.add_wires(ind_layid, conn_idx, (-ring_lenarr[-1] - width) // 2,
        #                                         (-ring_lenarr[-1] - width) // 2 + pin_len, width=conn_tr.dbl_value))
        # else:
        #     # get connect step on inductor layer
        #     for idx in range(n_conn):
        #         conn_idx = self.grid.coord_to_track(ind_layid, (- ring_lenarr[0] + conn_width) // 2 + idx * step,
        #                                             RoundMode.NEAREST)
        #         # top side
        #         self.add_wires(ind_layid, conn_idx, (ring_lenarr[0] - width) // 2, (ring_lenarr[-1] + width) // 2,
        #                        width=conn_tr.dbl_value)
        #         ring_conn.append(self.add_wires(ind_layid, conn_idx, (ring_lenarr[-1] + width) // 2 - pin_len,
        #                                         (ring_lenarr[-1] + width) // 2, width=conn_tr.dbl_value))
        #         # bot side
        #         self.add_wires(ind_layid, conn_idx, (-ring_lenarr[-1] - width) // 2, (-ring_lenarr[0] + width) // 2,
        #                        width=conn_tr.dbl_value)
        #         ring_conn.append(self.add_wires(ind_layid, conn_idx, (-ring_lenarr[-1] - width) // 2,
        #                                         (-ring_lenarr[-1] - width) // 2 + pin_len, width=conn_tr.dbl_value))
        #
        # # get connect step on inductor-1 layer
        # conn_tr = self.grid.dim_to_num_tracks(ind_layid - 1, conn_width, round_mode=RoundMode.GREATER_EQ)
        # conn_width = self.grid.track_to_coord(ind_layid - 1, conn_tr)
        # step = -(-(ring_lenarr[0] - conn_width) // (n_conn - 1))
        # for idx in range(n_conn):
        #     conn_idx = self.grid.coord_to_track(ind_layid - 1, (-ring_lenarr[0] + conn_width) // 2 + idx * step,
        #                                         RoundMode.NEAREST)
        #     # right side
        #     self.add_wires(ind_layid - 1, conn_idx, (ring_lenarr[0] - width) // 2, (ring_lenarr[-1] + width) // 2,
        #                    width=conn_tr.dbl_value)
        #     ring_conn.append(self.add_wires(ind_layid - 1, conn_idx, (ring_lenarr[-1] + width) // 2 - pin_len,
        #                                     (ring_lenarr[-1] + width) // 2, width=conn_tr.dbl_value))
        #
        #     # left side
        #     self.add_wires(ind_layid - 1, conn_idx, (-ring_lenarr[-1] - width) // 2, (-ring_lenarr[0] + width) // 2,
        #                    width=conn_tr.dbl_value)
        #     ring_conn.append(self.add_wires(ind_layid - 1, conn_idx, (-ring_lenarr[-1] - width) // 2,
        #                                     (-ring_lenarr[-1] - width) // 2 + pin_len, width=conn_tr.dbl_value))
        return ring_arr, ring_lenarr

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
            for i, path in enumerate(path_coord):
                if lay_id + 1 != ind_layid:
                    via_coord.append(((path[0][0] + path[1][0]) // 2, (path[0][1] + path[1][1]) // 2))
                    if path[0][0] == path[1][0]:
                        via_dir.append(1)
                        via_width.append(abs(path[0][1] - path[1][1]) - width * 2)
                    else:
                        via_dir.append(0)
                        via_width.append(abs(path[0][0] - path[1][0]) - width * 2)
                else:
                    pass

            # draw via on one layer
            for coord, _dir, wid in zip(via_coord, via_dir, via_width):
                if lay_id == ind_layid:  # skip for the last layer
                    if ind_layid % 2 == 0:
                        continue
                    lay_id -= 1
                if _dir == 0:
                    self.draw_via(coord, wid, width, lay_id, lay_id + 1)
                else:
                    self.draw_via(coord, width, wid, lay_id, lay_id + 1)
        return path_arr, length

    # def draw_sqr_guardring(self, halflen: int, width: int, ind_width: int, opening: int, ind_layid: int,
    #                        layer_list: List[int]) -> int:
    #     """
    #     Draw inductor guard ring for designated layers
    #
    #     Parameters
    #     ----------
    #     halflen: int
    #         guard ring half length
    #     width: int
    #         guard ring metal width
    #     ind_width: int
    #         inductor width
    #     opening : int
    #         lead opening
    #     ind_layid: int
    #         inductor top layer
    #     layer_list:
    #         layer list for guard ring
    #     Returns
    #     ----------
    #     length : int
    #     """
    #     # check if all layers are adjacent
    #     if len(layer_list) == 0:
    #         raise ValueError("Layer list should not be empty")
    #     elif len(layer_list) != layer_list[-1] - layer_list[0] + 1:
    #         raise ValueError("All layer should be adjacent, from low to high")
    #
    #     # some constant
    #     radius = halflen * np.sqrt(2)
    #     n_side = 4
    #
    #     # Step 1: draw each turn of guard ring
    #     path_arr = []
    #     # draw each turn of the guard ring
    #     for lay_id in layer_list:
    #         if lay_id == ind_layid:  # on inductor layer
    #             path_coord, _, _, _, _, _ = get_octpath_coord(radius, 0, n_side, width, 0, opening + ind_width * 4, 0,
    #                                                           0, mode=11)
    #         else:   # other layers
    #             path_coord, _, _, _, _, _ = get_octpath_coord(radius, 0, n_side, width, 0, opening + ind_width * 4,
    #                                                           ind_width * 2, 0, mode=0)
    #         # put them in an array
    #         path_arr.append(path_coord)
    #
    #     # draw path
    #     for path_coord, lay_id in zip(path_arr, layer_list):
    #         self.draw_path(lay_id, width, path_coord, end_style=PathStyle.extend, join_style=PathStyle.extend)
    #
    #     # get length of this guard ring
    #     length = path_arr[-1][0][0][0] * 2
    #
    #     # draw via on different layers
    #     for path_coord, lay_id in zip(path_arr, layer_list):
    #         via_coord = []
    #         via_dir = []
    #         via_width = []
    #         for i, path in enumerate(path_coord):
    #             if lay_id == layer_list[-1]:    # skip for the last layer
    #                 if i < n_side - 1:
    #                     if i % 2 == 0:
    #                         via_coord.append((path[0][0], 0))
    #                         via_dir.append(1)
    #                     else:
    #                         via_coord.append((0, path[0][1]))
    #                         via_dir.append(0)
    #                     via_width.append((np.abs(path[0][0]) - width) * 2)
    #                 else:
    #                     via_coord.append(((path[0][0]+path[1][0])//2, path[0][1]))
    #                     via_dir.append(0)
    #                     via_width.append(np.abs(path[1][0]-path[0][0]) - width*2)
    #             elif lay_id+1 == ind_layid:
    #                 pass
    #             else:
    #                 if i % 2 == 0:
    #                     via_coord.append((path[0][0], 0))
    #                     via_dir.append(1)
    #                 else:
    #                     via_coord.append((0, path[0][1]))
    #                     via_dir.append(0)
    #                 via_width.append((abs(path[0][0]) - width) * 2)
    #
    #         # draw via on one layer
    #         for coord, _dir, wid in zip(via_coord, via_dir, via_width):
    #             if lay_id == layer_list[-1]:  # skip for the last layer
    #                 lay_id -= 1
    #             if _dir == 0:
    #                 self.draw_via(coord, wid, width, lay_id, lay_id + 1)
    #             else:
    #                 self.draw_via(coord, width, wid, lay_id, lay_id + 1)
    #     return length

    # def draw_oct_guardring(self, radius: int, n_side: int, width: int, ind_width: int, opening: int, ind_layer: int,
    #                        ind_turn: int, layer_list: List[int]) -> None:
    #     """
    #     Draw inductor guard ring for designated layers
    #
    #     Parameters
    #     ----------
    #     radius: int
    #         guard ring radius
    #     n_side : int
    #         Number of sides
    #     width: int
    #         guard ring metal width
    #     ind_width: int
    #         inductor width
    #     opening : int
    #         lead opening
    #     ind_layer: int
    #         inductor top layer
    #     ind_turn: int
    #         inductor turn number, 8 for now
    #     layer_list:
    #         layer list for guard ring
    #
    #     Returns
    #     ----------
    #     None
    #     """
    #     # check if all layers are adjacent
    #     if len(layer_list) == 0:
    #         raise ValueError("Layer list should not be empty")
    #     elif len(layer_list) != layer_list[-1] - layer_list[0] + 1:
    #         raise ValueError("All layer should be adjacent, from low to high")
    #
    #     # get via length
    #     length = np.ceil(radius * np.sin(np.pi / n_side)) * 2
    #
    #     # Step 1: draw each turn of guard ring
    #     path_arr = []
    #     # draw each turn of the guard ring
    #     for lay_id in layer_list:
    #         if lay_id == ind_layer:
    #             if ind_turn >= 2:
    #                 mode = 11
    #             else:
    #                 mode = 12
    #         elif lay_id == ind_layer - 2:
    #             if ind_turn >= 3:
    #                 if ind_turn % 2 == 0:
    #                     mode = 11
    #                 else:
    #                     mode = 10
    #             else:
    #                 mode = 0
    #         else:
    #             mode = 0
    #         path_coord, _, _, _, _, _ = \
    #             get_octpath_coord(radius, 0, n_side, width, 0, opening + ind_width * 4, ind_width * 2, 0, mode=mode)
    #         # put them in an array
    #         path_arr.append(path_coord)
    #
    #     # draw path
    #     for path_coord, lay_id in zip(path_arr, layer_list):
    #         self.draw_path(lay_id, width, path_coord, end_style=PathStyle.round, join_style=PathStyle.round)
    #
    #     # Step 2: draw via between adjacent layers
    #     for i, lay_id in enumerate(layer_list):
    #         via_coord = []
    #
    #         if lay_id == layer_list[-1]:    # not draw via for top layer (M9)
    #             pass
    #         elif lay_id+1 == ind_layer:   # if inductor layer-1 (M8)is used, need consider how many turns
    #             if ind_turn >= 2:   # draw three groups of vias
    #                 for j in range(n_side // 2 - 1):
    #                     if j % 2 == 0:
    #                         d = np.ceil(radius * np.cos(4 * np.pi / n_side * j + np.pi / n_side))
    #                         via_coord.append([d, 0])
    #                     else:
    #                         d = np.ceil(radius * np.sin(4 * np.pi / n_side * j + np.pi / n_side))
    #                         via_coord.append([0, d])
    #             else:   # draw two groups of vias
    #                 for j in range(n_side // 2):
    #                     if j % 2 == 0:
    #                         d = np.ceil(radius * np.cos(4 * np.pi / n_side * j + np.pi / n_side))
    #                         via_coord.append([d, 0])
    #         elif lay_id == ind_layer - 2 or lay_id == ind_layer - 3:
    #             # considering inductor layer - 2 (M7)
    #             if ind_turn >= 3:
    #                 if ind_turn % 2 == 0:
    #                     for j in range(n_side // 2 - 1):
    #                         if j % 2 == 0:
    #                             d = np.ceil(radius * np.cos(4 * np.pi / n_side * j + np.pi / n_side))
    #                             via_coord.append([d, 0])
    #                         else:
    #                             d = np.ceil(radius * np.sin(4 * np.pi / n_side * j + np.pi / n_side))
    #                             via_coord.append([0, d])
    #                 else:
    #                     for j in range(n_side // 2):
    #                         if j == n_side // 4-1:
    #                             pass
    #                         elif j % 2 == 0:
    #                             d = np.ceil(radius * np.cos(4 * np.pi / n_side * j + np.pi / n_side))
    #                             via_coord.append([d, 0])
    #                         else:
    #                             d = np.ceil(radius * np.sin(4 * np.pi / n_side * j + np.pi / n_side))
    #                             via_coord.append([0, d])
    #             else:
    #                 for j in range(n_side // 2):
    #                     if j % 2 == 0:
    #                         d = np.ceil(radius * np.cos(4 * np.pi / n_side * j + np.pi / n_side))
    #                         via_coord.append([d, 0])
    #                     else:
    #                         d = np.ceil(radius * np.sin(4 * np.pi / n_side * j + np.pi / n_side))
    #                         via_coord.append([0, d])
    #         else:
    #             for j in range(n_side // 2):
    #                 if j % 2 == 0:
    #                     d = np.ceil(radius * np.cos(4 * np.pi / n_side * j + np.pi / n_side))
    #                     via_coord.append([d, 0])
    #                 else:
    #                     d = np.ceil(radius * np.sin(4 * np.pi / n_side * j + np.pi / n_side))
    #                     via_coord.append([0, d])
    #
    #         # draw via connect different layer
    #         for coord in via_coord:
    #             if coord[0] != 0:
    #                 self.draw_via(coord, width, length, lay_id, lay_id + 1)
    #             else:
    #                 self.draw_via(coord, length, width, lay_id, lay_id + 1)

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
                         res_space: int, center_tap_coord: PointType, orient: Orientation) -> WireArray:
        tap_ext = width // 2 + res_space + res3_l

        if n_turn % 2:
            if orient in (Orientation.R0, Orientation.MY) and ind_layid % 2 == 1 or \
                    orient is Orientation.R270 and ind_layid % 2 == 0:
                # add tap
                tap_idx = self.grid.coord_to_track(ind_layid, center_tap_coord[1], RoundMode.NEAREST)
                track = self.grid.dim_to_num_tracks(ind_layid, width, round_mode=RoundMode.GREATER_EQ)
                tap_ = self.add_wires(ind_layid, tap_idx, lower=center_tap_coord[0],
                                      upper=center_tap_coord[0] + tap_ext + tap_len, width=track.dbl_value)
                tap_bbox = tap_.bound_box
                tap_res_bbox = BBox(tap_bbox.xh - tap_len - res_space - res3_l, tap_bbox.yl,
                                    tap_bbox.xh - tap_len - res_space, tap_bbox.yh)

                # add ind_layid wire
                tap = self.add_wires(ind_layid, tap_idx, lower=tap_res_bbox.xh + res_space,
                                     upper=tap_res_bbox.xh + res_space + pin_len, width=track.dbl_value)

            elif orient is Orientation.R270 and ind_layid % 2 == 1 or \
                    orient in (Orientation.R0, Orientation.MY) and ind_layid % 2 == 0:
                # add tap
                tap_bbox = BBox(center_tap_coord[0] - width // 2, center_tap_coord[1],
                                center_tap_coord[0] + width // 2, center_tap_coord[1] + tap_ext + tap_len)
                lp = self.grid.tech_info.get_lay_purp_list(ind_layid)[0]
                self.add_rect(lp, tap_bbox)

                tap_res_bbox = BBox(tap_bbox.xl, tap_bbox.yh - tap_len - res_space - res3_l, tap_bbox.xh,
                                    tap_bbox.yh - tap_len - res_space)

                # add (ind_layid - 1) wire
                tap_idx = self.grid.coord_to_track(ind_layid - 1, center_tap_coord[0], RoundMode.NEAREST)
                wire_lower = tap_bbox.yh - tap_len
                # get track width
                track = self.grid.dim_to_num_tracks(ind_layid - 1, width, round_mode=RoundMode.GREATER_EQ)
                tap = self.add_wires(ind_layid - 1, tap_idx, lower=wire_lower, upper=wire_lower + pin_len,
                                     width=track.dbl_value)
                # add via to (ind_layid - 1) wire
                pin_bbox = BBox(tap_bbox.xl, tap_bbox.yh - tap_len, tap_bbox.xh, tap_bbox.yh)
                self.connect_bbox_to_track_wires(Direction.UPPER, lp, pin_bbox, tap)

            else:
                raise NotImplementedError('not supported yet')

            # add metal res
            self.add_res_metal(ind_layid, tap_res_bbox)

            return tap
        else:
            raise NotImplementedError('Multiple turns not supported yet.')

    def _draw_lead(self, ind_layid: int, width: int, lead_len: int, lead_coord: List[PointType], pin_len: int,
                   res1_l: int, res2_l: int, res_space: int, ring_len: int, ring_width: int, orient: Orientation,
                   via_width: Optional[int] = None) -> Tuple[WireArray, WireArray, int]:
        if via_width is None:
            via_width = width
        lead_ext = width // 2 + res_space + max(res1_l, res2_l)

        if orient in (Orientation.R0, Orientation.MY) and ind_layid % 2 == 1 or \
                orient is Orientation.R270 and ind_layid % 2 == 0:
            # get track width
            track = self.grid.dim_to_num_tracks(ind_layid, width, round_mode=RoundMode.LESS_EQ)
            # get track index
            term0_idx = self.grid.coord_to_track(ind_layid, lead_coord[0][1], RoundMode.NEAREST)
            term1_idx = self.grid.coord_to_track(ind_layid, lead_coord[1][1], RoundMode.NEAREST)
            # draw leads
            term_lower_coord = min(0, lead_coord[0][0] - lead_len - lead_ext)
            self.add_wires(ind_layid, term0_idx, lower=term_lower_coord, upper=lead_coord[0][0], width=track.dbl_value)
            self.add_wires(ind_layid, term1_idx, lower=term_lower_coord, upper=lead_coord[1][0], width=track.dbl_value)

            # draw metal for pins
            term0 = self.add_wires(ind_layid, term0_idx, lower=term_lower_coord, upper=term_lower_coord + pin_len,
                                   width=track.dbl_value)
            term1 = self.add_wires(ind_layid, term1_idx, lower=term_lower_coord, upper=term_lower_coord + pin_len,
                                   width=track.dbl_value)

            # add metal res
            term0_bbox = term0.bound_box
            term1_bbox = term1.bound_box
            if ind_layid % 2:
                term0_res_bbox = BBox(term0_bbox.xl, term0_bbox.yh + res_space, term0_bbox.xh,
                                      term0_bbox.yh + res1_l + res_space)
                term1_res_bbox = BBox(term1_bbox.xl, term1_bbox.yh + res_space, term1_bbox.xh,
                                      term1_bbox.yh + res2_l + res_space)
                term_res_w = term0_bbox.w
            else:
                term0_res_bbox = BBox(term0_bbox.xh + res_space, term0_bbox.yl, term0_bbox.xh + res1_l + res_space,
                                      term0_bbox.yh)
                term1_res_bbox = BBox(term1_bbox.xh + res_space, term1_bbox.yl, term1_bbox.xh + res2_l + res_space,
                                      term1_bbox.yh)
                term_res_w = term0_bbox.h
            self.add_res_metal(ind_layid, term0_res_bbox)
            self.add_res_metal(ind_layid, term1_res_bbox)

            # if orient is MY, swap two terminals
            if orient is Orientation.MY:
                term0, term1 = term1, term0

        elif orient in (Orientation.R180, Orientation.MX) and ind_layid % 2 == 1 or \
                orient is Orientation.R90 and ind_layid % 2 == 0:
            # get track width
            track = self.grid.dim_to_num_tracks(ind_layid, width, round_mode=RoundMode.LESS_EQ)
            # get track index
            term0_idx = self.grid.coord_to_track(ind_layid, lead_coord[0][0], RoundMode.NEAREST)
            term1_idx = self.grid.coord_to_track(ind_layid, lead_coord[1][0], RoundMode.NEAREST)
            # draw metal for pins
            term_coord_lower = (ring_len + ring_width) // 2 + lead_len + width // 2 - pin_len
            term_coord_upper = (ring_len + ring_width) // 2 + lead_len + width // 2
            # draw leads
            self.add_wires(ind_layid, term0_idx, lower=-lead_coord[0][1] - width // 2, upper=term_coord_upper,
                           width=track.dbl_value)
            self.add_wires(ind_layid, term1_idx, lower=-lead_coord[0][1] - width // 2, upper=term_coord_upper,
                           width=track.dbl_value)

            # draw metal for pins
            term0 = self.add_wires(ind_layid, term0_idx, lower=term_coord_lower, upper=term_coord_upper,
                                   width=track.dbl_value)
            term1 = self.add_wires(ind_layid, term1_idx, lower=term_coord_lower, upper=term_coord_upper,
                                   width=track.dbl_value)
            # add metal res
            term0_bbox = term0.bound_box
            term0_res_bbox = BBox(term0_bbox.xl, term0_bbox.yh - res_space - res1_l, term0_bbox.xh,
                                  term0_bbox.yh - res_space)
            self.add_res_metal(ind_layid, term0_res_bbox)
            term1_bbox = term1.bound_box
            term1_res_bbox = BBox(term1_bbox.xl, term1_bbox.yh - res_space - res2_l, term1_bbox.xh,
                                  term1_bbox.yh - res_space)
            self.add_res_metal(ind_layid, term1_res_bbox)
            term_res_w = term0_bbox.w
            # if orient is R180, swap two terminals
            if orient is Orientation.R180:
                term0, term1 = term1, term0

        elif orient is Orientation.R90 and ind_layid % 2 == 1 or \
                orient in (Orientation.R180, Orientation.MX) and ind_layid % 2 == 0:
            # get track width
            track = self.grid.dim_to_num_tracks(ind_layid - 1, width, round_mode=RoundMode.NEAREST)
            # get track index
            term0_idx = self.grid.coord_to_track(ind_layid - 1, lead_coord[0][0], RoundMode.NEAREST)
            term1_idx = self.grid.coord_to_track(ind_layid - 1, lead_coord[1][0], RoundMode.NEAREST)

            # draw metal for pins
            term_coord_lower = -(ring_len + ring_width) // 2 - lead_len - width // 2
            term_coord_upper = -(ring_len + ring_width) // 2 - lead_len + width // 2 + pin_len

            tr_width = self.grid.track_to_coord(ind_layid - 1, track)
            term0_y_coord = self.grid.track_to_coord(ind_layid - 1, term0_idx)
            term1_y_coord = self.grid.track_to_coord(ind_layid - 1, term1_idx)

            term0_bbox = BBox(term_coord_lower, term0_y_coord - tr_width // 2,
                              lead_coord[0][1] + width // 2, term0_y_coord + tr_width // 2)
            term1_bbox = BBox(term_coord_lower, term1_y_coord - tr_width // 2,
                              lead_coord[1][1] + width // 2, term1_y_coord + tr_width // 2)

            lp = self.grid.tech_info.get_lay_purp_list(ind_layid)[0]
            self.add_rect(lp, term0_bbox)
            self.add_rect(lp, term1_bbox)

            # add metal res
            term0_res_bbox = BBox(term0_bbox.xl + res_space, term0_bbox.yl, term0_bbox.xl + res_space + res1_l,
                                  term0_bbox.yh)
            self.add_res_metal(ind_layid, term0_res_bbox)
            term1_res_bbox = BBox(term1_bbox.xl + res_space, term1_bbox.yl, term1_bbox.xl + res_space + res2_l,
                                  term1_bbox.yh)
            self.add_res_metal(ind_layid, term1_res_bbox)
            term_res_w = term0_bbox.h

            # add via to ind_layid - 1
            via0_x_coord = term0_bbox.xl + width // 2
            via0_y_coord = term0_bbox.ym
            self.draw_via((via0_x_coord, via0_y_coord), width, width, ind_layid - 1, ind_layid)
            via1_x_coord = term1_bbox.xl + width // 2
            via1_y_coord = term1_bbox.ym
            self.draw_via((via1_x_coord, via1_y_coord), width, width, ind_layid - 1, ind_layid)

            # add (ind_layid - 1) metal
            self.add_wires(ind_layid - 1, term0_idx, lower=term0_bbox.xl, upper=term0_bbox.xl + via_width,
                           width=track.dbl_value)
            self.add_wires(ind_layid - 1, term1_idx, lower=term1_bbox.xl, upper=term1_bbox.xl + via_width,
                           width=track.dbl_value)

            term0 = self.add_wires(ind_layid - 1, term0_idx, lower=term0_bbox.xl, upper=term0_bbox.xl + pin_len,
                                   width=track.dbl_value)
            term1 = self.add_wires(ind_layid - 1, term1_idx, lower=term1_bbox.xl, upper=term1_bbox.xl + pin_len,
                                   width=track.dbl_value)
            # swap two terminals
            term0, term1 = term1, term0

        elif orient is Orientation.R270 and ind_layid % 2 == 1 or \
                orient in (Orientation.R0, Orientation.MY) and ind_layid % 2 == 0:
            # get track width
            track = self.grid.dim_to_num_tracks(ind_layid - 1, width, round_mode=RoundMode.NEAREST)
            # get track index
            term0_idx = self.grid.coord_to_track(ind_layid - 1, lead_coord[0][0], RoundMode.NEAREST)
            term1_idx = self.grid.coord_to_track(ind_layid - 1, lead_coord[1][0], RoundMode.NEAREST)

            # draw metal for pins
            term_lower_coord = min(0, lead_coord[0][1] - lead_len - lead_ext)
            term0_bbox = BBox(lead_coord[0][0] - width // 2, term_lower_coord,
                              lead_coord[0][0] + width // 2, lead_coord[0][1])
            term1_bbox = BBox(lead_coord[1][0] - width // 2, term_lower_coord,
                              lead_coord[1][0] + width // 2, lead_coord[1][1])

            lp = self.grid.tech_info.get_lay_purp_list(ind_layid)[0]
            self.add_rect(lp, term0_bbox)
            self.add_rect(lp, term1_bbox)

            # add metal res
            term0_res_bbox = BBox(term0_bbox.xl, term0_bbox.yl + lead_len + res_space, term0_bbox.xh,
                                  term0_bbox.yl + lead_len + res_space + res1_l)
            self.add_res_metal(ind_layid, term0_res_bbox)
            term1_res_bbox = BBox(term1_bbox.xl, term1_bbox.yl + lead_len + res_space, term1_bbox.xh,
                                  term1_bbox.yl + lead_len + res_space + res2_l)
            self.add_res_metal(ind_layid, term1_res_bbox)
            term_res_w = term0_bbox.w

            # add (ind_layid - 1) wire
            wire_upper = term0_bbox.yl + lead_len
            term0 = self.add_wires(ind_layid - 1, term0_idx, lower=wire_upper - pin_len, upper=wire_upper,
                                   width=track.dbl_value)
            term1 = self.add_wires(ind_layid - 1, term1_idx, lower=wire_upper - pin_len, upper=wire_upper,
                                   width=track.dbl_value)

            # add via to (ind_layid - 1) wire
            pin0_bbox = BBox(term0_bbox.xl, term0_bbox.yl, term0_bbox.xh, term0_bbox.yl + lead_len)
            pin1_bbox = BBox(term1_bbox.xl, term1_bbox.yl, term1_bbox.xh, term1_bbox.yl + lead_len)
            self.connect_bbox_to_track_wires(Direction.UPPER, lp, pin0_bbox, term0)
            self.connect_bbox_to_track_wires(Direction.UPPER, lp, pin1_bbox, term1)
        else:
            raise ValueError('not possible')
        return term0, term1, term_res_w

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
            via_arr.append(self.add_via(bbox, bot_lp, top_lp, bot_dir))
        # if via_coord is a coordinate list
        else:
            for coord in via_coord:
                bbox = BBox(coord[0] - width // 2, coord[1] - height // 2,
                            coord[0] + width // 2, coord[1] + height // 2)
                bot_dir = self.grid.get_direction(bot_layid)
                via_arr.append((self.add_via(bbox, bot_lp, top_lp, bot_dir)))
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
