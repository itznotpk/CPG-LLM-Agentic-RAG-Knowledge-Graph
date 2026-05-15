export default function SplashScreen() {
  return (
    <div style={{
      minHeight: '100vh',
      display: 'grid',
      placeItems: 'center',
      background: 'linear-gradient(160deg, #f8fafc 0%, #f1f5f9 55%, #e2e8f0 100%)',
    }}>
      <div style={{
        width: 32, height: 32,
        border: '2px solid rgba(20,184,166,.2)',
        borderTopColor: 'var(--primary-600, #0d9488)',
        borderRadius: '50%',
        animation: 'spin 0.8s linear infinite',
      }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
