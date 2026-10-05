"""Calculated longitudinal cutoff intervals, with no cuts drawn when infeasible."""

from textwrap import wrap
from PIL import Image, ImageDraw

from bridge_design.reporting.connected_chart_geometry import BLUE, RED, GRAY, GREEN, font


def foundation_cut_chart(result, path):
    canvas = Image.new("RGB", (2000, 1380), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((80, 35), "Cortes calculados del acero de zapata combinada", font=font(42), fill=BLUE)
    draw.text((80, 105), "Vista longitudinal por cara | Coordenadas x desde el extremo izquierdo | Sin escala vertical",
              font=font(25), fill=GRAY)
    steels = [s for s in result.reinforcement if s.foundation_reinforcement_cut is not None]
    length = result.inputs.total_length_m
    x = lambda coordinate: 160 + 1660*coordinate/length
    for index, steel in enumerate(steels):
        cut = steel.foundation_reinforcement_cut
        y = 240 + 490*index
        draw.text((80, y-90), f"{cut.arrangement} - {steel.bar_label} @ {steel.spacing_m:.3f} m - {cut.status}",
                  font=font(32), fill=BLUE)
        draw.rectangle((x(0), y, x(length), y+140), outline=GRAY, width=2)
        for face in (cut.inner_face_left_m, cut.inner_face_right_m):
            draw.line((x(face), y-10, x(face), y+155), fill=GRAY, width=2)
            draw.text((x(face)-45, y-40), f"{face:.2f}", font=font(22), fill=GRAY)
        cover = result.inputs.left.reinforcement.footing_cover_cm/100
        draw.line((x(cover), y+105, x(length-cover), y+105), fill=GREEN, width=6)
        if cut.status == "APLICA":
            for a, b in cut.additional_intervals_m:
                draw.line((x(a), y+40, x(b), y+40), fill=RED, width=7)
            for position in (cut.cutoff_left_m, cut.cutoff_right_m):
                draw.line((x(position), y+25, x(position), y+60), fill=RED, width=3)
                draw.text((x(position)-50, y+160), f"x={position:.2f}", font=font(23), fill=RED)
            p = cut.pattern
            note = (f"Rojo: se corta 1 de cada {p.cycle_bars}. Verde: barras continuas, {p.continuing_bars} de cada {p.cycle_bars}. "
                    f"Distancia desde cada cara interior: {abs(cut.distance_from_inner_face_m):.2f} m "
                    + ("hacia el centro." if cut.distance_from_inner_face_m >= 0 else "hacia el talon.") +
                    f" Prolongacion adoptada {cut.adopted_extension_m:.2f} m.")
            if p.cycle_bars == 2:
                note = (f"Verde: continuo {steel.bar_label} @ {p.equivalent_spacing_m:.3f} m. "
                        f"Rojo: adicional intercalado {steel.bar_label} @ {2*steel.spacing_m:.3f} m. "
                        f"Distancia desde cada cara interior: {abs(cut.distance_from_inner_face_m):.2f} m "
                        + ("hacia el centro." if cut.distance_from_inner_face_m >= 0 else "hacia el talon.") +
                        f" Prolongacion {cut.adopted_extension_m:.2f} m. Verificaciones locales en zonas_zapata.csv.")
        else:
            note = "Acero continuo, sin cortes. " + cut.reason
        for line, text in enumerate(wrap(note, 122)):
            draw.text((90, y+235+line*34), text, fill=GRAY, font=font(25))
    draw.text((80, 1260), "Longitudes horizontales calculadas; los doblados y anclajes exteriores se verifican por separado.",
              font=font(25), fill=GRAY)
    draw.text((80, 1305), "MTC 2018 Art. 2.6.5.6.1.2.1. El PDF aceros.pdf define la disposicion; sus cotas no se fijan como datos.",
              font=font(24), fill=GRAY)
    canvas.save(path)
