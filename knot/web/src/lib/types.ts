/** Shapes returned by the API (mirror of api/app/schemas.py). */

export interface Theme {
  mode?: 'night' | 'candle'
  preset?: string
  base_hue?: number
  accent_hue?: number
}

export interface Person {
  id: string
  display_name: string | null
  theme: Theme
}

export interface Me {
  id: string
  email: string
  display_name: string | null
  theme: Theme
  spicy_on: boolean
  role: 'owner' | 'partner'
  pair_complete: boolean
  partner: Person | null
}

export interface VerifyResult {
  status: 'signed_in' | 'new_owner' | 'needs_pairing'
  ticket: string | null
  me: Me | null
}

export type Depth = 'light' | 'medium' | 'deep'
export type HatCategory = 'cozy' | 'silly' | 'sweet' | 'big' | 'memories' | 'future'
export type Category = HatCategory | 'spicy'

export interface SharedSettings {
  depth: Depth
  categories: HatCategory[]
  random: boolean
  excluded: HatCategory[]
}

export interface HomeOut {
  settings: SharedSettings
  settings_updated_by: string | null
  spicy_me: boolean
  spicy_them: boolean
  in_play: Category[]
  turn_user_id: string | null
  partner_online: boolean
}

export type QuestionType = 'guess' | 'both' | 'wyr' | 'self'

export interface QuestionOut {
  id: string
  type: QuestionType
  depth: Depth
  category: Category
  text: string
  options: string[] | null
}

export interface RoundOut {
  id: string
  question: QuestionOut
  drawn_by: string
  subject_id: string | null
  state: 'open' | 'ready'
  i_answer: boolean
  i_sealed: boolean
  partner_answers: boolean
  partner_sealed: boolean
  pulled_by: string[]
  expires_at: string
  key_version: number
}

export interface AnswerOut {
  user_id: string
  ciphertext: string
  nonce: string
  key_version: number
}

export interface PullOut {
  revealed: boolean
  answers: AnswerOut[]
  question: QuestionOut | null
  turn_user_id: string | null
}

export interface InviteOut {
  code: string
  expires_at: string
}

export interface InviteStatus {
  pair_complete: boolean
  pending_invite_expires_at: string | null
}
