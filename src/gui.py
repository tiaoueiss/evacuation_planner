
import sys, os, math, random, time
import pygame

sys.path.insert(0, os.path.dirname(__file__))
from city_map import build_building_h, FLOOR_Y, FLOOR_ORDER
import search, audio

WIDTH      = 1280
HEIGHT     = 720
MAP_WIDTH  = 960
PANEL_X    = MAP_WIDTH
PANEL_W    = WIDTH - MAP_WIDTH

NODE_RADIUS = 20

BG         = (8,  12, 14)
PANEL_BG   = (11, 15, 19)
GRID_COLOR = (20, 35, 27)
GREEN      = (100, 228, 118)
GREEN_DIM  = (35,  98, 52)
GREEN_DK   = (12,  34, 20)
AMBER      = (255, 194, 78)
RED        = (228,  62, 62)
EXIT_GREEN = (78,  238, 118)
WHITE      = (216, 226, 218)
GRAY       = (82,  96,  96)
PATH_COLOR = (78,  212, 232)
CYAN_DIM   = (28,  85, 105)

WEIGHT_STEP = {"distance": 0.5, "infestation": 5.0, "radiation": 5.0}
WEIGHT_MAX  = {"distance": 5.0, "infestation": 50.0, "radiation": 100.0}



def rtext(surf, text, x, y, font, color=GREEN, glow=False):
    if glow:
        dim = tuple(max(0, c // 4) for c in color)
        s = font.render(text, True, dim)
        surf.blit(s, (x + 1, y + 1))
        surf.blit(s, (x - 1, y - 1))
    surf.blit(font.render(text, True, color), (x, y))

def scanlines(surf, alpha=28):
    ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for y in range(0, HEIGHT, 3):
        pygame.draw.line(ov, (0, 0, 0, alpha), (0, y), (WIDTH, y))
    surf.blit(ov, (0, 0))


def build_vignette():
    ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    cx, cy = WIDTH // 2, HEIGHT // 2
    md = math.hypot(cx, cy)
    for bx in range(0, WIDTH, 16):
        for by in range(0, HEIGHT, 16):
            d = math.hypot(bx - cx, by - cy) / md
            a = int(min(180, max(0, (d - 0.55) * 320)))
            if a:
                pygame.draw.rect(ov, (0, 0, 0, a), (bx, by, 16, 16))
    return ov

def pt_seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx*dx + dy*dy)))
    return math.hypot(px - x1 - t*dx, py - y1 - t*dy)


def dashed_line(surf, color, start, end, width=1, dash=8, gap=6):
    x1, y1 = start; x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    dist = math.hypot(dx, dy)
    if dist == 0:
        return
    for i in range(int(dist // (dash + gap)) + 1):
        t1 = (i * (dash + gap)) / dist
        t2 = min(1.0, (i * (dash + gap) + dash) / dist)
        pygame.draw.line(surf, color,
                         (x1 + dx*t1, y1 + dy*t1),
                         (x1 + dx*t2, y1 + dy*t2), width)



class SporeParticle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "size")

    def __init__(self, x, y):
        self.x = x + random.uniform(-NODE_RADIUS, NODE_RADIUS)
        self.y = y + random.uniform(-NODE_RADIUS, NODE_RADIUS)
        self.vx = random.uniform(-0.3, 0.3)
        self.vy = random.uniform(-0.85, -0.2)
        self.max_life = random.uniform(55, 105)
        self.life = self.max_life
        self.size = random.uniform(1.2, 2.4)

    def update(self):
        self.x += self.vx; self.y += self.vy; self.life -= 1
        return self.life > 0

    def draw(self, surf):
        a = int(175 * self.life / self.max_life)
        s = pygame.Surface((6, 6), pygame.SRCALPHA)
        pygame.draw.circle(s, (232, 68, 68, a), (3, 3), self.size)
        surf.blit(s, (int(self.x - 3), int(self.y - 3)))



class EvacuationApp:

    def __init__(self):
        pygame.init()
        audio.init()

        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("BUILDING H  //  EVAC PROTOCOL  //  CSC474")
        self.clock = pygame.time.Clock()

        self.font_big   = pygame.font.SysFont("consolas", 22, bold=True)
        self.font_med   = pygame.font.SysFont("consolas", 16)
        self.font_small = pygame.font.SysFont("consolas", 12)

        self.city       = build_building_h()
        self.start_node = 30
        self.algorithm  = "A*"
        self.weights    = {"distance": 1.0, "infestation": 10.0, "radiation": 30.0}

        self.expansion_anim   = []
        self.path_anim        = None
        self.anim_frame       = 0
        self.expanded_visible = set()
        self.path_progress    = 0

        self.particles    = []
        self.status_lines = [
            "Aliens detected in USEK Building H.",
            "L-click a room to set start, then click [RUN SEARCH].",
        ]
        self.last_result  = None
        self.popup        = None
        self.mouse_pos    = (0, 0)
        self.show_labels  = False

        self.vignette = build_vignette()
        self._init_buttons()
        audio.start_ambient()


    def _init_buttons(self):
        px = PANEL_X + 14
        bw = PANEL_W - 28

        aw = (bw - 6) // 2
        self.algo_rects = {}
        for i, algo in enumerate(["BFS", "UCS", "Greedy", "A*"]):
            col, row = i % 2, i // 2
            self.algo_rects[algo] = pygame.Rect(
                px + col * (aw + 6), 174 + row * 34, aw, 28)

        self.run_rect     = pygame.Rect(px, 248, bw, 50)
        half              = (bw - 6) // 2
        self.compare_rect = pygame.Rect(px,          306, half, 32)
        self.reset_rect   = pygame.Rect(px + half + 6, 306, half, 32)
        self.labels_rect  = pygame.Rect(px, 444, bw, 24)

        bx = px + bw - 26
        self.wt_rects = {}
        for i, key in enumerate(["distance", "infestation", "radiation"]):
            wy = 366 + i * 24
            self.wt_rects[f"{key}+"] = pygame.Rect(bx, wy,      24, 11)
            self.wt_rects[f"{key}-"] = pygame.Rect(bx, wy + 13, 24, 11)


    def _btn(self, rect, label, font, *, active=False, hover=False, accent=GREEN):
        bg = (28, 52, 36) if (active or hover) else GREEN_DK
        pygame.draw.rect(self.screen, bg, rect, border_radius=4)
        border = accent if (active or hover) else GREEN_DIM
        pygame.draw.rect(self.screen, border, rect, 1, border_radius=4)
        tc = WHITE if active else (accent if hover else GREEN_DIM)
        ts = font.render(label, True, tc)
        self.screen.blit(ts, (
            rect.x + (rect.w - ts.get_width())  // 2,
            rect.y + (rect.h - ts.get_height()) // 2,
        ))


    def _show_intro(self):
        fhuge = pygame.font.SysFont("consolas", 74, bold=True)
        fbig  = pygame.font.SysFont("consolas", 30, bold=True)
        fmed  = pygame.font.SysFont("consolas", 19)
        fsm   = pygame.font.SysFont("consolas", 14)
        fxs   = pygame.font.SysFont("consolas", 12)

        LINES = [
            "ALIEN FORCES HAVE BREACHED USEK BUILDING H.",
            "UB2 SERVER ROOM COMPROMISED.  HIVE EXPANDING.",
            "ALL STUDENTS: EVACUATE IMMEDIATELY.",
        ]
        FLOORS = [
            ("  [F3]  Chapel  Lecture Hall  Faculty Office  Library", False),
            ("  [F2]  Labs  Hallways", False),
            ("  [F1]  Reception  Atrium  Cafeteria   [2 EXITS HERE]", False),
            ("  [UB1] Parking  Bio Lab   (heavy alien infestation)", True),
            ("  [UB2] Server Room  HIVE   << ORIGIN POINT >>", True),
        ]

        noise = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for _ in range(280):
            pygame.draw.rect(noise, (210, 55, 55, random.randint(18, 75)),
                             (random.randint(0, WIDTH),
                              random.randint(0, HEIGHT),
                              random.randint(3, 45), 1))

        start      = time.time()
        last_alarm = -99.0
        running    = True

        while running:
            elapsed = time.time() - start

            if elapsed - last_alarm > 2.4:
                audio.play("alarm", volume=0.82)
                last_alarm = elapsed

            if elapsed > 9.0:
                break

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    audio.shutdown()
                    pygame.quit()
                    return False
                if ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    running = False

            self.screen.fill((2, 2, 4))

            alarm_a = int(55 * (0.5 + 0.5 * math.sin(elapsed * math.pi * 2.6)))
            ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            ov.fill((170, 0, 0, alarm_a))
            self.screen.blit(ov, (0, 0))

            if random.random() < 0.12:
                self.screen.blit(noise, (0, 0))

            ts = fxs.render(
                "EVACUATION PLANNER",
                True, (108, 155, 115))
            self.screen.blit(ts, ((WIDTH - ts.get_width()) // 2, 22))

            pulse = 0.72 + 0.28 * math.sin(elapsed * 3.8)
            rc = (int(218 * pulse), int(38 * pulse), int(38 * pulse))
            ts = fhuge.render("BUILDING   H", True, rc)
            self.screen.blit(ts, ((WIDTH - ts.get_width()) // 2, 50))

            lx = (WIDTH - 680) // 2
            pygame.draw.line(self.screen, (165, 28, 28), (lx, 158), (lx + 680, 158), 2)

            if math.sin(elapsed * 5.2) > 0:
                ts = fbig.render("[!!]  ALIEN INVASION DETECTED  [!!]", True, RED)
                self.screen.blit(ts, ((WIDTH - ts.get_width()) // 2, 172))

            box_x = (WIDTH - 720) // 2
            ty = 228
            for i, line in enumerate(LINES):
                visible = min(len(line), int(max(0, elapsed * 26 - i * 16)))
                seg = line[:visible]
                if visible < len(line) and math.sin(elapsed * 9) > 0:
                    seg += "|"
                ts = fmed.render(seg, True, AMBER)
                self.screen.blit(ts, (box_x, ty))
                ty += 34

            bar_w  = 620
            bar_x  = (WIDTH - bar_w) // 2
            bar_y  = 340
            prog   = min(1.0, elapsed / 8.0)
            pygame.draw.rect(self.screen, (35, 72, 45), (bar_x, bar_y, bar_w, 16), 1)
            pygame.draw.rect(self.screen, GREEN,
                             (bar_x + 1, bar_y + 1, int((bar_w - 2) * prog), 14))
            dots = "." * (int(elapsed * 3) % 4)
            ts = fsm.render(f"EVACUATION PROTOCOL LOADING{dots:<4}", True, GREEN)
            self.screen.blit(ts, ((WIDTH - ts.get_width()) // 2, bar_y + 20))

            bx_, by_ = (WIDTH - 680) // 2, 378
            bh_ = 10 + len(FLOORS) * 19
            bg_s = pygame.Surface((680, bh_), pygame.SRCALPHA)
            bg_s.fill((8, 20, 12, 210))
            self.screen.blit(bg_s, (bx_, by_))
            pygame.draw.rect(self.screen, (38, 88, 52), (bx_, by_, 680, bh_), 1)
            rtext(self.screen, "  BUILDING OVERVIEW:", bx_, by_ + 2, fxs, AMBER)
            for i, (fl, danger) in enumerate(FLOORS):
                col = (165, 58, 58) if danger else (82, 162, 100)
                rtext(self.screen, fl, bx_, by_ + 18 + i * 19, fxs, col)

            if math.sin(elapsed * 2.8) > 0:
                ts = fmed.render("[ PRESS ANY KEY TO BEGIN EVACUATION ]",
                                 True, (165, 215, 172))
                self.screen.blit(ts, ((WIDTH - ts.get_width()) // 2, 502))

            ts = fxs.render(f"T+{elapsed:.1f}s  //  THREAT ACTIVE", True, (130, 45, 45))
            self.screen.blit(ts, (WIDTH - ts.get_width() - 10, HEIGHT - 18))

            scanlines(self.screen, alpha=38)
            pygame.display.flip()
            self.clock.tick(60)

        return True


    def hit_node(self, mx, my):
        for node in self.city.nodes.values():
            if math.hypot(mx - node.x, my - node.y) <= NODE_RADIUS + 4:
                return node.id
        return None

    def hit_edge(self, mx, my, tol=13):
        best, bd = None, tol
        for edge in self.city.edges:
            u = self.city.nodes[edge.u]; v = self.city.nodes[edge.v]
            d = pt_seg_dist(mx, my, u.x, u.y, v.x, v.y)
            if d < bd:
                bd = d; best = edge
        return best

    def handle_left_click(self, pos):
        mx, my = pos
        if mx >= PANEL_X:
            self._panel_click(pos)
            return
        nid = self.hit_node(mx, my)
        if nid is not None:
            if self.city.nodes[nid].is_exit:
                self.status_lines = ["Exits are the TARGET — pick another room to start."]
                return
            self.start_node = nid
            self.status_lines = [
                f"Survivor: {self.city.nodes[nid].label}",
                "Now click  [RUN SEARCH]  to find the escape route.",
            ]
            self.clear_animation()
            return
        edge = self.hit_edge(mx, my)
        if edge:
            edge.blocked = not edge.blocked
            audio.play("block", volume=0.6)
            self.status_lines = [
                f"Corridor {edge.u}<->{edge.v}: "
                f"{'BLOCKED' if edge.blocked else 'OPEN'}"
            ]

    def handle_right_click(self, pos):
        mx, my = pos
        if mx >= PANEL_X:
            return
        nid = self.hit_node(mx, my)
        if nid is None or self.city.nodes[nid].is_exit:
            return
        node = self.city.nodes[nid]
        new = 0.0 if node.infestation > 0.5 else 0.95
        node.infestation = new
        audio.play("block", volume=0.4)
        self.status_lines = [f"Infestation at {node.label}: {new:.0%}"]

    def _panel_click(self, pos):
        for algo, rect in self.algo_rects.items():
            if rect.collidepoint(pos):
                self.algorithm = algo
                audio.play("blip_lo")
                return
        if self.run_rect.collidepoint(pos):
            self.run_search(); return
        if self.compare_rect.collidepoint(pos):
            self.compare_all(); return
        if self.reset_rect.collidepoint(pos):
            self.reset_map(); return
        for key_dir, rect in self.wt_rects.items():
            if rect.collidepoint(pos):
                key  = key_dir[:-1]
                sign = 1 if key_dir.endswith("+") else -1
                val  = self.weights[key] + sign * WEIGHT_STEP[key]
                self.weights[key] = max(0.0, min(WEIGHT_MAX[key], round(val, 1)))
                audio.play("blip_lo")
                return
        if self.labels_rect.collidepoint(pos):
            self.show_labels = not self.show_labels
            audio.play("blip_lo")
            return


    def run_search(self):
        self.clear_animation()
        result = search.run(self.algorithm, self.city, self.start_node, self.weights)
        self.last_result = result
        if not result.found:
            audio.play("failed")
            audio.play("alarm", volume=0.5)
            self.status_lines = [
                f"!! {self.algorithm}: NO EVACUATION ROUTE FOUND !!",
                "Try clearing a blocked corridor (click on red dashed line).",
            ]
            return
        self.expansion_anim   = list(result.expanded_order)
        self.path_anim        = result
        self.anim_frame       = 0
        self.expanded_visible = set()
        self.path_progress    = 0
        goal = self.city.nodes[result.goal_id].label
        self.status_lines = [f"Route found -> {goal}  |  scanning rooms..."]
        audio.play("blip_hi")

    def compare_all(self):
        rows = ["-- ALGORITHM COMPARISON --", ""]
        for name in ["BFS", "UCS", "Greedy", "A*"]:
            r = search.run(name, self.city, self.start_node, self.weights)
            if r.found:
                rows.append(
                    f" {name:7s} cost={r.total_cost:6.0f}  hops={len(r.path)-1}"
                    f"  exp={len(r.expanded_order):2d}  exit={self.city.nodes[r.goal_id].label}"
                )
            else:
                rows.append(f" {name:7s} NOT FOUND  exp={len(r.expanded_order):2d}")
        rows += ["", "Press any key or click to close."]
        self.popup = (rows, 500)
        audio.play("blip_hi")

    def reset_map(self):
        self.city = build_building_h()
        self.start_node = 30
        self.clear_animation()
        self.status_lines = ["Map reset. Alien invasion still in progress."]
        audio.play("block")

    def clear_animation(self):
        self.expansion_anim   = []
        self.path_anim        = None
        self.anim_frame       = 0
        self.expanded_visible = set()
        self.path_progress    = 0


    def update(self):
        if self.expansion_anim:
            self.anim_frame += 1
            if self.anim_frame % 5 == 0:
                nid = self.expansion_anim.pop(0)
                self.expanded_visible.add(nid)
                audio.play_blip_for_floor(self.city.nodes[nid].floor)
                if not self.expansion_anim:
                    audio.play("found", volume=0.7)
                    goal = self.city.nodes[self.path_anim.goal_id].label
                    self.status_lines = [
                        f"ROUTE FOUND  ->  {goal}",
                        f"cost={self.path_anim.total_cost:.0f}  "
                        f"hops={len(self.path_anim.path)-1}  "
                        f"expanded={len(self.path_anim.expanded_order)} rooms",
                    ]
        elif self.path_anim is not None:
            self.anim_frame += 1
            if self.anim_frame % 8 == 0:
                if self.path_progress < len(self.path_anim.path) - 1:
                    self.path_progress += 1

        for node in self.city.nodes.values():
            if node.infestation > 0.45 and random.random() < node.infestation * 0.07:
                self.particles.append(SporeParticle(node.x, node.y))
        self.particles = [p for p in self.particles if p.update()]

        if self.popup:
            lines, ttl = self.popup
            self.popup = (lines, ttl - 1) if ttl > 0 else None


    def draw(self):
        self.screen.fill(BG)
        self._draw_grid()
        self._draw_floor_labels()
        self._draw_edges()
        self._draw_path()
        self._draw_nodes()
        for p in self.particles:
            p.draw(self.screen)
        self._draw_panel()
        self._draw_status()
        scanlines(self.screen)
        self.screen.blit(self.vignette, (0, 0))
        if self.popup:
            self._draw_popup()
        self._draw_hud()
        pygame.display.flip()

    def _draw_grid(self):
        for x in range(0, MAP_WIDTH, 40):
            pygame.draw.line(self.screen, GRID_COLOR, (x, 0), (x, HEIGHT - 80), 1)
        for y in range(0, HEIGHT - 80, 40):
            pygame.draw.line(self.screen, GRID_COLOR, (0, y), (MAP_WIDTH, y), 1)

    def _draw_floor_labels(self):
        for floor in FLOOR_ORDER:
            fy  = FLOOR_Y[floor]
            ug  = floor.startswith("U")
            band = (48, 26, 26) if ug else (20, 50, 36)
            lc   = (138, 58, 58) if ug else (55, 138, 82)
            pygame.draw.rect(self.screen, band, (0, fy - 44, MAP_WIDTH, 88))
            pygame.draw.line(self.screen, lc, (0, fy - 44), (MAP_WIDTH, fy - 44))
            pygame.draw.line(self.screen, lc, (0, fy + 44), (MAP_WIDTH, fy + 44))
            rtext(self.screen, f"[{floor}]", 8, fy - 9, self.font_med, color=lc)

        gy = (FLOOR_Y["F1"] + FLOOR_Y["UB1"]) // 2 - 4
        for x in range(0, MAP_WIDTH, 16):
            pygame.draw.line(self.screen, (88, 68, 26), (x, gy), (x + 8, gy), 2)
        rtext(self.screen, "= GROUND LEVEL =", MAP_WIDTH // 2 - 64, gy - 14,
              self.font_small, color=(148, 122, 52))

    def _draw_edges(self):
        for edge in self.city.edges:
            u = self.city.nodes[edge.u]; v = self.city.nodes[edge.v]
            if edge.blocked:
                dashed_line(self.screen, RED, (u.x, u.y), (v.x, v.y), 2)
                mx, my = int((u.x + v.x) / 2), int((u.y + v.y) / 2)
                rtext(self.screen, "X", mx - 5, my - 9, self.font_med, color=RED)
            else:
                col = {"elevator": (172, 122, 210),
                       "stairs":   AMBER}.get(edge.kind, GREEN_DIM)
                pygame.draw.line(self.screen, col, (u.x, u.y), (v.x, v.y),
                                 3 if edge.kind != "corridor" else 2)
                if self.show_labels:
                    cost = self.city.edge_cost(edge, self.weights)
                    mx, my = (u.x + v.x) / 2, (u.y + v.y) / 2
                    dx, dy = v.x - u.x, v.y - u.y
                    d = math.hypot(dx, dy)
                    ox, oy = (-dy / d * 10, dx / d * 10) if d > 0 else (0, -10)
                    lbl = self.font_small.render(f"{cost:.0f}", True, AMBER)
                    lx = int(mx + ox) - lbl.get_width() // 2
                    ly = int(my + oy) - lbl.get_height() // 2
                    bg = pygame.Surface((lbl.get_width() + 4, lbl.get_height() + 2), pygame.SRCALPHA)
                    bg.fill((0, 0, 0, 185))
                    self.screen.blit(bg, (lx - 2, ly - 1))
                    self.screen.blit(lbl, (lx, ly))

    def _draw_path(self):
        if self.path_anim is None:
            return
        path = self.path_anim.path
        for i in range(min(self.path_progress, len(path) - 1)):
            u = self.city.nodes[path[i]]; v = self.city.nodes[path[i + 1]]
            gs = pygame.Surface((MAP_WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.line(gs, (78, 212, 232, 62), (u.x, u.y), (v.x, v.y), 14)
            self.screen.blit(gs, (0, 0))
            pygame.draw.line(self.screen, PATH_COLOR, (u.x, u.y), (v.x, v.y), 5)
            dx, dy = v.x - u.x, v.y - u.y
            d = math.hypot(dx, dy)
            if d > 1:
                nx, ny = dx / d, dy / d
                mx_, my_ = (u.x + v.x) // 2, (u.y + v.y) // 2
                tip = (mx_ + nx * 9,  my_ + ny * 9)
                lpt = (mx_ - nx * 9 + (-ny) * 7, my_ - ny * 9 + nx * 7)
                rpt = (mx_ - nx * 9 - (-ny) * 7, my_ - ny * 9 - nx * 7)
                pygame.draw.polygon(self.screen, PATH_COLOR, [tip, lpt, rpt])

    def _draw_nodes(self):
        t = time.time()
        show_h = self.show_labels and self.algorithm in ("Greedy", "A*")
        exits_list = self.city.exits() if show_h else []
        h_scale = self.weights.get("distance", 1.0) if self.algorithm == "A*" else 1.0

        for node in self.city.nodes.values():
            cx, cy = int(node.x), int(node.y)

            if node.infestation > 0.05:
                pulse = 0.5 + 0.5 * math.sin(t * 3 + node.id)
                gr    = int(NODE_RADIUS + 6 + 4 * pulse * node.infestation)
                ga    = int(112 * node.infestation)
                gs    = pygame.Surface((gr*2 + 2, gr*2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(gs, (255, 50, 50, ga), (gr + 1, gr + 1), gr)
                self.screen.blit(gs, (cx - gr - 1, cy - gr - 1))

            r_ = int(20 + 200 * node.infestation)
            g_ = int(30 + 30 * (1 - node.infestation))
            b_ = int(30 + 20 * (1 - node.infestation))
            pygame.draw.circle(self.screen, (min(r_, 255), g_, b_), (cx, cy), NODE_RADIUS)

            if node.is_exit:
                p   = 0.7 + 0.3 * math.sin(t * 4)
                col = tuple(int(c * p) for c in EXIT_GREEN)
                pygame.draw.circle(self.screen, col, (cx, cy), NODE_RADIUS, 3)
                for ang in range(0, 360, 60):
                    a  = math.radians(ang + t * 30)
                    ex = cx + math.cos(a) * (NODE_RADIUS + 7)
                    ey = cy + math.sin(a) * (NODE_RADIUS + 7)
                    pygame.draw.line(self.screen, col, (cx, cy), (int(ex), int(ey)), 1)
            elif node.id == self.start_node:
                p   = 0.7 + 0.3 * math.sin(t * 5)
                col = tuple(int(c * p) for c in PATH_COLOR)
                pygame.draw.circle(self.screen, col, (cx, cy), NODE_RADIUS + 5, 2)
                for dx_, dy_ in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    pygame.draw.line(self.screen, col,
                                     (cx + dx_ * (NODE_RADIUS + 7),
                                      cy + dy_ * (NODE_RADIUS + 7)),
                                     (cx + dx_ * (NODE_RADIUS + 13),
                                      cy + dy_ * (NODE_RADIUS + 13)), 2)
            elif node.id in self.expanded_visible:
                pygame.draw.circle(self.screen, AMBER, (cx, cy), NODE_RADIUS + 3, 2)
            else:
                pygame.draw.circle(self.screen, GREEN_DIM, (cx, cy), NODE_RADIUS, 1)

            ls  = self.font_small.render(node.label, True, WHITE)
            lbg = pygame.Surface((ls.get_width() + 6, ls.get_height() + 2), pygame.SRCALPHA)
            lbg.fill((0, 0, 0, 175))
            self.screen.blit(lbg, (cx - ls.get_width() // 2 - 3, cy + NODE_RADIUS + 4))
            self.screen.blit(ls,  (cx - ls.get_width() // 2,     cy + NODE_RADIUS + 5))

            if show_h and exits_list and not node.is_exit:
                raw_h = min(self.city.heuristic(node.id, e) for e in exits_list)
                h_val = h_scale * raw_h
                hs  = self.font_small.render(f"h={h_val:.0f}", True, (100, 200, 255))
                hbg = pygame.Surface((hs.get_width() + 4, hs.get_height() + 2), pygame.SRCALPHA)
                hbg.fill((0, 0, 0, 175))
                hx = cx - hs.get_width() // 2 - 2
                hy = cy - NODE_RADIUS - hs.get_height() - 4
                self.screen.blit(hbg, (hx, hy))
                self.screen.blit(hs,  (hx + 2, hy + 1))

    def _draw_panel(self):
        pygame.draw.rect(self.screen, PANEL_BG, (PANEL_X, 0, PANEL_W, HEIGHT))
        pygame.draw.line(self.screen, GREEN_DIM, (PANEL_X, 0), (PANEL_X, HEIGHT), 2)

        px   = PANEL_X + 14
        bw   = PANEL_W - 28
        mpos = self.mouse_pos
        t    = time.time()

        rtext(self.screen, "EVAC PROTOCOL v1.0", px, 12, self.font_big, GREEN, glow=True)
        rtext(self.screen, "// USEK BUILDING H //", px, 38, self.font_small, GREEN_DIM)

        threat = sum(n.infestation for n in self.city.nodes.values()) / len(self.city.nodes)
        tc = RED if threat > 0.5 else AMBER if threat > 0.25 else GREEN
        rtext(self.screen, f"THREAT: {threat:.0%}", px, 60, self.font_small, tc)
        pygame.draw.rect(self.screen, GREEN_DIM, (px, 75, bw, 7), 1)
        pygame.draw.rect(self.screen, tc, (px + 1, 76, int((bw - 2) * threat), 5))

        pygame.draw.line(self.screen, GREEN_DIM, (px, 90), (px + bw, 90))

        rtext(self.screen, "SURVIVOR", px, 96, self.font_small, AMBER)
        rtext(self.screen, f"  {self.city.nodes[self.start_node].label}",
              px, 112, self.font_med, WHITE)
        rtext(self.screen, "  target: glowing green EXIT nodes",
              px, 132, self.font_small, GRAY)

        pygame.draw.line(self.screen, GREEN_DIM, (px, 150), (px + bw, 150))

        rtext(self.screen, "ALGORITHM", px, 156, self.font_small, AMBER)
        for algo, rect in self.algo_rects.items():
            self._btn(rect, algo, self.font_small,
                      active=(algo == self.algorithm),
                      hover=rect.collidepoint(mpos),
                      accent=AMBER)

        pulse_c = tuple(int(c * (0.65 + 0.35 * math.sin(t * 2.8))) for c in GREEN)
        hov_run = self.run_rect.collidepoint(mpos)
        pygame.draw.rect(self.screen, GREEN_DK, self.run_rect, border_radius=6)
        pygame.draw.rect(self.screen,
                         GREEN if hov_run else pulse_c,
                         self.run_rect, 2, border_radius=6)
        ts = self.font_big.render("[>] RUN SEARCH", True, WHITE if hov_run else GREEN)
        self.screen.blit(ts, (
            self.run_rect.x + (self.run_rect.w - ts.get_width())  // 2,
            self.run_rect.y + (self.run_rect.h - ts.get_height()) // 2,
        ))

        self._btn(self.compare_rect, "[=] COMPARE ALL", self.font_small,
                  hover=self.compare_rect.collidepoint(mpos), accent=AMBER)
        self._btn(self.reset_rect,   "[R] RESET MAP",   self.font_small,
                  hover=self.reset_rect.collidepoint(mpos),   accent=GRAY)

        pygame.draw.line(self.screen, GREEN_DIM, (px, 344), (px + bw, 344))

        rtext(self.screen, "COST WEIGHTS", px, 348, self.font_small, AMBER)
        LABELS = {"distance": "Distance", "infestation": "Infestation",
                  "radiation": "Radiation"}
        MAXES  = {"distance": 5.0, "infestation": 50.0, "radiation": 100.0}
        wy = 366
        for key, label in LABELS.items():
            val      = self.weights[key]
            bar_avail = bw - 30
            bar_fill  = int(bar_avail * min(1.0, val / MAXES[key]))
            rtext(self.screen, f"{label}: {val:.1f}", px, wy, self.font_small, GREEN)
            pygame.draw.rect(self.screen, GREEN_DIM, (px, wy + 13, bar_avail, 5), 1)
            pygame.draw.rect(self.screen, GREEN,     (px + 1, wy + 14, bar_fill, 3))
            for suffix in ("+", "-"):
                r   = self.wt_rects[f"{key}{suffix}"]
                hov = r.collidepoint(mpos)
                pygame.draw.rect(self.screen,
                                 (24, 50, 32) if hov else GREEN_DK, r, border_radius=2)
                pygame.draw.rect(self.screen,
                                 GREEN if hov else GREEN_DIM, r, 1, border_radius=2)
                ts = self.font_small.render(suffix, True, WHITE if hov else GREEN_DIM)
                self.screen.blit(ts, (r.x + r.w // 2 - ts.get_width() // 2,
                                      r.y + r.h // 2 - ts.get_height() // 2))
            wy += 24

        pygame.draw.line(self.screen, GREEN_DIM, (px, 440), (px + bw, 440))

        lbl_state = "ON" if self.show_labels else "OFF"
        lbl_color = GREEN if self.show_labels else GRAY
        self._btn(self.labels_rect, f"[L] SHOW LABELS: {lbl_state}", self.font_small,
                  active=self.show_labels,
                  hover=self.labels_rect.collidepoint(mpos),
                  accent=lbl_color)

        pygame.draw.line(self.screen, GREEN_DIM, (px, 472), (px + bw, 472))

        rtext(self.screen, "LAST RESULT", px, 476, self.font_small, AMBER)
        if self.last_result:
            r = self.last_result
            if r.found:
                rtext(self.screen, "ROUTE FOUND", px, 493, self.font_med, GREEN, glow=True)
                goal_lbl = self.city.nodes[r.goal_id].label
                for i, line in enumerate([
                    f"  exit  : {goal_lbl}",
                    f"  algo  : {r.algorithm}",
                    f"  cost  : {r.total_cost:.0f}",
                    f"  hops  : {len(r.path) - 1}",
                    f"  scanned: {len(r.expanded_order)} rooms",
                    f"  time  : {r.runtime_ms:.2f} ms",
                ]):
                    rtext(self.screen, line, px, 514 + i * 17, self.font_small, WHITE)
            else:
                rtext(self.screen, "NO ROUTE FOUND", px, 493, self.font_med, RED, glow=True)
                rtext(self.screen, "  Clear a blocked corridor",
                      px, 516, self.font_small, GRAY)
                rtext(self.screen, "  or change your start room.",
                      px, 532, self.font_small, GRAY)
        else:
            rtext(self.screen, "  Run search to see results.",
                  px, 493, self.font_small, GRAY)

        pygame.draw.line(self.screen, GREEN_DIM, (px, 624), (px + bw, 624))

        rtext(self.screen, "TIPS", px, 628, self.font_small, AMBER)
        for i, tip in enumerate([
            "L-click room  -> set survivor start",
            "R-click room  -> toggle infestation",
            "Click red line -> block / unblock",
            "SPACE run  C compare  R reset  L labels  ESC quit",
        ]):
            rtext(self.screen, "  " + tip, px, 644 + i * 17, self.font_small, GRAY)

    def _draw_status(self):
        pygame.draw.rect(self.screen, (4, 8, 8), (0, HEIGHT - 70, MAP_WIDTH, 70))
        pygame.draw.line(self.screen, GREEN_DIM, (0, HEIGHT - 70), (MAP_WIDTH, HEIGHT - 70))
        rtext(self.screen, ">> STATUS", 12, HEIGHT - 62, self.font_small, AMBER)
        for i, line in enumerate(self.status_lines[-2:]):
            rtext(self.screen, "   " + line, 12, HEIGHT - 46 + i * 18, self.font_small, WHITE)

    def _draw_hud(self):
        if self.last_result and not self.last_result.found:
            if math.sin(time.time() * 4) > 0:
                rtext(self.screen, "!! NO ROUTE !!", 14, 14, self.font_big, RED, glow=True)

    def _draw_popup(self):
        lines, _ = self.popup
        h = len(lines) * 22 + 28
        w = 660
        x = (WIDTH - w) // 2
        y = (HEIGHT - h) // 2
        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill((8, 16, 12, 238))
        self.screen.blit(bg, (x, y))
        pygame.draw.rect(self.screen, GREEN, (x, y, w, h), 2)
        for i, line in enumerate(lines):
            col = AMBER if i == 0 else (GRAY if line == "" else WHITE)
            rtext(self.screen, line, x + 16, y + 14 + i * 22, self.font_med, col)


    def run(self):
        if not self._show_intro():
            return

        running = True
        while running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                elif ev.type == pygame.MOUSEMOTION:
                    self.mouse_pos = ev.pos
                elif ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        running = False
                    elif self.popup is not None:
                        self.popup = None
                    elif ev.key == pygame.K_SPACE:
                        self.run_search()
                    elif ev.key == pygame.K_c:
                        self.compare_all()
                    elif ev.key == pygame.K_r:
                        self.reset_map()
                    elif ev.key == pygame.K_1:
                        self.algorithm = "BFS";    audio.play("blip_lo")
                    elif ev.key == pygame.K_2:
                        self.algorithm = "UCS";    audio.play("blip_lo")
                    elif ev.key == pygame.K_3:
                        self.algorithm = "Greedy"; audio.play("blip_lo")
                    elif ev.key == pygame.K_4:
                        self.algorithm = "A*";     audio.play("blip_lo")
                    elif ev.key == pygame.K_l:
                        self.show_labels = not self.show_labels; audio.play("blip_lo")
                    elif ev.key in (pygame.K_PLUS, pygame.K_EQUALS):
                        self.weights["radiation"] = min(100.0, self.weights["radiation"] + 5)
                    elif ev.key == pygame.K_MINUS:
                        self.weights["radiation"] = max(0.0,   self.weights["radiation"] - 5)
                elif ev.type == pygame.MOUSEBUTTONDOWN:
                    if self.popup is not None:
                        self.popup = None
                    elif ev.button == 1:
                        self.handle_left_click(ev.pos)
                    elif ev.button == 3:
                        self.handle_right_click(ev.pos)

            self.update()
            self.draw()
            self.clock.tick(60)

        audio.shutdown()
        pygame.quit()


def main():
    EvacuationApp().run()


if __name__ == "__main__":
    main()
