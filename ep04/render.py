"""Renderizador do EP. 3 (Skia → ffmpeg). 1080x1920, 30 fps.

uso:
  python3 render.py video  --cta ig|yt  --out out/arquivo.mp4
  python3 render.py stills --cta ig     # PNGs de conferência em build/stills
  python3 render.py cover               # capa vertical em out/
"""
import argparse, json, math, os, subprocess, sys
from multiprocessing import Pool
import numpy as np
import skia

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(HERE, "build")
OUT = os.path.join(HERE, "out")
W, H, FPS = 1080, 1920, 30
MX = 70                      # margem lateral
CW = W - 2 * MX              # largura útil

# ---------------------------------------------------------------- identidade
WHITE = "#F4F7F5"; GREEN = "#3DDC84"; YELLOW = "#FFB020"; RED = "#FF4D4D"; GRAY = "#96ACA0"
BG_TOP = "#0E2E22"; BG_BOT = "#050E0B"; INK = "#050E0B"

FONT_DIR = "/usr/share/fonts/opentype/inter"
_TF = {}


def tf(w):
    if w not in _TF:
        name = {"black": "Inter-Black", "semibold": "Inter-SemiBold", "bold": "Inter-Bold",
                "extrabold": "Inter-ExtraBold"}[w]
        _TF[w] = skia.Typeface.MakeFromFile(f"{FONT_DIR}/{name}.otf")
    return _TF[w]


_EMOJI = None


def emoji_tf():
    global _EMOJI
    if _EMOJI is None:
        _EMOJI = skia.Typeface.MakeFromFile("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf")
    return _EMOJI


def C(hexs, a=1.0):
    h = hexs.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return skia.ColorSetARGB(int(round(255 * max(0, min(1, a)))), r, g, b)


def font(w, size):
    f = skia.Font(tf(w), size)
    f.setEdging(skia.Font.Edging.kAntiAlias)
    f.setSubpixel(True)
    return f


def text_w(s, w, size, tracking=0):
    f = font(w, size)
    return f.measureText(s) + tracking * max(len(s) - 1, 0)


def fit(s, w, size, maxw, tracking=0):
    tw = text_w(s, w, size, tracking)
    return size if tw <= maxw else size * maxw / tw


def cap_h(w, size):
    return font(w, size).getMetrics().fCapHeight


def text(cv, s, x, y, size, w="semibold", color=WHITE, a=1.0, align="left", tracking=0):
    """y = linha de base. Retorna a largura desenhada."""
    f = font(w, size)
    p = skia.Paint(AntiAlias=True, Color=C(color, a))
    tw = f.measureText(s) + tracking * max(len(s) - 1, 0)
    if align == "center":
        x -= tw / 2
    elif align == "right":
        x -= tw
    if tracking == 0:
        cv.drawString(s, x, y, f, p)
    else:
        cx = x
        for ch in s:
            cv.drawString(ch, cx, y, f, p)
            cx += f.measureText(ch) + tracking
    return tw


def text_mid(cv, s, x, cy, size, **kw):
    """Desenha centralizado verticalmente na altura de versal em cy."""
    w = kw.get("w", "semibold")
    return text(cv, s, x, cy + cap_h(w, size) / 2, size, **kw)


def rrect(cv, x, y, w, h, r, fill=None, a=1.0, stroke=None, sa=1.0, sw=3):
    rr = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), r, r)
    if fill:
        cv.drawRRect(rr, skia.Paint(AntiAlias=True, Color=C(fill, a)))
    if stroke:
        cv.drawRRect(rr, skia.Paint(AntiAlias=True, Color=C(stroke, sa), Style=skia.Paint.kStroke_Style,
                                    StrokeWidth=sw))


def card(cv, x, y, w, h, r=28, tone=None):
    """Cartão padrão: branco 7%. tone='red' → cartão vermelho."""
    if tone == "red":
        rrect(cv, x, y, w, h, r, fill=RED, a=0.16, stroke=RED, sa=0.75, sw=3)
    elif tone == "green":
        rrect(cv, x, y, w, h, r, fill=GREEN, a=1.0)
    else:
        rrect(cv, x, y, w, h, r, fill="#FFFFFF", a=0.07)


# ---------------------------------------------------------------- animação
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def back(x, s=1.9):
    x = clamp(x)
    x -= 1
    return 1 + x * x * ((s + 1) * x + s)


class Group:
    """Contexto de entrada: fade + leve subida (opcional: pop de escala)."""

    def __init__(self, cv, t, t0, d=0.45, rise=46, pop=0.0, cx=W / 2, cy=H / 2, alpha=1.0):
        self.cv, self.p = cv, clamp((t - t0) / d)
        self.rise, self.pop, self.cx, self.cy, self.alpha = rise, pop, cx, cy, alpha
        self.visible = t >= t0

    def __enter__(self):
        cv, p = self.cv, self.p
        cv.save()
        a = ease(p) * self.alpha
        if a < 0.999:
            cv.saveLayerAlpha(None, int(255 * a))
        cv.translate(0, (1 - ease(p)) * self.rise)
        if self.pop:
            s = 1 + self.pop * (1 - back(p))
            cv.translate(self.cx, self.cy)
            cv.scale(s, s)
            cv.translate(-self.cx, -self.cy)
        return self

    def __exit__(self, *a):
        self.cv.restore()
        if ease(self.p) * self.alpha < 0.999:
            self.cv.restore()


def count(t, t0, v0, v1, d=0.8):
    return v0 + (v1 - v0) * ease((t - t0) / d)


# ---------------------------------------------------------------- times (só nome e cor)
TEAM = {
    "Internacional": ("#D6001C", "#FFFFFF"), "Inter": ("#D6001C", "#FFFFFF"),
    "Grêmio": ("#0D80BF", "#111111"), "Vasco": ("#111111", "#FFFFFF"),
    "Bahia": ("#0055A4", "#E30613"), "Corinthians": ("#111111", "#FFFFFF"),
    "Botafogo": ("#111111", "#FFFFFF"), "Vitória": ("#E30613", "#111111"),
    "Bragantino": ("#FFFFFF", "#E30613"), "Coritiba": ("#00704A", "#FFFFFF"),
    "Mirassol": ("#FFD100", "#00843D"), "Remo": ("#1B2A6B", "#FFFFFF"),
    "Chapecoense": ("#00843D", "#FFFFFF"), "Santos": ("#FFFFFF", "#111111"),
}


def chip(cv, x, cy, team, h=52, w=14):
    c1, c2 = TEAM[team]
    y = cy - h / 2
    cv.save()
    rr = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), 5, 5)
    cv.clipRRect(rr, skia.ClipOp.kIntersect, True)
    cv.drawRect(skia.Rect.MakeXYWH(x, y, w, h / 2), skia.Paint(Color=C(c1)))
    cv.drawRect(skia.Rect.MakeXYWH(x, y + h / 2, w, h / 2), skia.Paint(Color=C(c2)))
    cv.restore()
    cv.drawRRect(rr, skia.Paint(AntiAlias=True, Color=C("#FFFFFF", 0.28), Style=skia.Paint.kStroke_Style,
                                StrokeWidth=1.5))


# ---------------------------------------------------------------- fundo
def background(cv, t, T):
    sh = skia.GradientShader.MakeLinear([skia.Point(0, 0), skia.Point(0, H)], [C(BG_TOP), C(BG_BOT)])
    cv.drawPaint(skia.Paint(Shader=sh))
    # linhas de campo bem sutis, com zoom lento
    s = 1.0 + 0.05 * (t / max(T, 1))
    cv.save()
    cv.translate(W / 2, H / 2); cv.scale(s, s); cv.translate(-W / 2, -H / 2)
    p = skia.Paint(AntiAlias=True, Color=C("#FFFFFF", 0.045), Style=skia.Paint.kStroke_Style, StrokeWidth=4)
    m = 60
    cv.drawRect(skia.Rect.MakeLTRB(m, m, W - m, H - m), p)
    cv.drawLine(m, H / 2, W - m, H / 2, p)
    cv.drawCircle(W / 2, H / 2, 175, p)
    cv.drawCircle(W / 2, H / 2, 7, skia.Paint(AntiAlias=True, Color=C("#FFFFFF", 0.06)))
    for top in (True, False):
        bw, bh, gw, gh = 640, 290, 300, 110
        y0 = m if top else H - m
        sgn = 1 if top else -1
        cv.drawRect(skia.Rect.MakeLTRB(W / 2 - bw / 2, min(y0, y0 + sgn * bh), W / 2 + bw / 2, max(y0, y0 + sgn * bh)), p)
        cv.drawRect(skia.Rect.MakeLTRB(W / 2 - gw / 2, min(y0, y0 + sgn * gh), W / 2 + gw / 2, max(y0, y0 + sgn * gh)), p)
        # meia-lua
        cy = y0 + sgn * 200
        oval = skia.Rect.MakeXYWH(W / 2 - 160, cy - 160, 320, 320)
        cv.drawArc(oval, 37 if top else 217, 106, False, p)
    cv.restore()
    # vinheta
    vg = skia.GradientShader.MakeRadial(skia.Point(W / 2, H * 0.45), H * 0.75,
                                        [C("#000000", 0.0), C("#000000", 0.45)], [0.55, 1.0])
    cv.drawPaint(skia.Paint(Shader=vg))


def brand(cv, a=1.0):
    y = 215
    w1 = text(cv, "SIMULA AÍ!", MX, y, 34, "black", GREEN, a)
    text(cv, "  ·  QUEM CAI? EP. 4", MX + w1, y, 34, "semibold", GRAY, a)


def label(cv, s, y, color=YELLOW, size=38, a=1.0, x=W / 2, align="center"):
    return text(cv, s, x, y, size, "bold", color, a, align, tracking=size * 0.12)


# ---------------------------------------------------------------- legendas
def sub_chunks(line, maxc=27):
    words = line["text"].split()
    chunks, cur = [], ""
    for w_ in words:
        cand = (cur + " " + w_).strip()
        if len(cand) > maxc and cur:
            chunks.append(cur); cur = w_
        else:
            cur = cand
    if cur:
        chunks.append(cur)
    # evita sobrar palavra solitária no fim
    if len(chunks) > 1 and len(chunks[-1]) < 12 and len(chunks[-2]) + len(chunks[-1]) < maxc + 10:
        tail_ = chunks.pop()
        chunks[-1] += " " + tail_
    total = sum(len(c) + 3 for c in chunks)
    st, out = line["start"], []
    dur = line["end"] - line["start"]
    for c in chunks:
        d = dur * (len(c) + 3) / total
        out.append((st, st + d, c)); st += d
    return out


def subtitles(cv, t, tl):
    for sc in tl["scenes"]:
        for ln in sc["lines"]:
            if ln["start"] - 0.05 <= t <= ln["end"] + 0.12:
                ch = sub_chunks(ln)
                for k, (a, b, c) in enumerate(ch):
                    if a - 0.05 <= t < b + (0.12 if k == len(ch) - 1 else 0):
                        draw_sub(cv, c, t - a)
                        return


def draw_sub(cv, s, dt):
    size = 56
    f = font("bold", size)
    tw = f.measureText(s)
    if tw > CW - 40:
        size = size * (CW - 40) / tw; tw = CW - 40
    padx, h = 30, size * 1.55
    cy = 1565
    a = clamp(dt / 0.08)
    rrect(cv, W / 2 - tw / 2 - padx, cy - h / 2, tw + 2 * padx, h, 18, fill="#000000", a=0.58 * a)
    text_mid(cv, s, W / 2, cy, size, w="bold", color=WHITE, a=a, align="center")


# ---------------------------------------------------------------- cenas
def L(sc, i, k="start"):
    return sc["lines"][i][k] - sc["start"]


def scene1(cv, t, sc, ctx):
    with Group(cv, t, 0.05, 0.4):
        label(cv, "QUEM CAI? · EP. 4", 640, size=46)
    s1 = fit("INTER E", "black", 210, CW)
    s2 = fit("GRÊMIO", "black", 210, CW)
    with Group(cv, t, 0.2, 0.45, rise=60):
        text(cv, "INTER E", W / 2, 860, min(s1, s2), "black", WHITE, align="center")
    with Group(cv, t, 0.38, 0.45, rise=60):
        text(cv, "GRÊMIO", W / 2, 1070, min(s1, s2), "black", WHITE, align="center")
    s3 = fit("NO Z4", "black", 290, CW)
    t3 = 0.95
    with Group(cv, t, t3, 0.5, rise=30, pop=0.35, cy=1220):
        text(cv, "NO Z4", W / 2, 1340, s3, "black", RED, align="center")
        # sublinhado vermelho crescendo
        p = ease((t - t3 - 0.25) / 0.5)
        uw = 520 * p
        rrect(cv, W / 2 - uw / 2, 1385, uw, 14, 7, fill=RED, a=0.9)


def scene2(cv, t, sc, ctx):
    label(cv, "BRASILEIRÃO 2026 · 35ª RODADA", 330, a=ease(t / 0.4))
    games = [
        ("Vasco", 2, "Internacional", 1, ("INTER PERDEU", RED), 0),
        ("Grêmio", 0, "Bahia", 0, ("GRÊMIO EMPATOU", YELLOW), 1),
        ("Corinthians", 4, "Botafogo", 0, ("RIVAL VENCEU", YELLOW), 2),
        ("Vitória", 2, "Bragantino", 1, ("RIVAL VENCEU", YELLOW), 3),
    ]
    starts = [0.15, L(sc, 1) - 0.1, L(sc, 2), L(sc, 3) - 0.1]
    ch = 214
    for k, (h, hs, a_, as_, tag, li) in enumerate(games):
        y = 400 + k * (ch + 30)
        with Group(cv, t, starts[k], 0.45):
            card(cv, MX, y, CW, ch)
            for row, (team, sc_, other) in enumerate(((h, hs, as_), (a_, as_, hs))):
                cy = y + 68 + row * 78
                win = sc_ > other
                lose = sc_ < other
                col = WHITE if not lose else GRAY
                chip(cv, MX + 34, cy, team, h=44, w=12)
                text_mid(cv, team, MX + 66, cy, 50, w="bold" if win else "semibold", color=col)
                text_mid(cv, str(sc_), W - MX - 44, cy, 70, w="black", color=col, align="right")
            # selo
            tg, tc = tag
            fs = 28
            tw = text_w(tg, "bold", fs, 2)
            pw, ph = tw + 36, 52
            px, py = W - MX - 130 - pw, y + ch / 2 - ph / 2
            rrect(cv, px, py, pw, ph, ph / 2, fill=tc, a=0.16, stroke=tc, sa=0.8, sw=2)
            text_mid(cv, tg, px + pw / 2, py + ph / 2, fs, w="bold", color=tc, align="center", tracking=2)


def scene3(cv, t, sc, ctx):
    label(cv, "CLASSIFICAÇÃO · APÓS 35 RODADAS", 320, a=ease(t / 0.4))
    rows = [(13, "Coritiba", 42), (14, "Vitória", 41), (15, "Mirassol", 41), (16, "Corinthians", 40),
            (17, "Internacional", 38), (18, "Grêmio", 38), (19, "Remo", 32), (20, "Chapecoense", 21)]
    rh, gap = 96, 12
    t_top = 0.35
    t_band = L(sc, 2) + 0.2
    t_z4 = L(sc, 3) - 0.35
    for i, (pos, team, pts) in enumerate(rows):
        z4 = pos >= 17
        y = 360 + i * (rh + gap) + (78 if z4 else 0)
        t0 = (t_z4 + (i - 4) * 0.12) if z4 else (t_top + i * 0.12)
        with Group(cv, t, t0, 0.42, rise=36):
            card(cv, MX, y, CW, rh, r=24, tone="red" if z4 else None)
            if team in ("Internacional", "Grêmio") and t > t_z4 + 0.6:
                pulse = 0.5 + 0.5 * math.sin((t - t_z4) * 6)
                rrect(cv, MX - 3, y - 3, CW + 6, rh + 6, 26, stroke=RED, sa=0.35 + 0.4 * pulse, sw=4)
            cy = y + rh / 2
            text_mid(cv, f"{pos}º", MX + 36, cy, 40, w="bold", color=RED if z4 else GRAY)
            chip(cv, MX + 140, cy, team, h=46, w=12)
            text_mid(cv, team, MX + 172, cy, 46, w="bold" if z4 else "semibold", color=WHITE)
            pw = text_w(" pts", "semibold", 28)
            text_mid(cv, " pts", W - MX - 36, cy + 4, 28, w="semibold", color=GRAY, align="right")
            text_mid(cv, str(pts), W - MX - 36 - pw, cy, 56, w="black", color=WHITE, align="right")
    # faixa Z4
    yb = 360 + 4 * (rh + gap) + 6
    with Group(cv, t, t_band, 0.4, rise=0):
        p = ease((t - t_band) / 0.6)
        lab = "ZONA DE REBAIXAMENTO"
        lw = text_w(lab, "black", 32, 5)
        text_mid(cv, lab, W / 2, yb + 30, 32, w="black", color=RED, align="center", tracking=5)
        side = (CW - lw - 60) / 2 * p
        rrect(cv, W / 2 - lw / 2 - 30 - side, yb + 28, side, 4, 2, fill=RED, a=0.8)
        rrect(cv, W / 2 + lw / 2 + 30, yb + 28, side, 4, 2, fill=RED, a=0.8)


def scene4(cv, t, sc, ctx):
    with Group(cv, t, 0.05, 0.4):
        label(cv, "200 MIL SIMULAÇÕES", 320)
    with Group(cv, t, 0.15, 0.45):
        text(cv, "CHANCE DE CAIR", W / 2, 430, fit("CHANCE DE CAIR", "black", 112, CW), "black", WHITE, align="center")
    bars = [("Grêmio", 71, RED, L(sc, 1) + 0.3), ("Internacional", 60, RED, L(sc, 2) + 0.15),
            ("Mirassol", 22, YELLOW, L(sc, 3) + 0.05), ("Vitória", 18, YELLOW, L(sc, 3) + 0.7),
            ("Corinthians", 16, YELLOW, L(sc, 4) + 0.05), ("Coritiba", 10, YELLOW, L(sc, 4) + 0.75),
            ("Botafogo", 3, GREEN, L(sc, 4) + 1.35)]
    y0, rh, maxw = 500, 112, 760
    for i, (team, v, col, tb) in enumerate(bars):
        y = y0 + i * rh
        with Group(cv, t, 0.35 + i * 0.07, 0.4, rise=30):
            chip(cv, MX, y + 22, team, h=32, w=10)
            text(cv, team, MX + 24, y + 36, 38, "semibold", WHITE)
            rrect(cv, MX, y + 52, CW, 44, 22, fill="#FFFFFF", a=0.07)
            p = ease((t - tb) / 0.9)
            bw = max(44 * min(1, p * 4), maxw * v / 100 * p) if t >= tb else 0
            if bw > 0:
                rrect(cv, MX, y + 52, bw, 44, 22, fill=col, a=0.95)
                val = int(round(v * p))
                text_mid(cv, f"{val}%", MX + bw + 18, y + 74, 48, w="black", color=col)
    tf_ = L(sc, 4) + 1.6
    with Group(cv, t, tf_, 0.45, rise=20):
        text(cv, "Remo e Chapecoense: rebaixados nas simulações", W / 2, 1345,
             fit("Remo e Chapecoense: rebaixados nas simulações", "semibold", 34, CW), "semibold", GRAY,
             align="center")


def scene5(cv, t, sc, ctx):
    with Group(cv, t, 0.05, 0.4):
        label(cv, "O DADO QUE ASSUSTA", 420)
    blocks = [("40%", "os dois caem juntos", 0.15, 40), ("9 em 10", "pelo menos um cai", L(sc, 1) - 0.05, None)]
    for k, (num, cap, t0, cnt) in enumerate(blocks):
        y = 480 + k * 430
        with Group(cv, t, t0, 0.5, rise=40, pop=0.12, cy=y + 190):
            card(cv, MX, y, CW, 390, r=36, tone="red")
            s = num if cnt is None else f"{int(round(count(t, t0 + 0.1, 0, cnt, 1.0)))}%"
            size = fit("9 em 10", "black", 230, CW - 120)
            text(cv, s, W / 2, y + 245, size, "black", RED, align="center")
            text(cv, cap, W / 2, y + 325, 52, "semibold", WHITE, align="center")


def scene6(cv, t, sc, ctx):
    with Group(cv, t, 0.05, 0.4):
        label(cv, "A CONTA DA SALVAÇÃO", 370)
    t44 = 0.2
    with Group(cv, t, t44, 0.5, rise=40, pop=0.1, cy=650):
        v = int(round(count(t, t44 + 0.2, 38, 44, 1.2)))
        text(cv, str(v), W / 2, 740, 330, "black", GREEN, align="center")
        text(cv, "PONTOS", W / 2, 870, 120, "black", GREEN, align="center", tracking=6)
    with Group(cv, t, L(sc, 0, "end") - 0.35, 0.45):
        text(cv, "= praticamente salvo", W / 2, 965, 56, "semibold", WHITE, align="center")
    tc = L(sc, 1) - 0.1
    y = 1030
    with Group(cv, t, tc, 0.45):
        card(cv, MX, y, CW, 330, r=32)
        x = MX + 44
        w1 = text(cv, "Grêmio e Inter têm ", x, y + 78, 44, "semibold", WHITE)
        w2 = text(cv, "38", x + w1, y + 78, 44, "black", RED)
        text(cv, " → precisam de", x + w1 + w2, y + 78, 44, "semibold", WHITE)
        text(cv, "2 vitórias e 1 empate nos 3 jogos", x, y + 140, 44, "semibold", WHITE)
    pills = [("VITÓRIA", "+3", GREEN), ("VITÓRIA", "+3", GREEN), ("EMPATE", "+1", YELLOW)]
    pw, gap = 262, 22
    px0 = W / 2 - (3 * pw + 2 * gap) / 2
    for k, (lab, pts, col) in enumerate(pills):
        tp = L(sc, 2) + 0.05 + k * 0.28
        with Group(cv, t, tp, 0.4, rise=24, pop=0.2, cx=px0 + k * (pw + gap) + pw / 2, cy=y + 245):
            px = px0 + k * (pw + gap)
            rrect(cv, px, y + 200, pw, 92, 46, fill=col, a=0.16, stroke=col, sa=0.85, sw=3)
            text_mid(cv, lab, px + 28, y + 246, 30, w="bold", color=col, tracking=2)
            text_mid(cv, pts, px + pw - 28, y + 246, 40, w="black", color=col, align="right")


def scene7(cv, t, sc, ctx):
    y = 290
    with Group(cv, t, 0.1, 0.45):
        card(cv, MX, y, CW, 230, r=32)
        label(cv, "PRÓXIMA RODADA", y + 70, size=34)
        s = "INTERNACIONAL x VITÓRIA"
        size = fit(s, "black", 80, CW - 80)
        text(cv, s, W / 2, y + 170, size, "black", WHITE, align="center")
    with Group(cv, t, L(sc, 1) - 0.2, 0.4, rise=20):
        text(cv, "CHANCE DE O INTER CAIR", W / 2, 600, 32, "bold", GRAY, align="center", tracking=4)
    rows = [("Inter vence", 38, YELLOW, L(sc, 1) + 0.1), ("Empate", 79, RED, L(sc, 2) + 0.05),
            ("Vitória vence", 90, RED, L(sc, 3) + 0.05)]
    for k, (lab, v, col, t0) in enumerate(rows):
        ry = 630 + k * 152
        with Group(cv, t, t0, 0.42, rise=30):
            card(cv, MX, ry, CW, 132, r=28)
            p = ease((t - t0 - 0.1) / 0.9)
            # barrinha de fundo proporcional
            rrect(cv, MX + 30, ry + 108, (CW - 60) * v / 100 * p, 8, 4, fill=col, a=0.9)
            text_mid(cv, lab, MX + 40, ry + 58, 48, w="semibold", color=WHITE)
            text_mid(cv, f"{int(round(v * p))}%", W - MX - 40, ry + 58, 76, w="black", color=col, align="right")
    t4 = L(sc, 4) - 0.1
    sy = 1100
    with Group(cv, t, t4, 0.45):
        x0, w0 = MX + 90, CW - 180
        card(cv, x0, sy, w0, 230, r=28)
        chip(cv, x0 + 36, sy + 70, "Santos", h=38, w=10); chip(cv, x0 + 50, sy + 70, "Grêmio", h=38, w=10)
        text_mid(cv, "Santos x Grêmio", x0 + 80, sy + 70, 46, w="black", color=WHITE)
        text_mid(cv, "se o Grêmio vencer →", x0 + 36, sy + 160, 40, w="semibold", color=GRAY)
        p = ease((t - t4 - 0.6) / 0.8)
        text_mid(cv, f"{int(round(39 * p))}%", x0 + w0 - 36, sy + 160, 76, w="black", color=YELLOW, align="right")


def scene8(cv, t, sc, ctx):
    with Group(cv, t, 0.1, 0.45, rise=50):
        text(cv, "QUEM SE SALVA?", W / 2, 560, fit("QUEM SE SALVA?", "black", 150, CW), "black", WHITE, align="center")
    with Group(cv, t, 0.35, 0.45):
        s = "GRÊMIO, INTER OU NENHUM?"
        text(cv, s, W / 2, 680, fit(s, "black", 80, CW), "black", YELLOW, align="center")
    tcm = L(sc, 1) - 0.1
    with Group(cv, t, tcm, 0.45):
        card(cv, MX + 110, 770, CW - 220, 160, r=32)
        s = "Comenta aí "
        f = font("bold", 66)
        ef = skia.Font(emoji_tf(), 66)
        sw = f.measureText(s); ew = ef.measureText("👇")
        x = W / 2 - (sw + ew) / 2
        text(cv, s, x, 850 + cap_h("bold", 66) / 2, 66, "bold", WHITE)
        bob = 6 * math.sin((t - tcm) * 5) if t > tcm else 0
        cv.drawString("👇", x + sw, 850 + 24 + bob, ef, skia.Paint(AntiAlias=True))
    tg = L(sc, 1) + 0.75
    with Group(cv, t, tg, 0.5, rise=40, pop=0.15, cy=1080):
        pulse = 1 + 0.025 * math.sin(max(0, t - tg - 0.6) * 4.5)
        cv.save(); cv.translate(W / 2, 1080); cv.scale(pulse, pulse); cv.translate(-W / 2, -1080)
        card(cv, MX, 990, CW, 180, r=36, tone="green")
        s = "Siga @simulaaibr" if ctx["cta"] == "ig" else "Inscreva-se no Simula Aí!"
        text_mid(cv, s, W / 2, 1080, fit(s, "black", 72, CW - 100), w="black", color=INK, align="center")
        cv.restore()
    with Group(cv, t, L(sc, 2) + 0.2, 0.45, rise=16):
        text(cv, "Modelo estatístico · não considera lesões novas", W / 2, 1300, 30, "semibold", GRAY, align="center")
        text(cv, "nem troca de técnico.", W / 2, 1344, 30, "semibold", GRAY, align="center")


SCENE_FN = {1: scene1, 2: scene2, 3: scene3, 4: scene4, 5: scene5, 6: scene6, 7: scene7, 8: scene8}
FADE_OUT = 0.28


# ---------------------------------------------------------------- frame
def draw_frame(cv, t, tl, ctx):
    T = tl["duration"]
    background(cv, t, T)
    sc = next((s for s in tl["scenes"] if s["start"] <= t < s["end"]), tl["scenes"][-1])
    ts = t - sc["start"]
    last = sc["id"] == len(tl["scenes"])
    a = 1.0 if last else clamp((sc["end"] - t) / FADE_OUT)
    if sc["id"] >= 2:
        brand(cv, a=1.0)
    cv.save()
    if a < 0.999:
        cv.saveLayerAlpha(None, int(255 * a))
    SCENE_FN[sc["id"]](cv, ts, sc, ctx)
    if a < 0.999:
        cv.restore()
    cv.restore()
    subtitles(cv, t, tl)


_G = {}


def _init(cta):
    _G["tl"] = json.load(open(os.path.join(B, "timeline.json")))
    _G["ctx"] = {"cta": cta}
    _G["surf"] = skia.Surface(W, H)


def _frame(i):
    surf = _G["surf"]
    cv = surf.getCanvas()
    cv.clear(skia.ColorBLACK)
    draw_frame(cv, i / FPS, _G["tl"], _G["ctx"])
    img = surf.makeImageSnapshot()
    return img.toarray(colorType=skia.kRGBA_8888_ColorType)[:, :, :3].tobytes()


def render_video(cta, out, audio):
    tl = json.load(open(os.path.join(B, "timeline.json")))
    n = int(math.ceil(tl["duration"] * FPS))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", audio, "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-profile:v", "high",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", out]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(os.cpu_count(), initializer=_init, initargs=(cta,)) as pool:
        for k, buf in enumerate(pool.imap(_frame, range(n), chunksize=8)):
            ff.stdin.write(buf)
            if k % 300 == 0:
                print(f"  frame {k}/{n}", flush=True)
    ff.stdin.close(); ff.wait()
    print("ok", out)


def save_png(cv_fn, path):
    surf = skia.Surface(W, H)
    cv = surf.getCanvas()
    cv_fn(cv)
    surf.makeImageSnapshot().save(path, skia.kPNG)


def stills(cta):
    tl = json.load(open(os.path.join(B, "timeline.json")))
    ctx = {"cta": cta}
    d = os.path.join(B, "stills"); os.makedirs(d, exist_ok=True)
    for sc in tl["scenes"]:
        t = sc["end"] - (0.05 if sc["id"] == len(tl["scenes"]) else FADE_OUT + 0.05)
        save_png(lambda cv: draw_frame(cv, t, tl, ctx), os.path.join(d, f"s{sc['id']}_{cta}.png"))
    print("stills ok")


def cover(path):
    def draw(cv):
        background(cv, 0, 1)
        label(cv, "SIMULA AÍ! · QUEM CAI? EP. 4", 470, size=40)
        s = fit("GRÊMIO", "black", 230, CW)
        text(cv, "INTER E", W / 2, 700, s, "black", WHITE, align="center")
        text(cv, "GRÊMIO", W / 2, 950, s, "black", WHITE, align="center")
        s3 = fit("NO Z4", "black", 300, CW)
        text(cv, "NO Z4", W / 2, 1230, s3, "black", RED, align="center")
        rrect(cv, W / 2 - 260, 1275, 520, 14, 7, fill=RED, a=0.9)
        # destaque dos números
        card(cv, MX, 1350, CW, 200, r=36, tone="red")
        text(cv, "71% e 60%", W / 2, 1450, 104, "black", RED, align="center")
        text(cv, "de chance de cair", W / 2, 1518, 50, "semibold", WHITE, align="center")
        text(cv, "@simulaaibr", W / 2, 1665, 40, "bold", GRAY, align="center")
    save_png(draw, path)
    print("cover ok", path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["video", "stills", "cover", "frame"])
    ap.add_argument("--cta", default="ig", choices=["ig", "yt"])
    ap.add_argument("--out")
    ap.add_argument("--audio", default=os.path.join(B, "mix.wav"))
    ap.add_argument("--t", type=float, default=0)
    a = ap.parse_args()
    if a.mode == "video":
        render_video(a.cta, a.out, a.audio)
    elif a.mode == "stills":
        stills(a.cta)
    elif a.mode == "frame":
        tl = json.load(open(os.path.join(B, "timeline.json")))
        save_png(lambda cv: draw_frame(cv, a.t, tl, {"cta": a.cta}), os.path.join(B, f"frame_{a.t:.2f}.png"))
    else:
        cover(a.out or os.path.join(OUT, "capa_ep04.png"))
