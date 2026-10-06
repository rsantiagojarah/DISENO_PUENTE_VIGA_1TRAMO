"""Gráficas de los datos de compresión efectivamente usados en el cálculo."""
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def original_serquen_curve(curve):
    """La figura original se muestra solo para la digitalización correspondiente."""
    if curve is None:
        return None
    from bridge_design.domain.serquen_bearings import serquen_compression_curve
    reference = serquen_compression_curve(curve.hardness)
    if curve.kind != 'referencia' or set(curve.points) != set(reference.points):
        return None
    return Path(__file__).parent / 'assets' / f'serquen_compresion_shore_{curve.hardness}.png'


def compression_chart(result):
    curve = result.inputs.compression_curve
    if curve is None:
        return None
    canvas = Image.new('RGB', (1800, 1240), 'white')
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype('arial.ttf', 36)
        small = ImageFont.truetype('arial.ttf', 32)
        title = ImageFont.truetype('arial.ttf', 44)
    except OSError:
        font = ImageFont.load_default(size=36)
        small = ImageFont.load_default(size=32)
        title = ImageFont.load_default(size=44)
    draw.text((150, 35), f'Compresión del elastómero Shore A {curve.hardness}', font=title, fill='black')
    left, top, right, bottom = 150, 145, 1220, 1040
    xmax = max(e * 100 for _, _, e in curve.points) * 1.05
    ymax = max(stress for _, stress, _ in curve.points) * 1.05
    def xy(e, stress):
        return left + e * 100 / xmax * (right-left), bottom-stress / ymax*(bottom-top)
    for tick in range(7):
        x = left+(right-left)*tick/6
        y = bottom-(bottom-top)*tick/6
        draw.line((x,top,x,bottom), fill='#dddddd', width=2)
        draw.line((left,y,right,y), fill='#dddddd', width=2)
        draw.text((x-22,bottom+15), f'{xmax*tick/6:.1f}', font=small, fill='black')
        draw.text((left-85,y-15), f'{ymax*tick/6:.1f}', font=small, fill='black')
    draw.rectangle((left,top,right,bottom), outline='black', width=3)
    draw.text((335,bottom+72), 'Deformación por compresión ε (%)', font=font, fill='black')
    draw.text((150,95), 'Esfuerzo de compresión σ (kgf/cm²)', font=font, fill='black')
    palette = ('#666666','#956a32','#2d6b82','#7e648e','#758544','#414141')
    legend_y = 150
    for index, shape in enumerate(sorted({s for s, _, _ in curve.points})):
        column = sorted((stress, e) for s, stress, e in curve.points if s == shape)
        color = palette[index % len(palette)]
        draw.line([xy(e,stress) for stress,e in column], fill=color, width=4)
        draw.line((1280,legend_y+15,1340,legend_y+15), fill=color, width=4)
        draw.text((1355,legend_y),f'S = {shape:g}',font=font,fill='black')
        legend_y += 47
    for layer, key, color in [('Interior','SI','#b52c2c'),('Exterior','SE','#006b67')]:
        shape = result.value(key)
        # Unir con todos los quiebres de las dos curvas que acotan S:
        # se reproduce la misma interpolación lineal que CompressionCurve.lookup.
        shapes = sorted({s for s,_,_ in curve.points})
        if shapes[0] <= shape <= shapes[-1]:
            lo = max(s for s in shapes if s <= shape)
            hi = min(s for s in shapes if s >= shape)
            cap = min(max(stress for s,stress,_ in curve.points if s == b) for b in (lo,hi))
            stresses = sorted({0.,cap} | {stress for s,stress,_ in curve.points if s in (lo,hi) and stress <= cap})
            draw.line([xy(curve.lookup(shape,stress)[0],stress) for stress in stresses], fill=color,width=7)
            draw.line((1280,legend_y+15,1340,legend_y+15),fill=color,width=7)
            draw.text((1355,legend_y),f'{layer} S={shape:.4g}',font=small,fill=color)
            legend_y += 47
    a = result.inputs.actions
    for num,(layer,load) in enumerate((('I','D'),('I','T'),('E','D'),('E','T')),1):
        strain = result.value('EPS_'+layer+load)
        if strain is None:
            continue
        stress = 1000*((a.dc_tn+a.dw_tn) if load == 'D' else result.value('P')-a.im_tn)/result.value('AREA')
        x,y = xy(strain,stress)
        draw.ellipse((x-10,y-10,x+10,y+10),fill='black',outline='white',width=2)
        draw.text((x+13,y-35),str(num),font=font,fill='black')
    for offset,label in enumerate(('1 Interior permanente','2 Interior total sin impacto','3 Exterior permanente','4 Exterior total sin impacto')):
        draw.text((1270,legend_y+35+offset*48),label,font=small,fill='black')
    draw.text((150,1170),'Líneas según los datos utilizados; puntos 1 a 4 según la tabla de lecturas.',font=small,fill='black')
    stream = BytesIO()
    canvas.save(stream,format='PNG')
    stream.seek(0)
    return stream
