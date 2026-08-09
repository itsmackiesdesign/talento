/** Response shapes mirroring `app/schemas.py`. Kept hand-written and small rather than
 *  generated, so the panel compiles without a codegen step in the loop. */

export type Language = "ru" | "uz" | "en";

export const SUPPORTED_LANGUAGES: Language[] = ["ru", "uz", "en"];

/** Language names are always shown in their own language, never translated. */
export const LANGUAGE_LABELS: Record<string, string> = {
  ru: "Русский",
  uz: "O‘zbekcha",
  en: "English",
};

/** {lang: {field: value}} — mirrors app/core/i18n.py. */
export type Translations = Record<string, Record<string, string | string[]>>;
export type VacancyStatus = "draft" | "active" | "archived";
export type QuestionType =
  | "short_text"
  | "long_text"
  | "single_choice"
  | "multi_choice"
  | "number"
  | "phone"
  | "file"
  | "datetime";

export type DatetimeMask = "date" | "datetime" | "time";

export const QUESTION_TYPES: QuestionType[] = [
  "short_text",
  "long_text",
  "single_choice",
  "multi_choice",
  "number",
  "phone",
  "file",
  "datetime",
];

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  telegram_user_id: number | null;
  created_at: string;
}

export interface Company {
  id: string;
  name: string;
  slug: string;
  logo_url: string | null;
  default_language: Language;
  enabled_languages: Language[];
  branches_enabled: boolean;
  plan: string;
  created_at: string;
}

export interface Me {
  user: User;
  companies: Company[];
  role: "owner" | "member" | null;
}

export interface TeamMember {
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  telegram_linked: boolean;
}

export interface Bot {
  id: string;
  bot_username: string;
  welcome_message: string | null;
  about_text: string | null;
  after_apply_message: string | null;
  contacts_text: string | null;
  translations: Translations;
  language: Language;
  notify_candidate_on_status: boolean;
  is_active: boolean;
  created_at: string;
  token_hint: string;
  webhook_url: string;
}

export interface WebhookStatus {
  ok: boolean;
  error?: string;
  url?: string;
  matches_expected?: boolean;
  pending_update_count?: number;
  last_error_message?: string | null;
}

export interface Branch {
  id: string;
  name: string;
  city: string | null;
  address: string | null;
  photo_url: string | null;
  latitude: number | null;
  longitude: number | null;
  translations: Translations;
  is_active: boolean;
  sort_order: number;
  created_at: string;
  active_vacancy_count: number;
}

/** A company's own kanban pipeline stage. 'new'/'hired'/'rejected' are system steps
 *  (is_system) seeded once per company and locked against edit/delete/reorder — see
 *  ApplicationStatus in app/models.py. */
export interface ApplicationStatusOut {
  id: string;
  label: string;
  translations: Translations;
  notify_candidate: boolean;
  is_system: boolean;
  sort_order: number;
  application_count: number;
}

export interface Vacancy {
  id: string;
  branch_id: string | null;
  branch_name: string | null;
  title: string;
  description: string;
  city: string | null;
  employment_type: string | null;
  salary_from: number | null;
  salary_to: number | null;
  currency: string;
  status: VacancyStatus;
  is_hot: boolean;
  photo_url: string | null;
  sort_order: number;
  translations: Translations;
  created_at: string;
  application_count: number;
  deep_link: string | null;
}

export interface Question {
  id: string;
  vacancy_id: string | null;
  text: string;
  type: QuestionType;
  options: string[] | null;
  is_required: boolean;
  validation: { min?: number; max?: number; mask?: DatetimeMask } | null;
  translations: Translations;
  sort_order: number;
}

export interface NewsItem {
  id: string;
  title: string;
  content: string;
  photo_url: string | null;
  link_url: string | null;
  is_published: boolean;
  sort_order: number;
  translations: Translations;
  created_at: string;
}

export interface Answer {
  question_id: string;
  question_text: string;
  type: QuestionType;
  answer: string | string[] | null;
  skipped: boolean;
}

export interface ApplicationListItem {
  id: string;
  status_id: string;
  created_at: string;
  vacancy_id: string;
  vacancy_title: string;
  branch_id: string | null;
  branch_name: string | null;
  candidate_name: string;
  candidate_username: string | null;
  candidate_phone: string | null;
}

export interface Comment {
  id: string;
  text: string;
  author_name: string;
  created_at: string;
}

export interface StatusHistoryEntry {
  // Snapshotted at transition time, not a live lookup — stays readable even after the
  // status itself is later renamed or deleted. See ApplicationStatusHistory in models.py.
  from_status_label: string | null;
  to_status_label: string;
  changed_by_name: string | null;
  created_at: string;
}

export interface ApplicationDetail extends ApplicationListItem {
  answers: Answer[];
  comments: Comment[];
  history: StatusHistoryEntry[];
}

export interface ApplicationPage {
  items: ApplicationListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface DashboardStats {
  applications_7d: number;
  applications_30d: number;
  applications_total: number;
  active_vacancies: number;
  // Keyed by status_id — the panel resolves labels/order against a separately fetched
  // ApplicationStatusOut[] (see Dashboard.tsx).
  by_status: Record<string, number>;
  by_vacancy: { vacancy_id: string; title: string; count: number }[];
  by_branch: { branch_id: string | null; name: string; count: number }[];
  daily: { date: string; count: number }[];
}

export interface LinkCode {
  code: string;
  expires_in: number;
  bot_username: string;
  deep_link: string | null;
}

export interface FilterOptions {
  vacancies: { id: string; title: string }[];
  branches: { id: string; name: string }[];
}
