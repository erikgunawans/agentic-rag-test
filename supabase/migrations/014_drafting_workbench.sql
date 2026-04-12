-- ============================================================
-- Feature 3: Enhanced Drafting Workbench
-- Clause library + document templates for legal document creation
-- ============================================================

-- 1. Clause library table
create table public.clause_library (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  title text not null,
  content text not null,
  category text not null
    check (category in ('confidentiality', 'termination', 'payment', 'liability', 'indemnity', 'force_majeure', 'dispute_resolution', 'compliance', 'intellectual_property', 'general')),
  applicable_doc_types text[] not null default '{}',
  risk_level text not null default 'low'
    check (risk_level in ('high', 'medium', 'low')),
  language text not null default 'id'
    check (language in ('id', 'en', 'both')),
  tags text[] not null default '{}',
  is_global boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 2. Document templates table
create table public.document_templates (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  name text not null,
  doc_type text not null,
  default_values jsonb not null default '{}'::jsonb,
  default_clauses uuid[] not null default '{}',
  is_global boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 3. Enable RLS
alter table public.clause_library enable row level security;
alter table public.document_templates enable row level security;

-- 4. RLS policies — clause_library
create policy "clause_library_select"
  on public.clause_library for select to authenticated
  using (auth.uid() = user_id or is_global = true);

create policy "clause_library_insert"
  on public.clause_library for insert to authenticated
  with check (auth.uid() = user_id and is_global = false);

create policy "clause_library_update"
  on public.clause_library for update to authenticated
  using (auth.uid() = user_id and is_global = false)
  with check (auth.uid() = user_id and is_global = false);

create policy "clause_library_delete"
  on public.clause_library for delete to authenticated
  using (auth.uid() = user_id and is_global = false);

-- 5. RLS policies — document_templates
create policy "document_templates_select"
  on public.document_templates for select to authenticated
  using (auth.uid() = user_id or is_global = true);

create policy "document_templates_insert"
  on public.document_templates for insert to authenticated
  with check (auth.uid() = user_id and is_global = false);

create policy "document_templates_update"
  on public.document_templates for update to authenticated
  using (auth.uid() = user_id and is_global = false)
  with check (auth.uid() = user_id and is_global = false);

create policy "document_templates_delete"
  on public.document_templates for delete to authenticated
  using (auth.uid() = user_id and is_global = false);

-- 6. Indexes
create index idx_clause_library_user_id on public.clause_library(user_id);
create index idx_clause_library_category on public.clause_library(category);
create index idx_clause_library_global on public.clause_library(is_global) where is_global = true;
create index idx_clause_library_doc_types on public.clause_library using gin(applicable_doc_types);

create index idx_document_templates_user_id on public.document_templates(user_id);
create index idx_document_templates_doc_type on public.document_templates(doc_type);

-- 7. Auto-update triggers (reuse handle_updated_at from migration 001)
create trigger handle_clause_library_updated_at
  before update on public.clause_library
  for each row execute function public.handle_updated_at();

create trigger handle_document_templates_updated_at
  before update on public.document_templates
  for each row execute function public.handle_updated_at();

-- 8. Seed 12 global Indonesian legal clauses
-- user_id is NULL for global clauses; is_global = true
-- Migration runs with service-role privileges, bypassing RLS

insert into public.clause_library (user_id, title, content, category, applicable_doc_types, risk_level, language, tags, is_global)
values
(
  null,
  'Pasal Kerahasiaan (Confidentiality Clause)',
  'Para Pihak sepakat untuk menjaga kerahasiaan seluruh informasi yang diperoleh sehubungan dengan pelaksanaan Perjanjian ini. Informasi Rahasia mencakup namun tidak terbatas pada data keuangan, strategi bisnis, informasi teknis, dan data pelanggan. Kewajiban kerahasiaan ini berlaku selama jangka waktu Perjanjian dan 2 (dua) tahun setelah berakhirnya Perjanjian. Pelanggaran terhadap ketentuan kerahasiaan ini dapat mengakibatkan tuntutan ganti rugi sesuai hukum yang berlaku.

The Parties agree to maintain the confidentiality of all information obtained in connection with the execution of this Agreement. Confidential Information includes but is not limited to financial data, business strategies, technical information, and customer data. This confidentiality obligation shall remain in effect during the term of the Agreement and for 2 (two) years after its termination. Breach of this confidentiality provision may result in claims for damages in accordance with applicable law.',
  'confidentiality',
  '{nda,vendor,service,employment}',
  'medium',
  'both',
  '{kerahasiaan,NDA,confidential}',
  true
),
(
  null,
  'Pasal Ganti Rugi (Indemnity Clause)',
  'Masing-masing Pihak setuju untuk memberikan ganti rugi dan membebaskan Pihak lainnya dari segala tuntutan, kerugian, biaya, dan pengeluaran (termasuk biaya hukum yang wajar) yang timbul akibat pelanggaran Perjanjian ini, kelalaian, atau perbuatan melawan hukum oleh Pihak yang bersangkutan. Klaim ganti rugi harus diajukan secara tertulis dalam waktu 30 (tiga puluh) hari sejak diketahuinya kerugian. Jumlah ganti rugi tidak melebihi total nilai Perjanjian kecuali dalam hal kelalaian berat atau kesengajaan.

Each Party agrees to indemnify and hold harmless the other Party from any claims, losses, costs, and expenses (including reasonable legal fees) arising from breach of this Agreement, negligence, or unlawful acts by the indemnifying Party. Indemnification claims must be submitted in writing within 30 (thirty) days of discovery of the loss. The indemnification amount shall not exceed the total value of this Agreement except in cases of gross negligence or willful misconduct.',
  'indemnity',
  '{sales,vendor,service}',
  'high',
  'both',
  '{ganti-rugi,indemnity,tanggung-jawab}',
  true
),
(
  null,
  'Pasal Pengakhiran (Termination Clause)',
  'Perjanjian ini dapat diakhiri oleh salah satu Pihak dengan pemberitahuan tertulis 30 (tiga puluh) hari sebelumnya. Perjanjian dapat diakhiri segera tanpa pemberitahuan apabila salah satu Pihak melakukan wanprestasi material dan gagal memperbaikinya dalam waktu 14 (empat belas) hari setelah menerima pemberitahuan tertulis. Pengakhiran Perjanjian tidak membebaskan para Pihak dari kewajiban yang telah timbul sebelum tanggal pengakhiran.

This Agreement may be terminated by either Party with 30 (thirty) days prior written notice. The Agreement may be terminated immediately without notice if either Party commits a material breach and fails to remedy it within 14 (fourteen) days after receiving written notification. Termination of the Agreement does not release the Parties from obligations that arose prior to the termination date.',
  'termination',
  '{generic,nda,sales,service,vendor,jv,property_lease,employment,sop_resolution}',
  'medium',
  'both',
  '{pengakhiran,termination,pemutusan}',
  true
),
(
  null,
  'Pasal Penyelesaian Sengketa - Arbitrase BANI (Dispute Resolution - BANI Arbitration)',
  'Setiap sengketa yang timbul dari atau sehubungan dengan Perjanjian ini akan diselesaikan secara musyawarah untuk mufakat dalam waktu 30 (tiga puluh) hari. Apabila musyawarah tidak mencapai kesepakatan, sengketa akan diselesaikan melalui arbitrase di Badan Arbitrase Nasional Indonesia (BANI) sesuai dengan Peraturan BANI yang berlaku. Putusan arbitrase bersifat final dan mengikat para Pihak. Biaya arbitrase ditanggung oleh Pihak yang dinyatakan kalah.

Any dispute arising from or in connection with this Agreement shall be resolved through deliberation to reach consensus within 30 (thirty) days. If deliberation fails to reach an agreement, the dispute shall be resolved through arbitration at the Indonesian National Arbitration Board (BANI) in accordance with applicable BANI Rules. The arbitration award shall be final and binding upon the Parties. Arbitration costs shall be borne by the losing Party.',
  'dispute_resolution',
  '{generic,nda,sales,service,vendor,jv,property_lease,employment,sop_resolution}',
  'low',
  'both',
  '{sengketa,arbitrase,BANI,dispute}',
  true
),
(
  null,
  'Pasal Force Majeure (Force Majeure Clause)',
  'Tidak ada Pihak yang bertanggung jawab atas keterlambatan atau kegagalan dalam melaksanakan kewajibannya berdasarkan Perjanjian ini yang disebabkan oleh keadaan kahar (force majeure), termasuk namun tidak terbatas pada bencana alam, perang, huru-hara, epidemi, kebijakan pemerintah, atau gangguan infrastruktur yang berada di luar kendali wajar. Pihak yang terkena dampak wajib memberitahukan keadaan force majeure secara tertulis dalam waktu 7 (tujuh) hari. Apabila force majeure berlangsung lebih dari 90 (sembilan puluh) hari, masing-masing Pihak berhak mengakhiri Perjanjian.

Neither Party shall be liable for delay or failure in performing its obligations under this Agreement caused by force majeure events, including but not limited to natural disasters, war, civil unrest, epidemics, government policies, or infrastructure disruptions beyond reasonable control. The affected Party must notify the force majeure event in writing within 7 (seven) days. If the force majeure continues for more than 90 (ninety) days, either Party may terminate this Agreement.',
  'force_majeure',
  '{generic,nda,sales,service,vendor,jv,property_lease,employment,sop_resolution}',
  'low',
  'both',
  '{force-majeure,keadaan-kahar,bencana}',
  true
),
(
  null,
  'Pasal Hukum yang Berlaku (Governing Law Clause)',
  'Perjanjian ini tunduk pada dan ditafsirkan berdasarkan hukum Negara Republik Indonesia. Segala hal yang tidak diatur dalam Perjanjian ini akan mengacu pada ketentuan peraturan perundang-undangan yang berlaku di Indonesia, termasuk Kitab Undang-Undang Hukum Perdata (KUHPerdata) dan peraturan pelaksanaannya.

This Agreement shall be governed by and construed in accordance with the laws of the Republic of Indonesia. Any matters not covered by this Agreement shall be governed by applicable Indonesian laws and regulations, including the Indonesian Civil Code (KUHPerdata) and its implementing regulations.',
  'general',
  '{generic,nda,sales,service,vendor,jv,property_lease,employment,sop_resolution}',
  'low',
  'both',
  '{hukum,governing-law,indonesia}',
  true
),
(
  null,
  'Pasal Pembatasan Tanggung Jawab (Limitation of Liability Clause)',
  'Total tanggung jawab masing-masing Pihak berdasarkan Perjanjian ini, baik dalam kontrak, perbuatan melawan hukum, atau dasar hukum lainnya, tidak akan melebihi total nilai Perjanjian yang telah dibayarkan dalam 12 (dua belas) bulan terakhir. Dalam keadaan apapun, tidak ada Pihak yang bertanggung jawab atas kerugian tidak langsung, kerugian konsekuensial, kehilangan keuntungan, atau kehilangan data. Pembatasan ini tidak berlaku untuk kasus kelalaian berat, kesengajaan, atau pelanggaran kewajiban kerahasiaan.

The total liability of each Party under this Agreement, whether in contract, tort, or other legal basis, shall not exceed the total Agreement value paid in the last 12 (twelve) months. Under no circumstances shall either Party be liable for indirect damages, consequential damages, loss of profits, or loss of data. This limitation does not apply to cases of gross negligence, willful misconduct, or breach of confidentiality obligations.',
  'liability',
  '{sales,vendor,service}',
  'high',
  'both',
  '{pembatasan,liability,tanggung-jawab}',
  true
),
(
  null,
  'Pasal Ketentuan Pembayaran (Payment Terms Clause)',
  'Pembayaran dilakukan dalam mata uang Rupiah Indonesia (IDR) melalui transfer bank ke rekening yang ditunjuk. Faktur akan diterbitkan sesuai dengan jadwal pembayaran yang disepakati. Pembayaran wajib dilakukan dalam waktu 30 (tiga puluh) hari kalender sejak tanggal faktur diterima. Keterlambatan pembayaran dikenakan denda sebesar 0,1% per hari dari jumlah yang tertunggak, maksimal 5% dari total tagihan. Pihak yang menerima pembayaran wajib menerbitkan tanda terima atau kwitansi resmi.

Payment shall be made in Indonesian Rupiah (IDR) via bank transfer to the designated account. Invoices shall be issued according to the agreed payment schedule. Payment must be made within 30 (thirty) calendar days from the date the invoice is received. Late payment shall incur a penalty of 0.1% per day of the outstanding amount, up to a maximum of 5% of the total invoice. The receiving Party shall issue an official receipt or acknowledgment.',
  'payment',
  '{sales,vendor,service}',
  'medium',
  'both',
  '{pembayaran,payment,faktur,invoice}',
  true
),
(
  null,
  'Pasal Hak Kekayaan Intelektual (Intellectual Property Clause)',
  'Masing-masing Pihak tetap memiliki hak kekayaan intelektual yang telah dimilikinya sebelum Perjanjian ini. Setiap kekayaan intelektual yang dihasilkan dalam pelaksanaan Perjanjian ini menjadi milik Pihak yang menugaskan pembuatannya, kecuali disepakati lain secara tertulis. Pihak pelaksana memberikan lisensi non-eksklusif yang tidak dapat dicabut kepada Pihak penugasan untuk menggunakan hasil karya tersebut. Pelanggaran hak kekayaan intelektual pihak ketiga menjadi tanggung jawab Pihak yang menyebabkan pelanggaran tersebut.

Each Party retains the intellectual property rights it owned prior to this Agreement. Any intellectual property created in the performance of this Agreement shall belong to the commissioning Party, unless otherwise agreed in writing. The performing Party grants an irrevocable, non-exclusive license to the commissioning Party to use such works. Infringement of third-party intellectual property rights shall be the responsibility of the Party causing such infringement.',
  'intellectual_property',
  '{nda,vendor,service,employment}',
  'high',
  'both',
  '{HAKI,intellectual-property,kekayaan-intelektual}',
  true
),
(
  null,
  'Pasal Kepatuhan Hukum (Legal Compliance Clause)',
  'Para Pihak wajib mematuhi seluruh peraturan perundang-undangan yang berlaku di Republik Indonesia dalam pelaksanaan Perjanjian ini, termasuk namun tidak terbatas pada peraturan tentang ketenagakerjaan, perpajakan, anti-korupsi, perlindungan data pribadi (UU PDP), dan peraturan sektoral terkait. Masing-masing Pihak menjamin bahwa tidak akan melakukan tindakan yang melanggar hukum anti-suap dan anti-korupsi. Pelanggaran terhadap ketentuan kepatuhan ini merupakan pelanggaran material yang dapat mengakibatkan pengakhiran Perjanjian.

The Parties shall comply with all applicable laws and regulations of the Republic of Indonesia in the performance of this Agreement, including but not limited to regulations on labor, taxation, anti-corruption, personal data protection (PDP Law), and relevant sectoral regulations. Each Party warrants that it shall not engage in any act that violates anti-bribery and anti-corruption laws. Violation of these compliance provisions constitutes a material breach that may result in termination of the Agreement.',
  'compliance',
  '{generic,nda,sales,service,vendor,jv,property_lease,employment,sop_resolution}',
  'medium',
  'both',
  '{kepatuhan,compliance,anti-korupsi,UU-PDP}',
  true
),
(
  null,
  'Pasal Larangan Persaingan (Non-Compete Clause)',
  'Selama jangka waktu Perjanjian dan 1 (satu) tahun setelah berakhirnya, Pihak Penerima sepakat untuk tidak secara langsung maupun tidak langsung terlibat dalam kegiatan usaha yang bersaing dengan Pihak Pengungkap di wilayah Indonesia. Larangan ini mencakup tidak bekerja pada, mendirikan, atau memiliki kepentingan dalam usaha yang serupa. Pelanggaran ketentuan ini memberikan hak kepada Pihak Pengungkap untuk menuntut ganti rugi dan/atau memperoleh perintah pengadilan untuk menghentikan persaingan tersebut.

During the term of the Agreement and for 1 (one) year after its termination, the Receiving Party agrees not to directly or indirectly engage in any business activity that competes with the Disclosing Party within the territory of Indonesia. This prohibition includes not working for, establishing, or holding any interest in a similar business. Violation of this provision entitles the Disclosing Party to claim damages and/or obtain a court order to cease such competition.',
  'general',
  '{nda,employment}',
  'high',
  'both',
  '{non-compete,persaingan,larangan}',
  true
),
(
  null,
  'Pasal Masa Percobaan (Probationary Period Clause)',
  'Karyawan akan menjalani masa percobaan selama 3 (tiga) bulan terhitung sejak tanggal mulai bekerja sesuai dengan Pasal 60 Undang-Undang Ketenagakerjaan No. 13 Tahun 2003. Selama masa percobaan, masing-masing pihak dapat mengakhiri hubungan kerja dengan pemberitahuan 7 (tujuh) hari sebelumnya. Setelah berhasil menyelesaikan masa percobaan, Karyawan akan diangkat sebagai karyawan tetap dengan hak dan kewajiban penuh sesuai peraturan perusahaan.

The Employee shall undergo a probationary period of 3 (three) months from the start date in accordance with Article 60 of the Manpower Act No. 13 of 2003. During the probationary period, either party may terminate the employment with 7 (seven) days prior notice. Upon successful completion of the probationary period, the Employee shall be appointed as a permanent employee with full rights and obligations in accordance with company regulations.',
  'general',
  '{employment}',
  'low',
  'both',
  '{percobaan,probation,ketenagakerjaan}',
  true
);

comment on table public.clause_library is
  'Reusable legal clauses with risk levels. Users see own + global clauses. Global clauses managed by admin via service-role.';

comment on table public.document_templates is
  'Document creation templates with pre-filled field values and default clause selections. Users see own + global templates.';
