export const REGIONS = [
  { id: 'BHR', name: 'Bihar', fullName: 'Bihar (NR)', color: '#00d4ff', x: 62, y: 35 },
  { id: 'UP', name: 'NR UP', fullName: 'Uttar Pradesh (NR)', color: '#0066ff', x: 42, y: 28 },
  { id: 'WB', name: 'West Bengal', fullName: 'West Bengal (ER)', color: '#8b5cf6', x: 72, y: 48 },
  { id: 'KAR', name: 'Karnataka', fullName: 'Karnataka (SR)', color: '#10b981', x: 42, y: 72 },
]

export const REGION_BY_ID = Object.fromEntries(REGIONS.map(region => [region.id, region]))
