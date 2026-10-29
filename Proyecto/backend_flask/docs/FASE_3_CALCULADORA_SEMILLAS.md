# Fase 3 · Calculadora de semillas, menú nuevo y sesión robusta

## Qué se ve
* Menú lateral verde con el orden del diseño: Inicio, Mis predios, Mapa, Catálogo agrícola, **Calculadoras ▸ (Semillas, Fertilizantes, ¿Me alcanza?)**, Actividades, Toma de decisiones, Reportes, Calendario, Buscar (y Administración solo para admins).
* Página `/calculadoras/semillas/`: 1) terreno (predio, potrero, mapa del perímetro, superficie en ha y m²), 2) cultivo y referencia técnica (INIA) con dosis ajustable, 3) resultados (kg, sacos, cobertura, sobrante, costo opcional, guardar en historial) y panel «Información técnica».

## Reglas de datos
* La cuenta la hace el servidor (`/calculos/ejecutar/`, mismo cálculo que el resto de la app). La pantalla solo muestra.
* Rangos de dosis: del catálogo único `backend_flask/data/catalogo_agricola.yaml`, cada uno con su estado: `cotejada_con_fuente` (arroz) o `citada_sin_cotejar` (trigo: la fuente INIA está citada pero aún no se cotejó con el documento).
* El tamaño del saco y el precio los escribe la persona. No hay marcas, presentaciones ni precios de mercado.
* Sin referencia verificada, el resultado se marca como **simulación** (también en el historial).
* «Época de siembra», «Profundidad», «Manejo», «Suelo» y «Rendimiento» solo se muestran si existe una ficha **verificada con fuente** para el cultivo y la zona del potrero; si no, dice «Sin dato verificado». No se muestra tipo de suelo porque AgroAsesor aún no lo registra.

## Sesión y cookies
* Si se borran las cookies con la página abierta: los formularios vuelven al login (o a la página anterior) con un aviso; las llamadas de la propia página responden JSON y la pantalla lleva al login con el aviso, sin errores ni botones muertos.
* Íconos, mapa, PDF y fuentes se usan desde `core/static/vendor/` si existe (`descargar-librerias.ps1`); si no, se cargan del CDN como antes. Si tampoco hay internet, los íconos muestran un símbolo de respaldo en vez de un cuadro vacío y el perímetro del potrero se dibuja con un SVG propio.

## Pendiente (siguientes fases)
Riego, Conversión de unidades, Fitosanitarios, Inventario, tarjeta de clima (no hay fuente de datos real todavía), Toma de decisiones y Comparador de cultivos con el diseño nuevo.
