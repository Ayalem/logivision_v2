/**
 * i18n - Internationalization system for LogiVision
 * Supports English, French, and Arabic
 */
import { useState, useEffect, useCallback } from 'react'

export type Language = 'en' | 'fr' | 'ar'

export const translations = {
  en: {
    // Sidebar
    overview: 'Overview',
    digitalTwin: 'Digital Twin',
    cameras: 'Cameras',
    analytics: 'Analytics',
    alerts: 'Alerts',
    inventory: 'Inventory',
    workforce: 'Workforce',
    settings: 'Settings',
    profile: 'Profile',
    mlMonitoring: 'ML Monitoring',
    system: 'System',
    activityLog: 'Activity Log',
    myTasks: 'My Tasks',

    // Header
    warehouse: 'Warehouse',
    date: 'DATE',
    time: 'TIME',
    systemStatus: 'SYSTEM STATUS',
    aiActive: 'AI ACTIVE',
    language: 'Language',
    notifications: 'Notifications',
    noAlerts: 'No alerts at the moment',
    markAllAsRead: 'Mark all as read',
    viewAllAlerts: 'View all alerts →',
    accountSettings: 'Account Settings',
    myProfile: 'My Profile',
    logout: 'Logout',
    critical: 'Critical',
    warnings: 'Warnings',
    information: 'Information',
    notificationCount: '{count} events',
    searchPlaceholder: 'Search orders, forklifts, workers...',

    // Metric Cards
    totalOrders: 'Total Orders',
    activeForklifts: 'Active Forklifts',
    inventoryStatus: 'Inventory Status',
    efficiencyScore: 'Efficiency Score',
    liveAlerts: 'Live Alerts',
    
    // Buttons / Links
    viewDetails: 'View Details',
    cancel: 'Cancel',
    save: 'Save',
    confirm: 'Confirm',
    snooze: 'Snooze',
    dismiss: 'Dismiss',

    // Login Page
    logivision: 'LOGIVISION',
    warehouseIntelligence: 'Warehouse Intelligence Platform',
    loginAs: 'Login As',
    admin: 'Admin',
    worker: 'Worker',
    email: 'Email',
    password: 'Password',
    rememberMe: 'Remember me',
    forgotPassword: 'Forgot password?',
    signIn: 'Sign In',
    dontHaveAccount: "Don't have an account?",
    requestAccess: 'Request access',
    demoCredentials: 'Demo Credentials:',
    adminDemo: 'Admin: admin@logivision.com / admin123',
    workerDemo: 'Worker: worker@logivision.com / worker123',
    loggingIn: 'Logging in...',
    pleaseEnterEmailPassword: 'Please enter email and password',
    invalidCredentials: 'Invalid email or password',
    loginFailed: 'Login failed',
    allRightsReserved: '© 2024 All rights reserved',
  },
  fr: {
    // Sidebar
    overview: "Vue d'ensemble",
    digitalTwin: 'Jumeau Numérique',
    cameras: 'Caméras',
    analytics: 'Analyses',
    alerts: 'Anomalies',
    inventory: 'Inventaire',
    workforce: 'Personnel',
    settings: 'Paramètres',
    profile: 'Profil',
    mlMonitoring: 'Suivi ML',
    system: 'Système',
    activityLog: "Journal d'activité",
    myTasks: 'Mes Tâches',

    // Header
    warehouse: 'Entrepôt',
    date: 'DATE',
    time: 'HEURE',
    systemStatus: 'ÉTAT DU SYSTÈME',
    aiActive: 'IA ACTIVE',
    language: 'Langue',
    notifications: 'Notifications',
    noAlerts: 'Aucune alerte pour le moment',
    markAllAsRead: 'Marquer tout comme lu',
    viewAllAlerts: 'Voir toutes les alertes →',
    accountSettings: 'Paramètres du compte',
    myProfile: 'Mon profil',
    logout: 'Déconnexion',
    critical: 'Critiques',
    warnings: 'Avertissements',
    information: 'Informations',
    notificationCount: '{count} événements',
    searchPlaceholder: 'Rechercher commandes, chariots, ouvriers...',

    // Metric Cards
    totalOrders: 'Total Commandes',
    activeForklifts: 'Chariots Actifs',
    inventoryStatus: 'État des Stocks',
    efficiencyScore: "Score d'Efficacité",
    liveAlerts: 'Alertes en Direct',

    // Buttons / Links
    viewDetails: 'Voir Détails',
    cancel: 'Annuler',
    save: 'Enregistrer',
    confirm: 'Confirmer',
    snooze: 'Répéter',
    dismiss: 'Ignorer',

    // Login Page
    logivision: 'LOGIVISION',
    warehouseIntelligence: "Plateforme d'intelligence d'entrepôt",
    loginAs: 'Connectez-vous en tant que',
    admin: 'Admin',
    worker: 'Opérateur',
    email: 'Email',
    password: 'Mot de passe',
    rememberMe: 'Se souvenir de moi',
    forgotPassword: 'Mot de passe oublié?',
    signIn: 'Se connecter',
    dontHaveAccount: "Vous n'avez pas de compte?",
    requestAccess: "Demander l'accès",
    demoCredentials: 'Identifiants de démonstration:',
    adminDemo: 'Admin: admin@logivision.com / admin123',
    workerDemo: 'Opérateur: worker@logivision.com / worker123',
    loggingIn: 'Connexion en cours...',
    pleaseEnterEmailPassword: 'Veuillez entrer votre email et mot de passe',
    invalidCredentials: 'Email ou mot de passe invalide',
    loginFailed: 'Connexion échouée',
    allRightsReserved: '© 2024 Tous droits réservés',
  },
  ar: {
    // Sidebar
    overview: 'نظرة عامة',
    digitalTwin: 'التوأم الرقمي',
    cameras: 'الكاميرات',
    analytics: 'التحليلات',
    alerts: 'التنبيهات',
    inventory: 'المخزون',
    workforce: 'القوى العاملة',
    settings: 'الإعدادات',
    profile: 'الملف الشخصي',
    mlMonitoring: 'مراقبة تعلم الآلة',
    system: 'النظام',
    activityLog: 'سجل النشاط',
    myTasks: 'مهامي',

    // Header
    warehouse: 'المستودع',
    date: 'التاريخ',
    time: 'الوقت',
    systemStatus: 'حالة النظام',
    aiActive: 'الذكاء الاصطناعي نشط',
    language: 'اللغة',
    notifications: 'الإشعارات',
    noAlerts: 'لا توجد تنبيهات حالياً',
    markAllAsRead: 'تحديد الكل كمقروء',
    viewAllAlerts: 'عرض جميع التنبيهات ←',
    accountSettings: 'إعدادات الحساب',
    myProfile: 'ملفي الشخصي',
    logout: 'تسجيل الخروج',
    critical: 'حرج',
    warnings: 'تحذيرات',
    information: 'معلومات',
    notificationCount: '{count} أحداث',
    searchPlaceholder: 'البحث عن الطلبات، الرافعات، العمال...',

    // Metric Cards
    totalOrders: 'إجمالي الطلبات',
    activeForklifts: 'الرافعات النشطة',
    inventoryStatus: 'حالة المخزون',
    efficiencyScore: 'درجة الكفاءة',
    liveAlerts: 'تنبيهات مباشرة',

    // Buttons / Links
    viewDetails: 'عرض التفاصيل',
    cancel: 'إلغاء',
    save: 'حفظ',
    confirm: 'تأكيد',
    snooze: 'غفوة',
    dismiss: 'تجاهل',

    // Login Page
    logivision: 'LOGIVISION',
    warehouseIntelligence: 'منصة ذكاء المستودعات',
    loginAs: 'تسجيل الدخول كـ',
    admin: 'مدير',
    worker: 'عامل',
    email: 'البريد الإلكتروني',
    password: 'كلمة المرور',
    rememberMe: 'تذكرني',
    forgotPassword: 'هل نسيت كلمة المرور؟',
    signIn: 'تسجيل الدخول',
    dontHaveAccount: 'ليس لديك حساب؟',
    requestAccess: 'طلب وصول',
    demoCredentials: 'بيانات الاعتماد التجريبية:',
    adminDemo: 'مدير: admin@logivision.com / admin123',
    workerDemo: 'عامل: worker@logivision.com / worker123',
    loggingIn: 'جاري تسجيل الدخول...',
    pleaseEnterEmailPassword: 'يرجى إدخال البريد الإلكتروني وكلمة المرور',
    invalidCredentials: 'البريد الإلكتروني أو كلمة المرور غير صحيحة',
    loginFailed: 'فشل تسجيل الدخول',
    allRightsReserved: '© 2024 جميع الحقوق محفوظة',
  },
}

export type TranslationKey = keyof typeof translations.en

export function t(key: TranslationKey, lang: Language = 'en', replacements?: Record<string, string>): string {
  let text = translations[lang][key] || translations.en[key] || key
  
  if (replacements) {
    Object.entries(replacements).forEach(([k, v]) => {
      text = text.replace(`{${k}}`, v)
    })
  }
  
  return text
}

export function getLang(): Language {
  if (typeof window !== 'undefined') {
    return (localStorage.getItem('logivision_lang') || 'en') as Language
  }
  return 'en'
}

export function setLang(lang: Language): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem('logivision_lang', lang)
    applyLanguageSettings(lang)
    // Dispatch a custom event to notify components about the language change
    window.dispatchEvent(new CustomEvent('languageChange', { detail: lang }))
  }
}

function applyLanguageSettings(lang: Language) {
  if (typeof document !== 'undefined') {
    if (lang === 'ar') {
      document.documentElement.dir = 'rtl'
      document.documentElement.lang = 'ar'
    } else {
      document.documentElement.dir = 'ltr'
      document.documentElement.lang = lang
    }
  }
}

export function useTranslation() {
  const [lang, setLangState] = useState<Language>(getLang())

  useEffect(() => {
    const handleLangChange = (e: any) => {
      setLangState(e.detail)
    }
    window.addEventListener('languageChange', handleLangChange)
    // Initial apply
    applyLanguageSettings(getLang())
    return () => window.removeEventListener('languageChange', handleLangChange)
  }, [])

  const translate = useCallback((key: TranslationKey, replacements?: Record<string, string>) => {
    return t(key, lang, replacements)
  }, [lang])

  return { t: translate, lang, setLang }
}
