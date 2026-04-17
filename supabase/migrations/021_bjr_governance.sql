-- ============================================================
-- 021_bjr_governance.sql
-- BJR Decision Governance Module
-- 6 tables: regulatory_items, checklist_templates, decisions,
--           evidence, gcg_aspects, risk_register
-- ============================================================

-- ── 1. bjr_regulatory_items ──────────────────────────────────

create table public.bjr_regulatory_items (
  id uuid primary key default gen_random_uuid(),
  code text not null,
  title text not null,
  layer text not null check (layer in ('uu', 'pp', 'pergub', 'ojk_bei', 'custom')),
  substance text,
  url text,
  critical_notes text,
  is_active boolean not null default true,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_bjr_reg_layer on public.bjr_regulatory_items(layer);
create index idx_bjr_reg_active on public.bjr_regulatory_items(is_active);

alter table public.bjr_regulatory_items enable row level security;

create policy "Authenticated users can read active regulatory items"
  on public.bjr_regulatory_items for select to authenticated
  using (is_active = true);

create policy "Admins can insert regulatory items"
  on public.bjr_regulatory_items for insert to authenticated
  with check ((auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin');

create policy "Admins can update regulatory items"
  on public.bjr_regulatory_items for update to authenticated
  using ((auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin');


-- ── 2. bjr_checklist_templates ───────────────────────────────

create table public.bjr_checklist_templates (
  id uuid primary key default gen_random_uuid(),
  phase text not null check (phase in ('pre_decision', 'decision', 'post_decision')),
  item_order int not null,
  title text not null,
  description text,
  regulatory_item_ids uuid[] default '{}',
  is_required boolean not null default true,
  is_active boolean not null default true,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now()
);

create index idx_bjr_checklist_phase on public.bjr_checklist_templates(phase);
create index idx_bjr_checklist_active on public.bjr_checklist_templates(is_active);

alter table public.bjr_checklist_templates enable row level security;

create policy "Authenticated users can read active checklist templates"
  on public.bjr_checklist_templates for select to authenticated
  using (is_active = true);

create policy "Admins can insert checklist templates"
  on public.bjr_checklist_templates for insert to authenticated
  with check ((auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin');

create policy "Admins can update checklist templates"
  on public.bjr_checklist_templates for update to authenticated
  using ((auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin');


-- ── 3. bjr_decisions ─────────────────────────────────────────

create table public.bjr_decisions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id),
  user_email text not null,
  title text not null,
  description text,
  decision_type text not null default 'other' check (decision_type in ('investment', 'procurement', 'partnership', 'divestment', 'capex', 'policy', 'other')),
  current_phase text not null default 'pre_decision' check (current_phase in ('pre_decision', 'decision', 'post_decision', 'completed')),
  status text not null default 'draft' check (status in ('draft', 'in_progress', 'under_review', 'approved', 'completed', 'cancelled')),
  risk_level text check (risk_level in ('critical', 'high', 'medium', 'low')),
  estimated_value numeric,
  bjr_score float not null default 0.0,
  gcg_aspect_ids uuid[] default '{}',
  metadata jsonb not null default '{}',
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_bjr_decisions_user on public.bjr_decisions(user_id);
create index idx_bjr_decisions_phase on public.bjr_decisions(current_phase);
create index idx_bjr_decisions_status on public.bjr_decisions(status);
create index idx_bjr_decisions_created on public.bjr_decisions(created_at desc);

-- updated_at trigger
create trigger bjr_decisions_updated_at
  before update on public.bjr_decisions
  for each row execute function public.set_updated_at();

-- Create the trigger function if it doesn't exist
create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

alter table public.bjr_decisions enable row level security;

create policy "Users can read own decisions"
  on public.bjr_decisions for select to authenticated
  using (user_id = auth.uid());

create policy "Admins can read all decisions"
  on public.bjr_decisions for select to authenticated
  using ((auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin');

create policy "Users can insert own decisions"
  on public.bjr_decisions for insert to authenticated
  with check (user_id = auth.uid());

create policy "Users can update own decisions"
  on public.bjr_decisions for update to authenticated
  using (user_id = auth.uid());


-- ── 4. bjr_evidence ──────────────────────────────────────────

create table public.bjr_evidence (
  id uuid primary key default gen_random_uuid(),
  decision_id uuid not null references public.bjr_decisions(id) on delete cascade,
  checklist_item_id uuid not null references public.bjr_checklist_templates(id),
  evidence_type text not null check (evidence_type in ('document', 'tool_result', 'manual_note', 'approval', 'external_link')),
  reference_id uuid,
  reference_table text,
  title text not null,
  notes text,
  file_path text,
  external_url text,
  llm_assessment jsonb,
  confidence_score float,
  review_status text not null default 'not_assessed' check (review_status in ('not_assessed', 'auto_approved', 'pending_review', 'approved', 'rejected')),
  attached_by uuid not null references auth.users(id),
  created_at timestamptz not null default now()
);

create index idx_bjr_evidence_decision on public.bjr_evidence(decision_id);
create index idx_bjr_evidence_checklist on public.bjr_evidence(checklist_item_id);
create index idx_bjr_evidence_status on public.bjr_evidence(review_status);

alter table public.bjr_evidence enable row level security;

create policy "Users can read evidence on own decisions"
  on public.bjr_evidence for select to authenticated
  using (
    exists (
      select 1 from public.bjr_decisions d
      where d.id = decision_id and d.user_id = auth.uid()
    )
  );

create policy "Admins can read all evidence"
  on public.bjr_evidence for select to authenticated
  using ((auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin');

create policy "Users can insert evidence on own decisions"
  on public.bjr_evidence for insert to authenticated
  with check (
    exists (
      select 1 from public.bjr_decisions d
      where d.id = decision_id and d.user_id = auth.uid()
    )
  );

create policy "Users can delete evidence on own decisions"
  on public.bjr_evidence for delete to authenticated
  using (
    exists (
      select 1 from public.bjr_decisions d
      where d.id = decision_id and d.user_id = auth.uid()
    )
  );


-- ── 5. bjr_gcg_aspects ──────────────────────────────────────

create table public.bjr_gcg_aspects (
  id uuid primary key default gen_random_uuid(),
  aspect_name text not null,
  regulatory_item_ids uuid[] default '{}',
  indicators text[] default '{}',
  frequency text check (frequency in ('per_transaction', 'monthly', 'quarterly', 'annually')),
  pic_role text,
  is_active boolean not null default true,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now()
);

alter table public.bjr_gcg_aspects enable row level security;

create policy "Authenticated users can read active GCG aspects"
  on public.bjr_gcg_aspects for select to authenticated
  using (is_active = true);

create policy "Admins can insert GCG aspects"
  on public.bjr_gcg_aspects for insert to authenticated
  with check ((auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin');

create policy "Admins can update GCG aspects"
  on public.bjr_gcg_aspects for update to authenticated
  using ((auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin');


-- ── 6. bjr_risk_register ─────────────────────────────────────

create table public.bjr_risk_register (
  id uuid primary key default gen_random_uuid(),
  decision_id uuid references public.bjr_decisions(id) on delete set null,
  risk_title text not null,
  description text,
  risk_level text not null check (risk_level in ('critical', 'high', 'medium', 'low')),
  mitigation text,
  status text not null default 'open' check (status in ('open', 'mitigated', 'accepted', 'closed')),
  owner_role text,
  is_global boolean not null default false,
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_bjr_risk_decision on public.bjr_risk_register(decision_id);
create index idx_bjr_risk_global on public.bjr_risk_register(is_global) where is_global = true;

create trigger bjr_risk_register_updated_at
  before update on public.bjr_risk_register
  for each row execute function public.set_updated_at();

alter table public.bjr_risk_register enable row level security;

create policy "Users can read own decision risks and global risks"
  on public.bjr_risk_register for select to authenticated
  using (
    is_global = true
    or exists (
      select 1 from public.bjr_decisions d
      where d.id = decision_id and d.user_id = auth.uid()
    )
    or (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

create policy "Users can insert risks on own decisions"
  on public.bjr_risk_register for insert to authenticated
  with check (
    is_global = false and exists (
      select 1 from public.bjr_decisions d
      where d.id = decision_id and d.user_id = auth.uid()
    )
    or (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );

create policy "Users can update own decision risks, admins can update all"
  on public.bjr_risk_register for update to authenticated
  using (
    exists (
      select 1 from public.bjr_decisions d
      where d.id = decision_id and d.user_id = auth.uid()
    )
    or (auth.jwt() -> 'app_metadata' ->> 'role') = 'super_admin'
  );


-- ════════════════════════════════════════════════════════════
-- SEED DATA
-- ════════════════════════════════════════════════════════════

-- ── Layer 1: UU (National Laws) ──────────────────────────────

insert into public.bjr_regulatory_items (code, title, layer, substance, critical_notes) values
('UU No. 40/2007', 'Undang-Undang Perseroan Terbatas', 'uu',
 'DASAR HUKUM UTAMA PT. Pasal 97 ayat (5) = basis eksplisit doktrin Business Judgment Rule (BJR). Direksi tidak dapat dipersalahkan jika: (1) terbukti bertindak dengan itikad baik, (2) tidak ada benturan kepentingan, (3) sudah mengambil langkah pencegahan kerugian.',
 'Kritis untuk BJR Ancol'),

('UU No. 23/2014', 'Pemerintahan Daerah', 'uu',
 'Mengatur BUMD sebagai instrumen pelayanan publik dan pemberdayaan ekonomi daerah. Dasar kewenangan Gubernur DKI atas Ancol sebagai BUMD Perseroda.',
 'Landasan eksistensi BUMD'),

('UU No. 19/2003', 'Badan Usaha Milik Negara (BUMN)', 'uu',
 'Berlaku analogis untuk BUMD Perseroda. Mengatur prinsip tata kelola dan akuntabilitas. Pasal 11: ketentuan UU PT berlaku untuk Persero BUMN.',
 'Referensi analogis GCG'),

('UU No. 1/2025', 'Perubahan UU BUMN (Terbaru)', 'uu',
 'PERKEMBANGAN KRITIS: (1) Menghapus status kekayaan BUMN/BUMD sebagai bagian keuangan negara setelah dipisahkan dari APBN; (2) Direksi tidak lagi dikategorikan sebagai Penyelenggara Negara dalam konteks pidana — MEMPERKUAT POSISI BJR SECARA SIGNIFIKAN.',
 'Terbaru — angin segar BJR'),

('UU No. 6/2023', 'Cipta Kerja (Penetapan Perppu 2/2022)', 'uu',
 'Memperbarui sejumlah ketentuan UU PT termasuk tata kelola perseroan dan penyederhanaan regulasi. Relevan untuk Ancol sebagai Tbk.',
 'Update UU PT'),

('UU No. 40/2007 jo. UU No. 6/2023', 'Perseroan Terbatas — Pasal 97 & 104 (BJR Lengkap)', 'uu',
 'Pasal 97(5): Pembebasan tanggung jawab pribadi Direksi. Pasal 104(4): Proteksi serupa untuk Direksi dalam kondisi kepailitan/insolvensi jika sudah bertindak dengan itikad baik.',
 'Pasal kunci BJR');


-- ── Layer 2: PP (Government Regulations) ─────────────────────

insert into public.bjr_regulatory_items (code, title, layer, substance, critical_notes) values
('PP No. 54/2017', 'Badan Usaha Milik Daerah', 'pp',
 'REGULASI INDUK BUMD. Mengatur: bentuk hukum, permodalan, organ & kepegawaian, Satuan Pengawas Intern, Komite Audit, perencanaan, operasional, pelaporan, Tata Kelola Perusahaan yang Baik, pengadaan barang/jasa, kerjasama, pinjaman, penggunaan laba, anak perusahaan, evaluasi kinerja.',
 'Wajib diacu Ancol'),

('PP No. 23/2022', 'Pendirian, Pengurusan, Pengawasan dan Pembubaran BUMN', 'pp',
 'Mengadopsi BJR secara eksplisit untuk BUMN/BUMD. Direksi bertanggung jawab penuh secara pribadi KECUALI terbukti tidak lalai. Menetapkan tahapan BJR: Pre-Decision (due diligence, feasibility study) → Decision (rapat Direksi, review kontrak) → Post-Decision (monitoring & evaluasi).',
 'BJR BUMN/BUMD — analog Ancol'),

('PP No. 45/2005', 'Pendirian, Pengurusan, Pengawasan dan Pembubaran BUMN (Asal)', 'pp',
 'Regulasi pendahulu PP 23/2022. Masih relevan sebagai referensi historis tata kelola dan sebagai basis praktik GCG BUMD yang sudah mapan.',
 'Diubah oleh PP 23/2022');


-- ── Layer 3: Pergub & KepGub DKI Jakarta ─────────────────────

insert into public.bjr_regulatory_items (code, title, layer, substance, critical_notes) values
('KepGub No. 96/2004', 'Penerapan Praktik GCG pada BUMD DKI Jakarta', 'pergub',
 'MEWAJIBKAN seluruh BUMD DKI — termasuk Ancol — menerapkan GCG secara konsisten sebagai landasan operasional.',
 'Wajib GCG — dasar semua Pergub'),

('KepGub No. 4/2004', 'Penilaian Tingkat Kesehatan BUMD DKI', 'pergub',
 'Kriteria KPI dan benchmark penilaian kinerja BUMD DKI. Mengatur mekanisme penilaian aspek keuangan dan non-keuangan.',
 'Benchmark kinerja Ancol'),

('Pergub No. 109/2011', 'Kepengurusan Badan Usaha Milik Daerah', 'pergub',
 'Mengatur struktur organ BUMD DKI: tugas dan wewenang Direksi, Dewan Komisaris/Pengawas, hak dan kewajiban organ perusahaan.',
 'Struktur organ Ancol'),

('Pergub No. 10/2012', 'Penyusunan Rencana Jangka Panjang BUMD', 'pergub',
 'Mengatur tata cara penyusunan RJPP (Rencana Jangka Panjang Perusahaan) BUMD DKI. Keputusan di luar RJPP berisiko menggugurkan perlindungan BJR.',
 'RJPP — kunci keabsahan BJR'),

('Pergub No. 204/2016', 'Kebijakan Pengadaan Barang/Jasa BUMD', 'pergub',
 'Mengatur mekanisme pengadaan barang dan jasa khusus BUMD DKI. Compliance pengadaan adalah salah satu syarat terpenuhinya unsur itikad baik dalam BJR.',
 'Pengadaan — risiko compliance'),

('Pergub No. 5/2018', 'Tata Cara Pengangkatan dan Pemberhentian Direksi BUMD', 'pergub',
 'Mengatur seleksi, persyaratan, manajemen talenta, pengangkatan, dan pemberhentian Direksi BUMD DKI.',
 'Legitimasi Direksi'),

('Pergub No. 50/2018', 'Dewan Pengawas BUMD', 'pergub',
 'Mengatur komposisi, tugas, wewenang, dan mekanisme kerja Dewan Pengawas BUMD DKI. Pengawasan aktif Dewas adalah indikator akuntabilitas GCG.',
 'Struktur Dewas Ancol'),

('Pergub No. 79/2019', 'Pedoman Penetapan Penghasilan Direksi, Dewan Pengawas, dan Komisaris BUMD', 'pergub',
 'Mengatur struktur dan batas atas remunerasi organ perusahaan BUMD DKI. Transparansi remunerasi merupakan prinsip GCG (Disclosure).',
 'Remunerasi organ'),

('Pergub No. 127/2019', 'Rencana Bisnis dan RKAB BUMD', 'pergub',
 'Mengatur penyusunan Rencana Bisnis dan RKAB. KRITIS: Keputusan bisnis di luar RKAB yang disetujui berpotensi membatalkan perlindungan BJR.',
 'RKAB — syarat mutlak BJR'),

('Pergub No. 131/2019', 'Pembinaan Badan Usaha Milik Daerah', 'pergub',
 'Mengatur mekanisme monitoring, evaluasi, dan intervensi Pemprov DKI atas kinerja BUMD.',
 'Monitoring Pemprov DKI'),

('Pergub No. 1/2020', 'Sistem Pengendalian Internal BUMD', 'pergub',
 'Mengatur kerangka Sistem Pengendalian Internal (SPI) BUMD DKI. SPI yang berjalan efektif merupakan bukti pelaksanaan kehati-hatian — unsur penting BJR.',
 'SPI — bukti kehati-hatian'),

('Pergub No. 13/2020', 'Komite Audit dan Komite Lainnya pada BUMD', 'pergub',
 'Mengatur pembentukan, komposisi, dan mekanisme kerja Komite Audit. Komite Audit aktif berfungsi sebagai clearing house untuk keputusan high-risk.',
 'Komite Audit — organ kunci GCG'),

('Pergub No. 92/2020', 'Pengelolaan Investasi pada BUMD', 'pergub',
 'Mengatur tata cara pengelolaan investasi BUMD, pengurangan modal daerah, dan perubahan penggunaan penyertaan modal. Kritis untuk capex Ancol.',
 'Investasi & capex Ancol'),

('SE Gubernur No. 13/2017', 'Panduan Pengelolaan LHKPN di BUMD DKI', 'pergub',
 'Kewajiban pelaporan Laporan Harta Kekayaan Penyelenggara Negara (LHKPN) bagi pejabat BUMD DKI. Compliance LHKPN merupakan indikator integritas GCG.',
 'Integritas pejabat');


-- ── Layer 4: OJK & BEI ───────────────────────────────────────

insert into public.bjr_regulatory_items (code, title, layer, substance, critical_notes) values
('POJK No. 21/POJK.04/2015', 'Pedoman Tata Kelola Emiten dan Perusahaan Publik', 'ojk_bei',
 'GCG khusus perusahaan publik/Tbk. Mengatur: keterbukaan informasi, RUPS, Direksi dan Dewan Komisaris, komite-komite, fungsi audit internal, sekretaris perusahaan.',
 'Berlaku karena Ancol = Tbk'),

('POJK No. 34/POJK.04/2014', 'Komite Nominasi dan Remunerasi Emiten', 'ojk_bei',
 'Kewajiban pembentukan Komite Nominasi dan Remunerasi bagi Emiten/Perusahaan Publik.',
 'Komite Nominasi & Remunerasi'),

('POJK No. 35/POJK.04/2014', 'Sekretaris Perusahaan Emiten', 'ojk_bei',
 'Mengatur fungsi, kewajiban, dan kompetensi Sekretaris Perusahaan pada Emiten. Corporate Secretary adalah jembatan GCG.',
 'Sekretaris Perusahaan'),

('Peraturan BEI No. I-A', 'Ketentuan Umum Pencatatan Efek Bersifat Ekuitas', 'ojk_bei',
 'GCG Perusahaan Tercatat di BEI. Kewajiban keterbukaan informasi material, laporan keuangan berkala, dan corporate action.',
 'Kewajiban BEI — Tbk'),

('POJK No. 29/2016', 'Laporan Tahunan Emiten atau Perusahaan Publik', 'ojk_bei',
 'Mengatur kewajiban dan format laporan tahunan Emiten. Termasuk laporan GCG, laporan keberlanjutan, dan pengungkapan keputusan bisnis material.',
 'Laporan tahunan & GCG disclosure');


-- ── Checklist Templates: PRE-DECISION (5 items) ─────────────

insert into public.bjr_checklist_templates (phase, item_order, title, description, is_required) values
('pre_decision', 1, 'Due Diligence telah dilakukan secara komprehensif',
 'Pemeriksaan menyeluruh atas aspek hukum, keuangan, operasional, dan risiko dari keputusan yang akan diambil. Dasar: PP 23/2022, PP 54/2017.', true),
('pre_decision', 2, 'Feasibility Study / Kajian Kelayakan tersedia dan terdokumentasi',
 'Studi kelayakan tertulis yang mencakup analisis biaya-manfaat, risiko, dan proyeksi dampak. Dasar: PP 23/2022, Pergub 127/2019.', true),
('pre_decision', 3, 'Aktivitas masuk dalam RKAB yang disetujui',
 'Keputusan harus tercantum dalam Rencana Kerja dan Anggaran Bisnis yang telah disetujui. Keputusan di luar RKAB membatalkan proteksi BJR. Dasar: Pergub 127/2019.', true),
('pre_decision', 4, 'Aktivitas masuk dalam RJPP (Rencana Jangka Panjang)',
 'Keputusan harus selaras dengan Rencana Jangka Panjang Perusahaan. Dasar: Pergub 10/2012.', true),
('pre_decision', 5, 'Tidak ada benturan kepentingan (conflict of interest)',
 'Seluruh Direksi yang terlibat dalam pengambilan keputusan tidak memiliki kepentingan pribadi. Dasar: UU PT Pasal 97(5)c.', true);


-- ── Checklist Templates: DECISION (6 items) ──────────────────

insert into public.bjr_checklist_templates (phase, item_order, title, description, is_required) values
('decision', 1, 'Rapat Direksi telah diselenggarakan dengan quorum yang sah',
 'Rapat pengambilan keputusan memenuhi persyaratan quorum sesuai Anggaran Dasar. Dasar: UU PT No. 40/2007, Anggaran Dasar Ancol.', true),
('decision', 2, 'Risalah Rapat (Minutes of Meeting) Direksi telah dibuat dan ditandatangani',
 'Notulen rapat tertulis, mencakup seluruh deliberasi dan keputusan, ditandatangani peserta. Dasar: UU PT, POJK 21/2015.', true),
('decision', 3, 'Dasar analisis dan pertimbangan risiko tercatat dalam risalah',
 'Risalah rapat memuat analisis risiko, pertimbangan bisnis, dan dasar pengambilan keputusan. Dasar: PP 23/2022, POJK 21/2015.', true),
('decision', 4, 'Kontrak/perjanjian telah di-review oleh tim hukum perusahaan',
 'Seluruh dokumen kontraktual telah melalui legal review sebelum penandatanganan. Dasar: PP 23/2022, Anggaran Dasar.', true),
('decision', 5, 'Persetujuan Dewan Komisaris/Pengawas diperoleh (jika dipersyaratkan AD)',
 'Untuk keputusan yang melampaui threshold, persetujuan Dewas/Komisaris telah diperoleh. Dasar: Pergub 50/2018, Anggaran Dasar Ancol.', true),
('decision', 6, 'Disclosure kepada OJK/BEI dilakukan (jika transaksi material)',
 'Keterbukaan informasi material disampaikan ke OJK dan BEI sesuai ketentuan. Dasar: POJK 29/2016, Peraturan BEI.', false);


-- ── Checklist Templates: POST-DECISION (5 items) ─────────────

insert into public.bjr_checklist_templates (phase, item_order, title, description, is_required) values
('post_decision', 1, 'Mekanisme monitoring dan evaluasi atas keputusan ditetapkan',
 'SOP monitoring pelaksanaan keputusan telah disusun dan diaktifkan. Dasar: PP 23/2022, Pergub 131/2019.', true),
('post_decision', 2, 'Sistem Pengendalian Internal (SPI) aktif mengawasi pelaksanaan',
 'SPI perusahaan secara aktif memantau implementasi keputusan. Dasar: Pergub 1/2020.', true),
('post_decision', 3, 'Komite Audit diinformasikan atas keputusan strategis',
 'Komite Audit telah menerima informasi dan dokumentasi keputusan strategis. Dasar: Pergub 13/2020, PP 54/2017.', true),
('post_decision', 4, 'Laporan perkembangan kepada Dewas/Komisaris dilakukan berkala',
 'Laporan progress pelaksanaan keputusan disampaikan secara berkala. Dasar: Pergub 50/2018, POJK 21/2015.', true),
('post_decision', 5, 'Dokumentasi lengkap tersimpan dan dapat diakses jika dibutuhkan aparat hukum',
 'Seluruh dokumentasi (FS, risalah, kontrak, approval, monitoring) tersimpan dalam sistem dan dapat diakses. Dasar: UU PT Pasal 97(5), PP 23/2022.', true);


-- ── GCG Aspects (11) ─────────────────────────────────────────

insert into public.bjr_gcg_aspects (aspect_name, indicators, frequency, pic_role) values
('Tata Kelola Organ',
 array['RUPS tahunan terlaksana', 'Rapat Direksi terdokumentasi', 'Dewas aktif bersidang'],
 'annually', 'Sekper / Legal'),

('Rencana Bisnis',
 array['RJPP dan RKAB disusun', 'Disetujui Dewas', 'Dilaporkan ke Pemprov DKI'],
 'annually', 'Direksi / Keuangan'),

('Pengadaan Barang/Jasa',
 array['SOP pengadaan sesuai Pergub', 'Tidak ada penyimpangan prosedur', 'Dokumentasi lengkap'],
 'per_transaction', 'Procurement'),

('Investasi & Capex',
 array['Setiap investasi dengan due diligence terdokumentasi', 'Persetujuan organ sesuai threshold'],
 'per_transaction', 'BD / Keuangan'),

('Laporan Keuangan',
 array['Laporan keuangan audited', 'Disampaikan tepat waktu ke OJK dan BEI'],
 'quarterly', 'Keuangan / Sekper'),

('Keterbukaan Informasi',
 array['Material information disampaikan ke OJK/BEI', 'Laporan Tahunan dengan bagian GCG'],
 'per_transaction', 'Sekper / Legal'),

('Audit Internal',
 array['SPI beroperasi', 'Laporan SPI ke Direksi dan Komite Audit', 'Tindak lanjut temuan'],
 'quarterly', 'SPI / Komite Audit'),

('Komite Audit',
 array['Komite Audit aktif bersidang', 'Laporan Komite Audit dalam Laporan Tahunan'],
 'monthly', 'Komite Audit'),

('Remunerasi Organ',
 array['Remunerasi sesuai Pergub dan persetujuan RUPS', 'Diungkapkan dalam Laporan Tahunan'],
 'annually', 'HR / Sekper'),

('LHKPN & Integritas',
 array['Seluruh pejabat wajib LHKPN melaporkan tepat waktu', 'Tidak ada konflik kepentingan'],
 'annually', 'Legal / HR'),

('BJR Documentation',
 array['Setiap keputusan strategis dilengkapi: FS, risalah rapat, review legal, persetujuan organ'],
 'per_transaction', 'Direksi / Legal / BD');


-- ── Standing Risks (4) ───────────────────────────────────────

insert into public.bjr_risk_register (risk_title, description, risk_level, mitigation, status, owner_role, is_global) values
('Dualisme Rezim Hukum',
 'Ancol tunduk pada hukum korporasi (UU PT + OJK) DAN hukum keuangan daerah (PP BUMD + Pergub DKI) secara bersamaan. Kerugian bisnis berisiko dikualifikasikan sebagai kerugian keuangan daerah.',
 'high', 'Dokumentasi BJR ketat; pastikan setiap keputusan masuk RKAB', 'open', 'Direksi / Legal', true),

('Keputusan di Luar RKAB',
 'Aktivitas atau keputusan yang tidak tercantum dalam RKAB yang telah disetujui secara otomatis membatalkan perlindungan BJR — preseden dari kasus BUMN.',
 'high', 'Setiap inisiatif baru masukkan dalam RKAB; gunakan RUPS jika mendesak', 'open', 'Direksi / Keuangan', true),

('Transisi Kepemimpinan',
 'Pergantian Dirut berpotensi menimbulkan gap legitimasi — keputusan yang diambil dalam periode transisi rentan dipersoalkan dari sisi keabsahan organ.',
 'medium', 'Pastikan seluruh keputusan strategis saat transisi melalui mekanisme RUPS', 'open', 'Sekper / Legal', true),

('Disclosure Tidak Tepat Waktu (Tbk)',
 'Sebagai perusahaan publik, keterlambatan disclosure informasi material ke OJK/BEI dapat menimbulkan sanksi dan melemahkan posisi GCG Ancol.',
 'medium', 'SOP disclosure material event; penguatan fungsi Corporate Secretary', 'open', 'Sekper / Corporate Secretary', true);
