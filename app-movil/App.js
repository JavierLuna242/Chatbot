// App móvil del Asistente Académico: muestra el mismo chat de la web (https://chatbot.javier.life) dentro de un WebView.
// La web sigue siendo el producto principal: la app no tiene lógica propia, así que cualquier cambio de la web aparece aquí sin recompilar.
// Se abre con Expo Go (react-native-webview y react-native-safe-area-context vienen incluidos en Expo Go).
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, BackHandler, Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { WebView } from 'react-native-webview';

const SITIO = 'https://chatbot.javier.life';
const FONDO = '#0b3b5c';   // mismo color de tema que la web

export default function App() {
  const web = useRef(null);
  const [puedeVolver, setPuedeVolver] = useState(false);
  const [sinConexion, setSinConexion] = useState(false);

  // botón Atrás de Android: navega dentro del chat antes de cerrar la app
  useEffect(() => {
    const sub = BackHandler.addEventListener('hardwareBackPress', () => {
      if (!puedeVolver) return false;
      web.current?.goBack();
      return true;
    });
    return () => sub.remove();
  }, [puedeVolver]);

  return (
    <SafeAreaProvider>
      <SafeAreaView style={estilos.pantalla} edges={['top', 'bottom']}>
        <StatusBar style="light" />
        <WebView
          ref={web}
          source={{ uri: `${SITIO}/chat` }}
          style={[estilos.web, sinConexion && estilos.oculto]}
          applicationNameForUserAgent="AsistenteAcademicoApp/1.0"
          startInLoadingState
          renderLoading={() => (
            <View style={estilos.centro}>
              <ActivityIndicator size="large" color="#ffffff" />
            </View>
          )}
          onNavigationStateChange={(estado) => setPuedeVolver(estado.canGoBack)}
          onLoadEnd={() => setSinConexion(false)}
          onError={() => setSinConexion(true)}
          // solo el chat se abre dentro de la app; cualquier otro enlace (por ejemplo, una noticia) va al navegador
          onShouldStartLoadWithRequest={(peticion) => {
            if (peticion.url.startsWith(SITIO) || peticion.url.startsWith('about:')) return true;
            Linking.openURL(peticion.url);
            return false;
          }}
          setSupportMultipleWindows={false}
          allowsBackForwardNavigationGestures
        />
        {sinConexion && (
          <View style={estilos.centro}>
            <Text style={estilos.titulo}>Sin conexión con el asistente</Text>
            <Text style={estilos.texto}>Revisa tu conexión a internet e inténtalo de nuevo.</Text>
            <Pressable
              style={({ pressed }) => [estilos.boton, pressed && estilos.botonPresionado]}
              onPress={() => { setSinConexion(false); web.current?.reload(); }}
              accessibilityRole="button"
            >
              <Text style={estilos.textoBoton}>Reintentar</Text>
            </Pressable>
          </View>
        )}
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

const estilos = StyleSheet.create({
  pantalla: { flex: 1, backgroundColor: FONDO },
  web: { flex: 1, backgroundColor: FONDO },
  oculto: { display: 'none' },
  centro: { ...StyleSheet.absoluteFillObject, alignItems: 'center', justifyContent: 'center', padding: 32, backgroundColor: FONDO },
  titulo: { color: '#f5f7fa', fontSize: 20, fontWeight: '700', marginBottom: 8, textAlign: 'center' },
  texto: { color: 'rgba(236, 241, 247, 0.8)', fontSize: 15, textAlign: 'center', marginBottom: 24 },
  boton: { backgroundColor: '#5fd27a', borderRadius: 999, paddingVertical: 12, paddingHorizontal: 28 },
  botonPresionado: { opacity: 0.8 },
  textoBoton: { color: '#0c2914', fontSize: 16, fontWeight: '700' },
});
