// Altura realmente visible. En iOS el teclado virtual no reduce 100dvh y taparía el campo de escritura:
// la ventana usa --alto (visualViewport) y así el chat se encoge cuando aparece el teclado.
if (window.visualViewport) {
    const ajustar = () => {
        if (visualViewport.scale > 1.01) return;   // con zoom por pellizco no se toca el diseño
        document.documentElement.style.setProperty('--alto', visualViewport.height + 'px');
        if (document.body.classList.contains('pantalla-ventana')) window.scrollTo(0, 0);   // la ventana no se desplaza como página
    };
    visualViewport.addEventListener('resize', ajustar);
    visualViewport.addEventListener('scroll', ajustar);
    ajustar();
}

