"""API pública de catálogo y cálculo orientativo de sacos de semilla."""

from flask import Blueprint, jsonify, request
from app.services.catalogo import (
    CatalogoError,
    cargar_catalogo,
    fuentes,
    categorias,
    productos,
    producto_por_id,
    referencias_siembra,
    calcular_sacos,
)

bp = Blueprint("catalogo", __name__)


def _entero(name, default):
    raw = request.args.get(name, str(default))
    if not raw.isdigit():
        raise CatalogoError(f"{name} debe ser entero positivo")
    return int(raw)


@bp.get("/catalogo/categorias")
def listar_categorias():
    return jsonify({"resultados": categorias()})


@bp.get("/catalogo/fuentes")
def listar_fuentes():
    return jsonify({"fecha_consulta": cargar_catalogo()["fecha_consulta"], "resultados": fuentes()})


@bp.get("/catalogo/productos")
def listar_productos():
    try:
        return jsonify(
            productos(
                q=request.args.get("q", ""),
                categoria=request.args.get("categoria", ""),
                pagina=_entero("pagina", 1),
                limite=_entero("limite", 20),
            )
        )
    except CatalogoError as exc:
        return jsonify({"error": {"codigo": "VALIDACION_CATALOGO", "mensaje": str(exc)}}), 400


@bp.get("/catalogo/productos/<string:product_id>")
def detalle_producto(product_id):
    product = producto_por_id(product_id)
    if product is None:
        return jsonify({"error": {"codigo": "NO_ENCONTRADO", "mensaje": "Producto no encontrado"}}), 404
    return jsonify(product)


@bp.get("/catalogo/referencias-siembra")
def listar_referencias():
    return jsonify({"resultados": referencias_siembra()})


@bp.post("/catalogo/calcular-sacos")
def calcular_sacos_endpoint():
    if not request.is_json:
        return jsonify({"error": {"codigo": "TIPO_CONTENIDO", "mensaje": "Se requiere application/json"}}), 415
    try:
        return jsonify(calcular_sacos(request.get_json(silent=True)))
    except CatalogoError as exc:
        return jsonify({"error": {"codigo": "VALIDACION_CATALOGO", "mensaje": str(exc)}}), 400
