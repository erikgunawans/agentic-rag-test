export type Locale = 'id' | 'en'

export const translations: Record<Locale, Record<string, string>> = {
  id: {
    // Welcome screen
    'welcome.greeting': 'Halo, {name}',
    'welcome.subtitle':
      'Ajukan pertanyaan tentang dokumen legal, kontrak, dan kepatuhan regulasi Anda.',

    // Chat
    'chat.placeholder': 'Apa pertanyaan anda saat ini?',
    'chat.newChat': 'Chat Baru',
    'chat.send': 'Kirim pesan',
    'chat.startConversation': 'Kirim pesan untuk memulai percakapan',

    // Navigation
    'nav.documents': 'Dokumen',
    'nav.settings': 'Pengaturan',
    'nav.chat': 'Chat',
    'nav.signOut': 'Keluar',

    // Suggestion chips
    'chip.searchDoc': 'Pencarian Dokumen',
    'chip.compareDoc': 'Perbandingan Dokumen',
    'chip.validateDoc': 'Keabsahan Dokumen',
    'chip.createDoc': 'Pembuatan Dokumen',

    // Thread groups
    'thread.today': 'Hari Ini',
    'thread.yesterday': 'Kemarin',
    'thread.previous7': '7 Hari Terakhir',
    'thread.older': 'Lebih Lama',

    // Sidebar
    'sidebar.title': 'Knowledge Hub',
    'sidebar.subtitle': 'Legal AI Assistant',
    'sidebar.recentConversations': 'PERCAKAPAN TERBARU',

    // Settings
    'settings.title': 'Pengaturan',
    'settings.admin': 'Konfigurasi Admin',
    'settings.adminDesc': 'Kelola konfigurasi sistem global',
    'settings.language': 'Bahasa',
    'settings.languageDesc': 'Pilih bahasa tampilan.',
    'settings.notifications': 'Notifikasi',
    'settings.notificationsDesc': 'Kontrol preferensi notifikasi.',
    'settings.enableNotifications': 'Aktifkan Notifikasi',
    'settings.enableNotificationsDesc':
      'Terima notifikasi tentang pemrosesan dokumen dan pembaruan sistem.',
    'settings.save': 'Simpan Preferensi',
    'settings.saving': 'Menyimpan...',
    'settings.saved': 'Tersimpan!',

    // Documents
    'documents.title': 'Dokumen',
    'documents.upload': 'Unggah Dokumen',
    'documents.yourDocs': 'Dokumen Anda',

    // Auth
    'auth.title': 'RAG Chat',
    'auth.subtitle': 'Powered by OpenAI + Supabase',
    'auth.login': 'Masuk',
    'auth.signup': 'Daftar',
    'auth.email': 'Email',
    'auth.password': 'Kata Sandi',
    'auth.loading': 'Mohon tunggu…',
    'auth.confirmEmail': 'Periksa email Anda untuk tautan konfirmasi.',
    'auth.error': 'Terjadi kesalahan',

    // File upload
    'upload.drop': 'Letakkan file atau klik untuk mengunggah',
    'upload.uploading': 'Mengunggah…',
    'upload.formats': 'PDF, TXT, Markdown, DOCX, CSV, HTML, atau JSON · Maks 50 MB',
    'upload.unsupported': 'Hanya file PDF, TXT, Markdown, DOCX, CSV, HTML, dan JSON yang didukung.',
    'upload.duplicate': '"{filename}" sudah diunggah dan diproses.',
    'upload.failed': 'Gagal mengunggah',

    // Document list
    'docList.empty': 'Belum ada dokumen. Unggah di atas.',
    'docList.chunks': '{count} bagian',
    'docList.more': '+{count} lainnya',
    'docList.delete': 'Hapus dokumen',

    // Thinking
    'thinking': 'Sedang berpikir...',
  },
  en: {
    // Welcome screen
    'welcome.greeting': 'Hi, {name}',
    'welcome.subtitle':
      'Ask questions about your legal documents, contracts, and compliance requirements.',

    // Chat
    'chat.placeholder': 'What is your question right now?',
    'chat.newChat': 'New Chat',
    'chat.send': 'Send message',
    'chat.startConversation': 'Send a message to start the conversation',

    // Navigation
    'nav.documents': 'Documents',
    'nav.settings': 'Settings',
    'nav.chat': 'Chat',
    'nav.signOut': 'Sign Out',

    // Suggestion chips
    'chip.searchDoc': 'Document Search',
    'chip.compareDoc': 'Document Comparison',
    'chip.validateDoc': 'Document Validation',
    'chip.createDoc': 'Document Creation',

    // Thread groups
    'thread.today': 'Today',
    'thread.yesterday': 'Yesterday',
    'thread.previous7': 'Previous 7 Days',
    'thread.older': 'Older',

    // Sidebar
    'sidebar.title': 'Knowledge Hub',
    'sidebar.subtitle': 'Legal AI Assistant',
    'sidebar.recentConversations': 'RECENT CONVERSATIONS',

    // Settings
    'settings.title': 'Settings',
    'settings.admin': 'Admin Configuration',
    'settings.adminDesc': 'Manage global system configuration',
    'settings.language': 'Language',
    'settings.languageDesc': 'Choose your display language.',
    'settings.notifications': 'Notifications',
    'settings.notificationsDesc': 'Control notification preferences.',
    'settings.enableNotifications': 'Enable Notifications',
    'settings.enableNotificationsDesc':
      'Receive notifications about document processing and system updates.',
    'settings.save': 'Save Preferences',
    'settings.saving': 'Saving...',
    'settings.saved': 'Saved!',

    // Documents
    'documents.title': 'Documents',
    'documents.upload': 'Upload Document',
    'documents.yourDocs': 'Your Documents',

    // Auth
    'auth.title': 'RAG Chat',
    'auth.subtitle': 'Powered by OpenAI + Supabase',
    'auth.login': 'Log In',
    'auth.signup': 'Sign Up',
    'auth.email': 'Email',
    'auth.password': 'Password',
    'auth.loading': 'Please wait…',
    'auth.confirmEmail': 'Check your email for a confirmation link.',
    'auth.error': 'Something went wrong',

    // File upload
    'upload.drop': 'Drop a file or click to upload',
    'upload.uploading': 'Uploading…',
    'upload.formats': 'PDF, TXT, Markdown, DOCX, CSV, HTML, or JSON · Max 50 MB',
    'upload.unsupported': 'Only PDF, TXT, Markdown, DOCX, CSV, HTML, and JSON files are supported.',
    'upload.duplicate': '"{filename}" is already uploaded and processed.',
    'upload.failed': 'Upload failed',

    // Document list
    'docList.empty': 'No documents yet. Upload one above.',
    'docList.chunks': '{count} chunks',
    'docList.more': '+{count} more',
    'docList.delete': 'Delete document',

    // Thinking
    'thinking': 'Thinking...',
  },
}
