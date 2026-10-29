# Contratos de ejemplo para discutir con el equipo

Los siguientes cuerpos son **propuestas** y NO están implementados.

## Confirmar perímetro de potrero

`POST /api/v1/potreros/12/confirmar-perimetro`

```json
{
  "geometria": {
    "type": "Polygon",
    "coordinates": [[[-71.5, -33.7], [-71.49, -33.7], [-71.49, -33.71], [-71.5, -33.7]]]
  },
  "confirmado": true
}
```

Las coordenadas son **ficticias**, solo ilustran la estructura GeoJSON. El backend
deberá validar anillos cerrados, topología, proyección/método de área, propietario
y permisos antes de guardar.

## Resultado de cálculo de semillas (propuesto)

`POST /api/v1/calculos/semillas`

```json
{
  "potrero_id": 12,
  "cultivo_id": 5,
  "superficie_ha": 1.25
}
```

La fórmula real y parámetros requeridos se definirán a partir de la calculadora
Django actual y referencias agrícolas validadas. **No generar cifras inventadas.**
