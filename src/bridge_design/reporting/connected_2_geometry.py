"""Geometry presentation shared by console and Word for the ver_2l command."""


def connected_2_geometry_rows(data):
    g = data.left.geometry
    values = (
        ("Luz libre superior", data.upper_clear_span_m),
        ("Luz libre inferior calculada", data.clear_span_m),
        ("Ancho total de cimentacion calculado", data.total_length_m),
        ("Espesor uniforme de cimentacion", data.slab_thickness_m),
        ("Altura de pantalla hasta asiento", g.stem_height_above_footing_m - g.seat_block_height_m),
        ("Altura de parapeto sobre asiento", g.seat_block_height_m),
        ("Espesor del parapeto", g.seat_wall_width_m),
        ("Longitud horizontal del asiento", g.bearing_seat_length_m),
        ("Espesor superior de pantalla calculado", g.upper_stem_thickness_m),
        ("Espesor inferior de pantalla", g.lower_stem_thickness_m),
        ("Longitud de talon exterior", g.heel_length_m),
        ("Altura total de relleno desde fondo de base", g.retained_height_m),
        ("Relleno interior sobre la zapata combinada", 0.0),
        ("Altura adicional de frenado sobre coronacion", g.bridge_seat_to_bearing_height_m),
    )
    return [(label, f"{value:.3f}") for label, value in values]
