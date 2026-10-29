# Catálogo agrícola AgroAsesor · Fuentes oficiales y criterios de verificación

**Fecha de consulta:** 28 de octubre de 2026. **Alcance:** Chile.

## Datos que sí están respaldados

- SAG publica registros de plaguicidas autorizados, restringidos, prohibidos y cancelados; planilla general actualizada el 26/10/2026. También publica etiquetas y hojas de datos de seguridad.
- SAG regula comercialización, etiquetado y certificación de semillas. La categoría de semilla certificada corresponde a **lotes/variedades y procedimientos**, no a que AgroAsesor certifique una bolsa.
- SAG estableció nuevas exigencias de etiquetado de fertilizantes y bioestimulantes a partir del 28/08/2026, incluyendo identificación, composición, calidad, seguridad, lote y vencimiento.
- INIA publica referencias técnicas de siembra. Se incluyen **solo tres contextos**: trigo de invierno/alternativo (160–200 kg/ha), trigo de primavera (200–220 kg/ha) y arroz en siembra directa (130–145 kg/ha). **No son dosis universales**.
- ODEPA publica estadísticas mensuales de precios de insumos y fertilizantes. **No equivalen a cotizaciones vigentes de tiendas**.
- Etiquetas SAG documentan nombres como FUNGISEI, ABAMECTIN 84 SC, BIRD SHIELD y CAPTIVA PRIME. El número de registro que aparece en una etiqueta se guarda como **registro indicado en etiqueta**, no como certificación de vigencia.

Los enlaces específicos, organismos y fechas están en `data/catalogo_agricola.yaml`, y se muestran por API.

## Datos que NO están verificados y NO deben presentarse como reales

- Precios CLP, stock, tiendas, distribuidores, envases comerciales de 25 kg/50 kg, formatos de bidones o disponibilidad.
- Vigencia actual de autorización individual de un fitosanitario sin cotejo con el registro SAG vigente.
- Aplicación de un fitosanitario a un cultivo/plaga específica, dosis, mezclas, compatibilidad, carencia, reingreso o toxicidad sin cotejar **etiqueta actual y registro vigente**.
- Composición de fertilizantes de una marca específica, calidad de un lote, sello orgánico o certificación de semilla por una categoría genérica.
- Afirmaciones de certificación, sello, aval, alianza o patrocinio de SAG/INIA/ODEPA hacia AgroAsesor.

## Cómo completar el catálogo real (pendiente)

1. Obtener archivo oficial actualizado de SAG y documentar fecha, URL, checksum SHA-256 y formato de licencia/uso de datos.
2. Cotejar **cada producto** con el registro vigente, restricciones, estado, número de autorización y etiqueta/HDS correspondiente.
3. Para semillas, validar especie, variedad LVOD/RVAC, categoría, lote, certificación y presentación del proveedor.
4. Para fertilizantes, registrar nombre comercial, fabricante, composición declarada, lote, fecha de vencimiento y etiqueta conforme a normativa.
5. Para precios y formatos comerciales, incorporar fuente de distribuidor con fecha, región, moneda, IVA y disponibilidad; no atribuir estos datos a SAG.
6. Establecer revisión periódica y retirar la marca de "verificado vigente" si vence el plazo de revisión o cambia el registro.
7. Añadir control editorial: revisión humana, bitácora de cambios y pruebas antes de publicar.

## Política de procedencia (propuesta)

- `fuente_institucional`: documento publicado en dominio oficial.
- `registro_indicado_en_etiqueta`: número transcrito de una etiqueta, no estado vigente.
- `requiere_cotejo_vigente`: estado por defecto para fitosanitarios del borrador.
- `presentaciones_comerciales_verificadas`: vacío hasta contar con documentación comercial comprobable.
- `precio_clp`: `null` hasta contar con oferta actual verificable.
- `formato_simulado`: dato ilustrativo editable por usuario, nunca mostrar como producto comercial.

## Seguridad de implementación

La API carga YAML con `yaml.safe_load`, valida URLs institucionales y no ejecuta importaciones remotas ni toca SQLite. No incluye automatización de recomendaciones químicas. El cálculo de sacos solo opera sobre semillas con referencias INIA y parámetros proporcionados por el usuario.

## Huella digital local del catálogo

`data/catalogo_agricola.sha256` conserva el hash SHA-256 de la versión distribuida. Ejecutar:

```powershell
.\.venv\Scripts\python.exe scripts\verificar_integridad_catalogo.py
```

Esto **detecta cambios locales** respecto del paquete entregado. **No** es firma digital gubernamental, no comprueba la vigencia de registros SAG y no sustituye la revisión humana de las fuentes. Tras un cambio editorial autorizado, se debe generar una nueva versión y huella del catálogo.
