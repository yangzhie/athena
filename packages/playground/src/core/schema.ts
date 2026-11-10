/**
 * A small JSON Schema subset for object configs. The same schemas go to the
 * model (as part of the component catalog) and validate what it writes.
 */
export type Schema =
  | { type: 'string'; enum?: string[]; description?: string }
  | { type: 'number'; minimum?: number; maximum?: number; description?: string }
  | { type: 'integer'; minimum?: number; maximum?: number; description?: string }
  | { type: 'boolean'; description?: string }
  | { type: 'array'; items: Schema; minItems?: number; maxItems?: number; description?: string }
  | { type: 'object'; properties: Record<string, Schema>; required?: string[]; description?: string }

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)

/** Validate a value; returns one message per problem, with the path to it. */
export function validate(schema: Schema, value: unknown, path = 'config'): string[] {
  switch (schema.type) {
    case 'string':
      if (typeof value !== 'string') return [`${path} must be a string`]
      if (schema.enum && !schema.enum.includes(value)) return [`${path} must be one of ${schema.enum.join(', ')}`]
      return []
    case 'number':
    case 'integer': {
      if (typeof value !== 'number' || !Number.isFinite(value)) return [`${path} must be a number`]
      if (schema.type === 'integer' && !Number.isInteger(value)) return [`${path} must be an integer`]
      if (schema.minimum !== undefined && value < schema.minimum) return [`${path} must be ≥ ${schema.minimum}`]
      if (schema.maximum !== undefined && value > schema.maximum) return [`${path} must be ≤ ${schema.maximum}`]
      return []
    }
    case 'boolean':
      return typeof value === 'boolean' ? [] : [`${path} must be true or false`]
    case 'array': {
      if (!Array.isArray(value)) return [`${path} must be an array`]
      if (schema.minItems !== undefined && value.length < schema.minItems) return [`${path} needs at least ${schema.minItems} items`]
      if (schema.maxItems !== undefined && value.length > schema.maxItems) return [`${path} allows at most ${schema.maxItems} items`]
      return value.flatMap((v, i) => validate(schema.items, v, `${path}[${i}]`))
    }
    case 'object': {
      if (!isObject(value)) return [`${path} must be an object`]
      const missing = (schema.required ?? []).filter((k) => !(k in value)).map((k) => `${path}.${k} is required`)
      const unknown = Object.keys(value)
        .filter((k) => !(k in schema.properties))
        .map((k) => `${path}.${k} is not a known field`)
      const nested = Object.entries(schema.properties).flatMap(([k, s]) => (k in value ? validate(s, value[k], `${path}.${k}`) : []))
      return [...missing, ...unknown, ...nested]
    }
  }
}

/** Shorthands for writing schemas. */
export const s = {
  string: (description?: string, enumValues?: string[]): Schema => ({ type: 'string', description, ...(enumValues ? { enum: enumValues } : {}) }),
  number: (description?: string, minimum?: number, maximum?: number): Schema => ({ type: 'number', description, minimum, maximum }),
  integer: (description?: string, minimum?: number, maximum?: number): Schema => ({ type: 'integer', description, minimum, maximum }),
  boolean: (description?: string): Schema => ({ type: 'boolean', description }),
  array: (items: Schema, description?: string, minItems?: number, maxItems?: number): Schema => ({ type: 'array', items, description, minItems, maxItems }),
  object: (properties: Record<string, Schema>, required: string[] = Object.keys(properties), description?: string): Schema => ({
    type: 'object',
    properties,
    required,
    description,
  }),
  empty: (): Schema => ({ type: 'object', properties: {}, required: [] }),
}
