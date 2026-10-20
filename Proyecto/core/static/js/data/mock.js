window.AGRO_MOCK = {
  disclaimer: 'Esta recomendación es orientativa y no reemplaza la evaluación de un ingeniero agrónomo certificado.',
  version: 'demo-1.0',
  users: [
    { email: 'agricultor@agroasesor.cl', name: 'Juan Pérez', role: 'Agricultor' },
    { email: 'admin@agroasesor.cl', name: 'Ana González', role: 'Administrador' }
  ],
  predios: [
    { id: 'p1', name: 'Santa Rita', location: 'Melipilla, Región Metropolitana', zone: 'Metropolitana', area: 12.5 },
    { id: 'p2', name: 'La Esperanza', location: 'Melipilla, Región Metropolitana', zone: 'Metropolitana', area: 8.2 },
    { id: 'p3', name: 'Los Aromos', location: 'Melipilla, Región Metropolitana', zone: 'Metropolitana', area: 6 }
  ],
  plots: [
    {
      id: 't1', predio: 'p1', name: 'Potrero Norte', crop: 'Maíz', variety: 'Híbrido demo',
      status: 'En crecimiento', sowing: '2026-09-01', harvest: '2027-03-01', areaHa: 4.8,
      coordinates: [[-71.216, -33.692], [-71.209, -33.692], [-71.209, -33.6878], [-71.216, -33.6878]]
    },
    {
      id: 't2', predio: 'p1', name: 'Potrero La Esperanza', crop: 'Tomate', variety: 'Industrial demo',
      status: 'Planificado', sowing: '2026-10-01', harvest: '2027-02-01', areaHa: 1.245,
      coordinates: [[-71.216, -33.6876], [-71.2124, -33.6876], [-71.2124, -33.6854], [-71.216, -33.6854]]
    },
    {
      id: 't3', predio: 'p2', name: 'Sector B', crop: 'Trigo', variety: 'Demo invierno',
      status: 'En crecimiento', sowing: '2026-06-01', harvest: '2026-12-01', areaHa: 3.2,
      coordinates: [[-71.2086, -33.692], [-71.2036, -33.692], [-71.2036, -33.6876], [-71.2086, -33.6876]]
    },
    {
      id: 't4', predio: 'p2', name: 'Potrero Sur', crop: 'Alfalfa', variety: 'Demo',
      status: 'En crecimiento', sowing: '2026-08-15', harvest: '2027-01-15', areaHa: 2.6,
      coordinates: [[-71.2086, -33.6874], [-71.2036, -33.6874], [-71.2036, -33.6846], [-71.2086, -33.6846]]
    },
    {
      id: 't5', predio: 'p3', name: 'Lote Maicero', crop: 'Maíz', variety: 'Híbrido demo',
      status: 'Planificado', sowing: '2026-10-10', harvest: '2027-04-01', areaHa: 5.1,
      coordinates: [[-71.216, -33.685], [-71.208, -33.685], [-71.208, -33.6814], [-71.216, -33.6814]]
    }
  ],
  cultivos: ['Maíz', 'Trigo', 'Papa', 'Alfalfa', 'Tomate', 'Cebolla'],
  zonas: ['Metropolitana', 'O’Higgins', 'Maule', 'Valparaíso'],
  problemas: [
    { id: 'pr1', name: 'Gusano cogollero', active: true },
    { id: 'pr2', name: 'Nutrición', active: true },
    { id: 'pr3', name: 'Malezas de hoja ancha', active: true }
  ],
  insumos: [
    {
      id: 'i1', name: 'Insumo demostrativo A', active: true, crop: 'Maíz', problem: 'Gusano cogollero',
      type: 'Insecticida', ingredient: 'No definido: ficha ficticia', dose: 2, unit: 'L',
      application: 'Ejemplo de interfaz; no aplicar en terreno.',
      safety: 'Consultar etiqueta autorizada y un profesional.',
      source: 'SAG (referencia institucional; ficha no validada)', updated: '2026-09-07'
    },
    {
      id: 'i2', name: 'Fertilizante demostrativo B', active: true, crop: 'Trigo', problem: 'Nutrición',
      type: 'Fertilizante', ingredient: 'Composición ficticia', dose: 250, unit: 'kg',
      application: 'Ejemplo de cálculo, sin prescripción agronómica.',
      safety: 'Requiere análisis de suelo y asesoría profesional.',
      source: 'SAG (referencia institucional; ficha no validada)', updated: '2026-09-07'
    },
    {
      id: 'i3', name: 'Insumo archivado', active: false, crop: 'Maíz', problem: 'Gusano cogollero',
      type: 'Insecticida', ingredient: 'Ficha no vigente', dose: 1, unit: 'L',
      application: 'No disponible.', safety: 'No usar.', source: 'SAG (demo)', updated: '2025-01-01'
    },
    {
      id: 'i4', name: 'Semilla demostrativa C', active: true, crop: 'Maíz', problem: 'Nutrición',
      type: 'Semilla', ingredient: 'Híbrido ficticio', dose: 25, unit: 'kg',
      application: 'Densidad de siembra de ejemplo.', safety: 'Usar semilla certificada cuando corresponda.',
      source: 'SAG (referencia institucional; ficha no validada)', updated: '2026-08-20'
    }
  ],
  semillas: [
    { id: 's1', name: 'Maíz híbrido demo', crop: 'Maíz', density: 25, unit: 'kg' },
    { id: 's2', name: 'Trigo demo', crop: 'Trigo', density: 160, unit: 'kg' },
    { id: 's3', name: 'Papa semilla demo', crop: 'Papa', density: 2500, unit: 'kg' }
  ],
  calendario: [
    { name: 'Maíz', sow: 9, cycle: 6, notes: 'Zona Central: siembra de primavera. Datos demostrativos.' },
    { name: 'Trigo', sow: 5, cycle: 7, notes: 'Siembra de otoño-invierno. Datos demostrativos.' },
    { name: 'Papa', sow: 8, cycle: 5, notes: 'Ajustar según heladas locales. Datos demostrativos.' },
    { name: 'Alfalfa', sow: 8, cycle: 5, notes: 'Puede cortarse varias veces. Datos demostrativos.' },
    { name: 'Tomate', sow: 9, cycle: 5, notes: 'Trasplante en recinto protegido si hay frío. Datos demostrativos.' },
    { name: 'Cebolla', sow: 7, cycle: 6, notes: 'Almácigo y transplante. Datos demostrativos.' }
  ],
  yields: { Maíz: 9.2, Trigo: 5.5, Papa: 30, Alfalfa: 12, Tomate: 70, Cebolla: 40 },
  adminStats: { agricultores: 18, cultivos: 6, insumos: 4, consultas: 47 }
};
