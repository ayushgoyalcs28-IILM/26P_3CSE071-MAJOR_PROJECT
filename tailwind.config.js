/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'Aptos', 'ui-sans-serif', 'system-ui', 'sans-serif'] },
      colors: {
        navy: '#0c1a34', royal: '#245cfc', slateblue: '#7182aa', paper: '#f4f7fc'
      },
      boxShadow: { soft: '0 12px 50px rgba(20, 46, 91, .075)', float: '0 24px 70px rgba(28, 62, 126, .14)' }
    }
  }, plugins: []
};
