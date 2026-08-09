import {
  ArrowDown,
  ArrowRight,
  Bell,
  Bot,
  BriefcaseBusiness,
  Check,
  ChevronDown,
  CircleUserRound,
  Download,
  FileText,
  GripVertical,
  LayoutDashboard,
  MapPin,
  MessageSquareText,
  MoveRight,
  Send,
  ShieldCheck,
  Sparkles,
  UsersRound,
} from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import Lenis from "lenis";

import { LANGUAGES, setLanguage } from "@/lib/i18n";
import { cn } from "@/lib/utils";

import type { IntroTimeline, LandingTimeline, ShotSample } from "./landing-types";
import "./landing.css";

const LandingScene = lazy(() => import("./LandingScene"));

const SHOT_IDS = [
  "signal",
  "open-access",
  "discover",
  "apply",
  "transfer",
  "manage",
  "system",
  "resolution",
] as const;

type ShotId = (typeof SHOT_IDS)[number];
type Locale = "ru" | "uz" | "en";

const COPY = {
  ru: {
    nav: { story: "Путь кандидата", product: "Продукт", system: "Система", faq: "Вопросы", login: "Войти", start: "Запустить бота" },
    intro: { line1: "ТАЛАНТ", line2: "ISTE’DOD", line3: "TALENT", eyebrow: "КАНДИДАТ УЖЕ В TELEGRAM", thesis: "ОТКРОЙТЕ ДОСТУП", bridge: "И ПЕРЕВЕДИТЕ ТАЛАНТ В РАБОТУ", skip: "Пропустить" },
    hero: {
      eyebrow: "HR-ПЛАТФОРМА ДЛЯ TELEGRAM",
      title: "Найм начинается там, где уже живут кандидаты.",
      alternate: "Откройте доступ к таланту.",
      body: "Запустите собственный Telegram-бот вакансий. Кандидаты проходят весь путь в чате, а команда ведёт заявки в одной HR-панели.",
      primary: "Запустить своего бота",
      secondary: "Посмотреть путь кандидата",
      proofs: ["10 минут до запуска", "8 типов вопросов", "RU · UZ · EN"],
    },
    discover: {
      index: "01 · DISCOVER",
      title: "Вакансия находит кандидата в привычном интерфейсе.",
      body: "Язык, филиал, условия и отклик — внутри Telegram. Без отдельного карьерного сайта и новой учётной записи.",
      bot: "Acme Coffee · вакансии",
      online: "бот на связи",
      welcome: "Здравствуйте! На каком языке вам удобнее продолжить?",
      branch: "Выберите филиал",
      branchValue: "Чиланзар · Ташкент",
      role: "Бариста",
      salary: "4 000 000–6 000 000 сум",
      location: "ул. Бунёдкор, 12",
      apply: "Откликнуться",
    },
    apply: {
      index: "02 · APPLY",
      title: "Анкета ощущается как диалог, а не как длинная форма.",
      body: "talento задаёт вопросы по одному, проверяет формат ответа и сохраняет точный снимок анкеты.",
      progress: "Вопрос 3 из 5",
      question: "В какие смены готовы работать?",
      options: ["Утро", "День", "Вечер", "Выходные"],
      types: "Текст · выбор · число · телефон · файл · дата/время",
    },
    transfer: {
      index: "03 · TRANSFER",
      title: "Один отклик. Два мира. Ни одного ручного переноса.",
      body: "Подтверждённая анкета сразу становится карточкой кандидата в HR-панели — вместе с ответами, вакансией и филиалом.",
      sent: "Анкета отправлена",
      candidate: "Малика Юсупова",
      role: "Бариста · Чиланзар",
      status: "Новая заявка",
    },
    manage: {
      index: "04 · MANAGE",
      title: "Вся воронка найма — в одном рабочем пространстве.",
      body: "Dashboard, настраиваемые статусы, ответы, комментарии, история и Telegram-уведомления HR.",
      dashboard: "Панель найма",
      total: "Всего заявок",
      week: "За 7 дней",
      vacancies: "Активных вакансий",
      columns: ["Новая", "Интервью", "Оффер", "Принят"],
      candidates: ["Малика Ю.", "Азиз К.", "Дилшод Р.", "Севара М."],
      notification: "Новая заявка: Малика · Бариста",
    },
    system: {
      index: "05 · ONE SYSTEM",
      title: "Один продукт — для каждого филиала, языка и этапа.",
      body: "Контент переводится без дублей. Каждый тенант изолирован. Команда видит только свою компанию и свои данные.",
      modules: [
        ["Свой бот", "getMe, webhook и зашифрованный token"],
        ["Филиалы", "Адрес, фото и точка на карте"],
        ["Конструктор", "8 типов вопросов и drag-and-drop"],
        ["Mini-ATS", "Статусы, комментарии и история"],
        ["Уведомления", "Новая заявка приходит HR в Telegram"],
        ["Dashboard + CSV", "Динамика, филиалы и экспорт"],
        ["Tenant security", "Изоляция компаний и безопасный webhook"],
      ],
    },
    resolution: {
      index: "06 · OPEN ACCESS",
      title: "Откройте доступ к таланту.",
      body: "Создайте компанию, подключите бот от @BotFather и опубликуйте первую вакансию.",
      primary: "Начать настройку",
      secondary: "Войти в панель",
    },
    faq: {
      eyebrow: "Коротко о главном",
      title: "Вопросы до запуска",
      items: [
        ["Что видит кандидат?", "Только Telegram-бот: язык, меню, вакансии, анкету и статус своих заявок. HR-панель кандидатам недоступна."],
        ["Можно работать с несколькими филиалами?", "Да. Кандидат сначала выбирает филиал, а бот показывает связанные вакансии, адрес и точку на карте."],
        ["Какие ответы поддерживает анкета?", "Короткий и длинный текст, один или несколько вариантов, число, телефон, файл и дата/время."],
        ["Что происходит с данными?", "Заявки хранятся в PostgreSQL внутри tenant-контура компании. Персональные данные кандидата можно удалить из панели."],
      ],
    },
    footer: { line: "Найм через Telegram — от первого сообщения до выхода в команду.", product: "Продукт", access: "Доступ", rights: "Все права защищены." },
  },
  uz: {
    nav: { story: "Nomzod yo‘li", product: "Mahsulot", system: "Tizim", faq: "Savollar", login: "Kirish", start: "Botni ishga tushirish" },
    intro: { line1: "ISTE’DOD", line2: "TALANT", line3: "ТАЛАНТ", eyebrow: "NOMZOD TELEGRAMDA", thesis: "ISTE’DODGA YO‘L OCHING", bridge: "VA UNI JAMOAGA OLIB KELING", skip: "O‘tkazib yuborish" },
    hero: {
      eyebrow: "TELEGRAM UCHUN HR-PLATFORMA",
      title: "Yollash nomzodlar allaqachon yashaydigan joyda boshlanadi.",
      alternate: "Iste’dodga yo‘l oching.",
      body: "O‘zingizning Telegram vakansiyalar botingizni ishga tushiring. Nomzod chatda ariza topshiradi, jamoa esa hammasini bitta HR-panelda boshqaradi.",
      primary: "O‘z botingizni ishga tushirish",
      secondary: "Nomzod yo‘lini ko‘rish",
      proofs: ["Ishga tushirishgacha 10 daqiqa", "8 turdagi savol", "RU · UZ · EN"],
    },
    discover: { index: "01 · DISCOVER", title: "Vakansiya nomzodni tanish interfeysda topadi.", body: "Til, filial, shartlar va ariza — barchasi Telegram ichida.", bot: "Acme Coffee · vakansiyalar", online: "bot aloqada", welcome: "Assalomu alaykum! Qaysi tilda davom etamiz?", branch: "Filialni tanlang", branchValue: "Chilonzor · Toshkent", role: "Barista", salary: "4 000 000–6 000 000 so‘m", location: "Bunyodkor ko‘chasi, 12", apply: "Ariza qoldirish" },
    apply: { index: "02 · APPLY", title: "Anketa uzun forma emas, suhbatdek ishlaydi.", body: "talento savollarni bittadan beradi, formatni tekshiradi va anketaning aniq nusxasini saqlaydi.", progress: "5 tadan 3-savol", question: "Qaysi smenalarda ishlay olasiz?", options: ["Ertalab", "Kunduzi", "Kechqurun", "Dam olish kunlari"], types: "Matn · tanlov · raqam · telefon · fayl · sana/vaqt" },
    transfer: { index: "03 · TRANSFER", title: "Bitta ariza. Ikki muhit. Qo‘lda ko‘chirish yo‘q.", body: "Tasdiqlangan anketa darhol HR-paneldagi nomzod kartasiga aylanadi.", sent: "Anketa yuborildi", candidate: "Malika Yusupova", role: "Barista · Chilonzor", status: "Yangi ariza" },
    manage: { index: "04 · MANAGE", title: "Butun yollash voronkasi — bitta ish maydonida.", body: "Dashboard, moslashuvchan bosqichlar, javoblar, izohlar, tarix va HR Telegram bildirishnomalari.", dashboard: "Yollash paneli", total: "Jami arizalar", week: "7 kun ichida", vacancies: "Faol vakansiyalar", columns: ["Yangi", "Suhbat", "Taklif", "Qabul"], candidates: ["Malika Yu.", "Aziz K.", "Dilshod R.", "Sevara M."], notification: "Yangi ariza: Malika · Barista" },
    system: { index: "05 · ONE SYSTEM", title: "Har bir filial, til va bosqich uchun bitta mahsulot.", body: "Kontent nusxalarsiz tarjima qilinadi. Har bir tenant va uning ma’lumotlari izolyatsiya qilingan.", modules: [["O‘z botingiz", "Webhook va shifrlangan token"], ["Filiallar", "Manzil, foto va xarita nuqtasi"], ["Konstruktor", "8 savol turi va drag-and-drop"], ["Mini-ATS", "Bosqichlar, izohlar va tarix"], ["Bildirishnomalar", "Yangi ariza HR Telegramiga boradi"], ["Dashboard + CSV", "Dinamika va eksport"], ["Tenant security", "Kompaniyalar izolyatsiyasi"]] },
    resolution: { index: "06 · OPEN ACCESS", title: "Iste’dodga yo‘l oching.", body: "Kompaniya yarating, @BotFather botini ulang va birinchi vakansiyani chiqaring.", primary: "Sozlashni boshlash", secondary: "Panelga kirish" },
    faq: { eyebrow: "Qisqacha", title: "Ishga tushirishdan oldingi savollar", items: [["Nomzod nimani ko‘radi?", "Faqat Telegram-bot: til, menyu, vakansiyalar, anketa va ariza holati."], ["Bir nechta filial mumkinmi?", "Ha. Nomzod avval filialni tanlaydi, bot esa bog‘langan vakansiyalarni ko‘rsatadi."], ["Qanday javoblar bor?", "Matn, tanlov, raqam, telefon, fayl va sana/vaqt — jami sakkiz tur."], ["Ma’lumotlar qayerda?", "Arizalar kompaniyaning tenant-konturida PostgreSQL bazasida saqlanadi."]] },
    footer: { line: "Telegram orqali yollash — birinchi xabardan jamoaga qo‘shilishgacha.", product: "Mahsulot", access: "Kirish", rights: "Barcha huquqlar himoyalangan." },
  },
  en: {
    nav: { story: "Candidate journey", product: "Product", system: "System", faq: "FAQ", login: "Sign in", start: "Launch a bot" },
    intro: { line1: "TALENT", line2: "ТАЛАНТ", line3: "ISTE’DOD", eyebrow: "THE CANDIDATE IS ALREADY IN TELEGRAM", thesis: "OPEN ACCESS", bridge: "AND MOVE TALENT INTO WORK", skip: "Skip" },
    hero: { eyebrow: "AN HR PLATFORM FOR TELEGRAM", title: "Hiring starts where candidates already live.", alternate: "Open access to talent.", body: "Launch your own Telegram vacancy bot. Candidates complete the journey in chat while your team manages every application in one HR workspace.", primary: "Launch your bot", secondary: "See the candidate journey", proofs: ["10 minutes to launch", "8 question types", "RU · UZ · EN"] },
    discover: { index: "01 · DISCOVER", title: "The vacancy meets candidates in a familiar interface.", body: "Language, branch, conditions and application — entirely inside Telegram.", bot: "Acme Coffee · careers", online: "bot online", welcome: "Hi! Which language would you like to use?", branch: "Choose a branch", branchValue: "Chilanzar · Tashkent", role: "Barista", salary: "UZS 4,000,000–6,000,000", location: "12 Bunyodkor Street", apply: "Apply" },
    apply: { index: "02 · APPLY", title: "The application feels like a conversation, not a long form.", body: "talento asks one question at a time, validates the answer and preserves an exact application snapshot.", progress: "Question 3 of 5", question: "Which shifts can you work?", options: ["Morning", "Day", "Evening", "Weekends"], types: "Text · choice · number · phone · file · date/time" },
    transfer: { index: "03 · TRANSFER", title: "One application. Two worlds. Zero manual transfer.", body: "A confirmed form becomes a candidate card in the HR workspace with answers, role and branch intact.", sent: "Application sent", candidate: "Malika Yusupova", role: "Barista · Chilanzar", status: "New application" },
    manage: { index: "04 · MANAGE", title: "The entire hiring pipeline in one workspace.", body: "Dashboard, custom stages, answers, comments, history and Telegram notifications for HR.", dashboard: "Hiring workspace", total: "Total applications", week: "Last 7 days", vacancies: "Active vacancies", columns: ["New", "Interview", "Offer", "Hired"], candidates: ["Malika Y.", "Aziz K.", "Dilshod R.", "Sevara M."], notification: "New application: Malika · Barista" },
    system: { index: "05 · ONE SYSTEM", title: "One product for every branch, language and stage.", body: "Content translates without duplicate records. Every tenant and its data remain isolated.", modules: [["Your bot", "Webhook and encrypted token"], ["Branches", "Address, image and map pin"], ["Form builder", "8 question types and drag-and-drop"], ["Mini ATS", "Stages, comments and history"], ["Notifications", "New applications reach HR in Telegram"], ["Dashboard + CSV", "Trends, branches and export"], ["Tenant security", "Company and webhook isolation"]] },
    resolution: { index: "06 · OPEN ACCESS", title: "Open access to talent.", body: "Create a company, connect your @BotFather bot and publish the first vacancy.", primary: "Start setup", secondary: "Sign in" },
    faq: { eyebrow: "The essentials", title: "Questions before launch", items: [["What does a candidate see?", "Only the Telegram bot: language, menu, vacancies, form and their application status."], ["Can I run several branches?", "Yes. Candidates choose a branch first and the bot shows its roles, address and map pin."], ["Which answers are supported?", "Short and long text, single and multiple choice, number, phone, file and date/time."], ["Where is candidate data stored?", "Applications live in PostgreSQL inside the company tenant boundary and can be deleted from the panel."]] },
    footer: { line: "Hiring through Telegram — from the first message to the first day.", product: "Product", access: "Access", rights: "All rights reserved." },
  },
} as const;

function getLocale(language: string): Locale {
  const code = language.split("-")[0];
  return code === "uz" || code === "en" ? code : "ru";
}

function supportsWebGL() {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

function measureRanges(root: HTMLElement) {
  const sections = Array.from(root.querySelectorAll<HTMLElement>("[data-shot]"));
  const rootTop = root.offsetTop;
  return sections.map((section, index) => ({
    id: section.dataset.shot as ShotId,
    start: section.offsetTop - rootTop,
    end: (sections[index + 1]?.offsetTop ?? root.scrollHeight) - rootTop,
  }));
}

function useJourney(timeline: LandingTimeline, setActiveShot: (id: ShotId) => void) {
  const root = useRef<HTMLElement>(null);

  useEffect(() => {
    const node = root.current;
    if (!node) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let ranges = measureRanges(node);
    let currentId: ShotId = "signal";
    let frame = 0;
    const lenis = reduced ? null : new Lenis({ lerp: 0.09, smoothWheel: true, wheelMultiplier: 0.92 });

    const sample = () => {
      const y = Math.max(0, window.scrollY - node.offsetTop + window.innerHeight * 0.42);
      let index = 0;
      for (let i = 1; i < ranges.length; i += 1) {
        if (y >= ranges[i].start) index = i;
        else break;
      }
      const range = ranges[index] ?? ranges[0];
      const local = Math.min(1, Math.max(0, (y - range.start) / Math.max(1, range.end - range.start)));
      timeline.current = { index, id: range.id, local };
      node.dataset.activeShot = range.id;
      if (range.id !== currentId) {
        currentId = range.id;
        setActiveShot(range.id);
      }
    };

    const raf = (time: number) => {
      lenis?.raf(time);
      sample();
      frame = requestAnimationFrame(raf);
    };
    frame = requestAnimationFrame(raf);

    const refresh = () => {
      ranges = measureRanges(node);
      sample();
    };
    const observer = new ResizeObserver(refresh);
    observer.observe(node);
    window.addEventListener("resize", refresh);
    document.fonts.ready.then(refresh);

    return () => {
      cancelAnimationFrame(frame);
      lenis?.destroy();
      observer.disconnect();
      window.removeEventListener("resize", refresh);
    };
  }, [setActiveShot, timeline]);

  return root;
}

function BrandLogo({ compact = false }: { compact?: boolean }) {
  return (
    <span className={cn("tlc-logo", compact && "tlc-logo--compact")}>
      <img src="/assets/brand/talento-symbol-white.svg" alt="" aria-hidden />
      <span>talento</span>
    </span>
  );
}

function LanguageSwitch() {
  const { i18n } = useTranslation();
  const locale = getLocale(i18n.language);
  return (
    <div className="tlc-language" aria-label="Language">
      {LANGUAGES.map((language) => (
        <button
          key={language.code}
          type="button"
          className={cn(locale === language.code && "is-active")}
          onClick={() => setLanguage(language.code)}
          aria-pressed={locale === language.code}
        >
          {language.code}
        </button>
      ))}
    </div>
  );
}

function Intro({ copy, leaving, playing, onComplete }: { copy: (typeof COPY)[Locale]["intro"]; leaving: boolean; playing: boolean; onComplete: () => void }) {
  return (
    <div className={cn("tlc-intro", playing && "is-playing", leaving && "is-leaving")} role="dialog" aria-label="talento intro">
      <div className="tlc-intro__index" aria-hidden><span>OPEN PORTAL</span><span>00 — 01</span></div>
      <div className="tlc-intro__type" aria-hidden>
        <span>{copy.line1}</span>
        <span>{copy.line2}</span>
        <span>{copy.line3}</span>
      </div>
      <div className="tlc-intro__message">
        <span>{copy.eyebrow}</span>
        <strong>{copy.thesis}</strong>
        <p>{copy.bridge}</p>
      </div>
      <div className="tlc-intro__axes" aria-hidden><span>X · DISCOVER</span><span>Y · APPLY</span><span>Z · MANAGE</span></div>
      <div className="tlc-intro__brand"><BrandLogo /><small>HIRING THROUGH TELEGRAM</small></div>
      <button type="button" className="tlc-intro__skip" onClick={onComplete}>{copy.skip} <ArrowRight /></button>
    </div>
  );
}

function Navigation({ copy }: { copy: (typeof COPY)[Locale]["nav"] }) {
  return (
    <header className="tlc-nav">
      <a href="#open-access" aria-label="talento — home"><BrandLogo compact /></a>
      <nav aria-label="Main navigation">
        <a href="#discover">{copy.story}</a>
        <a href="#manage">{copy.product}</a>
        <a href="#system">{copy.system}</a>
        <a href="#faq">{copy.faq}</a>
      </nav>
      <div className="tlc-nav__actions">
        <LanguageSwitch />
        <Link className="tlc-nav__login" to="/login">{copy.login}</Link>
        <Link className="tlc-button tlc-button--small" to="/register">{copy.start}<ArrowRight /></Link>
      </div>
    </header>
  );
}

function ShotSection({ id, active, children, className }: { id: ShotId; active: boolean; children: React.ReactNode; className?: string }) {
  return <section id={id} data-shot={id} className={cn("tlc-shot", `tlc-shot--${id}`, active && "is-active", className)}><div className="tlc-shot__sticky">{children}</div></section>;
}

function TelegramFlow({ copy }: { copy: (typeof COPY)[Locale]["discover"] }) {
  return (
    <div className="tlc-telegram" aria-label="Telegram candidate flow">
      <div className="tlc-telegram__bar">
        <span className="tlc-avatar"><Bot /></span>
        <span><strong>{copy.bot}</strong><small><i />{copy.online}</small></span>
        <span className="tlc-telegram__time">10:08</span>
      </div>
      <div className="tlc-telegram__messages">
        <div className="tlc-message">{copy.welcome}<div className="tlc-message__choices"><span>Русский</span><span>O‘zbekcha</span><span>English</span></div></div>
        <div className="tlc-message tlc-message--branch"><small>{copy.branch}</small><strong><MapPin />{copy.branchValue}</strong></div>
        <div className="tlc-vacancy">
          <span className="tlc-vacancy__meta"><BriefcaseBusiness />FULL TIME</span>
          <h3>{copy.role}</h3><strong>{copy.salary}</strong><p><MapPin />{copy.location}</p>
          <button type="button">{copy.apply}<Send /></button>
        </div>
      </div>
    </div>
  );
}

function QuestionDeck({ copy }: { copy: (typeof COPY)[Locale]["apply"] }) {
  return (
    <div className="tlc-question">
      <div className="tlc-question__top"><span>{copy.progress}</span><strong>60%</strong></div>
      <div className="tlc-question__line"><i /></div>
      <div className="tlc-question__message"><MessageSquareText /><h3>{copy.question}</h3></div>
      <div className="tlc-question__options">{copy.options.map((option, index) => <button type="button" key={option} className={index < 2 ? "is-selected" : ""}><span>{index < 2 && <Check />}</span>{option}</button>)}</div>
      <p>{copy.types}</p>
    </div>
  );
}

function TransferStage({ copy }: { copy: (typeof COPY)[Locale]["transfer"] }) {
  return (
    <div className="tlc-transfer" aria-label="Application transfer from Telegram to HR workspace">
      <div className="tlc-transfer__source"><Send /><span>TELEGRAM</span><strong>{copy.sent}</strong></div>
      <div className="tlc-transfer__route"><i /><MoveRight /><i /></div>
      <div className="tlc-candidate-card">
        <span className="tlc-candidate-card__avatar">MY</span>
        <span><small>{copy.status}</small><strong>{copy.candidate}</strong><em>{copy.role}</em></span>
        <span className="tlc-candidate-card__badge">NEW</span>
      </div>
    </div>
  );
}

function ProductWorkspace({ copy }: { copy: (typeof COPY)[Locale]["manage"] }) {
  return (
    <div className="tlc-workspace">
      <aside><BrandLogo compact /><div><LayoutDashboard /><BriefcaseBusiness /><UsersRound /><MessageSquareText /></div><CircleUserRound /></aside>
      <div className="tlc-workspace__main">
        <header><span><small>WORKSPACE / 2026</small><strong>{copy.dashboard}</strong></span><span className="tlc-workspace__notice"><Bell />1</span></header>
        <div className="tlc-stats">
          <div><small>{copy.total}</small><strong>128</strong><em>+18.4%</em></div>
          <div><small>{copy.week}</small><strong>24</strong><em>+7</em></div>
          <div><small>{copy.vacancies}</small><strong>12</strong><em>LIVE</em></div>
        </div>
        <div className="tlc-kanban">
          {copy.columns.map((column, index) => (
            <div key={column} className="tlc-kanban__column"><header><i /><span>{column}</span><small>{index + 1}</small></header><div className={cn("tlc-kanban__card", index === 1 && "is-focus")}><GripVertical /><span className="tlc-kanban__avatar">{copy.candidates[index].slice(0, 1)}</span><span><strong>{copy.candidates[index]}</strong><small>Barista · Telegram</small></span></div></div>
          ))}
        </div>
        <div className="tlc-workspace__telegram"><Send /><span><small>talento notify</small><strong>{copy.notification}</strong></span></div>
      </div>
    </div>
  );
}

function SystemModules({ copy }: { copy: (typeof COPY)[Locale]["system"] }) {
  const icons = [Bot, MapPin, FileText, UsersRound, Bell, Download, ShieldCheck];
  return <div className="tlc-modules">{copy.modules.map(([title, body], index) => { const Icon = icons[index]; return <article key={title}><span><Icon /></span><small>0{index + 1}</small><h3>{title}</h3><p>{body}</p></article>; })}</div>;
}

function FAQ({ copy }: { copy: (typeof COPY)[Locale]["faq"] }) {
  const [open, setOpen] = useState(0);
  return (
    <section id="faq" className="tlc-faq">
      <div className="tlc-faq__heading"><p className="tlc-kicker">{copy.eyebrow}</p><h2>{copy.title}</h2></div>
      <div>{copy.items.map(([question, answer], index) => <article key={question} className={cn(open === index && "is-open")}><button type="button" onClick={() => setOpen(open === index ? -1 : index)} aria-expanded={open === index}><span>0{index + 1}</span><strong>{question}</strong><ChevronDown /></button><div><p>{answer}</p></div></article>)}</div>
    </section>
  );
}

export default function LandingPage() {
  const { i18n } = useTranslation();
  const locale = getLocale(i18n.language);
  const copy = COPY[locale];
  const timeline = useRef<ShotSample>({ index: 0, id: "signal", local: 0 });
  const [activeShot, setActiveShot] = useState<ShotId>("signal");
  const journeyRef = useJourney(timeline, setActiveShot);
  const introTimeline = useRef(0);
  const [introVisible, setIntroVisible] = useState(true);
  const [introLeaving, setIntroLeaving] = useState(false);
  const [sceneReady, setSceneReady] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [renderPath, setRenderPath] = useState<"live" | "poster">("poster");

  useEffect(() => {
    document.documentElement.lang = locale;
    document.title = locale === "ru"
      ? "talento — найм через Telegram"
      : locale === "uz"
        ? "talento — Telegram orqali yollash"
        : "talento — hiring through Telegram";
  }, [locale]);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setReducedMotion(reduced);
    const live = !reduced && supportsWebGL();
    setRenderPath(live ? "live" : "poster");
    if (!live) {
      console.info(`[talento] poster fallback: ${reduced ? "reduced-motion" : "webgl-unavailable"}`);
      setSceneReady(true);
    }
  }, []);

  useEffect(() => {
    if (!sceneReady || !introVisible) return;
    if (reducedMotion) {
      introTimeline.current = 1;
      setIntroLeaving(true);
      const reducedTimer = window.setTimeout(() => setIntroVisible(false), 900);
      return () => window.clearTimeout(reducedTimer);
    }

    const duration = 7600;
    const startedAt = window.performance.now();
    let frame = 0;
    const play = (now: number) => {
      const progress = Math.min(1, Math.max(0, (now - startedAt) / duration));
      introTimeline.current = progress;
      if (progress >= 0.84) setIntroLeaving(true);
      if (progress >= 1) {
        setIntroVisible(false);
        sessionStorage.setItem("talento-intro-seen", "1");
        return;
      }
      frame = window.requestAnimationFrame(play);
    };
    frame = window.requestAnimationFrame(play);
    return () => window.cancelAnimationFrame(frame);
  }, [introVisible, reducedMotion, sceneReady]);

  const closeIntro = () => {
    introTimeline.current = 1;
    setIntroLeaving(true);
    sessionStorage.setItem("talento-intro-seen", "1");
    window.setTimeout(() => setIntroVisible(false), 850);
  };

  const timelineValue = timeline as LandingTimeline;
  const introTimelineValue = introTimeline as IntroTimeline;
  const sceneClass = useMemo(() => `tlc-scene tlc-scene--${activeShot}`, [activeShot]);

  return (
    <div className={cn("tlc", introVisible && "is-intro") }>
      {introVisible && <Intro copy={copy.intro} leaving={introLeaving} playing={sceneReady} onComplete={closeIntro} />}
      <a className="tlc-skip-link" href="#open-access">Skip to content</a>
      <Navigation copy={copy.nav} />

      <div className={sceneClass} aria-hidden="true">
        <div className="tlc-scene__poster"><img src="/assets/brand/talento-symbol-blue.svg" alt="" /></div>
        {renderPath === "live" && (
          <Suspense fallback={<div className="tlc-scene__loader"><i /><span>OPENING TALENT</span></div>}>
            <LandingScene timeline={timelineValue} introTimeline={introTimelineValue} reducedMotion={reducedMotion} onReady={() => setSceneReady(true)} />
          </Suspense>
        )}
      </div>
      <div className="tlc-human-field" aria-hidden="true" />
      <div className="tlc-grain" aria-hidden="true" />

      <main
        ref={journeyRef}
        data-render-path={renderPath}
        data-scene-ready={sceneReady}
        data-active-shot={activeShot}
      >
        <ShotSection id="signal" active={activeShot === "signal"}>
          <div className="tlc-signal-type" aria-hidden><span>TALENT</span><span>ТАЛАНТ</span><span>ISTE’DOD</span></div>
          <div className="tlc-shot-number">00 / 07</div>
          <a className="tlc-scroll-cue" href="#open-access"><span>SCROLL TO OPEN</span><ArrowDown /></a>
        </ShotSection>

        <ShotSection id="open-access" active={activeShot === "open-access"}>
          <div className="tlc-copy tlc-copy--hero">
            <p className="tlc-kicker"><Sparkles />{copy.hero.eyebrow}</p>
            <h1>{copy.hero.title}</h1>
            <p>{copy.hero.body}</p>
            <div className="tlc-actions"><Link to="/register" className="tlc-button">{copy.hero.primary}<ArrowRight /></Link><a href="#discover" className="tlc-button tlc-button--ghost">{copy.hero.secondary}<ArrowDown /></a></div>
            <div className="tlc-proof">{copy.hero.proofs.map((proof, index) => <span key={proof}><small>0{index + 1}</small>{proof}</span>)}</div>
          </div>
          <p className="tlc-vertical-label">{copy.hero.alternate}</p>
        </ShotSection>

        <ShotSection id="discover" active={activeShot === "discover"}>
          <div className="tlc-two-col">
            <div className="tlc-copy"><p className="tlc-kicker">{copy.discover.index}</p><h2>{copy.discover.title}</h2><p>{copy.discover.body}</p></div>
            <TelegramFlow copy={copy.discover} />
          </div>
        </ShotSection>

        <ShotSection id="apply" active={activeShot === "apply"}>
          <div className="tlc-two-col tlc-two-col--reverse">
            <QuestionDeck copy={copy.apply} />
            <div className="tlc-copy"><p className="tlc-kicker">{copy.apply.index}</p><h2>{copy.apply.title}</h2><p>{copy.apply.body}</p></div>
          </div>
        </ShotSection>

        <ShotSection id="transfer" active={activeShot === "transfer"}>
          <div className="tlc-copy tlc-copy--transfer"><p className="tlc-kicker">{copy.transfer.index}</p><h2>{copy.transfer.title}</h2><p>{copy.transfer.body}</p></div>
          <TransferStage copy={copy.transfer} />
        </ShotSection>

        <ShotSection id="manage" active={activeShot === "manage"}>
          <div className="tlc-manage-heading"><div className="tlc-copy"><p className="tlc-kicker">{copy.manage.index}</p><h2>{copy.manage.title}</h2><p>{copy.manage.body}</p></div></div>
          <ProductWorkspace copy={copy.manage} />
        </ShotSection>

        <ShotSection id="system" active={activeShot === "system"}>
          <div className="tlc-system-heading"><div className="tlc-copy"><p className="tlc-kicker">{copy.system.index}</p><h2>{copy.system.title}</h2><p>{copy.system.body}</p><LanguageSwitch /></div></div>
          <SystemModules copy={copy.system} />
        </ShotSection>

        <ShotSection id="resolution" active={activeShot === "resolution"}>
          <div className="tlc-resolution"><p className="tlc-kicker">{copy.resolution.index}</p><BrandLogo /><h2>{copy.resolution.title}</h2><p>{copy.resolution.body}</p><div className="tlc-actions"><Link to="/register" className="tlc-button">{copy.resolution.primary}<ArrowRight /></Link><Link to="/login" className="tlc-button tlc-button--ghost">{copy.resolution.secondary}</Link></div></div>
        </ShotSection>

        <FAQ copy={copy.faq} />
        <footer className="tlc-footer"><div><BrandLogo /><p>{copy.footer.line}</p></div><div><a href="#discover">{copy.footer.product}</a><Link to="/login">{copy.footer.access}</Link><LanguageSwitch /></div><p>© {new Date().getFullYear()} talento. {copy.footer.rights}</p></footer>
      </main>
    </div>
  );
}
