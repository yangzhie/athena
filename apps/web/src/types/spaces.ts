/** A subject, stable across years, e.g. CSE5DMI Data Mining. */
export interface Unit {
  code: string
  title: string
}

export type Semester = 'Semester 1' | 'Semester 2' | 'Summer'

/**
 * One run of a unit (year + semester). The lecturer's "study space".
 * A student enrolled in it gets their own private environment inside it.
 */
export interface Offering {
  id: string
  unit: Unit
  year: number
  semester: Semester
  /** Starter prompts shown in an empty chat. */
  suggestions: string[]
}
