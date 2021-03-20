#
import time
from geometry_manager import merge_polygons_path, offset_polygon, offset_polygon_holes, get_bbox_area_sh, fill_holes_sh
from plot_stuff import plot_paths


class MachinePath:

    def __init__(self, machining_type='gerber'):
        # machining type
        # gerber, profile

        self.geom_list = []
        if machining_type == 'gerber':
            self.cfg = {'tool_diameter': 0.2, 'passages': 3 }
            if self.cfg['passages'] < 1:
                print("[WARNING] At Least One Pass")
                self.cfg['passages'] = 1
        elif machining_type == 'profile':
            self.cfg = {'tool_diameter': 1.0, 'margin': 0.1, 'taps_number': 4, 'taps_length': 1.0}
        elif machining_type == 'pocketing':
            self.cfg = {'tool_diameter': 1.0}
        else:
            self.cfg = {}
        self.type = machining_type

    def load_geom(self, geom_list):
        self.geom_list = geom_list

    def load_cfg(self, cfg):
        self.cfg = cfg

    def execute(self):
        if self.type == 'gerber':
            self.execute_gerber()
        elif self.type == 'profile':
            self.execute_profile()
        elif self.type == 'pocketing':
            self.execute_pocketing()

    def execute_gerber(self):
        # creo il primo passaggio di lavorazione, quello più vicino alle piste.
        t0 = time.time()
        og_list = []
        prev_poly = []
        for g in self.geom_list:
            prev_poly.append(g.geom)
            og = offset_polygon(g, self.cfg['tool_diameter']/2.0)
            if og is not None:
                og_list.append(og)

        # per i sucessivi si parte dal path precedente, lo si ingrandisce del raggio del tool
        # se ne fa l'or e poi lo si riduce del raggio del tool
        # a quel punto lo si ingrandisce del diametro del tool*(1-perc_di_overlap) [qui è da rivedere la formula]
        for i in range(self.cfg['passages']-1):
            sub_og_list = self._subpath_execute(og_list)
            og_list += sub_og_list

        # plot_shapely(og_list + prev_poly)
        t1 = time.time()
        print("Path Generation Done in " + str(t1-t0) + " sec")
        plot_paths(prev_poly, [og_list], grb_color='green', path_color='black')
        # plot_shapely(og_list)
        # print(og_list)

    def execute_pocketing(self):
        print("Pocketing")
        # creo il primo passaggio di lavorazione, quello più vicino al profilo del foro
        t0 = time.time()
        og_list = []
        prev_poly = []
        for g in self.geom_list:
            prev_poly.append(g.geom)
            og = offset_polygon(g, -self.cfg['tool_diameter']/2.0)
            if og is not None:
                if not og.is_empty:
                    og_list.append(og)

        # per i sucessivi si parte dal path precedente, lo si ingrandisce del raggio del tool
        # se ne fa l'or e poi lo si riduce del raggio del tool
        # a quel punto lo si ingrandisce del diametro del tool*(1-perc_di_overlap) [qui è da rivedere la formula]
        # for i in range(self.cfg['passages']-1):
        #     sub_og_list = self._subpath_execute(og_list)
        #     og_list += sub_og_list

        # plot_shapely(og_list + prev_poly)
        t1 = time.time()
        print("Path Generation Done in " + str(t1-t0) + " sec")
        plot_paths(prev_poly, [og_list], grb_color='grey', path_color='black')
        # plot_shapely(og_list)
        # print(og_list)

    def execute_profile(self):
        # per eseguire la lavorazione di profilo, va prima individuata la geometria
        # esterna, ci sarà un check che indicherà se le altre geom saranno interne
        # Se la geometria esterna è l'unica, verranno elaborati anche i suoi fori
        # se invece sono presenti altre geometrie saranno considerate dei contorni
        # a dei fori che andranno lavorati.

        t0 = time.time()
        og_list = []
        prev_poly = [g.geom for g in self.geom_list]

        # check di singolarità del profilo
        if len(self.geom_list) == 1:
            # profilo mono polygono con eventuali fori
            ext_path = offset_polygon(fill_holes_sh(self.geom_list[0].geom),
                                      self.cfg['tool_diameter'] / 2.0 + self.cfg['margin'], shapely_poly=True)
            if ext_path is not None:
                og_list.append(ext_path)
            og = offset_polygon_holes(self.geom_list[0], -self.cfg['tool_diameter'] / 2.0 + self.cfg['margin'])
            if og is not None:
                og_list.append(og)
        else:
            # profilo composto da più poligoni
            # per individuare il profilo esterno calcolo le aree delle bbox di ogni poligono
            # il poligono con la bbox più grande sarà quello esterno.
            geoms = [g.geom for g in self.geom_list]
            bba = get_bbox_area_sh(geoms.pop(0))
            id = 0

            for i, p in enumerate(geoms):
                a = get_bbox_area_sh(p)
                # print("Area: " + str(a) + " " + str(i+1))
                if a > bba:
                    bba = a
                    id = i + 1

            # print(id)

            # id contiene ora l'indice della geom con bbox maggiore.
            # todo: fare il check che tutte le altre geom siano contenute in essa

            # print("GEOM POLY")
            # print(self.geom_list)
            # print(len(self.geom_list))

            ext_p = self.geom_list[id]
            ext_path = offset_polygon(fill_holes_sh(ext_p.geom),
                                      self.cfg['tool_diameter'] / 2.0 + self.cfg['margin'], shapely_poly=True)
            if ext_path is not None:
                og_list.append(ext_path)

            for i, g in enumerate(self.geom_list):
                if i != id:
                    og = offset_polygon_holes(g, -self.cfg['tool_diameter'] / 2.0 + self.cfg['margin'])
                    if og is not None:
                        og_list.append(og)

        # plot_shapely(og_list + prev_poly)
        t1 = time.time()
        print("Path Generation Done in " + str(t1-t0) + " sec")
        plot_paths(prev_poly, [og_list], grb_color='green', path_color='black')
        # plot_shapely(og_list)
        # print(og_list)

    def _subpath_execute(self, ppg_list):

        # ppg_list pre path list
        pre_offset = self.cfg['tool_diameter']/2.0
        og_list = []

        # print("ORIG")
        # plot_shapely(ppg_list)

        for g in ppg_list:
            og = offset_polygon(g, pre_offset, shapely_poly=True)
            if og is not None:
                if og.geom_type == 'MultiPolygon':
                    for sog in og:
                        og_list.append(sog)
                else:
                    og_list.append(og)

        # print("OFFSET")
        # plot_shapely(og_list)

        mg_list = merge_polygons_path(og_list)

        # print("MERGED")
        # plot_shapely(mg_list)

        mog_list = []
        for g in mg_list:
            mog = offset_polygon(g, -pre_offset, shapely_poly=True)
            if mog is not None:
                if mog.geom_type == 'MultiPolygon':
                    for smog in mog:
                        mog_list.append(smog)
                else:
                    mog_list.append(mog)

        # definisco l'ultima operzione in base al diametro del tool ed il valore dell'overlap

        ng_list = []
        for g in mog_list:
            ng = offset_polygon(g, self.cfg['tool_diameter'] / 2.0, shapely_poly=True)
            if ng is not None:
                # ng_list.append(ng)
                if ng.geom_type == 'MultiPolygon':
                    for sng in ng:
                        ng_list.append(sng)
                else:
                    ng_list.append(ng)

        fmg_list = merge_polygons_path(ng_list)

        return fmg_list