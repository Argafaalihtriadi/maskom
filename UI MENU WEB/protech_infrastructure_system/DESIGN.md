---
name: ProTech Infrastructure System
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#464554'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#767586'
  outline-variant: '#c7c4d7'
  surface-tint: '#494bd6'
  primary: '#4648d4'
  on-primary: '#ffffff'
  primary-container: '#6063ee'
  on-primary-container: '#fffbff'
  inverse-primary: '#c0c1ff'
  secondary: '#565e74'
  on-secondary: '#ffffff'
  secondary-container: '#dae2fd'
  on-secondary-container: '#5c647a'
  tertiary: '#904900'
  on-tertiary: '#ffffff'
  tertiary-container: '#b55d00'
  on-tertiary-container: '#fffbff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e1e0ff'
  primary-fixed-dim: '#c0c1ff'
  on-primary-fixed: '#07006c'
  on-primary-fixed-variant: '#2f2ebe'
  secondary-fixed: '#dae2fd'
  secondary-fixed-dim: '#bec6e0'
  on-secondary-fixed: '#131b2e'
  on-secondary-fixed-variant: '#3f465c'
  tertiary-fixed: '#ffdcc5'
  tertiary-fixed-dim: '#ffb783'
  on-tertiary-fixed: '#301400'
  on-tertiary-fixed-variant: '#703700'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  headline-lg:
    fontFamily: Hanken Grotesk
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Hanken Grotesk
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Hanken Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 40px
---

## Brand & Style
Sistem desain ini mencerminkan identitas infrastruktur teknologi yang canggih, andal, dan presisi. Kepribadian merek ini bersifat profesional dan sistematis, dengan fokus pada kejelasan operasional untuk audiens insinyur, manajer proyek, dan administrator sistem.

Gaya desain yang digunakan adalah **Corporate / Modern** yang dipadukan dengan prinsip **Minimalism**. UI menggunakan ruang putih (whitespace) yang luas untuk mengurangi beban kognitif pada data yang kompleks. Antarmuka terasa terstruktur dengan batas-batas yang bersih dan tipografi yang fungsional, memberikan kesan stabilitas dan efisiensi tinggi dalam manajemen infrastruktur digital.

## Colors
Palet warna telah diperbarui untuk tema terang guna memastikan keterbacaan maksimum. 

- **Primary (#6366f1):** Digunakan untuk tindakan utama, status aktif, dan elemen branding inti. Warna ini dioptimalkan agar tetap kontras di atas latar belakang terang.
- **Secondary / Text (#0f172a):** Slate gelap yang dalam digunakan untuk tipografi utama dan elemen navigasi untuk memberikan kontras yang tajam.
- **Neutral / Background (#f8fafc):** Off-white dengan nuansa abu-abu dingin digunakan sebagai latar belakang aplikasi untuk mengurangi kelelahan mata dibandingkan warna putih murni.
- **Status Colors:** Warna fungsional (Sukses, Peringatan, Kesalahan, Info) menggunakan nada yang jenuh agar mudah dikenali pada antarmuka yang bersih.

## Typography
Tipografi dipilih untuk mendukung kejelasan teknis. 

- **Hanken Grotesk** digunakan untuk judul guna memberikan kesan modern dan tajam.
- **Inter** digunakan untuk teks isi (body) karena netralitasnya dan keterbacaan yang sangat baik pada ukuran kecil.
- **Geist** digunakan untuk label, metadata, dan elemen UI fungsional lainnya untuk menonjolkan aspek teknis dan presisi sistem.

Pastikan hierarki visual terjaga dengan menggunakan variasi berat font (weight) daripada hanya mengandalkan ukuran. Teks utama selalu menggunakan warna Slate gelap (#0f172a), sedangkan teks sekunder menggunakan Slate menengah (#64748b).

## Layout & Spacing
Sistem ini menggunakan **Fluid Grid** dengan basis kelipatan 4px untuk menjaga konsistensi ritme vertikal dan horizontal.

- **Desktop:** Menggunakan sistem 12-kolom dengan margin 40px dan selokan (gutter) 24px. Content container memiliki lebar maksimal 1440px.
- **Tablet:** Menggunakan sistem 8-kolom dengan margin 24px.
- **Mobile:** Menggunakan sistem 4-kolom dengan margin 16px.

Gunakan padding yang konsisten pada kartu dan kontainer (biasanya `md` atau `lg`) untuk menciptakan ruang napas yang cukup bagi data teknis yang padat.

## Elevation & Depth
Kedalaman dalam sistem ini dicapai melalui **Tonal Layers** dan **Low-contrast outlines**, menghindari bayangan yang terlalu berat untuk mempertahankan estetika bersih.

- **Level 0 (Background):** Menggunakan warna netral dasar (#f8fafc).
- **Level 1 (Cards/Surface):** Menggunakan warna putih murni (#ffffff) dengan garis tepi tipis (border) 1px berwarna Slate-200 (#e2e8f0).
- **Level 2 (Dropdowns/Modals):** Menggunakan bayangan ambient yang sangat halus (soft shadow) dengan blur 12px dan opasitas 5% untuk membedakan elemen yang melayang dari permukaan utama.
- **Interaksi:** Saat elemen ditekan atau aktif, gunakan perubahan warna latar belakang yang halus daripada peningkatan bayangan.

## Shapes
Bentuk yang digunakan dalam sistem ini bersifat **Soft**. Sudut-sudut yang sedikit membulat memberikan kesan modern namun tetap mempertahankan struktur yang tegas untuk aplikasi tingkat perusahaan.

- Sudut standar: 0.25rem (4px) untuk tombol kecil dan input.
- Sudut besar: 0.5rem (8px) untuk kartu, panel, dan dialog.
- Elemen seperti tag atau indikator status dapat menggunakan sudut yang lebih besar (0.75rem) untuk membedakannya dari elemen aksi utama.

## Components
Instruksi komponen untuk antarmuka ProTech:

- **Buttons:** Tombol primer menggunakan latar belakang #6366f1 dengan teks putih. Tombol sekunder menggunakan outline Slate-200 dengan teks Slate-900.
- **Input Fields:** Latar belakang putih dengan border #e2e8f0. Saat fokus, border berubah menjadi #6366f1 dengan ring fokus tipis 2px.
- **Cards:** Permukaan putih murni, tanpa bayangan yang menonjol, hanya garis tepi 1px sebagai pemisah konten.
- **Lists:** Gunakan pembagi (divider) horizontal yang sangat halus (#f1f5f9). Baris daftar harus memiliki padding vertikal yang cukup untuk memudahkan pemindaian data.
- **Chips/Status:** Menggunakan latar belakang dengan opasitas rendah (10%) dari warna status yang relevan, dengan teks warna penuh di atasnya untuk kontras.
- **Checkboxes & Radios:** Menggunakan warna primer (#6366f1) saat dalam keadaan terpilih, dengan ukuran yang konsisten mengikuti label-md.