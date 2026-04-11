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

    // Branching
    'branch.forkMode': 'Memulai cabang percakapan dari pesan ini',
    'branch.fork': 'Cabangkan di sini',
    'branch.cancel': 'Batal',

    // Admin settings
    'admin.title': 'Konfigurasi Global',
    'admin.badge': 'Khusus Admin',
    'admin.llm.title': 'Model LLM',
    'admin.llm.description': 'Model yang digunakan untuk respons chat (via OpenRouter).',
    'admin.embedding.title': 'Model Embedding',
    'admin.embedding.description': 'Digunakan untuk menyematkan dokumen dan kueri untuk pencarian kesamaan.',
    'admin.rag.title': 'Konfigurasi RAG',
    'admin.rag.description': 'Mengontrol perilaku retrieval-augmented generation.',
    'admin.rag.topK': 'Hasil Top K',
    'admin.rag.threshold': 'Ambang Kesamaan',
    'admin.rag.chunkSize': 'Ukuran Chunk',
    'admin.rag.chunkOverlap': 'Overlap Chunk',
    'admin.rag.hybrid': 'Pencarian Hibrida',
    'admin.rag.hybridDesc': 'Gabungkan pencarian vektor + teks penuh dengan RRF',
    'admin.rag.rrfK': 'Konstanta RRF K',
    'admin.tools.title': 'Pemanggilan Alat',
    'admin.tools.description': 'Mengontrol pencarian web, kueri database, dan alat pencarian dokumen.',
    'admin.tools.enable': 'Aktifkan Alat',
    'admin.tools.enableDesc': 'Izinkan LLM memanggil alat selama chat',
    'admin.tools.maxIterations': 'Maks Iterasi Alat',
    'admin.tools.agents': 'Aktifkan Sub-Agen',
    'admin.tools.agentsDesc': 'Rutekan kueri ke agen spesialis melalui orkestrator',
    'admin.error.load': 'Gagal memuat pengaturan. Apakah Anda seorang admin?',
    'admin.error.save': 'Gagal menyimpan',
    'admin.save.saving': 'Menyimpan...',
    'admin.save.saved': 'Tersimpan!',
    'admin.save.button': 'Simpan Konfigurasi',

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

    // Branching
    'branch.forkMode': 'Forking conversation from this message',
    'branch.fork': 'Fork here',
    'branch.cancel': 'Cancel',

    // Admin settings
    'admin.title': 'Global Configuration',
    'admin.badge': 'Admin Only',
    'admin.llm.title': 'LLM Model',
    'admin.llm.description': 'The model used for chat responses (via OpenRouter).',
    'admin.embedding.title': 'Embedding Model',
    'admin.embedding.description': 'Used to embed documents and queries for similarity search.',
    'admin.rag.title': 'RAG Configuration',
    'admin.rag.description': 'Controls retrieval-augmented generation behavior.',
    'admin.rag.topK': 'Top K Results',
    'admin.rag.threshold': 'Similarity Threshold',
    'admin.rag.chunkSize': 'Chunk Size',
    'admin.rag.chunkOverlap': 'Chunk Overlap',
    'admin.rag.hybrid': 'Hybrid Search',
    'admin.rag.hybridDesc': 'Combine vector + full-text search with RRF',
    'admin.rag.rrfK': 'RRF K Constant',
    'admin.tools.title': 'Tool Calling',
    'admin.tools.description': 'Controls web search, database queries, and document search tools.',
    'admin.tools.enable': 'Enable Tools',
    'admin.tools.enableDesc': 'Allow the LLM to call tools during chat',
    'admin.tools.maxIterations': 'Max Tool Iterations',
    'admin.tools.agents': 'Enable Sub-Agents',
    'admin.tools.agentsDesc': 'Route queries to specialized agents via orchestrator',
    'admin.error.load': 'Failed to load settings. Are you an admin?',
    'admin.error.save': 'Failed to save',
    'admin.save.saving': 'Saving...',
    'admin.save.saved': 'Saved!',
    'admin.save.button': 'Save Configuration',

    // Thinking
    'thinking': 'Thinking...',
  },
}
