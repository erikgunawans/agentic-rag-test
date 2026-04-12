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

    // Welcome screen cards
    'sidebar.chatHistory': 'Riwayat Chat',
    'sidebar.searchPlaceholder': 'Cari percakapan...',
    'sidebar.role': 'Konsultan Hukum',
    'welcome.version': 'Legal AI v1.0',
    'card.create.title': 'Pembuatan Dokumen',
    'card.create.desc': 'Draft NDAs, kontrak & perjanjian',
    'card.compare.title': 'Perbandingan Dokumen',
    'card.compare.desc': 'Bandingkan versi & temukan perbedaan',
    'card.compliance.title': 'Kepatuhan Dokumen',
    'card.compliance.desc': 'Cek regulasi & persyaratan hukum',
    'card.analysis.title': 'Analisis Kontrak',
    'card.analysis.desc': 'Identifikasi risiko & klausul kritis',

    // Branching
    'branch.forkMode': 'Memulai cabang percakapan dari pesan ini',
    'branch.fork': 'Cabangkan di sini',
    'branch.cancel': 'Batal',

    // Navigation (new screens)
    'nav.create': 'Buat Dokumen',
    'nav.compare': 'Perbandingan',
    'nav.compliance': 'Kepatuhan',
    'nav.analysis': 'Analisis',
    'nav.moreModules': 'Modul Lainnya',
    'nav.comingSoon': 'Segera hadir',

    // Shared components
    'shared.dropzone.title': 'Letakkan file di sini atau klik untuk memilih',
    'shared.dropzone.subtitle': 'PDF, DOCX, TXT · Maks 50 MB',
    'shared.dropzone.attached': 'File terlampir',
    'shared.dropzone.remove': 'Hapus',
    'shared.history.viewAll': 'Lihat semua',
    'shared.history.empty': 'Belum ada riwayat',
    'shared.emptyState.title': 'Belum ada hasil',
    'shared.emptyState.subtitle': 'Mulai dengan mengunggah dokumen dan mengisi formulir di sebelah kiri.',

    // Document Creation
    'create.title': 'Buat Dokumen',
    'create.docType': 'Jenis Dokumen',
    'create.docType.generic': 'Dokumen Umum',
    'create.docType.nda': 'Perjanjian Kerahasiaan (NDA)',
    'create.docType.sales': 'Kontrak Penjualan',
    'create.docType.service': 'Perjanjian Layanan',
    'create.party1': 'Pihak Pertama',
    'create.party2': 'Pihak Kedua',
    'create.effectiveDate': 'Tanggal Berlaku',
    'create.duration': 'Durasi',
    'create.purpose': 'Tujuan',
    'create.scope': 'Ruang Lingkup',
    'create.governingLaw': 'Hukum yang Berlaku',
    'create.notes': 'Catatan Tambahan',
    'create.language': 'Bahasa Keluaran',
    'create.language.bilingual': 'Indonesia & Inggris',
    'create.language.id': 'Indonesia Saja',
    'create.reference': 'Dokumen Referensi (opsional)',
    'create.template': 'Template (opsional)',
    'create.generate': 'Buat Dokumen',
    'create.history': 'Dokumen Terbaru',

    // Document Comparison
    'compare.title': 'Perbandingan Dokumen',
    'compare.doc1': 'Dokumen A',
    'compare.doc2': 'Dokumen B',
    'compare.swap': 'Tukar dokumen',
    'compare.focus': 'Fokus Perbandingan',
    'compare.focus.full': 'Dokumen Lengkap',
    'compare.focus.clauses': 'Klausul Utama Saja',
    'compare.focus.risks': 'Perbedaan Risiko',
    'compare.generate': 'Bandingkan Dokumen',
    'compare.history': 'Perbandingan Terbaru',

    // Compliance Check
    'compliance.title': 'Pemeriksaan Kepatuhan',
    'compliance.document': 'Unggah Dokumen',
    'compliance.framework': 'Kerangka Kepatuhan',
    'compliance.framework.ojk': 'Regulasi OJK',
    'compliance.framework.international': 'Standar Internasional',
    'compliance.framework.gdpr': 'GDPR',
    'compliance.framework.custom': 'Aturan Kustom',
    'compliance.scope': 'Cakupan Pemeriksaan',
    'compliance.scope.legal': 'Klausul Hukum',
    'compliance.scope.risks': 'Tanda Risiko',
    'compliance.scope.missing': 'Ketentuan yang Hilang',
    'compliance.scope.regulatory': 'Kepatuhan Regulasi',
    'compliance.context': 'Konteks Tambahan',
    'compliance.run': 'Jalankan Pemeriksaan',
    'compliance.history': 'Pemeriksaan Terbaru',

    // Contract Analysis
    'analysis.title': 'Analisis Kontrak',
    'analysis.document': 'Unggah Kontrak',
    'analysis.type': 'Jenis Analisis',
    'analysis.type.risk': 'Penilaian Risiko',
    'analysis.type.obligations': 'Kewajiban Utama',
    'analysis.type.clauses': 'Klausul Kritis',
    'analysis.type.missing': 'Ketentuan yang Hilang',
    'analysis.law': 'Hukum yang Berlaku',
    'analysis.law.indonesia': 'Hukum Indonesia',
    'analysis.law.singapore': 'Hukum Singapura',
    'analysis.law.international': 'Hukum Internasional',
    'analysis.law.custom': 'Lainnya',
    'analysis.depth': 'Kedalaman Analisis',
    'analysis.depth.quick': 'Pemindaian Cepat',
    'analysis.depth.standard': 'Standar',
    'analysis.depth.deep': 'Mendalam',
    'analysis.context': 'Konteks Tambahan',
    'analysis.run': 'Jalankan Analisis',
    'analysis.history': 'Analisis Terbaru',

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

    // Audit Trail
    'audit.title': 'Jejak Audit',
    'audit.export': 'Ekspor CSV',
    'audit.filters': 'Filter',
    'audit.filter.allActions': 'Semua Aksi',
    'audit.filter.resourceType': 'Tipe sumber daya...',
    'audit.empty': 'Belum ada log audit.',
    'audit.col.timestamp': 'Waktu',
    'audit.col.user': 'Pengguna',
    'audit.col.action': 'Aksi',
    'audit.col.resource': 'Sumber Daya',
    'audit.col.details': 'Detail',
    'audit.showing': 'Menampilkan',
    'audit.prev': 'Sebelumnya',
    'audit.next': 'Selanjutnya',
    'audit.error.load': 'Gagal memuat log audit.',
    'settings.auditTrail': 'Jejak Audit',

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

    // Welcome screen cards
    'sidebar.chatHistory': 'Chat History',
    'sidebar.searchPlaceholder': 'Search conversations...',
    'sidebar.role': 'Legal Consultant',
    'welcome.version': 'Legal AI v1.0',
    'card.create.title': 'Document Creation',
    'card.create.desc': 'Draft NDAs, contracts & agreements',
    'card.compare.title': 'Document Comparison',
    'card.compare.desc': 'Compare versions & find differences',
    'card.compliance.title': 'Compliance Check',
    'card.compliance.desc': 'Check regulations & legal requirements',
    'card.analysis.title': 'Contract Analysis',
    'card.analysis.desc': 'Identify risks & critical clauses',

    // Branching
    'branch.forkMode': 'Forking conversation from this message',
    'branch.fork': 'Fork here',
    'branch.cancel': 'Cancel',

    // Navigation (new screens)
    'nav.create': 'Create Document',
    'nav.compare': 'Comparison',
    'nav.compliance': 'Compliance',
    'nav.analysis': 'Analysis',
    'nav.moreModules': 'More Modules',
    'nav.comingSoon': 'Coming soon',

    // Shared components
    'shared.dropzone.title': 'Drop a file here or click to select',
    'shared.dropzone.subtitle': 'PDF, DOCX, TXT · Max 50 MB',
    'shared.dropzone.attached': 'File attached',
    'shared.dropzone.remove': 'Remove',
    'shared.history.viewAll': 'View all',
    'shared.history.empty': 'No history yet',
    'shared.emptyState.title': 'No results yet',
    'shared.emptyState.subtitle': 'Start by uploading a document and filling out the form on the left.',

    // Document Creation
    'create.title': 'Create Document',
    'create.docType': 'Document Type',
    'create.docType.generic': 'Generic Document',
    'create.docType.nda': 'Non-Disclosure Agreement (NDA)',
    'create.docType.sales': 'Sales Contract',
    'create.docType.service': 'Service Agreement',
    'create.party1': 'Party 1',
    'create.party2': 'Party 2',
    'create.effectiveDate': 'Effective Date',
    'create.duration': 'Duration',
    'create.purpose': 'Purpose',
    'create.scope': 'Scope',
    'create.governingLaw': 'Governing Law',
    'create.notes': 'Additional Notes',
    'create.language': 'Output Language',
    'create.language.bilingual': 'English & Indonesian',
    'create.language.id': 'Indonesian Only',
    'create.reference': 'Reference Document (optional)',
    'create.template': 'Template (optional)',
    'create.generate': 'Generate Document',
    'create.history': 'Recent Documents',

    // Document Comparison
    'compare.title': 'Document Comparison',
    'compare.doc1': 'Document A',
    'compare.doc2': 'Document B',
    'compare.swap': 'Swap documents',
    'compare.focus': 'Comparison Focus',
    'compare.focus.full': 'Full Document',
    'compare.focus.clauses': 'Key Clauses Only',
    'compare.focus.risks': 'Risk Differences',
    'compare.generate': 'Compare Documents',
    'compare.history': 'Recent Comparisons',

    // Compliance Check
    'compliance.title': 'Compliance Check',
    'compliance.document': 'Upload Document',
    'compliance.framework': 'Compliance Framework',
    'compliance.framework.ojk': 'OJK Regulations',
    'compliance.framework.international': 'International Standards',
    'compliance.framework.gdpr': 'GDPR',
    'compliance.framework.custom': 'Custom Rules',
    'compliance.scope': 'Check Scope',
    'compliance.scope.legal': 'Legal Clauses',
    'compliance.scope.risks': 'Risk Flags',
    'compliance.scope.missing': 'Missing Terms',
    'compliance.scope.regulatory': 'Regulatory Alignment',
    'compliance.context': 'Additional Context',
    'compliance.run': 'Run Compliance Check',
    'compliance.history': 'Recent Checks',

    // Contract Analysis
    'analysis.title': 'Contract Analysis',
    'analysis.document': 'Upload Contract',
    'analysis.type': 'Analysis Type',
    'analysis.type.risk': 'Risk Assessment',
    'analysis.type.obligations': 'Key Obligations',
    'analysis.type.clauses': 'Critical Clauses',
    'analysis.type.missing': 'Missing Terms',
    'analysis.law': 'Governing Law',
    'analysis.law.indonesia': 'Indonesian Law',
    'analysis.law.singapore': 'Singapore Law',
    'analysis.law.international': 'International Law',
    'analysis.law.custom': 'Other',
    'analysis.depth': 'Analysis Depth',
    'analysis.depth.quick': 'Quick Scan',
    'analysis.depth.standard': 'Standard',
    'analysis.depth.deep': 'Deep Analysis',
    'analysis.context': 'Additional Context',
    'analysis.run': 'Run Contract Analysis',
    'analysis.history': 'Recent Analyses',

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

    // Audit Trail
    'audit.title': 'Audit Trail',
    'audit.export': 'Export CSV',
    'audit.filters': 'Filters',
    'audit.filter.allActions': 'All Actions',
    'audit.filter.resourceType': 'Resource type...',
    'audit.empty': 'No audit logs yet.',
    'audit.col.timestamp': 'Timestamp',
    'audit.col.user': 'User',
    'audit.col.action': 'Action',
    'audit.col.resource': 'Resource',
    'audit.col.details': 'Details',
    'audit.showing': 'Showing',
    'audit.prev': 'Previous',
    'audit.next': 'Next',
    'audit.error.load': 'Failed to load audit logs.',
    'settings.auditTrail': 'Audit Trail',

    // Thinking
    'thinking': 'Thinking...',
  },
}
